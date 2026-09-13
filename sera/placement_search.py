"""Measured frontier selection for caller-supplied, frozen two-model plans."""

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import math
from pathlib import Path

from .agent import ArbiterDecision
from .config import Budget, Objective
from .placement import PlacementMemoryEstimate, place
from .placement_config import validate_memory_accounting, validate_placement_plan
from .placement_reference import bind_placement_reference
from .provider_check import require_provider_check
from .runtime import CleanupError
from .storage import content_hash, save_json


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _measured_objectives(report):
    joint = report.get('joint', {})
    if (report.get('decision', {}).get('outcome') != 'safe-placement'
            or not joint.get('gates') or not all(gate.get('passed') is True for gate in joint['gates'].values())):
        return None
    trials = list(joint.get('trials', {}).values())
    latencies = [trial.get('reduced', {}).get('p95_latency_ms') for trial in trials]
    memory = report.get('shared_runtime', {}).get('sampled_peak_memory_mib')
    if len(trials) != 2 or not all(_positive(value) for value in latencies) or not _positive(memory):
        return None
    elapsed = 0.
    for load in joint.get('overlap', []):
        windows = list(load['windows'].values())
        elapsed += max(window['ended'] for window in windows) - min(window['started'] for window in windows)
    tokens = sum(trial.get('reduced', {}).get('output_tokens', 0) for trial in trials)
    return dict(latency=max(latencies), memory=memory,
                throughput=tokens/elapsed if _positive(elapsed) and _positive(tokens) else None)


def _progress(before, after, objective):
    if before is None:
        return True, True, None
    old, new = before[objective.priority], after[objective.priority]
    gain = (new-old)/old if objective.priority == 'throughput' else (old-new)/old
    better = gain > 0 or (new == old and after['memory'] < before['memory'])
    qualifying = gain > 0 and (gain >= objective.min_improvement_fraction
                              or math.isclose(gain, objective.min_improvement_fraction, rel_tol=1e-12))
    return better, qualifying, gain


@dataclass
class PlacementSearchResult:
    report: dict
    output_dir: Path
    placement: object = None
    _trace_on_close: object = field(default=None, repr=False)

    @property
    def models(self):
        return self.placement.models if self.placement is not None else []

    @property
    def weave_url(self):
        return self.report.get('weave_url')

    def _save(self):
        if self.placement is not None:
            self.report['returned_placement'] = self.placement.report
        save_json(self.output_dir/'result.json', self.report)
        lines = ['# Sera automatic two-model placement', '',
            f"Status: {self.report['status']}", f"Stop reason: {self.report.get('stop_reason', 'running')}",
            f"Selected plan: {self.report.get('selected_plan_id') or 'none'}",
            f"Objective: {self.report['objective']['priority']}",
            f"Joint search trials: {len(self.report['trials'])}",
            f"Joint restoration trials: {1 if 'restoration' in self.report else 0}",
            'Quality and latency limits remain mandatory for both models.',
            'Latency objective is the worst service p95. Memory is sampled device peak.',
            'Throughput is both services\' output tokens divided by the sum of shared load-window durations.',
            ('Capacity evidence: measured quantized placement versus an estimated BF16 fit rejection.'
             if self.report.get('quantization_enabled_placement') else 'Quantization-enabled placement is not established.'),
            'No measured memory-savings claim without a measured matching BF16 pair; no global-optimality claim.',
            'Provider certificate proves existing schema formatting, not placement reasoning quality.']
        if self.report.get('memory_accounting') == 'total-device':
            lines.append('Total-device accounting: service allocations are configured vLLM budgets, not separately verified hard caps.')
        if self.report.get('weave_url'):
            lines.append(f"Weave: {self.report['weave_url']}")
        (self.output_dir/'report.md').write_text('\n'.join(lines)+'\n')

    def close(self):
        try:
            if self.placement is not None:
                self.placement.close()
            self.report.update(status='closed', returned_runner_closed=True)
        except BaseException as error:
            self.report.update(status='cleanup-failed', returned_runner_closed=False,
                               cleanup_error=type(error).__name__)
            raise
        finally:
            if self._trace_on_close is not None:
                self._trace_on_close(self)
            self._save()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _plan_evidence(plan, bound):
    return dict(proposal_id=plan.plan_hash, plan=plan.model_dump(),
        reference=bound['provenance'], isolated={model:dict(
            config_hash=trial['config_hash'], reduced=trial['reduced'],
            sampled_peak_memory_mib=trial['runtime']['sampled_peak_memory_mib'],
            task_quality=trial['task_quality'], measured_task_quality=trial['measured_task_quality'])
            for model,trial in bound['isolated'].items()},
        joint_measurement_status='not-tested', contention_cause='not-established')


def optimize_placement(*, plans, workloads, memory_estimates, isolated_references,
                       agent, provider_check, output_dir, objective=None, budget=None, weave_project=None,
                       memory_accounting='per-service'):
    """Choose and test measured eligible plans until plateau plus confirmation.

    No allocation or user requirement is generated here. Each plan must have a
    bound isolated reference, normally made with measure_placement_references.
    A supplied finite menu can end before a confirmation when no legal plan
    remains. Restoring an earlier winner is a separate, fully gated joint run.
    """
    memory_accounting = validate_memory_accounting(memory_accounting)
    if weave_project is not None:
        if not isinstance(weave_project, str) or not weave_project.strip():
            raise ValueError('weave_project must be a nonempty explicit project')
        from .placement_search_tracing import traced_placement_search
        arguments = dict(plans=plans, workloads=workloads, memory_estimates=memory_estimates,
            isolated_references=isolated_references, agent=agent, provider_check=provider_check,
            output_dir=output_dir, objective=objective, budget=budget, memory_accounting=memory_accounting)
        return traced_placement_search(_optimize_placement, arguments, weave_project)
    return _optimize_placement(plans=plans, workloads=workloads, memory_estimates=memory_estimates,
        isolated_references=isolated_references, agent=agent, provider_check=provider_check,
        output_dir=output_dir, objective=objective, budget=budget, memory_accounting=memory_accounting)


def _optimize_placement(*, plans, workloads, memory_estimates, isolated_references,
                       agent, provider_check, output_dir, objective=None, budget=None, _observe=None,
                       memory_accounting='per-service'):
    memory_accounting = validate_memory_accounting(memory_accounting)
    if not isinstance(plans, list) or not plans:
        raise ValueError('Supply at least one explicit placement plan')
    checked = [validate_placement_plan(plan) for plan in plans]
    by_id = {plan.plan_hash:plan for plan in checked}
    if len(by_id) != len(checked):
        raise ValueError('Duplicate placement plans are not independent candidates')
    if set(memory_estimates) != set(by_id) or set(isolated_references) != set(by_id):
        raise ValueError('Supply memory estimates and isolated references for exactly these plan hashes')
    first = checked[0]
    contracts = {service.model_id:service.constraints for service in first.services}
    for plan in checked:
        if (plan.physical_gpu_bytes != first.physical_gpu_bytes or plan.declared_budget_bytes != first.declared_budget_bytes
                or {service.model_id:service.constraints for service in plan.services} != contracts):
            raise ValueError('All compared plans must preserve physical/declared capacity and per-model requirements')
    if set(workloads) != set(contracts):
        raise ValueError('Supply each requested model\'s workload')
    profiles = {model:profile.validated() for model,profile in workloads.items()}
    objective = Objective() if objective is None else Objective.model_validate(objective)
    budget = Budget(max_candidate_trials=None) if budget is None else Budget.model_validate(budget)
    certificate = require_provider_check(provider_check, agent)
    estimates = {}
    for plan_id, plan in by_id.items():
        if set(memory_estimates[plan_id]) != set(contracts):
            raise ValueError('Each plan requires per-model memory components')
        estimates[plan_id] = {model:PlacementMemoryEstimate.model_validate(
            value.model_dump() if isinstance(value, PlacementMemoryEstimate) else value)
            for model,value in memory_estimates[plan_id].items()}
    folder = Path(output_dir).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    report = dict(schema_version='sera-placement-search-v1', status='running',
        memory_accounting=memory_accounting,
        objective=objective.model_dump(), budget=budget.model_dump(),
        plan_ids=list(by_id), plans={key:plan.model_dump() for key,plan in by_id.items()},
        memory_estimates={plan_id:{model:value.model_dump() for model,value in services.items()}
                          for plan_id,services in estimates.items()},
        workload_hash=content_hash({model:profile.manifest() for model,profile in profiles.items()}),
        rejected=[], references={}, rounds=[], trials=[], selected_plan_id=None,
        returned_runner_closed=True, no_progress_rounds=0,
        provider=dict(model=agent.model, project=agent.project, provider=getattr(agent, 'provider', 'wandb'),
                      certificate_schema_hash=certificate.get('schema_hash'),
                      certificate_scope='existing typed schema format; placement semantics are locally gated'),
        quantization_enabled_placement=False)
    result = PlacementSearchResult(report, folder)
    if _observe is not None:
        _observe(result)
    result._save()
    eligible = {}
    frozen_references = {}
    (folder/'references').mkdir()
    for plan_id, plan in by_id.items():
        try:
            fit = {service.model_id:dict(required_bytes=estimates[plan_id][service.model_id].total_bytes,
                allocation_bytes=service.allocation_bytes, components=estimates[plan_id][service.model_id].model_dump(),
                fits=estimates[plan_id][service.model_id].total_bytes <= service.allocation_bytes) for service in plan.services}
            if not all(row['fits'] for row in fit.values()):
                report['rejected'].append(dict(plan_id=plan_id, plan=plan.model_dump(),
                    reason='estimated-memory-does-not-fit', fit_check=fit,
                    measurement_status='not-measured', estimate_source='caller-supplied-component-estimates'))
                continue
            bound = bind_placement_reference(isolated_references[plan_id], plan, profiles)
            raw = Path(isolated_references[plan_id]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != bound['provenance']['sha256']:
                raise ValueError('Isolated reference changed during validation')
            frozen = folder/'references'/f'{plan_id}.json'
            frozen.write_bytes(raw)
            frozen_references[plan_id] = frozen
            eligible[plan_id] = _plan_evidence(plan, bound)
            report['references'][plan_id] = bound['provenance']
        except (OSError, ValueError, KeyError, TypeError) as error:
            detail = str(error) if isinstance(error, ValueError) and str(error).startswith(
                ('Placement reference rejected:', 'Estimated memory')) else 'Reference unavailable or invalid'
            report['rejected'].append(dict(plan_id=plan_id, reason='isolated-evidence-or-fit-rejected',
                                           error_type=type(error).__name__, detail=detail))
    result._save()
    remaining = list(eligible)
    active, active_id, best_values, best_id = None, None, None, None
    history = []
    try:
        while True:
            if report['no_progress_rounds'] >= 2:
                report['stop_reason'] = 'objective-plateau-confirmed'
                break
            if budget.max_candidate_trials is not None and len(report['trials']) >= budget.max_candidate_trials:
                report['stop_reason'] = 'explicit-trial-budget'
                break
            if not remaining:
                report['stop_reason'] = 'no-legal-plans'
                break
            evidence = dict(placement=True, legal_proposal_ids=remaining[:],
                proposals=[eligible[key] for key in remaining], objective=objective.model_dump(),
                rejected_plans=deepcopy(report['rejected']), memory_accounting=memory_accounting,
                allocation_scope=('configured vLLM budgets, not separately verified hard caps'
                                  if memory_accounting == 'total-device' else 'per-service sampled hard caps'),
                remaining_trials=None if budget.max_candidate_trials is None else budget.max_candidate_trials-len(report['trials']),
                incumbent_plan_id=best_id, incumbent_objectives=best_values,
                confirmation_round=report['no_progress_rounds'] == 1, history=deepcopy(history),
                policy='quality first; measured objective; one no-progress round plus one confirmation')
            round_record = dict(round=len(report['rounds'])+1, evidence=evidence)
            report['rounds'].append(round_record)
            try:
                response = agent.request('arbiter', evidence,
                    'Act as the placement frontier reader and arbiter. Select at most one legal_proposal_ids entry, '
                    'or abstain with an empty list when another trial is not useful for the supplied objective. '
                    'Every proposed plan has measured passing isolated evidence, not passing joint evidence. '
                    'rejected_plans includes deterministic fit failures, not measured performance. '
                    'Explain whether weight quantization is needed under those specific allocations, but never select a rejected plan. '
                    'Use recorded quality, memory, latency and failed joint outcomes; state expected contention '
                    'as a hypothesis, not an observed cause. Do not invent plans, allocations, thresholds, '
                    'quality scores, or speedups. Honor confirmation_round and the remaining budget. '
                    'The deterministic executor owns all eligibility and final selection gates.')
                response = ArbiterDecision.model_validate(response.model_dump() if response is not None else None)
                round_record['response'] = response.model_dump()
                if any(key not in remaining for key in response.ranked_proposal_ids):
                    raise ValueError('Unknown or already tested placement plan')
            except Exception as error:
                round_record.update(status='rejected', error_type=type(error).__name__)
                report['stop_reason'] = 'invalid-agent-decision'
                break
            if not response.ranked_proposal_ids:
                round_record['status'] = 'abstained'
                report['stop_reason'] = 'agent-abstained'
                break
            selected = response.ranked_proposal_ids[0]
            round_record.update(status='accepted', selected_plan_id=selected)
            remaining.remove(selected)
            if active is not None:
                active.close()
                active = None
            trial_number = len(report['trials']) + 1
            pending = dict(plan_id=selected, output_dir=str(folder/f'trial-{trial_number:03d}'),
                           status='starting', report={})
            report['trials'].append(pending)
            result._save()
            active = place(plan=by_id[selected], workloads=profiles, memory_estimates=estimates[selected],
                           isolated_reference=frozen_references[selected],
                           trial_namespace=f"trial-{trial_number:03d}",
                           memory_accounting=memory_accounting,
                           output_dir=folder/f"trial-{trial_number:03d}")
            active_id = selected
            values = _measured_objectives(active.report)
            eligible_result = values is not None and _positive(values.get(objective.priority))
            better, qualifying, gain = _progress(best_values, values, objective) if eligible_result else (False, False, None)
            if better:
                best_values, best_id = values, selected
            report['selected_plan_id'] = best_id
            report['no_progress_rounds'] = 0 if qualifying else report['no_progress_rounds']+1
            pending.update(status='completed', report=active.report,
                         eligible=eligible_result, objectives=values, qualifying_progress=qualifying,
                         improvement_fraction=gain)
            history.append(dict(plan_id=selected, decision=active.report['decision'],
                objective_value=values[objective.priority] if eligible_result else None,
                objectives=values, qualifying_progress=qualifying,
                quality_gates=active.report.get('joint', {}).get('gates'),
                memory=active.report.get('shared_runtime'),
                quality_outputs={model:trial.get('quality', []) for model,trial in active.report.get('joint', {}).get('trials', {}).items()}))
            result._save()
            shared = active.report.get('shared_runtime', {})
            if shared.get('errors') or active.report.get('status') == 'cleanup-failed':
                report['stop_reason'] = 'runtime-safety-failure'
                break

        if best_id is not None and report['stop_reason'] != 'runtime-safety-failure':
            if active is None or active_id != best_id:
                if active is not None:
                    active.close()
                    active = None
                active = place(plan=by_id[best_id], workloads=profiles, memory_estimates=estimates[best_id],
                    isolated_reference=frozen_references[best_id], trial_namespace='return-validation',
                    memory_accounting=memory_accounting,
                    output_dir=folder/'return-validation')
                report['restoration'] = active.report
            if _measured_objectives(active.report) is not None and len(active.models) == 2:
                result.placement, active = active, None
                report.update(status='ready', returned_runner_closed=False)
            else:
                report.update(status='no-safe-placement', selected_plan_id=None, return_failure='restoration-requirements-failed')
        else:
            report.update(status='no-safe-placement', selected_plan_id=None)
        if active is not None:
            active.close()
            active = None
        if result.placement is not None:
            from .placement_capacity import capacity_evidence
            proof = capacity_evidence(by_id[best_id], report['rejected'], by_id, result.placement.report)
            proof['workload_hash'] = report['workload_hash']
            report.update(capacity_evidence=proof, quantization_enabled_placement=proof['established'])
            result.placement.report.update(capacity_evidence=proof, quantization_enabled_placement=proof['established'])
            result.placement._save()
        result._save()
        return result
    except BaseException as error:
        if report['trials'] and report['trials'][-1].get('status') == 'starting':
            report['trials'][-1].update(status='failed', error_type=type(error).__name__)
        report.update(status='failed', error_type=type(error).__name__, stop_reason='execution-failed')
        errors = []
        for owned in (active, result.placement):
            if owned is not None:
                try:
                    owned.close()
                except BaseException as cleanup_error:
                    errors.append(type(cleanup_error).__name__)
        if errors:
            report.update(status='cleanup-failed', cleanup_errors=errors, returned_runner_closed=False)
        result.placement = None
        result._save()
        raise
