"""Explicit restart of a saved measured investigation, without trial replay."""

from copy import deepcopy
from pathlib import Path
import subprocess

from .config import Budget, Constraints, Objective, Workload
from .ledger import Ledger, environment_fingerprint, read_checkpoint, timestamp
from .measurement import objective_value, select_candidate


def inspect_recovery(output_dir):
    """Read the authoritative checkpoint. This does not claim any GPU process."""
    report, revision = read_checkpoint(Path(output_dir).resolve())
    return dict(run_hash=report['durability']['run_hash'], revision=revision,
                checkpoint=report.get('recovery_checkpoint'), report=report)


def verify_idle_hardware(report):
    """Reject changed or busy GPUs. Never signal a PID saved by another process."""
    from .hardware import discover_gpus
    runtime = report['baseline']['runtime']
    previous = runtime.get('gpus') or [runtime.get('gpu')]
    if not previous or any(not gpu or not gpu.get('uuid') for gpu in previous):
        raise ValueError('The checkpoint has no verified GPU identity; resume is unsafe')
    current = {gpu['uuid']: gpu for gpu in discover_gpus()}
    identity_keys = ('uuid', 'name', 'total_mib', 'compute_capability', 'driver')
    for gpu in previous:
        actual = current.get(gpu['uuid'])
        if actual is None or any(actual.get(key) != gpu.get(key) for key in identity_keys):
            raise ValueError('GPU identity or driver differs from the saved experiment')
        if actual['used_mib'] > 128:
            raise RuntimeError('A saved GPU is busy; resolve its owner before resuming')
    processes = subprocess.run(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid',
        '--format=csv,noheader,nounits'], check=True, capture_output=True, text=True, timeout=10).stdout
    assigned = {gpu['uuid'] for gpu in previous}
    for row in processes.splitlines():
        if row.split(',')[0].strip() in assigned:
            raise RuntimeError('A saved GPU has a compute process; resume will not stop it')


def recovered_best(report, objective, constraints):
    baseline = report['baseline']
    best = baseline if select_candidate(baseline, None, objective=objective, constraints=constraints)['selected'] else None
    for trial in report['search_trials']:
        decision = select_candidate(baseline, trial, objective=objective, constraints=constraints)
        if decision['selected'] != 'candidate':
            continue
        new = objective_value(trial, objective.priority)
        old = objective_value(best, objective.priority) if best is not None else None
        better = old is None or (new > old if objective.priority == 'throughput' else new < old)
        memory, old_memory = objective_value(trial, 'memory'), objective_value(best, 'memory') if best else None
        if better or (new == old and memory is not None and (old_memory is None or memory < old_memory)):
            best = trial
    return best


def _resolve_interrupted_round(report, objective, constraints):
    from .investigation import objective_progress
    from .diagnosis import trial_diagnosis
    search = report['search']
    if not search['rounds'] or search['rounds'][-1].get('completed'):
        return
    record = search['rounds'][-1]
    record['recovery_interrupted'] = True
    trials = [trial for trial in report['search_trials'] if trial['trial_id'] in record['trial_ids']]
    for trial in trials:
        if trial['status'] == 'starting' or (trial['status'] == 'collected'
                and report.get('evaluation') and 'task_quality' not in trial):
            trial.update(status='interrupted', failure_stage='optimizer-interrupted',
                error='No complete committed measurement and quality gate; this configuration will not be retried')
        trial.setdefault('decision', select_candidate(report['baseline'], trial,
                                                       objective=objective, constraints=constraints))
        trial.setdefault('diagnosis', trial_diagnosis(report['baseline'], trial, trial['decision']))
        if 'review' not in trial and 'review_error' not in trial:
            trial['review_error'] = 'OptimizerInterruptedBeforeReviewCompleted'
    if search['budget']['max_candidate_trials'] is None and 'objective_progress' not in record:
        if trials:
            record['objective_progress'] = objective_progress(search['plateau'], report['baseline'], trials,
                objective=objective, constraints=constraints, round_number=record['round'])
            if search['plateau']['consecutive_no_progress_rounds'] >= 2:
                search['stop_reason'] = 'objective-plateau-confirmed'
        else:
            record['recovery_note'] = 'No GPU trial was committed; interruption does not count as an objective plateau'
    elif search['budget']['max_candidate_trials'] is not None and trials:
        from .investigation import search_frontier
        prior_trials = [trial for trial in report['search_trials'] if trial not in trials]
        def points(history):
            return {tuple(objective_value(trial, priority) for priority in ('latency', 'memory', 'throughput'))
                    for trial in search_frontier(report['baseline'], history, constraints=constraints)}
        changed = points(prior_trials) != points(report['search_trials'])
        search['stagnant_rounds'] = 0 if changed else search.get('stagnant_rounds', 0) + 1
        if search['stagnant_rounds'] >= 2:
            search['stop_reason'] = 'two-rounds-without-frontier-improvement'
    record['completed'] = True


def resume(*, output_dir, expected_run_hash, agent, provider_check, evaluation=None,
           evaluation_version=None, confirm_interrupted=False, trace_reader=None, weave_project=None):
    """Resume the same run on idle, unchanged hardware with an explicit identity.

    Supply the same versioned evaluator. Incomplete GPU trials count as failed
    attempts and are never repeated. No old process is adopted or killed. A new
    winner process is a deployment restore, not another measurement trial.
    """
    from . import pipeline
    from .investigation import investigate
    from .provider_check import require_provider_check
    from .swarm import validate_swarm_options

    folder = Path(output_dir).resolve()
    ledger = Ledger(folder, existing=True)
    try:
        report, revision = read_checkpoint(folder)
        if expected_run_hash != report['durability']['run_hash']:
            raise ValueError('Expected run hash differs from this ledger')
        if report['durability']['environment'] != environment_fingerprint():
            raise ValueError('Code or software environment changed; resume requires the saved environment')
        if not report.get('search') or report.get('baseline', {}).get('status') != 'collected':
            raise ValueError('Resume requires a committed measured baseline and investigation checkpoint')
        if report.get('evaluation'):
            if not callable(evaluation) or evaluation_version != report['evaluation']['version']:
                raise ValueError('Resume requires the same evaluation version and callable')
        elif evaluation is not None or evaluation_version is not None:
            raise ValueError('Cannot change quick mode into task evaluation on resume')
        if report['status'] != 'closed' and confirm_interrupted is not True:
            raise ValueError('Explicit confirm_interrupted=True is required for unfinished external work')
        validation = require_provider_check(provider_check, agent)
        if validation != report.get('provider_validation'):
            raise ValueError('Provider validation differs from the saved investigation')
        budget = Budget.model_validate(report['search']['budget'])
        swarm = report.get('swarm_enabled', False)
        if weave_project is None or trace_reader is not None:
            validate_swarm_options(swarm, budget, agent, trace_reader)
        elif swarm and not callable(getattr(agent, 'fork', None)):
            raise ValueError('Swarm recovery requires a forkable agent')
        if swarm and trace_reader is None and weave_project is None:
            raise ValueError('Swarm recovery requires weave_project or a scoped trace reader')
        if weave_project is not None and (not isinstance(weave_project, str) or weave_project != agent.project):
            raise ValueError('Resume Weave project must match the validated agent project')
        verify_idle_hardware(report)
        objective = Objective.model_validate(report['objective'])
        constraints = Constraints.model_validate(report['constraints']) if report.get('constraints') else None
        _resolve_interrupted_round(report, objective, constraints)
        report.setdefault('recovery_events', []).append(dict(time=timestamp(), checkpoint_revision=revision,
            previous_status=report['status'], previous_error=report.pop('error', None),
            prior_weave_url=report.get('weave_url'), hardware_verified_idle=True,
            interrupted_agent_calls=ledger.resolve_interrupted_calls(),
            decision='Continue without repeating committed or interrupted configurations'))
        report.update(status='running', _resume_investigation=True, returned_runner_closed=True)
        agent.history[:0] = deepcopy(report.get('agent_calls', []))
        runtime_factory = None
        execution = report.get('execution', {})
        if execution.get('hardware_assignment'):
            from .hardware import HardwareAssignment, ModelDescriptor
            from .portable_runtime import PortableRuntimeFactory
            runtime_factory = PortableRuntimeFactory(
                model=ModelDescriptor.model_validate(execution['model_descriptor']),
                hardware=HardwareAssignment.model_validate(execution['hardware_assignment']))
        result = pipeline.SeraResult(models=[], report=report, output_dir=folder, _ledger=ledger)
        result._save()
        arguments = dict(result=result, active=None, agent=agent, history_start=0, budget=budget,
            objective=objective, constraints=constraints, evaluation=evaluation,
            evaluation_version=evaluation_version, workload=Workload(concurrency=report['workload']['concurrency']),
            initial_trials_used=report['search']['initial_trials_used'], swarm=swarm,
            trace_reader=trace_reader, runtime_factory=runtime_factory)
        if weave_project is not None:
            return _resume_traced(arguments, weave_project)
        report['recovery_events'][-1]['trace_mode'] = 'caller-managed'
        return investigate(**arguments)
    except BaseException:
        ledger.close()
        raise


def _export_saved_evidence(result):
    """Republish committed measurements, explicitly labeled as imports, not trials."""
    from .measurement import export_trial_events
    from .diagnosis import export_trial_diagnosis
    from .storage import content_hash
    imported = []
    for saved in [result.report['baseline'], *result.report['search_trials']]:
        trial = deepcopy(saved)
        trial['trial_id'] = saved.get('source_trial_id', saved['trial_id'])
        if saved['status'] == 'collected':
            trial['trace_export'] = dict(status='running', emitted_events=0,
                timing_scope='Recovery import of committed measurements; no inference was executed.')
            export_trial_events(trial, result.report['prompts'])
            if trial['trace_export']['status'] != 'complete':
                raise RuntimeError('Recovery could not import saved request evidence to Weave')
        if 'diagnosis' in trial:
            export_trial_diagnosis(trial)
            if trial.get('diagnosis_trace_export', {}).get('status') != 'complete':
                raise RuntimeError('Recovery could not import the saved diagnosis to Weave')
        imported.append(dict(trial_id=trial['trial_id'], source_record_hash=content_hash(saved),
                             status=saved['status'], inference_executed=False))
    result.report['recovery_events'][-1]['imported_evidence'] = imported
    result._save()
    return dict(source='committed SQLite checkpoint', imported_trials=imported,
                note='These operations export historical evidence, not new measurements.')


def _resume_traced(arguments, project):
    import weave
    from .investigation import investigate
    from .tracing import use_event_sink
    from .weave_evidence import WeaveEvidenceReader
    from .weave_integration import (TracedInvestigationAgent, traced_evidence_reader,
                                    trial_trace_failures, weave_event_sink)
    result = arguments['result']
    agent = TracedInvestigationAgent(arguments['agent'], weave)
    client = weave.init(project)

    def run():
        call = weave.get_current_call()
        if call is None:
            raise RuntimeError('Weave did not create the required recovery root')
        result.report['recovery_events'][-1].update(trace_mode='weave', weave_url=call.ui_url,
                                                   trace_id=call.trace_id)
        result.report.update(weave_url=call.ui_url, trace_status='recovering')
        result._save()
        def restore_evidence():
            return _export_saved_evidence(result)
        weave.op(name='restore_saved_trial_evidence')(restore_evidence)()
        reader = None
        if arguments['swarm']:
            reader = arguments.get('trace_reader') or WeaveEvidenceReader(client, call.trace_id)
            reader = traced_evidence_reader(weave, reader)
        investigate(**(arguments | dict(agent=agent, trace_reader=reader)))
        failures = trial_trace_failures(result.report) + agent.trace_failures
        result.report.update(trace_status='failed' if failures else 'enabled', trace_export_failures=failures)
        result._save()
        return result.report

    try:
        try:
            with use_event_sink(weave_event_sink(weave)):
                weave.op(name='sera_resume')(run)()
        finally:
            client.flush()
    except BaseException as error:
        result.report.update(trace_status='failed', recovery_trace_error=type(error).__name__)
        try:
            result.close()
        except BaseException as cleanup_error:
            error.add_note(f'Recovery cleanup failed: {type(cleanup_error).__name__}')
        raise
    return result
