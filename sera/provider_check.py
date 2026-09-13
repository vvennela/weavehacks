"""The spec's bounded 30-response provider compatibility experiment."""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .agent import AGENT_MODEL, SCHEMAS, WandbAgent, schema_hash, validate_proposal
from .config import MODEL_ID, SUPPORTED_CHANGES
from .storage import content_hash, save_json


def provider_cases():
    """Freeze ten evidence conditions for each of the three actual schemas."""
    cases = []
    conditions = ["active-cache", "active-batching", "inactive", "rejection-history", "budget-exhausted",
                  "missing-metric", "ranking", "placement-disabled", "latency-outlier", "quality-failure"]
    for index, condition in enumerate(conditions):
        baseline = {"trial_id": "baseline", "model_id": MODEL_ID,
                    "metrics": {"p95_latency_ms": 100 + index, "mean_queue_ms": 0.1,
                                "kv_cache_percent": 40, "generation_errors": 0},
                    "remaining_trials": 1, "supported_changes": deepcopy(SUPPORTED_CHANGES),
                    "fixture": True, "condition": condition}
        if condition == "active-cache":
            baseline["supported_changes"] = {"kv_cache_dtype": ["fp8"]}
        elif condition == "active-batching":
            baseline["supported_changes"] = {"max_num_batched_tokens": [2048]}
            baseline["metrics"]["mean_queue_ms"] = 40
        elif condition in {"inactive", "placement-disabled"}:
            baseline["supported_changes"] = {}
        elif condition == "rejection-history":
            baseline["supported_changes"] = {"max_num_batched_tokens": [2048]}
            baseline["history"] = [{"change": "fp8 KV", "quality_pass": False}]
        elif condition == "budget-exhausted":
            baseline["remaining_trials"] = 0
        elif condition == "missing-metric":
            baseline["metrics"]["mean_queue_ms"] = None
        elif condition == "latency-outlier":
            baseline["metrics"]["p95_latency_ms"] = 54000
            baseline["warning"] = "One outlier dominates; do not claim an established speedup."
        elif condition == "quality-failure":
            baseline["supported_changes"] = {}
            baseline["history"] = [{"trial_id": "candidate", "quality_pass": False, "p95_latency_ms": 50}]
        cases.append({"id": f"proposal-{condition}", "role": "proposal", "evidence": baseline})
        active = bool(baseline["supported_changes"]) and baseline["remaining_trials"] > 0
        ranking = {"fixture": True, "condition": condition, "remaining_trials": baseline["remaining_trials"],
                   "legal_proposal_ids": ["p1", "p2"] if active else [],
                   "proposals": [{"proposal_id": "p1", "estimated_cost": 1, "predicted_p95_ms": 90},
                                 {"proposal_id": "p2", "estimated_cost": 1, "predicted_p95_ms": 95}],
                   "placement": "not-supported-in-single-model-milestone",
                   "instruction": "Rank only legal proposals; return an empty list when none are eligible."}
        cases.append({"id": f"arbiter-{condition}", "role": "arbiter", "evidence": ranking})
        tested = condition in {"quality-failure", "ranking", "rejection-history"}
        accepted = condition == "ranking"
        frontier = {"fixture": True, "condition": condition,
                    "eligible_trial_ids": ["candidate"] if accepted else ["baseline"],
                    "deterministic_selection": "candidate" if accepted else "baseline",
                    "candidate_tested": tested,
                    "candidate_quality_pass": accepted if tested else None,
                    "candidate_p95_ms": 80 if tested else None, "baseline_p95_ms": 100,
                    "proposal_prediction": "At least 5% lower p95 while preserving quality",
                    "placement": "not-supported-in-single-model-milestone"}
        cases.append({"id": f"frontier-{condition}", "role": "frontier", "evidence": frontier})
    return cases


def validate_context(role, parsed, evidence):
    if role == "proposal":
        validate_proposal(parsed, evidence)
    elif role == "arbiter":
        if not set(parsed.ranked_proposal_ids).issubset(evidence["legal_proposal_ids"]):
            raise ValueError("Ranking includes an ineligible proposal")
    elif parsed.selected_trial_id not in evidence["eligible_trial_ids"]:
        raise ValueError("Frontier reader selected an ineligible trial")


def check_provider(*, project, output_dir, model=AGENT_MODEL):
    folder = Path(output_dir).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    cases = provider_cases()
    agent = WandbAgent(project=project, model=model)
    record = {"schema_version": "sera-provider-check-v1", "model": model, "project": project,
              "created_at": datetime.now(timezone.utc).isoformat(), "status": "running",
              "schema_hash": schema_hash(), "cases_hash": content_hash(cases), "cases": cases,
              "schemas": {name: schema.model_json_schema() for name, schema in SCHEMAS.items()},
              "requests": agent.history, "context_checks": [],
              "limits": "Synthetic evidence; schema compatibility only, not search quality or GPU evidence."}
    path = folder / "result.json"
    save_json(path, record)
    try:
        for case in cases:
            if case["role"] == "proposal":
                parsed = agent.propose(case["evidence"])
            elif case["role"] == "frontier":
                parsed = agent.review(case["evidence"])
            else:
                parsed = agent.request("arbiter", case["evidence"],
                    "Rank only legal_proposal_ids for the remaining budget. Empty means no legal experiment.")
            context = {"case_id": case["id"], "passed": False}
            if parsed is not None:
                try:
                    validate_context(case["role"], parsed, case["evidence"])
                    context["passed"] = True
                except ValueError as error:
                    context["error"] = str(error)
            record["context_checks"].append(context)
            save_json(path, record)
            print(f"Provider check {len(agent.history)}/30: {case['id']}; valid={parsed is not None}", flush=True)
            last = agent.history[-1]["attempts"][-1]
            if last.get("http_status") in {401, 403, 404}:
                record["stop_reason"] = last["error"]
                break
    finally:
        first = sum(entry["attempts"][0]["schema_valid"] for entry in agent.history)
        valid = sum(any(attempt["schema_valid"] for attempt in entry["attempts"]) for entry in agent.history)
        complete = len(agent.history) == 30
        record.update(first_pass_valid=first, valid_with_one_retry=valid,
                      completed_requests=len(agent.history),
                      retries=sum(len(entry["attempts"]) - 1 for entry in agent.history),
                      passed=complete and first >= 29 and valid == 30,
                      status="complete" if complete else "incomplete")
        save_json(path, record)
    return record


def require_provider_check(path, agent):
    """Recompute acceptance, including case/schema identity; do not trust a pass flag."""
    import json
    record = json.loads(Path(path).read_text())
    if (record.get("schema_version") != "sera-provider-check-v1"
            or record.get("model") != agent.model or record.get("project") != agent.project
            or record.get("schema_hash") != schema_hash()
            or record.get("cases_hash") != content_hash(provider_cases())):
        raise ValueError("Provider check does not match this model, project, and schemas")
    requests = record.get("requests", [])
    if len(requests) != 30:
        raise ValueError("A complete 30-request provider check is required")
    first = 0
    for case, entry in zip(provider_cases(), requests):
        if entry.get("role") != case["role"] or entry.get("evidence") != case["evidence"]:
            raise ValueError("Provider check cases do not match the frozen experiment")
        attempts = entry.get("attempts", [])
        if not 1 <= len(attempts) <= 2:
            raise ValueError("Each provider request allows at most one retry")
        valid = []
        for attempt in attempts:
            try:
                choice = attempt["raw_response"]["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise ValueError("Incomplete provider response")
                SCHEMAS[case["role"]].model_validate_json(choice["message"]["content"])
                valid.append(True)
            except (ValueError, KeyError, TypeError, IndexError):
                valid.append(False)
        first += valid[0]
        if not any(valid):
            raise ValueError("Provider check contains a request that failed both attempts")
    if first < 29:
        raise ValueError("Provider check needs at least 29 first-pass valid responses")
    return {"path": str(Path(path).resolve()), "schema_hash": schema_hash(),
            "model": agent.model, "first_pass_valid": first, "valid_with_one_retry": 30}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    report = check_provider(project=args.project, output_dir=args.output_dir)
    print({key: report[key] for key in ("passed", "first_pass_valid", "valid_with_one_retry")})
