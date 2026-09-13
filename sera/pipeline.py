"""One baseline, one controlled candidate, a deterministic gate, and a live return."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import uuid

from .config import BASELINE_NAME, LARGE_MODEL_ID, LARGE_MODEL_REVISION, MODEL_ID, MODEL_REVISION, Budget, Candidate, Constraints, Objective, RuntimeConfig, Workload, resolve_investigation_space, validate_candidate
from .measurement import collect_trial, measured_frontier, select_candidate, token_agreement
from .quality import evaluate_quality
from .runtime import CleanupError, GENERATION, SeraModel
from .storage import content_hash, save_json


def load_snapshot_metrics(trial):
    """Expose after-load cumulative snapshots, not measured-window averages."""
    metrics = {}
    for load in trial.get('loads', []):
        snapshot = load.get('metrics', {}).get('after-measurement', {})
        prefix = f"concurrency_{load['concurrency']}_cumulative_snapshot_"
        for name in ('mean_queue_ms', 'mean_ttft_ms', 'preemptions'):
            metrics[prefix + name] = snapshot.get(name)
    return metrics


def trial_trace_scope(trial):
    """Correlate recorded requests to their original trial and fixed local scores."""
    from copy import deepcopy
    runtime = trial.get('runtime', {})
    quality = trial.get('task_quality', {})
    return dict(trial_id=trial.get('source_trial_id', trial.get('trial_id')),
        model_id=runtime.get('model_id', MODEL_ID), revision=runtime.get('revision', MODEL_REVISION),
        config_hash=trial.get('config_hash'),
        diagnosis_required='diagnosis' in trial or 'diagnosis_trace_export' in trial,
        task_quality={key: deepcopy(quality[key]) for key in
                      ('version', 'floor', 'passed', 'per_prompt') if key in quality})


def agent_evidence(baseline, objective=None, constraints=None, *, prompts=()):
    from copy import deepcopy
    from .config import SUPPORTED_CHANGES
    from .trace_evidence import request_evidence
    requests = request_evidence(baseline, prompts)
    metrics = dict(baseline["reduced"])
    metrics.update(trace_failed_task_count=requests['failed_task_count'],
                   trace_measured_request_count=requests['measured_request_count'])
    snapshot = baseline.get("metrics", {}).get("after-measurement", {})
    metrics.update(mean_queue_ms=snapshot.get("mean_queue_ms"),
                   mean_ttft_ms=snapshot.get("mean_ttft_ms"),
                   preemptions=snapshot.get("preemptions"),
                   sampled_peak_memory_mib=baseline["runtime"].get("sampled_peak_memory_mib"))
    metrics.update(load_snapshot_metrics(baseline))
    model_id = baseline["runtime"].get("model_id", MODEL_ID)
    portable = baseline['runtime'].get('adapter') == 'explicit-single-host-v1'
    supported = SUPPORTED_CHANGES if model_id == MODEL_ID and not portable else {"max_num_batched_tokens": [2048]}
    return {"trial_id": "baseline", "model_id": model_id,
            "revision": baseline["runtime"].get("revision", MODEL_REVISION),
            "objective": (objective or Objective()).model_dump(),
            "constraints": constraints.model_dump() if constraints is not None else None,
            "quality_mode": "verified" if constraints is not None else "token-agreement",
            "task_quality": baseline.get("task_quality"),
            "request_evidence": requests,
            "workload": deepcopy(baseline.get("workload", {})),
            "trace_scope": [trial_trace_scope(baseline)],
            "configuration": baseline["runtime"]["configuration"],
            "metrics": metrics, "remaining_trials": 1, "supported_changes": supported,
            "baseline_self_check": token_agreement(baseline["quality"], baseline["self_check"]),
            "limitations": ["No measured in-flight KV peak; idle KV use is not pressure evidence.",
                            "concurrency_N_cumulative_snapshot_* fields are snapshots after that load, "
                            "cumulative since server startup and including warmup and earlier loads; "
                            "they are not measured-window means or counter deltas. Legacy unprefixed "
                            "mean_queue_ms, mean_ttft_ms, and preemptions have the same cumulative scope.",
                            "Token agreement does not establish task correctness.",
                            "Sampled peak memory includes runtime reservation, not just model weights.",
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
        if "search_trials" in self.report:
            return self.baselines + self.report["search_trials"]
        return self.baselines + ([self.report["candidate_trial"]] if "candidate_trial" in self.report else [])

    @property
    def rejected(self):
        return self.report.get("rejected", [])

    @property
    def weave_url(self):
        return self.report.get("weave_url")

    @property
    def frontier(self):
        if "search_trials" in self.report:
            from .investigation import search_frontier
            return search_frontier(self.report["baseline"], self.report["search_trials"],
                                   constraints=self.report.get("constraints"))
        return measured_frontier(self.report.get("baseline", {}), self.report.get("candidate_trial"),
                                 constraints=self.report.get("constraints"))

    def _save(self):
        self.report["returned_runtimes"] = [model.record for model in self.models]
        self.report["frontier_trial_ids"] = [trial["trial_id"] for trial in self.frontier]
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
             f"Objective: {report.get('objective', Objective().model_dump())}",
             f"Measured frontier: {report.get('frontier_trial_ids', [])}",
             ("Task scores use the supplied versioned evaluator; see each trial's gate and constraints."
              if report.get("evaluation") else
              "Task quality was not verified. The gate checks token agreement, not correct answers."),
             ("This bounded search is not a statistically established advantage over other search methods."
              if report.get('search') else "This is one comparison, not a statistically established speedup."), ""]
    entries = [(report.get("baseline"), "Baseline"), (report.get("candidate_trial"), "Candidate")]
    entries.extend((trial, trial['trial_id']) for trial in report.get('search_trials', []))
    for trial, label in entries:
        if trial:
            reduced = trial.get("reduced", {})
            lines.append(f"{label}: {trial['status']}; requests={reduced.get('request_count', 'unavailable')}; "
                         f"p95={reduced.get('p95_latency_ms', 'unavailable')} ms; "
                         f"throughput={reduced.get('output_tokens_per_second', 'unavailable')} output tokens/s; "
                         f"peak memory={trial.get('runtime', {}).get('sampled_peak_memory_mib', 'unavailable')} MiB; "
                         f"output tokens={reduced.get('output_tokens', 'unavailable')}; "
                         f"startup={trial.get('runtime', {}).get('startup_seconds', 'unavailable')} s.")
            for load in trial.get("loads", []):
                values = load.get("reduced", {})
                lines.append(f"  concurrency={load['concurrency']}; requests={values.get('request_count')}; "
                             f"p95={values.get('p95_latency_ms')} ms; "
                             f"throughput={values.get('output_tokens_per_second')} output tokens/s.")
    if any(report.get(key, {}).get("loads") for key in ("baseline", "candidate_trial")):
        lines.extend(["", "Selection latency is the worst per-load p95; percentiles are not pooled. "
                      "Aggregate throughput divides all output tokens by the sum of measured load durations."])
    gate = decision.get("candidate_quality")
    if gate:
        label = "Task score" if report.get("evaluation") else "Token agreement"
        lines.append(f"{label}: {gate['mean']:.4f}; required >= {gate['floor']}; pass={gate['passed']}.")
    if report.get("constraints"):
        lines.append(f"Hard limits: {report['constraints']}; failures: {decision.get('constraint_failures', {})}.")
    if report.get("search"):
        search = report["search"]
        cap = search['budget']['max_candidate_trials']
        trial_count = f"{search['trials_used']}/{cap}" if cap is not None else f"{search['trials_used']}; no total trial cap"
        lines.extend(["", f"Investigation trials: {trial_count}; "
                      f"stop: {search.get('stop_reason', 'running')}.",
                      "Each round records proposals, arbitration, measurements, gates, and prediction review.",
                      "This investigation is not proof of a search advantage."])
    lines.extend(["", f"Workload: {report.get('workload')}",
                  f"Generation: {report.get('generation')}",
                  f"Record: {output_dir / 'result.json'}", ""])
    if report.get('search'):
        from .investigation_report import render_investigation
        lines.extend([render_investigation(report), ''])
    return "\n".join(lines)


def optimize(*, models, prompts, output_dir=None, candidate=None, agent=None, provider_check=None,
             objective=None, evaluation=None, evaluation_version=None, constraints=None,
             workload=None, baseline_configuration=None, budget=None, investigation_space=None,
             automatic_space=False, swarm=False, trace_reader=None, _runtime_factory=None):
    """One candidate, or an opt-in bounded agent investigation; no joint placement.

    Uses at most 32 supplied prompts, declared loads, up to 16 warm-ups, three
    measured passes, and separate quality passes. The caller owns result.close().
    automatic_space derives normal-mode controls after measuring the reference;
    it never expands an explicit investigation space and defaults to disabled.
    """
    from .swarm import validate_swarm_options
    validate_swarm_options(swarm, budget, agent, trace_reader)
    if type(automatic_space) is not bool:
        raise ValueError('automatic_space must be a boolean')
    if automatic_space and (investigation_space is not None or candidate is not None
                            or budget is None or agent is None):
        raise ValueError('Automatic space requires an agent investigation budget and no explicit space or fixed candidate')
    objective = Objective() if objective is None else Objective.model_validate(objective)
    workload = Workload() if workload is None else Workload.model_validate(workload)
    budget = Budget.model_validate(budget) if budget is not None else None
    if budget is not None and (agent is None or candidate is not None):
        raise ValueError("An investigation budget requires an agent and no fixed candidate")
    if investigation_space is not None and budget is None:
        raise ValueError("An explicit investigation space requires an agent investigation budget")
    if evaluation is None:
        if constraints is not None or evaluation_version is not None:
            raise ValueError("Verified constraints require an evaluation callable and its version")
    else:
        if not callable(evaluation) or not isinstance(evaluation_version, str) or not evaluation_version.strip():
            raise ValueError("Supply evaluation(prompt, output) and a nonempty evaluation_version")
        if isinstance(constraints, list):
            if len(constraints) != 1:
                raise ValueError("This single-model path requires exactly one Constraints record")
            constraints = constraints[0]
        if constraints is None:
            raise ValueError("Verified mode requires an explicit quality floor in Constraints")
        constraints = Constraints.model_validate(constraints)
    if _runtime_factory is not None:
        from .portable_runtime import PortableRuntimeFactory
        if not isinstance(_runtime_factory, PortableRuntimeFactory):
            raise ValueError('An explicit run requires a validated PortableRuntimeFactory')
        if models != [_runtime_factory.model.model_id]:
            raise ValueError('Model list differs from the explicit pinned model')
        if evaluation is None:
            raise ValueError('Explicit hardware optimization requires versioned task requirements')
    elif models not in ([MODEL_ID], [LARGE_MODEL_ID]):
        raise ValueError("Supply one supported pinned Qwen model")
    runtime_factory = _runtime_factory or SeraModel
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 32:
        raise ValueError("Supply 1 to 32 prompts; inputs are never silently dropped")
    for prompt in prompts:
        if not isinstance(prompt, (str, list)) or not prompt:
            raise ValueError("Each prompt must be nonempty text or chat messages")
    model_id = models[0]
    revision = (_runtime_factory.model.revision if _runtime_factory is not None else
                LARGE_MODEL_REVISION if model_id == LARGE_MODEL_ID else MODEL_REVISION)
    if _runtime_factory is None and model_id == LARGE_MODEL_ID and baseline_configuration is None:
        from .fit import optimize_fit
        if candidate is not None:
            raise ValueError("The fit-first path selects its candidate from the validated memory plans")
        if max(workload.concurrency) > RuntimeConfig().max_num_seqs:
            raise ValueError("Workload concurrency exceeds the reference sequence limit")
        if investigation_space is not None:
            investigation_space = resolve_investigation_space(investigation_space,
                baseline=RuntimeConfig(quantization="fp8_per_tensor"),
                model_id=model_id, workload=workload)
        return optimize_fit(prompts=prompts, output_dir=output_dir, objective=objective,
                            evaluation=evaluation, evaluation_version=evaluation_version,
                            constraints=constraints, agent=agent, provider_check=provider_check,
                            workload=workload, budget=budget, investigation_space=investigation_space,
                            automatic_space=automatic_space, swarm=swarm, trace_reader=trace_reader)
    baseline_config = (_runtime_factory.baseline_configuration(baseline_configuration) if _runtime_factory is not None else
                       RuntimeConfig() if baseline_configuration is None else RuntimeConfig.model_validate(baseline_configuration))
    if _runtime_factory is None and baseline_configuration is not None:
        if model_id != LARGE_MODEL_ID or baseline_config != RuntimeConfig(quantization="fp8_per_tensor"):
            raise ValueError("An explicit reference is supported only for the proven Qwen72B FP8 weight plan")
        if evaluation is None:
            raise ValueError("The Qwen72B comparison requires verified task requirements")
    if max(workload.concurrency) > baseline_config.max_num_seqs:
        raise ValueError("Workload concurrency exceeds the reference sequence limit")
    if investigation_space is not None:
        investigation_space = resolve_investigation_space(investigation_space, baseline=baseline_config,
                                                          model_id=model_id, workload=workload)
        if _runtime_factory is not None and investigation_space['supported_changes'].get('kv_cache_dtype'):
            raise ValueError('Portable optimization supports BF16 weights and KV only')
    provider_validation = None
    if agent is not None:
        from .provider_check import require_provider_check
        if candidate is not None or provider_check is None:
            raise ValueError("Agent mode requires provider_check and no fixed candidate")
        provider_validation = require_provider_check(provider_check, agent)
        history_start = len(agent.history)
    else:
        batch_default = _runtime_factory is not None or model_id == LARGE_MODEL_ID
        candidate = validate_candidate(candidate if candidate is not None else Candidate(
            name="batch-2048" if batch_default else "kv-fp8",
            reason="Test one predeclared supported change against the reference",
            config=RuntimeConfig.model_validate(baseline_config.model_dump() | (
                {"max_num_batched_tokens": 2048} if batch_default else {"kv_cache_dtype": "fp8"}))),
            baseline=baseline_config)
        if _runtime_factory is not None:
            _runtime_factory.validate_configuration(candidate.config)
        if model_id == LARGE_MODEL_ID and candidate.config.kv_cache_dtype != "auto":
            raise ValueError("Combined FP8 weights and FP8 KV are not enabled for Qwen72B")
    folder = Path(output_dir or Path("sera-runs") / uuid.uuid4().hex).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": "sera-single-model-v1", "status": "running",
              "created_at": datetime.now(timezone.utc).isoformat(),
              "mode": "agent-guided" if agent is not None else "fixed-candidate",
              "model_id": model_id, "model_revision": revision,
              "baseline_name": ('sera-explicit-bf16-reference-v1' if _runtime_factory is not None else
                                "sera-fp8-weight-reference-v1" if model_id == LARGE_MODEL_ID else BASELINE_NAME),
              "baseline_configuration": baseline_config.model_dump(),
              "candidate": candidate.model_dump() if candidate else None,
              "prompts": prompts, "workload_hash": content_hash(prompts),
              "generation": {**GENERATION, "enable_thinking": False},
              "workload": {"prompt_count": len(prompts), "concurrency": workload.concurrency,
                           "warmup_requests_per_load": min(len(prompts), 16),
                           "measured_requests_per_load": 3 * len(prompts), "quality_requests": len(prompts),
                           "quality_concurrency": 1, "latency_reduction": "worst-per-load-percentile",
                           "throughput_reduction": "total-tokens-over-total-measured-window-seconds"},
              "task_quality_verified": False,
              "constraints": constraints.model_dump() if constraints is not None else None,
              "evaluation": {"version": evaluation_version, "signature": "evaluation(prompt, output) -> score in [0, 1]"}
                            if evaluation is not None else None,
              "objective": objective.model_dump(),
              "agent_selection": "enabled" if agent is not None else "not-enabled",
              "provider_validation": provider_validation,
              "investigation_space": investigation_space,
              "automatic_space": automatic_space,
              "swarm_enabled": swarm,
              "limits": ["single model", "one candidate", "non-streaming requests",
                         "TTFT and queue percentiles unavailable",
                         "Quality is limited to the supplied evaluator and prompts" if evaluation else "no task-correctness claim"],
              "rejected": []}
    if _runtime_factory is not None:
        report['execution'] = dict(adapter='explicit-single-host-v1',
            model_descriptor=_runtime_factory.model.model_dump(),
            hardware_assignment=_runtime_factory.hardware.model_dump(),
            tensor_parallel_selection='caller-fixed', memory_fit='requires-runtime-startup',
            precision_support='BF16-only', live_validation_scope='this run only')
    result = SeraResult(models=[], report=report, output_dir=folder)
    active = None
    result._save()
    try:
        active = runtime_factory(artifact_dir=folder / "baseline", model_id=model_id,
                           revision=revision, configuration=baseline_config)
        active.start()
        report["baseline"] = collect_trial(active, prompts, "baseline", baseline=True, workload=workload)
        if evaluation is not None:
            report["baseline"]["task_quality"] = evaluate_quality(report["baseline"], prompts, evaluation,
                version=evaluation_version, floor=constraints.quality_floor)
        result._save()
        baseline = report["baseline"]
        if evaluation is not None and not baseline["task_quality"]["valid_outputs"]:
            raise RuntimeError("Baseline task evaluation failed; inspect saved per-prompt errors")
        stable = token_agreement(baseline["quality"], baseline["self_check"])["passed"]
        can_compare = evaluation is not None or stable
        trial = None
        if budget is not None:
            from .investigation import investigate
            # The controller owns all later runtimes, including cleanup and the live return.
            investigation_runner, active = active, None
            return investigate(result=result, active=investigation_runner, agent=agent,
                history_start=history_start, budget=budget, objective=objective, constraints=constraints,
                evaluation=evaluation, evaluation_version=evaluation_version, workload=workload,
                swarm=swarm, trace_reader=trace_reader, runtime_factory=runtime_factory)
        if agent is not None and baseline["status"] == "collected" and can_compare:
            from .agent import validate_proposal
            evidence = agent_evidence(baseline, objective, constraints, prompts=prompts)
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
        if baseline["status"] == "collected" and can_compare and candidate is not None:
            active.close()
            result._save()
            active = runtime_factory(artifact_dir=folder / "candidate", configuration=candidate.config,
                               model_id=model_id, revision=revision)
            try:
                active.start()
                trial = collect_trial(active, prompts, "candidate", workload=workload)
            except CleanupError:
                raise
            except Exception as error:
                trial = {"trial_id": "candidate", "status": "startup-failed",
                         "error": f"{type(error).__name__}: {error}", "runtime": active.record}
            report["candidate_trial"] = trial
            if evaluation is not None:
                trial["task_quality"] = evaluate_quality(trial, prompts, evaluation,
                    version=evaluation_version, floor=constraints.quality_floor)
            result._save()
        report["decision"] = select_candidate(baseline, trial, objective=objective, constraints=constraints)
        if agent is not None and trial is None and stable and report["decision"]["selected"] == "baseline":
            report["decision"]["reason"] = ("agent-kept-baseline" if report.get("proposal_validation") == "passed"
                                             else "agent-proposal-rejected")
        if agent is not None and report.get("proposal") and report["decision"]["selected"] is not None:
            feedback = {"proposal": report["proposal"], "decision": report["decision"],
                        "objective": objective.model_dump(),
                        "constraints": constraints.model_dump() if constraints is not None else None,
                        "quality_mode": "verified" if evaluation is not None else "token-agreement",
                        "candidate_tested": trial is not None,
                        "baseline_metrics": baseline.get("reduced"),
                        "candidate_metrics": trial.get("reduced") if trial else None,
                        "candidate_status": trial.get("status") if trial else "not-tested",
                        "frontier_trial_ids": [item["trial_id"] for item in result.frontier],
                        "eligible_trial_ids": [report["decision"]["selected"]]}
            report["agent_feedback"] = feedback
            try:
                final = agent.review(feedback)
                if final is None or final.selected_trial_id not in feedback["eligible_trial_ids"]:
                    raise ValueError("Final agent response did not respect the deterministic selection")
                if (final.prediction_outcome == "not-tested") != (trial is None):
                    raise ValueError("Final agent response misstated whether the candidate was tested")
                report["agent_final"] = final.model_dump()
            except Exception as error:
                report["agent_final_error"] = f"{type(error).__name__}: {error}"
            report["agent_calls"] = agent.history[history_start:]
        result._save()
        if report["decision"]["selected"] is None:
            active.close()
            report.update(status="no-safe-configuration", returned_runner_closed=True)
            result._save()
            return result
        if report["decision"]["selected"] == "baseline" and trial is not None:
            active.close()
            active = runtime_factory(artifact_dir=folder / "returned-baseline", configuration=baseline_config,
                               model_id=model_id, revision=revision)
            active.start()
        if baseline["status"] != "collected":
            raise RuntimeError("Baseline measurement failed; see the saved trial before retrying")
        active._require_ready()
        result.models = [active]
        report["task_quality_verified"] = evaluation is not None
        report.update(status="ready", returned_runner_closed=False)
        result._save()
        return result
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        result.models = []
        try:
            if active is not None:
                active.close()
        except BaseException as cleanup_error:
            report.update(cleanup_error=type(cleanup_error).__name__, returned_runner_closed=False)
            raise
        finally:
            try:
                result._save()
            except BaseException as save_error:
                report['save_error'] = type(save_error).__name__
        raise
