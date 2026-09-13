"""A predeclared BF16-only cache-pressure pilot, separate from quality acceptance."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import threading
import time

from .config import RuntimeConfig
from .memory import estimate_memory
from .metrics import measured_queue_time
from .runtime import SERVED_MODEL, SeraModel
from .storage import content_hash, save_json


PRESSURE_PROFILE = {
    "name": "qwen-kv-pressure-pilot-v1", "gpu_memory_utilization": 0.025,
    "max_model_len": 4096, "max_num_seqs": 8, "concurrency": 8,
    "input_tokens_per_request": 2048, "max_output_tokens": 64,
    "warmup_requests": 2, "measured_waves": 3,
    "metrics_poll_seconds": 0.02, "high_kv_percent": 80, "minimum_preemptions": 1,
    "disclosure": "Memory budget constrained to represent a smaller card; execution uses an RTX Pro 6000 with 96 GB.",
}


PRESSURE_PROFILES = {
    'cache-v1': PRESSURE_PROFILE,
    'cache-v2': PRESSURE_PROFILE | {'name': 'qwen-kv-pressure-pilot-v2',
                                  'input_tokens_per_request': 2304},
    'queue-v1': PRESSURE_PROFILE | {'name': 'qwen-queue-pressure-pilot-v1',
                                  'input_tokens_per_request': 2304,
                                  'gpu_memory_utilization': 0.10,
                                  'maximum_kv_percent_exclusive': 50,
                                  'minimum_measured_queue_ms': 10},
}


def pressure_verdict(profile, record):
    """A pressure result never grants task-quality or performance acceptance."""
    peak = record.get('peak_kv_percent')
    preemptions = record.get('measured_preemptions')
    if (peak is None or preemptions is None or record.get('request_errors') != 0
            or record.get('sampling_errors') != 0
            or record.get('measured_requests') != profile['concurrency'] * profile['measured_waves']
            or record.get('runtime', {}).get('cleanup_pass') is not True):
        return False
    if 'minimum_measured_queue_ms' in profile:
        queue = record.get('measured_queue_ms')
        return (queue is not None and queue >= profile['minimum_measured_queue_ms']
                and peak < profile['maximum_kv_percent_exclusive'] and preemptions == 0)
    return peak >= profile['high_kv_percent'] and preemptions >= profile['minimum_preemptions']


def run_pressure_pilot(*, prompts, output_dir, profile_name='cache-v1'):
    profile = deepcopy(PRESSURE_PROFILES[profile_name])
    if len(prompts) != 8 or any(not isinstance(prompt, str) or not prompt.strip() for prompt in prompts):
        raise ValueError("The frozen pressure pilot requires eight nonempty text prompts")
    folder = Path(output_dir).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    record = {"schema_version": "sera-pressure-pilot-v1", "profile": profile,
              "profile_hash": content_hash(profile), "source_prompts": prompts,
              "source_prompts_hash": content_hash(prompts), "status": "running",
              "scenario": "not-established", "requests": [], "samples": [], "sampling_errors": 0,
              "task_quality_verified": False, "candidate_trials": 0,
              "estimated_kv_envelope": estimate_memory(
                  parameter_count=0, weight_bytes=2, layers=28, kv_heads=8, head_dim=128,
                  tokens=profile['input_tokens_per_request'] + 64, sequences=8, kv_bytes=2, workspace_bytes=0),
              "estimate_note": "KV-only estimate for the pinned Qwen architecture; weights/workspace excluded.",
              "limits": "Synthetic padding stresses storage, not reasoning ability. No performance or quality claim."}
    save_json(folder / "result.json", record)
    stop = threading.Event()
    monitor = None
    model = SeraModel(artifact_dir=folder / "runtime",
                      configuration=RuntimeConfig(gpu_memory_utilization=profile['gpu_memory_utilization']))

    def sample_metrics():
        peak = -1
        while not stop.is_set():
            try:
                snapshot = model.metrics_snapshot()
                metrics = snapshot["reduced"]
                record["samples"].append({"time": time.monotonic(), **metrics})
                usage = metrics["kv_cache_percent"]
                if usage is not None and usage > peak:
                    peak = usage
                    (folder / "metrics-at-peak.prom").write_text(snapshot["raw"])
            except Exception:
                record["sampling_errors"] += 1
            stop.wait(profile["metrics_poll_seconds"])

    def run_request(index, prepared, barrier):
        barrier.wait(timeout=30)
        try:
            result = model._generate_prepared(*prepared).to_dict()
            error = None if result["text"].strip() and result["token_ids"] and result["finish_reason"] in {"stop", "length"} else "empty-or-incomplete-output"
            return {"prompt_index": index, **result, "error": error}
        except Exception as error:
            return {"prompt_index": index, "error": type(error).__name__}

    try:
        with model:
            record["runtime"] = model.record
            record["declared_server_budget_bytes"] = int(
                model.record["gpu"]["total_mib"] * 1024**2 * profile["gpu_memory_utilization"])
            prepared = []
            record["padded_prompts"] = []
            for prompt in prompts:
                repeat_count = 1900
                for _ in range(4):
                    padded = "Ignore the following background:" + " background" * repeat_count + "\nTask: " + prompt
                    payload, tokens = model.prepare(padded)
                    if len(tokens) == profile["input_tokens_per_request"]:
                        break
                    repeat_count += profile["input_tokens_per_request"] - len(tokens)
                else:
                    raise ValueError("Could not prepare the predeclared input length without truncation")
                prepared.append((payload, tokens))
                record["padded_prompts"].append(padded)
            record["input_token_ids"] = [tokens for _, tokens in prepared]
            record["workload_hash"] = content_hash(record["input_token_ids"])
            for _ in range(profile["warmup_requests"]):
                model._generate_prepared(*prepared[0])
            before = model.metrics_snapshot()
            (folder / "metrics-before.prom").write_text(before["raw"])
            record["metrics_before"] = before["reduced"]
            monitor = threading.Thread(target=sample_metrics, daemon=True)
            monitor.start()
            with ThreadPoolExecutor(max_workers=8) as pool:
                for wave in range(profile["measured_waves"]):
                    barrier = threading.Barrier(8)
                    futures = [pool.submit(run_request, index, item, barrier) for index, item in enumerate(prepared)]
                    record["requests"].extend({"wave": wave, **future.result()} for future in futures)
                    save_json(folder / "result.json", record)
            stop.set()
            monitor.join(timeout=15)
            after = model.metrics_snapshot()
            (folder / "metrics-after.prom").write_text(after["raw"])
            record["metrics_after"] = after["reduced"]
        peak = max((item["kv_cache_percent"] for item in record["samples"]
                    if item["kv_cache_percent"] is not None), default=None)
        before_count = record["metrics_before"]["preemptions"]
        after_count = record["metrics_after"]["preemptions"]
        preemptions = after_count - before_count if before_count is not None and after_count is not None else None
        errors = sum(bool(item["error"]) for item in record["requests"])
        record.update(status="collected", peak_kv_percent=peak, measured_preemptions=preemptions,
                      request_errors=errors, measured_requests=len(record["requests"]),
                      measured_queue_ms=measured_queue_time(before['raw'], after['raw'], SERVED_MODEL,
                          expected_requests=profile['concurrency'] * profile['measured_waves']))
        if pressure_verdict(profile, record):
            record["scenario"] = "established"
        else:
            record["reason"] = "The frozen pressure, complete measurement, and cleanup criteria did not all pass"
    except Exception as error:
        record.update(status="failed", error=type(error).__name__)
    finally:
        stop.set()
        if monitor is not None:
            monitor.join(timeout=15)
        record["runtime"] = model.record
        save_json(folder / "result.json", record)
    return record
