"""Compare correctness and timing without turning this pilot into an optimizer."""

import math
import statistics

from benchmarks.grade import dataset_hash, score_responses


def summarize_vector(cases, record):
    expected_ids = [case["id"] for case in cases]
    expected_public_cases = [{key: case[key] for key in ("id", "prompt", "max_tokens")} for case in cases]
    if record["cases"] != expected_public_cases:
        raise ValueError("Recorded prompts differ from the frozen cases")
    if [item["id"] for item in record["requests"]] != expected_ids:
        raise ValueError("The task vector is incomplete or its case order changed")
    if record["dataset_sha256"] != dataset_hash(cases):
        raise ValueError("The answer key differs from the frozen dataset")
    responses = {
        item["id"]: item["text"] if item.get("request_error") is None else ""
        for item in record["requests"]
    }
    summary = score_responses(cases, responses)
    measured = [item for item in record["requests"] if item.get("request_error") is None]
    latencies = sorted(item["latency_ms"] for item in measured)
    if any(not math.isfinite(value) or value <= 0 for value in latencies):
        raise ValueError("Invalid latency sample")
    output_tokens = sum(item["usage"]["completion_tokens"] for item in measured)
    summary["runtime"] = {
        "status": record["status"], "cleanup_pass": record["cleanup_pass"],
        "request_errors": len(record["requests"]) - len(measured),
        "truncated_outputs": sum(item.get("finish_reason") == "length" for item in measured),
        "measured_requests": len(measured),
        "median_latency_ms": statistics.median(latencies) if latencies else None,
        "p95_latency_ms": latencies[math.ceil(0.95 * len(latencies)) - 1] if latencies else None,
        "max_latency_ms": max(latencies) if latencies else None,
        "total_request_seconds": sum(latencies) / 1000,
        "completion_tokens": output_tokens,
        "output_tokens_per_request_second": output_tokens / (sum(latencies) / 1000) if latencies else None,
        "startup_seconds": record.get("startup_seconds"),
        "sampled_peak_memory_mib": record["sampled_peak_memory_mib"],
        "memory_after_mib": record["memory_after_mib"],
    }
    return summary


def compare_vectors(cases, baseline, candidate):
    for field in ["model_id", "revision", "workload_hash", "dataset_sha256", "cases",
                  "system_prompt", "generation", "concurrency", "warmup_requests", "measured_passes", "versions", "gpu"]:
        if baseline[field] != candidate[field]:
            raise ValueError(f"Comparison mismatch: {field}")
    if baseline["kv_cache_dtype"] != "auto" or candidate["kv_cache_dtype"] != "fp8":
        raise ValueError("Expected BF16 reference and FP8 KV candidate")
    commands = []
    for record in (baseline, candidate):
        command = list(record["command"])
        if command[command.index("--kv-cache-dtype") + 1] != record["kv_cache_dtype"]:
            raise ValueError("Cache metadata differs from the executed command")
        for flag in ("--port", "--kv-cache-dtype"):
            command[command.index(flag) + 1] = "<comparison-variable>"
        commands.append(command)
    if commands[0] != commands[1]:
        raise ValueError("Server flags differ beyond cache precision and the local port")
    baseline_scores = summarize_vector(cases, baseline)
    candidate_scores = summarize_vector(cases, candidate)
    comparison = []
    agreements = []
    for before, after, before_output, after_output in zip(
        baseline_scores["per_case"], candidate_scores["per_case"], baseline["requests"], candidate["requests"]
    ):
        if before_output.get("request_error") is None and after_output.get("request_error") is None:
            before_prompt = before_output.get("prompt_token_ids")
            after_prompt = after_output.get("prompt_token_ids")
            if not before_prompt or before_prompt != after_prompt:
                raise ValueError(f"Rendered prompt tokens missing or different: {before['id']}")
        before_ids, after_ids = before_output.get("token_ids"), after_output.get("token_ids")
        agreement = None
        if before_ids and after_ids:
            agreement = sum(a == b for a, b in zip(before_ids, after_ids)) / max(len(before_ids), len(after_ids))
            agreements.append(agreement)
        comparison.append({
            "id": before["id"], "category": before["category"],
            "baseline_pass": before["passed"], "fp8_pass": after["passed"],
            "baseline_reason": before["reason"], "fp8_reason": after["reason"],
            "identical_text": before_output["text"] == after_output["text"],
            "token_agreement": agreement,
        })
    return {
        "benchmark": baseline_scores["benchmark"], "dataset_sha256": dataset_hash(cases),
        "baseline": baseline_scores, "fp8_kv": candidate_scores,
        "paired": {
            "both_correct": sum(row["baseline_pass"] and row["fp8_pass"] for row in comparison),
            "both_wrong": sum(not row["baseline_pass"] and not row["fp8_pass"] for row in comparison),
            "regressions": [row["id"] for row in comparison if row["baseline_pass"] and not row["fp8_pass"]],
            "gains": [row["id"] for row in comparison if not row["baseline_pass"] and row["fp8_pass"]],
            "different_text_both_correct": sum(row["baseline_pass"] and row["fp8_pass"] and not row["identical_text"] for row in comparison),
            "mean_token_agreement": statistics.mean(agreements) if len(agreements) == len(cases) else None,
        },
        "per_case": comparison,
        "selection": "Not made: this is a task-quality pilot, not an optimization acceptance run.",
        "limits": [
            "24 original cases; not official HLE, DeepSWE, or SWE-bench scores.",
            "One measured pass per configuration; latency is descriptive, not statistically established.",
            "Task latency excludes warmup; saved server metrics include warmup.",
            "Output token counts can differ. Request-level token throughput is not isolated decode speed.",
            "Coding tasks test tracing and repair selection, not free-form code execution or repository repair.",
        ],
    }


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    from benchmarks.grade import load_cases

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    arguments = parser.parse_args()
    result = compare_vectors(load_cases(), json.loads(arguments.baseline.read_text()), json.loads(arguments.candidate.read_text()))
    print(json.dumps(result, indent=2))
