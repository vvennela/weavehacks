"""Fit-first loading for the pinned 72B model; estimates never count as measurements."""

from datetime import datetime, timezone
from copy import deepcopy
from pathlib import Path
import uuid

from .config import LARGE_MODEL_ID, LARGE_MODEL_REVISION, RuntimeConfig, Workload
from .agent import ArbiterDecision
from .diagnosis import export_trial_diagnosis, trial_diagnosis
from .memory import fits_memory
from .measurement import collect_trial, select_candidate
from .quality import evaluate_quality
from .runtime import CleanupError, GENERATION, SeraModel, gpu_snapshot
from .storage import content_hash


def recommend_fit_plan(agent, evidence):
    """A quantization advisor proposes a legal plan; the arbiter decides to test it."""
    supplied = evidence | {"specialist_role": "quantization"}
    record = {"role": "quantization", "evidence": supplied, "status": "rejected"}
    try:
        response = agent.request("arbiter", supplied,
            "Act as the quantization specialist, not the final arbiter. Recommend at most one "
            "legal_plan_ids entry using the supplied weight, KV, workspace and GPU estimates. "
            "Explain the precision and memory trade-off. Empty means abstain. No latency or "
            "task quality has been measured: propose deployment feasibility, not a speedup. "
            "The independent arbiter and deterministic gates will decide whether to use it.")
        record["response"] = response.model_dump() if response is not None else None
        response = ArbiterDecision.model_validate(record["response"])
        if any(plan_id not in evidence["legal_plan_ids"] for plan_id in response.ranked_proposal_ids):
            raise ValueError("Quantization specialist named an illegal fit plan")
        record["status"] = "accepted" if response.ranked_proposal_ids else "abstained"
        return record, response.ranked_proposal_ids
    except Exception as error:
        record["error"] = type(error).__name__
        return record, []


def continue_fit_investigation(result, active, *, agent, history_start, budget,
                              investigation_space, objective, constraints,
                              evaluation, evaluation_version, workload, swarm=False, trace_reader=None):
    """Promote a measured, eligible deployment to the search reference without reloading."""
    report = result.report
    try:
        from .investigation import investigate

        keys = ("candidate", "candidate_trial", "planning_specialist", "planning_decision",
                "agent_feedback", "agent_final", "agent_final_error", "decision")
        # Prepare the handoff before changing the fit report. Historical deployment
        # evidence must not share nested mutable objects with the new reference.
        deployment = {"infeasible_baseline": deepcopy(report["baseline"])}
        deployment.update({key: deepcopy(report[key]) for key in keys if key in report})
        reference = dict(deepcopy(deployment["candidate_trial"]), trial_id="baseline",
                         source_trial_id=deployment["candidate_trial"]["trial_id"])
        configuration = active.configuration.model_dump()
        report.update(deployment=deployment, baseline=reference,
            baseline_name="sera-fp8-weight-reference-v1",
            baseline_configuration=configuration, investigation_space=investigation_space,
            agent_selection="enabled", status="running")
        for key in keys:
            report.pop(key, None)
    except BaseException:
        # optimize_fit already transferred ownership here, but investigate has not
        # received it yet. The transfer preparation must close its own runner.
        result.models = []
        try:
            active.close()
            report['returned_runner_closed'] = True
        except BaseException as cleanup_error:
            report.update(cleanup_error=type(cleanup_error).__name__, returned_runner_closed=False)
            raise
        raise
    # Ownership moves directly to investigate, whose exception path closes it.
    result.models = []
    return investigate(result=result, active=active, agent=agent,
        history_start=history_start, budget=budget, initial_trials_used=1,
        objective=objective, constraints=constraints, evaluation=evaluation,
        evaluation_version=evaluation_version, workload=workload, swarm=swarm, trace_reader=trace_reader)


def plan_fit(*, gpu_memory_mib, workspace_bytes=4 * 1024**3):
    if type(gpu_memory_mib) is not int or gpu_memory_mib <= 0:
        raise ValueError("GPU memory must be a positive integer in MiB")
    if type(workspace_bytes) is not int or workspace_bytes < 0:
        raise ValueError("Workspace must be nonnegative integer bytes")
    # Pinned Qwen2.5-72B config: 80 layers, 8 KV heads, 128 head dimension.
    parameters = 72706203648
    unquantized = 2 * 152064 * 8192 + 2 * 80 * 8192 + 8192 + 80 * (8192 + 2 * 1024)
    config = RuntimeConfig()
    physical = gpu_memory_mib * 1024**2
    budget = int(physical * config.gpu_memory_utilization)
    kv_bytes = 2 * 80 * 8 * 128 * config.max_model_len * config.max_num_seqs * 2
    plans = []
    for name, quantization, weights in [
        ("baseline", None, parameters * 2),
        ("weight-fp8", "fp8_per_tensor", parameters + unquantized + 16 * 1024**2),
    ]:
        configuration = RuntimeConfig(quantization=quantization)
        required = weights + kv_bytes + workspace_bytes
        plans.append({"plan_id": name, "configuration": configuration.model_dump(),
                      "weights_bytes": weights, "kv_bytes": kv_bytes,
                      "workspace_bytes": workspace_bytes, "estimated_peak_bytes": required,
                      "estimated_fit": fits_memory(required_bytes=required, budget_bytes=budget, reserve_bytes=0),
                      "measurement_status": "not-measured"})
    return {"version": "qwen72-fit-v1", "model_id": LARGE_MODEL_ID, "revision": LARGE_MODEL_REVISION,
            "physical_bytes": physical, "service_budget_bytes": budget,
            "physical_reserve_bytes": physical - budget, "download_bytes": parameters * 2,
            "plans": plans,
            "assumptions": ["Full-context BF16 KV storage for all eight configured sequences.",
                            "FP8 estimate retains embeddings, output head, norms and biases at BF16.",
                            "16 MiB allowance for quantization metadata; workspace includes conversion scratch.",
                            "Workspace is an explicit estimate, not a measured guarantee.",
                            "Original BF16 files are downloaded; linear weights are quantized during loading."]}


def fit_review_evidence(plan, trial, decision):
    """Keep deployment feasibility separate from an unavailable BF16 comparison."""
    return {"decision": decision, "fit_plan": plan,
            "prediction": {"kind": "deployment-feasibility",
                           "statement": "Online FP8 weights let the requested model run on this GPU and meet the supplied task and resource constraints."},
            "baseline_measured": False, "speedup_claim_allowed": False,
            "candidate_tested": True, "candidate_status": trial["status"],
            "candidate_metrics": trial.get("reduced"),
            "candidate_task_quality": trial.get("task_quality"),
            "candidate_peak_memory_mib": trial.get("runtime", {}).get("sampled_peak_memory_mib"),
            "eligible_trial_ids": [decision["selected"] or "no-safe-configuration"]}


def optimize_fit(*, prompts, output_dir, objective, evaluation, evaluation_version,
                 constraints, agent, provider_check, workload=None, budget=None,
                 investigation_space=None, automatic_space=False, swarm=False, trace_reader=None):
    from .pipeline import SeraResult
    from .provider_check import require_provider_check
    from .swarm import validate_swarm_options
    validate_swarm_options(swarm, budget, agent, trace_reader)
    workload = Workload() if workload is None else Workload.model_validate(workload)

    if evaluation is None or constraints is None:
        raise ValueError("Fit-first loading requires a versioned task evaluator and explicit quality floor")
    provider_validation = None
    history_start = len(agent.history) if agent is not None else 0
    if agent is not None:
        if provider_check is None:
            raise ValueError("Fit-first agent selection requires a matching provider check")
        provider_validation = require_provider_check(provider_check, agent)
    gpu = gpu_snapshot()
    if gpu["used_mib"] > 128 or gpu["compute_capability"] != "12.0":
        raise ValueError("Fit-first trial requires the idle supplied sm_120 GPU")
    plan = plan_fit(gpu_memory_mib=gpu["total_mib"])
    if plan["plans"][0]["estimated_fit"]:
        raise ValueError("This fit-first path is for a BF16 baseline that exceeds the GPU budget")
    folder = Path(output_dir or Path("sera-runs") / uuid.uuid4().hex).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": "sera-fit-first-v1", "status": "planning",
              "created_at": datetime.now(timezone.utc).isoformat(), "mode": "fit-first",
              "model_id": LARGE_MODEL_ID, "model_revision": LARGE_MODEL_REVISION,
              "prompts": prompts, "workload_hash": content_hash(prompts),
              "generation": {**GENERATION, "enable_thinking": False},
              "workload": {"prompt_count": len(prompts), "concurrency": workload.concurrency,
                           "warmup_requests_per_load": min(len(prompts), 16),
                           "measured_requests_per_load": 3 * len(prompts), "quality_requests": len(prompts)},
              "objective": objective.model_dump(), "constraints": constraints.model_dump(),
              "evaluation": {"version": evaluation_version}, "task_quality_verified": False,
              "provider_validation": provider_validation, "fit_plan": plan, "gpu": gpu,
              "automatic_space": automatic_space,
              "swarm_enabled": swarm,
              "baseline": {"trial_id": "baseline", "status": "infeasible",
                           "reason": "Estimated BF16 runtime exceeds the service memory budget",
                           "fit_estimate": plan["plans"][0]},
              "limits": ["one model", "one fit candidate", "no measured BF16 baseline",
                         "no speedup or search superiority claim", "no multi-GPU placement"],
              "rejected": [], "returned_runner_closed": True}
    result = SeraResult(models=[], report=report, output_dir=folder)
    active = None
    result._save()
    try:
        feasible = [item for item in plan["plans"] if item["estimated_fit"]]
        chosen = feasible[0] if feasible else None
        if agent is not None and feasible:
            evidence = {"fit_plan": plan, "objective": objective.model_dump(),
                        "constraints": constraints.model_dump(),
                        "legal_plan_ids": [p["plan_id"] for p in feasible], "remaining_trials": 1}
            if budget is not None:
                specialist, recommended = recommend_fit_plan(agent, evidence)
                report["planning_specialist"] = specialist
                evidence = evidence | {"legal_plan_ids": recommended,
                                       "specialist_recommendation": specialist.get("response")}
                report["agent_calls"] = agent.history[history_start:]
                result._save()
            chosen = None
            report["planning_decision"] = None
            if evidence["legal_plan_ids"]:
                try:
                    ranking = agent.request("arbiter", evidence,
                        "Rank at most one plan from legal_plan_ids for a real trial. These are memory estimates, "
                        "not latency or quality measurements. Explain the fit trade-off and why a trial is useful. "
                        "Do not rank an infeasible plan or claim that quality has passed. The prediction is deployment "
                        "feasibility, not a throughput gain: no BF16 baseline will run, so speedup cannot be measured. "
                        "An empty ranking declines the trial.")
                    report["planning_decision"] = ranking.model_dump() if ranking is not None else None
                    ranking = ArbiterDecision.model_validate(report["planning_decision"])
                    if any(plan_id not in evidence["legal_plan_ids"] for plan_id in ranking.ranked_proposal_ids):
                        raise ValueError("Arbiter named an illegal fit plan")
                    chosen = next((p for p in feasible if ranking.ranked_proposal_ids == [p["plan_id"]]), None)
                except Exception as error:
                    report["planning_error"] = type(error).__name__
            report["agent_calls"] = agent.history[history_start:]
            if chosen is None:
                report["rejected"].append({"reason": "Agent declined or returned an invalid fit plan"})
        result._save()
        if chosen is not None:
            configuration = RuntimeConfig.model_validate(chosen["configuration"])
            report["candidate"] = {"name": chosen["plan_id"], "config": configuration.model_dump(),
                                   "reason": "Test whether online weight quantization makes the requested model feasible"}
            report["status"] = "running"
            result._save()
            stage = 'constructor'
            trial = dict(trial_id='candidate', status='starting', config_hash=configuration.config_hash,
                         runtime=dict(model_id=LARGE_MODEL_ID, revision=LARGE_MODEL_REVISION,
                                      configuration=configuration.model_dump()))
            try:
                active = SeraModel(artifact_dir=folder / "candidate", model_id=LARGE_MODEL_ID,
                                   revision=LARGE_MODEL_REVISION, configuration=configuration)
                trial['runtime'] = active.record
                stage = 'startup'
                active.start()
                stage = 'measurement'
                trial = collect_trial(active, prompts, "candidate", workload=workload)
            except CleanupError:
                raise
            except Exception as failure:
                trial.update(status='measurement-failed' if stage == 'measurement' else 'startup-failed',
                             failure_stage=stage, error=type(failure).__name__)
            trial["task_quality"] = evaluate_quality(trial, prompts, evaluation,
                version=evaluation_version, floor=constraints.quality_floor)
            report["candidate_trial"] = trial
        report["decision"] = select_candidate(report["baseline"], report.get("candidate_trial"),
                                               objective=objective, constraints=constraints)
        if report.get('candidate_trial'):
            trial = report['candidate_trial']
            trial['decision'] = deepcopy(report['decision'])
            trial['diagnosis'] = trial_diagnosis(report['baseline'], trial, report['decision'])
            result._save()
            export_trial_diagnosis(trial)
            result._save()
        if agent is not None and chosen is not None:
            selected = report["decision"]["selected"] or "no-safe-configuration"
            feedback = fit_review_evidence(chosen, report["candidate_trial"], report["decision"])
            feedback['diagnosis'] = deepcopy(report['candidate_trial']['diagnosis'])
            report["agent_feedback"] = feedback
            try:
                final = agent.review(feedback)
                if final is None or final.selected_trial_id != selected or final.prediction_outcome == "not-tested":
                    raise ValueError("Agent final response did not respect measured selection")
                report["agent_final"] = final.model_dump()
            except Exception as failure:
                report["agent_final_error"] = f"{type(failure).__name__}: {failure}"
            report["agent_calls"] = agent.history[history_start:]
        if report["decision"]["selected"] == "candidate":
            active._require_ready()
            result.models = [active]
            report.update(status="ready", returned_runner_closed=False, task_quality_verified=True)
        else:
            if active is not None:
                active.close()
            report["status"] = "no-safe-configuration"
        result._save()
        if budget is not None and result.models:
            runner, active = active, None
            return continue_fit_investigation(result, runner, agent=agent,
                history_start=history_start, budget=budget, investigation_space=investigation_space,
                objective=objective, constraints=constraints, evaluation=evaluation,
                evaluation_version=evaluation_version, workload=workload, swarm=swarm, trace_reader=trace_reader)
        return result
    except BaseException as failure:
        report.update(status="failed", error=f"{type(failure).__name__}: {failure}")
        result.models = []
        try:
            if active is not None:
                active.close()
                report["returned_runner_closed"] = True
        except BaseException as cleanup_error:
            report.update(cleanup_error=type(cleanup_error).__name__, returned_runner_closed=False)
            raise
        finally:
            try:
                result._save()
            except BaseException as save_error:
                report["save_error"] = type(save_error).__name__
        raise
