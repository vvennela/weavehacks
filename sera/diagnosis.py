"""Explain observed trial rejection without inventing a hardware or model cause."""

from copy import deepcopy
import re

from .measurement import objective_value
from .tracing import TraceSinkError, emit_event, event_sink_enabled


def trial_diagnosis(baseline, trial, decision):
    status = trial.get('status')
    failures = decision.get('constraint_failures', {}).get('candidate', [])
    measured_quality = status == 'collected' or bool(trial.get('quality'))
    gate = decision.get('candidate_quality') or trial.get('task_quality') or {}
    quality = ({key: deepcopy(gate[key]) for key in
                ('version', 'floor', 'mean', 'passed', 'valid_outputs', 'per_prompt', 'scores')
                if key in gate} if measured_quality else None)
    reason = decision.get('reason')
    if status == 'startup-failed' or trial.get('failure_stage') in ('constructor', 'startup'):
        kind = 'startup-failed'
    elif status != 'collected':
        kind = 'measurement-failed'
    elif 'input-token-mismatch' in failures or reason == 'input-token-mismatch':
        kind = 'invalid-comparison'
    elif quality is not None and not quality.get('passed'):
        kind = 'task-quality-rejected' if 'task_quality' in trial else 'token-agreement-rejected'
    elif failures:
        kind = 'constraints-rejected'
    elif decision.get('selected') == 'candidate':
        kind = 'accepted'
    else:
        kind = 'objective-not-improved'
    error_type = (trial.get('error') or '').split(':', 1)[0]
    error_type = error_type if re.fullmatch(r'[A-Za-z_]\w{0,79}', error_type) else None
    objective = decision.get('objective') or {}
    priority = objective.get('priority', 'latency')
    observed = dict(status=status, failure_stage=trial.get('failure_stage'), error_type=error_type,
        generation_errors=trial.get('generation_errors', trial.get('reduced', {}).get('generation_errors')),
        selection_reason=reason, constraint_failures=list(failures), quality=quality,
        objective=dict(priority=priority, baseline_value=objective_value(baseline, priority),
            candidate_value=objective_value(trial, priority),
            improvement_fraction=decision.get('objective_improvement_fraction'),
            required_improvement_fraction=objective.get('min_improvement_fraction')))
    actions = ['Do not retry the same tested configuration in this bounded search.',
               'Preserve the fixed quality floor and all workload constraints.']
    if kind in ('startup-failed', 'measurement-failed'):
        actions.append('Inspect the persisted failure record; absent requests are not a quality or speed result.')
    elif kind in ('task-quality-rejected', 'token-agreement-rejected'):
        actions.append('Inspect failed task outputs and fixed evaluator results before proposing another setting.')
    elif kind == 'objective-not-improved':
        actions.append('Use the measured gain and required gain to justify a different setting, or abstain.')
    else:
        actions.append('Use the recorded constraints and measurements to justify the next action, or abstain.')
    paths = ['status', 'decision']
    paths.extend(key for key in ('failure_stage', 'error', 'reduced') if key in trial)
    if 'sampled_peak_memory_mib' in trial.get('runtime', {}):
        paths.append('runtime/sampled_peak_memory_mib')
    if 'per_prompt' in trial.get('task_quality', {}):
        paths.append('task_quality/per_prompt')
    elif quality is not None:
        paths.append('decision/candidate_quality')
    return dict(failure_kind=kind, observed=observed, evidence_paths=paths,
        root_cause=dict(status='not-established', reason=
            'The observed outcome does not establish a model, kernel, memory-pressure, or scheduling cause. '
            'A startup error category is not the underlying server-log cause.'),
        next_proposal_constraints=actions)


def export_trial_diagnosis(trial):
    """Publish the already-saved verdict after measurement, without altering it."""
    if not event_sink_enabled():
        return
    runtime = trial.get('runtime', {})
    export = trial['diagnosis_trace_export'] = dict(status='running', emitted_events=0)
    try:
        emit_event('recorded_trial_diagnosis', dict(trial_id=trial['trial_id'],
            model_id=runtime.get('model_id'), revision=runtime.get('revision'),
            config_hash=trial.get('config_hash'), diagnosis=deepcopy(trial['diagnosis']),
            timing_scope='Saved deterministic trial verdict; span duration is export time, not inference.'))
        export.update(status='complete', emitted_events=1)
    except TraceSinkError as error:
        export.update(status='failed', error_type=error.error_type, failed_event=error.event_name)
