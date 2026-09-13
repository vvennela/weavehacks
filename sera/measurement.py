"""Serial measurement and the fixed token-agreement-v1 acceptance rules."""

import math
import time

from .storage import save_json


def nearest_rank(values, percentile):
    if not values:
        return None
    return sorted(values)[max(0, math.ceil(len(values) * percentile / 100) - 1)]


def reduce_requests(requests, elapsed_seconds):
    successful = [item for item in requests if not item.get("error")]
    latencies = [item["latency_ms"] for item in successful]
    output_tokens = sum(item["usage"]["completion_tokens"] for item in successful)
    input_tokens = sum(item["usage"]["prompt_tokens"] for item in successful)
    return {"request_count": len(requests), "successful_requests": len(successful),
            "generation_errors": len(requests) - len(successful),
            "p50_latency_ms": nearest_rank(latencies, 50),
            "p95_latency_ms": nearest_rank(latencies, 95),
            "p99_latency_ms": nearest_rank(latencies, 99),
            "p99_reliable": False, "request_wall_seconds": elapsed_seconds,
            "output_tokens": output_tokens, "input_tokens": input_tokens,
            "output_tokens_per_second": output_tokens / elapsed_seconds if elapsed_seconds > 0 else None,
            "input_tokens_per_second": input_tokens / elapsed_seconds if elapsed_seconds > 0 else None,
            "p95_ttft_ms": None, "p95_queue_ms": None, "p95_time_per_output_token_ms": None}


def collect_trial(model, prompts, trial_id, *, baseline=False):
    """Warm up, measure three serial passes, then collect separate quality passes."""
    folder = model.artifact_dir
    record = {"trial_id": trial_id, "status": "running", "runtime": model.record,
              "config_hash": model.configuration.config_hash, "requests": [],
              "warmup": [], "quality": [], "self_check": [], "metrics": {}}

    def save():
        save_json(folder / "trial.json", record)

    def request(prepared, index):
        payload, tokens = prepared
        try:
            result = model._generate_prepared(payload, tokens).to_dict()
            result["error"] = None
            if not result["text"].strip() or not result["token_ids"]:
                result["error"] = "empty-output"
            elif result["finish_reason"] not in {"stop", "length"}:
                result["error"] = "generation-did-not-complete"
        except Exception as error:
            result = {"text": "", "token_ids": [], "prompt_token_ids": tokens,
                      "error": f"{type(error).__name__}: {error}"}
        return {"prompt_index": index, **result}

    def snapshot(name):
        try:
            metrics = model.metrics_snapshot()
            (folder / f"metrics-{name}.prom").write_text(metrics["raw"])
            record["metrics"][name] = metrics["reduced"]
        except Exception as error:
            record["metrics"][name] = {"unavailable": f"{type(error).__name__}: {error}"}

    save()
    try:
        prepared = [model.prepare(prompt) for prompt in prompts]
        record["input_token_ids"] = [tokens for _, tokens in prepared]
        for index in range(min(len(prompts), 16)):
            record["warmup"].append(request(prepared[index], index))
            save()
        snapshot("before-measurement")
        # Exclude local evidence writes and metrics scraping from the measured interval.
        started = time.perf_counter()
        for index in range(min(3 * len(prompts), 96)):
            prompt_index = index % len(prompts)
            record["requests"].append(request(prepared[prompt_index], prompt_index))
        elapsed = time.perf_counter() - started
        record["reduced"] = reduce_requests(record["requests"], elapsed)
        save()
        snapshot("after-measurement")
        for phase in (["quality", "self_check"] if baseline else ["quality"]):
            for index, item in enumerate(prepared):
                record[phase].append(request(item, index))
                save()
        record["generation_errors"] = sum(bool(item.get("error"))
            for phase in ("warmup", "requests", "quality", "self_check") for item in record[phase])
        record["status"] = "collected" if record["generation_errors"] == 0 else "request-errors"
    except Exception as error:
        record.update(status="failed", error=f"{type(error).__name__}: {error}")
    save()
    return record


def token_agreement(reference, candidate):
    """Mean position-wise agreement. Missing/empty/error outputs always reject."""
    scores = []
    valid = bool(reference) and len(reference) == len(candidate)
    for index, left in enumerate(reference):
        right = candidate[index] if index < len(candidate) else {}
        first, second = left.get("token_ids", []), right.get("token_ids", [])
        pair_valid = (not left.get("error") and not right.get("error")
                      and bool(left.get("text", "").strip()) and bool(right.get("text", "").strip()))
        pair_valid = (pair_valid and bool(first) and bool(second)
                      and left.get("prompt_index") == right.get("prompt_index")
                      and bool(left.get("prompt_token_ids"))
                      and left.get("prompt_token_ids") == right.get("prompt_token_ids"))
        score = sum(a == b for a, b in zip(first, second)) / max(len(first), len(second)) if pair_valid else 0.0
        scores.append(score)
        valid = valid and pair_valid
    mean = sum(scores) / len(scores) if scores else 0.0
    return {"version": "token-agreement-v1", "floor": 0.99, "scores": scores,
            "mean": mean, "valid_outputs": bool(valid), "passed": bool(valid and mean >= 0.99),
            "task_quality_verified": False}


def select_candidate(baseline, candidate):
    self_check = token_agreement(baseline.get("quality", []), baseline.get("self_check", []))
    quality = token_agreement(baseline.get("quality", []), (candidate or {}).get("quality", []))
    decision = {"selected": "baseline", "outcome": "no-safe-improvement",
                "baseline_self_check": self_check, "candidate_quality": quality,
                "p95_improvement_fraction": None}
    if baseline.get("status") != "collected":
        reason = "baseline-measurement-failed"
    elif not self_check["passed"]:
        reason = "unstable-reference"
    elif not candidate or candidate.get("status") != "collected":
        reason = "candidate-not-collected"
    elif baseline.get("input_token_ids") != candidate.get("input_token_ids"):
        reason = "input-token-mismatch"
    elif not quality["passed"]:
        reason = "candidate-quality-failed"
    else:
        baseline_p95 = baseline["reduced"]["p95_latency_ms"]
        candidate_p95 = candidate["reduced"]["p95_latency_ms"]
        if (baseline_p95 is None or candidate_p95 is None or baseline_p95 <= 0
                or not math.isfinite(baseline_p95) or not math.isfinite(candidate_p95)):
            reason = "latency-unavailable"
        else:
            decision["p95_improvement_fraction"] = 1 - candidate_p95 / baseline_p95
            if candidate_p95 <= baseline_p95 * 0.95:
                decision.update(selected="candidate", outcome="improved")
                reason = "quality-passed-and-p95-improved-at-least-five-percent"
            else:
                reason = "p95-improvement-below-five-percent"
    decision["reason"] = reason
    return decision
