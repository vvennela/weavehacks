"""Provider compatibility: original 30 cases plus the four new control types."""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .agent import (AGENT_MODEL, REQUEST_SCHEMA_PROTOCOL, SCHEMAS, WandbAgent,
                    parse_response, request_schema, schema_hash, validate_proposal)
from .config import MODEL_ID, RuntimeConfig, SUPPORTED_CHANGES
from .storage import content_hash, save_json


def provider_cases():
    """Freeze 30 original conditions plus four new-control proposal cases."""
    cases = []
    conditions = ["active-cache", "active-batching", "active-sequences", "active-context", "actual-parent",
                  "budget-exhausted", "missing-metric", "ranking", "inactive", "quality-failure"]
    for index, condition in enumerate(conditions):
        baseline = {"trial_id": "baseline", "model_id": MODEL_ID,
                    "metrics": {"p95_latency_ms": 100 + index, "mean_queue_ms": 0.1,
                                "kv_cache_percent": 40, "generation_errors": 0},
                    "remaining_trials": 1, "supported_changes": deepcopy(SUPPORTED_CHANGES),
                    "configuration": RuntimeConfig().model_dump(),
                    "fixture": True, "condition": condition}
        if condition == "active-cache":
            baseline["supported_changes"] = {"kv_cache_dtype": ["fp8"]}
        elif condition == "active-batching":
            baseline["supported_changes"] = {"max_num_batched_tokens": [2048]}
            baseline["metrics"]["mean_queue_ms"] = 40
        elif condition == "active-sequences":
            baseline["supported_changes"] = {"max_num_seqs": [4]}
        elif condition == "active-context":
            baseline["supported_changes"] = {"max_model_len": [2048]}
        elif condition == "actual-parent":
            baseline["configuration"] = RuntimeConfig(max_num_batched_tokens=2048).model_dump()
            baseline["supported_changes"] = {"max_num_batched_tokens": [4096]}
        elif condition == "inactive":
            baseline["supported_changes"] = {}
        elif condition == "budget-exhausted":
            baseline["remaining_trials"] = 0
        elif condition == "missing-metric":
            baseline["metrics"]["mean_queue_ms"] = None
        elif condition == "quality-failure":
            baseline["supported_changes"] = {}
            baseline["history"] = [{"trial_id": "candidate", "quality_pass": False, "p95_latency_ms": 50}]
        active = bool(baseline["supported_changes"]) and baseline["remaining_trials"] > 0
        baseline["format_check_action"] = "trial" if active else "keep-baseline"
        cases.append({"id": f"proposal-{condition}", "role": "proposal", "evidence": baseline})
        ranking = {"fixture": True, "condition": condition, "remaining_trials": baseline["remaining_trials"],
                   "legal_proposal_ids": ["p1", "p2"] if active else [],
                   "proposals": [{"proposal_id": "p1", "estimated_cost": 1, "predicted_p95_ms": 90},
                                 {"proposal_id": "p2", "estimated_cost": 1, "predicted_p95_ms": 95}],
                   "placement": "not-supported-in-single-model-milestone",
                   "instruction": "Rank only legal proposals; return an empty list when none are eligible."}
        cases.append({"id": f"arbiter-{condition}", "role": "arbiter", "evidence": ranking})
        tested = condition in {"quality-failure", "ranking"}
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
    for lever, value in [('enable_prefix_caching', True), ('enable_chunked_prefill', False),
                         ('enforce_eager', False), ('gpu_memory_utilization', .85)]:
        evidence = deepcopy(cases[0]['evidence'])
        evidence.update(condition=f'active-{lever}', supported_changes={lever: [value]})
        cases.append(dict(id=f'proposal-active-{lever}', role='proposal', evidence=evidence))
    return cases


def validate_context(role, parsed, evidence):
    if role == "proposal":
        validate_proposal(parsed, evidence)
        if parsed.action != evidence["format_check_action"]:
            raise ValueError("Proposal did not exercise the required format-check action")
    elif role == "arbiter":
        if not set(parsed.ranked_proposal_ids).issubset(evidence["legal_proposal_ids"]):
            raise ValueError("Ranking includes an ineligible proposal")
    elif parsed.selected_trial_id not in evidence["eligible_trial_ids"]:
        raise ValueError("Frontier reader selected an ineligible trial")


def check_provider(*, project, output_dir, model=AGENT_MODEL, agent=None):
    agent = WandbAgent(project=project, model=model) if agent is None else agent
    if agent.project != project or agent.model != model or agent.history:
        raise ValueError("Format check requires a fresh agent matching model and project")
    folder = Path(output_dir).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    cases = provider_cases()
    record = {"schema_version": "sera-provider-check-v1", "model": model, "project": project,
              "provider": getattr(agent, "provider", "wandb"),
              "created_at": datetime.now(timezone.utc).isoformat(), "status": "running",
              "schema_hash": schema_hash(), "cases_hash": content_hash(cases), "cases": cases,
              "request_schema_protocol": REQUEST_SCHEMA_PROTOCOL,
              "schemas": {name: schema.model_json_schema() for name, schema in SCHEMAS.items()},
              "requests": agent.history, "context_checks": [],
              "limits": "Synthetic evidence; schema compatibility only, not search quality or GPU evidence."}
    path = folder / "result.json"
    save_json(path, record)
    try:
        for case in cases:
            if case["role"] == "proposal":
                parsed = agent.request("proposal", case["evidence"],
                    "This is a synthetic format test, not a live experiment or a performance claim. "
                    "Use the supplied format_check_action to exercise that response shape. For trial, "
                    "choose one supported_changes value with the correct specialist role and cost one. "
                    "For keep-baseline, use null lever/value and cost zero. Reference the supplied model "
                    "and parent trial, cite exact available metric names, and state a testable prediction. "
                    "Respect the actual parent configuration and remaining trial budget.")
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
            print(f"Provider check {len(agent.history)}/{len(cases)}: {case['id']}; valid={parsed is not None}", flush=True)
            last = agent.history[-1]["attempts"][-1]
            if last.get("http_status") in {401, 403, 404}:
                record["stop_reason"] = last["error"]
                break
    finally:
        first = sum(entry["attempts"][0]["schema_valid"] for entry in agent.history)
        valid = sum(any(attempt["schema_valid"] for attempt in entry["attempts"]) for entry in agent.history)
        complete = len(agent.history) == len(cases)
        record.update(first_pass_valid=first, valid_with_one_retry=valid,
                      completed_requests=len(agent.history),
                      retries=sum(len(entry["attempts"]) - 1 for entry in agent.history),
                      passed=complete and first >= len(cases) - 1 and valid == len(cases)
                             and all(check["passed"] for check in record["context_checks"]),
                      status="complete" if complete else "incomplete")
        save_json(path, record)
    return record


def require_provider_check(path, agent):
    """Recompute acceptance, including case/schema identity; do not trust a pass flag."""
    import json
    record = json.loads(Path(path).read_text())
    provider = getattr(agent, "provider", "wandb")
    if record.get("provider", "wandb") != provider:
        raise ValueError("Provider check does not match this provider transport")
    if (record.get("schema_version") != "sera-provider-check-v1"
            or record.get("model") != agent.model or record.get("project") != agent.project
            or record.get("schema_hash") != schema_hash()
            or record.get("cases_hash") != content_hash(provider_cases())):
        raise ValueError("Provider check does not match this model, project, and schemas")
    requests = record.get("requests", [])
    total = len(provider_cases())
    if len(requests) != total:
        raise ValueError(f"A complete {total}-request provider check is required")
    first = 0
    for case, entry in zip(provider_cases(), requests):
        if entry.get("provider", "wandb") != provider:
            raise ValueError("Provider request does not match this provider transport")
        if entry.get("role") != case["role"] or entry.get("evidence") != case["evidence"]:
            raise ValueError("Provider check cases do not match the frozen experiment")
        expected_schema = request_schema(case["role"], case["evidence"])
        if (entry.get("schema_hash") != content_hash(expected_schema)
                or entry.get("request_schema") != expected_schema):
            raise ValueError("Provider check request schema does not match the frozen evidence")
        attempts = entry.get("attempts", [])
        if not 1 <= len(attempts) <= 2:
            raise ValueError("Each provider request allows at most one retry")
        valid = []
        for attempt in attempts:
            try:
                choice = attempt["raw_response"]["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise ValueError("Incomplete provider response")
                parsed = parse_response(case["role"], choice["message"]["content"], case["evidence"])
                valid.append(True)
            except (ValueError, KeyError, TypeError, IndexError):
                valid.append(False)
                continue
            try:
                validate_context(case["role"], parsed, case["evidence"])
            except ValueError as error:
                raise ValueError(f"Provider check context failed: {case['id']}") from error
        first += valid[0]
        if not any(valid):
            raise ValueError("Provider check contains a request that failed both attempts")
    if first < total - 1:
        raise ValueError(f"Provider check needs at least {total - 1} first-pass valid responses")
    return {"path": str(Path(path).resolve()), "schema_hash": schema_hash(),
            "model": agent.model, "provider": provider,
            "first_pass_valid": first, "valid_with_one_retry": total}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", default=AGENT_MODEL, help="Hosted investigator model to certify")
    parser.add_argument("--provider", choices=['wandb', 'codex-relay'], default='wandb')
    parser.add_argument("--relay-dir", help="Shared request directory for the local Codex controller")
    args = parser.parse_args(argv)
    if (args.provider == 'codex-relay') != bool(args.relay_dir):
        parser.error('--relay-dir is required only with --provider codex-relay')
    agent = None
    if args.provider == 'codex-relay':
        from .relay import RelayAgent
        agent = RelayAgent(project=args.project, model=args.model, relay_dir=args.relay_dir)
    report = check_provider(project=args.project, output_dir=args.output_dir, model=args.model, agent=agent)
    print({key: report[key] for key in ("passed", "first_pass_valid", "valid_with_one_retry")})


if __name__ == "__main__":
    main()
