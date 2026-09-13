"""Serial measurement and the fixed token-agreement-v1 acceptance rules."""

import math
import time
from concurrent.futures import ThreadPoolExecutor

from .storage import save_json
from .config import Constraints, Objective, Workload
from .tracing import TraceSinkError, emit_event, event_sink_enabled, recorded_model_request


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


def reduce_loads(loads):
    """Worst per-load latency; throughput across the declared measurement windows."""
    metrics = [load["reduced"] for load in loads]
    result = {key: sum(item[key] for item in metrics) for key in
              ("request_count", "successful_requests", "generation_errors", "request_wall_seconds",
               "output_tokens", "input_tokens")}
    for key in ("p50_latency_ms", "p95_latency_ms", "p99_latency_ms"):
        values = [item[key] for item in metrics]
        result[key] = max(values) if values and all(value is not None for value in values) else None
    elapsed = result["request_wall_seconds"]
    result.update(output_tokens_per_second=result["output_tokens"] / elapsed if elapsed > 0 else None,
                  input_tokens_per_second=result["input_tokens"] / elapsed if elapsed > 0 else None,
                  p99_reliable=False, p95_ttft_ms=None, p95_queue_ms=None, p95_time_per_output_token_ms=None)
    return result


def export_trial_events(record, prompts):
    """Log saved requests only after all measured and quality passes finish."""
    export = record['trace_export']
    runtime = record['runtime']
    identity = dict(trial_id=record['trial_id'], model_id=runtime.get('model_id'),
                    revision=runtime.get('revision'), config_hash=record['config_hash'])

    def publish_requests(responses, phase, concurrency):
        for response in responses:
            index = response['prompt_index']
            recorded_model_request(**identity, phase=phase, concurrency=concurrency,
                                   prompt_index=index, prompt=prompts[index], response=response)
            export['emitted_events'] += 1

    try:
        for load in record['loads']:
            publish_requests(load['warmup'], 'warmup', load['concurrency'])
            publish_requests(load['requests'], 'measured', load['concurrency'])
        for phase in ('quality', 'self_check'):
            publish_requests(record[phase], phase, 1)
        emit_event('recorded_trial_metrics', {
            **identity, 'status': record['status'], 'reduced': record.get('reduced'),
            'loads': [{'concurrency': load['concurrency'], 'reduced': load.get('reduced')}
                      for load in record['loads']],
            'generation_errors': record.get('generation_errors'),
            'quality_requests': len(record['quality']), 'self_check_requests': len(record['self_check']),
            'timing_scope': export['timing_scope'],
        })
        export['emitted_events'] += 1
        export['status'] = 'complete'
    except TraceSinkError as error:
        # Trace failure is not a generation failure. Preserve measured verdicts
        # and expose the export error separately for the calling application.
        export.update(status='failed', error_type=error.error_type, failed_event=error.event_name)


def collect_trial(model, prompts, trial_id, *, baseline=False, workload=None):
    """Measure each declared load separately, then collect serial quality passes."""
    workload = Workload() if workload is None else Workload.model_validate(workload)
    if max(workload.concurrency) > model.configuration.max_num_seqs:
        raise ValueError("Workload concurrency exceeds the service sequence limit")
    folder = model.artifact_dir
    record = {"trial_id": trial_id, "status": "running", "runtime": model.record,
              "config_hash": model.configuration.config_hash, "requests": [],
              "warmup": [], "quality": [], "self_check": [], "metrics": {}, "loads": [],
              "workload": {**workload.model_dump(), "quality_concurrency": 1,
                           "latency_reduction": "worst-per-load-percentile",
                           "throughput_reduction": "total-tokens-over-total-measured-window-seconds"}}

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
        for concurrency in workload.concurrency:
            load = {"concurrency": concurrency, "warmup": [], "requests": []}
            record["loads"].append(load)
            for index in range(min(len(prompts), 16)):
                item = request(prepared[index], index)
                load["warmup"].append(item)
                record["warmup"].append(item)
            prefix = "" if workload.concurrency == [1] else f"concurrency-{concurrency}-"
            snapshot(prefix + "before-measurement")

            def measured_request(index):
                prompt_index = index % len(prompts)
                return request(prepared[prompt_index], prompt_index)

            # Keep file writes and metric scraping outside every measured window.
            started = time.perf_counter()
            indices = range(min(3 * len(prompts), 96))
            if concurrency == 1:
                load["requests"] = [measured_request(index) for index in indices]
            else:
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    load["requests"] = list(executor.map(measured_request, indices))
            elapsed = time.perf_counter() - started
            load["reduced"] = reduce_requests(load["requests"], elapsed)
            record["requests"].extend(load["requests"])
            snapshot(prefix + "after-measurement")
            load["metrics"] = {name: record["metrics"][prefix + name]
                               for name in ("before-measurement", "after-measurement")}
            save()
        record["reduced"] = reduce_loads(record["loads"])
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
    if event_sink_enabled():
        record['trace_export'] = {
            'status': 'running', 'emitted_events': 0,
            'timing_scope': 'Events are exported after measurement; span durations measure logging time.'}
        save()
        export_trial_events(record, prompts)
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


def objective_value(trial, priority):
    if priority == "memory":
        value = trial.get("runtime", {}).get("sampled_peak_memory_mib")
    else:
        key = "p95_latency_ms" if priority == "latency" else "output_tokens_per_second"
        value = trial.get("reduced", {}).get(key)
    return value if type(value) in (int, float) and math.isfinite(value) and value > 0 else None


def constraint_failures(trial, constraints):
    if trial.get("status") == "infeasible":
        return ["estimated-memory-does-not-fit"]
    failures = []
    if trial.get("status") != "collected":
        failures.append("measurement-failed")
    gate = trial.get("task_quality", {})
    score = gate.get("mean")
    if (not gate.get("valid_outputs") or type(score) not in (int, float)
            or not math.isfinite(score) or not constraints.quality_floor <= score <= 1):
        failures.append("task-quality-failed")
    for priority, limit in (("latency", constraints.p95_latency_ms), ("memory", constraints.max_memory_mib)):
        if limit is not None:
            value = objective_value(trial, priority)
            if value is None or value > limit:
                failures.append(f"{priority}-requirement-failed")
    return failures


def measured_frontier(baseline, candidate, *, constraints=None):
    """Keep quality-valid trade-offs; missing metrics cannot prove dominance."""
    if constraints is not None:
        constraints = Constraints.model_validate(constraints)
        viable = [trial for trial in [baseline, candidate] if trial and not constraint_failures(trial, constraints)]
        if (candidate and baseline.get("status") != "infeasible"
                and baseline.get("input_token_ids") != candidate.get("input_token_ids")):
            viable = [trial for trial in viable if trial is baseline]
    elif (baseline.get("status") != "collected"
            or not token_agreement(baseline.get("quality", []), baseline.get("self_check", []))["passed"]):
        return []
    else:
        viable = [baseline]
        if (candidate and candidate.get("status") == "collected"
                and baseline.get("input_token_ids") == candidate.get("input_token_ids")
                and token_agreement(baseline.get("quality", []), candidate.get("quality", []))["passed"]):
            viable.append(candidate)

    def dominates(left, right):
        a = [objective_value(left, p) for p in ("latency", "memory", "throughput")]
        b = [objective_value(right, p) for p in ("latency", "memory", "throughput")]
        if None in a or None in b:
            return False
        no_worse = a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2]
        better = a[0] < b[0] or a[1] < b[1] or a[2] > b[2]
        return no_worse and better

    return [trial for trial in viable if not any(dominates(other, trial) for other in viable)]


def select_candidate(baseline, candidate, *, objective=None, constraints=None):
    objective = Objective() if objective is None else Objective.model_validate(objective)
    self_check = token_agreement(baseline.get("quality", []), baseline.get("self_check", []))
    quality = token_agreement(baseline.get("quality", []), (candidate or {}).get("quality", []))
    decision = {"selected": "baseline", "outcome": "no-safe-improvement",
                "baseline_self_check": self_check, "candidate_quality": quality,
                "p95_improvement_fraction": None, "objective": objective.model_dump(),
                "objective_improvement_fraction": None}
    # Report performance even when quality rejects it; measurement is not approval.
    baseline_p95 = objective_value(baseline, "latency")
    candidate_p95 = objective_value(candidate or {}, "latency")
    if baseline_p95 is not None and candidate_p95 is not None:
        decision["p95_improvement_fraction"] = 1 - candidate_p95 / baseline_p95
    before = objective_value(baseline, objective.priority)
    after = objective_value(candidate or {}, objective.priority)
    if before is not None and after is not None:
        gain = (after - before) / before if objective.priority == "throughput" else (before - after) / before
        decision["objective_improvement_fraction"] = gain
    if constraints is not None:
        constraints = Constraints.model_validate(constraints)
        failures = {"baseline": constraint_failures(baseline, constraints),
                    "candidate": constraint_failures(candidate or {}, constraints)}
        if (candidate and baseline.get("status") != "infeasible"
                and baseline.get("input_token_ids") != candidate.get("input_token_ids")):
            failures["candidate"].append("input-token-mismatch")
        if after is None:
            failures["candidate"].append("objective-metric-unavailable")
        decision.update(constraints=constraints.model_dump(), constraint_failures=failures,
                        baseline_quality=baseline.get("task_quality"),
                        candidate_quality=(candidate or {}).get("task_quality"))
        if failures["baseline"]:
            if failures["candidate"]:
                decision.update(selected=None, outcome="no-safe-configuration", reason="no-trial-meets-constraints")
            else:
                decision.update(selected="candidate", outcome="feasible", reason="candidate-meets-constraints-baseline-does-not")
            return decision
        if failures["candidate"]:
            decision["reason"] = "candidate-constraints-failed"
            return decision
    if baseline.get("status") != "collected":
        reason = "baseline-measurement-failed"
    elif constraints is None and not self_check["passed"]:
        reason = "unstable-reference"
    elif not candidate or candidate.get("status") != "collected":
        reason = "candidate-not-collected"
    elif baseline.get("input_token_ids") != candidate.get("input_token_ids"):
        reason = "input-token-mismatch"
    elif constraints is None and not quality["passed"]:
        reason = "candidate-quality-failed"
    else:
        gain = decision["objective_improvement_fraction"]
        if gain is None:
            reason = "latency-unavailable" if objective.priority == "latency" else "objective-metric-unavailable"
        else:
            if gain > 0 and (gain >= objective.min_improvement_fraction
                             or math.isclose(gain, objective.min_improvement_fraction, rel_tol=1e-12)):
                decision.update(selected="candidate", outcome="improved")
                reason = ("quality-passed-and-p95-improved-at-least-five-percent"
                          if objective == Objective() else "quality-passed-and-objective-improved")
            else:
                reason = ("p95-improvement-below-five-percent" if objective == Objective()
                          else "objective-improvement-below-threshold")
    decision["reason"] = reason
    return decision
