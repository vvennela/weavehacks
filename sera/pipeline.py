"""One baseline, one controlled candidate, a deterministic gate, and a live return."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import uuid

from .config import BASELINE_NAME, MODEL_ID, MODEL_REVISION, Candidate, RuntimeConfig, validate_candidate
from .measurement import collect_trial, select_candidate, token_agreement
from .runtime import CleanupError, GENERATION, SeraModel
from .storage import content_hash, save_json


def agent_evidence(baseline):
    from .config import SUPPORTED_CHANGES
    metrics = dict(baseline["reduced"])
    snapshot = baseline.get("metrics", {}).get("after-measurement", {})
    metrics.update(mean_queue_ms=snapshot.get("mean_queue_ms"),
                   mean_ttft_ms=snapshot.get("mean_ttft_ms"),
                   preemptions=snapshot.get("preemptions"))
    return {"trial_id": "baseline", "model_id": MODEL_ID, "revision": MODEL_REVISION,
            "configuration": baseline["runtime"]["configuration"],
            "metrics": metrics, "remaining_trials": 1, "supported_changes": SUPPORTED_CHANGES,
            "baseline_self_check": token_agreement(baseline["quality"], baseline["self_check"]),
            "limitations": ["No measured KV peak in this serial run; idle KV use is not pressure evidence.",
                            "Token agreement does not establish task correctness.",
                            "This small sample cannot establish statistical significance."]}


@dataclass
class SeraResult:
    models: list[SeraModel]
    report: dict
    output_dir: Path

    @property
    def recommended(self):
        return self.report["decision"]["outcome"]

    @property
    def baselines(self):
        return [self.report["baseline"]] if "baseline" in self.report else []

    @property
    def trials(self):
        return self.baselines + ([self.report["candidate_trial"]] if "candidate_trial" in self.report else [])

    @property
    def rejected(self):
        return self.report.get("rejected", [])

    @property
    def weave_url(self):
        return self.report.get("weave_url")

    @property
    def frontier(self):
        viable = []
        for trial in self.trials:
            if trial["trial_id"] == "baseline" or self.report["decision"]["selected"] == "candidate":
                if trial["status"] == "collected":
                    viable.append(trial)
        # The first milestone selects on latency only; full Pareto search is deferred.
        return sorted(viable, key=lambda trial: trial["reduced"]["p95_latency_ms"])[:1]

    def _save(self):
        self.report["returned_runtimes"] = [model.record for model in self.models]
        save_json(self.output_dir / "result.json", self.report)
        (self.output_dir / "report.md").write_text(render_summary(self.report, self.output_dir))

    def print_summary(self):
        print(render_summary(self.report, self.output_dir))

    def close(self):
        try:
            for model in self.models:
                model.close()
            self.report["returned_runner_closed"] = True
            self.report["status"] = "closed"
        finally:
            self._save()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def render_summary(report, output_dir):
    decision = report.get("decision", {})
    lines = ["# Sera single-model result", "", f"Status: {report['status']}",
             f"Selection: {decision.get('selected', 'none')}",
             f"Reason: {decision.get('reason', report.get('error', 'not finished'))}", "",
             "Task quality was not verified. The gate checks token agreement, not correct answers.",
             "This is one comparison, not a statistically established speedup.", ""]
    for key, label in (("baseline", "Baseline"), ("candidate_trial", "Candidate")):
        trial = report.get(key)
        if trial:
            reduced = trial.get("reduced", {})
            lines.append(f"{label}: {trial['status']}; requests={reduced.get('request_count', 'unavailable')}; "
                         f"p95={reduced.get('p95_latency_ms', 'unavailable')} ms; "
                         f"output tokens={reduced.get('output_tokens', 'unavailable')}; "
                         f"startup={trial.get('runtime', {}).get('startup_seconds', 'unavailable')} s.")
    gate = decision.get("candidate_quality")
    if gate:
        lines.append(f"Token agreement: {gate['mean']:.4f}; required >= {gate['floor']}; pass={gate['passed']}.")
    lines.extend(["", f"Workload: {report.get('workload')}",
                  f"Generation: {report.get('generation')}",
                  f"Record: {output_dir / 'result.json'}", ""])
    return "\n".join(lines)


def optimize(*, models, prompts, output_dir=None, candidate=None, agent=None, provider_check=None):
    """One measured candidate, fixed or agent-proposed; no joint placement or search claim.

    Uses at most 32 supplied prompts, serial load, up to 16 warm-ups, three
    measured passes, and separate quality passes. The caller owns result.close().
    """
    if models != [MODEL_ID]:
        raise ValueError(f"This milestone requires models=[{MODEL_ID!r}]")
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 32:
        raise ValueError("Supply 1 to 32 prompts; inputs are never silently dropped")
    for prompt in prompts:
        if not isinstance(prompt, (str, list)) or not prompt:
            raise ValueError("Each prompt must be nonempty text or chat messages")
    provider_validation = None
    if agent is not None:
        from .provider_check import require_provider_check
        if candidate is not None or provider_check is None:
            raise ValueError("Agent mode requires provider_check and no fixed candidate")
        provider_validation = require_provider_check(provider_check, agent)
        history_start = len(agent.history)
    else:
        candidate = validate_candidate(candidate if candidate is not None else Candidate(
            name="kv-fp8", reason="The predeclared first candidate changes only the checked KV precision",
            config=RuntimeConfig(kv_cache_dtype="fp8")))
    folder = Path(output_dir or Path("sera-runs") / uuid.uuid4().hex).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": "sera-single-model-v1", "status": "running",
              "created_at": datetime.now(timezone.utc).isoformat(),
              "mode": "agent-guided" if agent is not None else "fixed-candidate",
              "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
              "baseline_name": BASELINE_NAME, "candidate": candidate.model_dump() if candidate else None,
              "prompts": prompts, "workload_hash": content_hash(prompts),
              "generation": {**GENERATION, "enable_thinking": False},
              "workload": {"prompt_count": len(prompts), "concurrency": 1,
                           "warmup_requests": min(len(prompts), 16),
                           "measured_requests": 3 * len(prompts), "quality_requests": len(prompts)},
              "task_quality_verified": False,
              "agent_selection": "enabled" if agent is not None else "not-enabled",
              "provider_validation": provider_validation,
              "limits": ["single model", "one candidate", "non-streaming requests",
                         "TTFT and queue percentiles unavailable", "no task-correctness claim"],
              "rejected": []}
    result = SeraResult(models=[], report=report, output_dir=folder)
    active = None
    result._save()
    try:
        active = SeraModel(artifact_dir=folder / "baseline")
        active.start()
        report["baseline"] = collect_trial(active, prompts, "baseline", baseline=True)
        result._save()
        baseline = report["baseline"]
        stable = token_agreement(baseline["quality"], baseline["self_check"])["passed"]
        trial = None
        if agent is not None and baseline["status"] == "collected" and stable:
            from .agent import validate_proposal
            evidence = agent_evidence(baseline)
            report["agent_input"] = evidence
            try:
                proposal = agent.propose(evidence)
                if proposal is None:
                    raise ValueError("Agent produced no schema-valid proposal within one retry")
                report["proposal"] = proposal.model_dump()
                candidate = validate_proposal(proposal, evidence)
                report["proposal_validation"] = "passed"
                report["candidate"] = candidate.model_dump() if candidate else None
            except Exception as error:
                candidate = None
                report["proposal_validation"] = "rejected"
                report["rejected"].append({"reason": f"{type(error).__name__}: {error}"})
            report["agent_calls"] = agent.history[history_start:]
            result._save()
        if baseline["status"] == "collected" and stable and candidate is not None:
            active.close()
            result._save()
            active = SeraModel(artifact_dir=folder / "candidate", configuration=candidate.config)
            try:
                active.start()
                trial = collect_trial(active, prompts, "candidate")
            except CleanupError:
                raise
            except Exception as error:
                trial = {"trial_id": "candidate", "status": "startup-failed",
                         "error": f"{type(error).__name__}: {error}", "runtime": active.record}
            report["candidate_trial"] = trial
            result._save()
        report["decision"] = select_candidate(baseline, trial)
        if agent is not None and trial is None and stable:
            report["decision"]["reason"] = ("agent-kept-baseline" if report.get("proposal_validation") == "passed"
                                             else "agent-proposal-rejected")
        if agent is not None and report.get("proposal"):
            feedback = {"proposal": report["proposal"], "decision": report["decision"],
                        "candidate_tested": trial is not None,
                        "baseline_metrics": baseline.get("reduced"),
                        "candidate_metrics": trial.get("reduced") if trial else None,
                        "candidate_status": trial.get("status") if trial else "not-tested",
                        "eligible_trial_ids": [report["decision"]["selected"]]}
            report["agent_feedback"] = feedback
            try:
                final = agent.review(feedback)
                if final is None or final.selected_trial_id not in feedback["eligible_trial_ids"]:
                    raise ValueError("Final agent response did not respect the deterministic selection")
                report["agent_final"] = final.model_dump()
            except Exception as error:
                report["agent_final_error"] = f"{type(error).__name__}: {error}"
            report["agent_calls"] = agent.history[history_start:]
        result._save()
        if report["decision"]["selected"] == "baseline" and trial is not None:
            active.close()
            active = SeraModel(artifact_dir=folder / "returned-baseline")
            active.start()
        if baseline["status"] != "collected":
            raise RuntimeError("Baseline measurement failed; see the saved trial before retrying")
        active._require_ready()
        result.models = [active]
        report.update(status="ready", returned_runner_closed=False)
        result._save()
        return result
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        try:
            if active is not None:
                active.close()
        finally:
            result._save()
        raise
