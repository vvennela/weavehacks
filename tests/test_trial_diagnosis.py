"""Observed rejection reasons are not unsupported causal explanations."""

from copy import deepcopy

import pytest

from sera.diagnosis import trial_diagnosis
from sera.tracing import InspectionReadError, use_event_sink
from test_investigation import install_fakes, run
from test_fit_investigation import boundaries, run as run_fit


def records():
    baseline = {'reduced': {'p95_latency_ms': 100}}
    trial = {'trial_id': 'trial-1', 'status': 'collected',
             'reduced': {'p95_latency_ms': 98},
             'task_quality': {'version': 'fixed-v1', 'mean': .875, 'floor': .99,
                 'passed': False, 'valid_outputs': True,
                 'per_prompt': [{'prompt_index': 7, 'score': 0, 'error': None}]}}
    decision = {'selected': 'baseline', 'reason': 'candidate-constraints-failed',
        'constraint_failures': {'candidate': ['task-quality-failed']},
        'candidate_quality': trial['task_quality'],
        'objective': {'priority': 'latency', 'min_improvement_fraction': .05},
        'objective_improvement_fraction': .02}
    return baseline, trial, decision


def test_quality_rejection_explains_fixed_score_and_failed_prompt_without_claiming_quantization_cause():
    baseline, trial, decision = records()
    diagnosis = trial_diagnosis(baseline, trial, decision)
    assert diagnosis['failure_kind'] == 'task-quality-rejected'
    assert diagnosis['observed']['quality']['mean'] == .875
    assert diagnosis['observed']['quality']['floor'] == .99
    assert diagnosis['observed']['quality']['per_prompt'][0]['prompt_index'] == 7
    assert diagnosis['root_cause']['status'] == 'not-established'
    assert 'task_quality/per_prompt' in diagnosis['evidence_paths']
    assert any('quality floor' in action for action in diagnosis['next_proposal_constraints'])


def test_objective_miss_is_threshold_evidence_not_a_model_or_kernel_diagnosis():
    baseline, trial, decision = records()
    trial['task_quality'].update(mean=1., passed=True)
    decision.update(reason='p95-improvement-below-five-percent', constraint_failures={'candidate': []})
    diagnosis = trial_diagnosis(baseline, trial, decision)
    assert diagnosis['failure_kind'] == 'objective-not-improved'
    assert diagnosis['observed']['objective'] == dict(priority='latency', baseline_value=100,
        candidate_value=98, improvement_fraction=.02, required_improvement_fraction=.05)
    assert 'does not establish' in diagnosis['root_cause']['reason']


def test_startup_failure_does_not_mislabel_unrun_quality_as_quality_degradation():
    baseline, trial, decision = records()
    trial.update(status='startup-failed', failure_stage='startup', error='RuntimeError: secret detail')
    trial.pop('reduced')
    diagnosis = trial_diagnosis(baseline, trial, decision)
    assert diagnosis['failure_kind'] == 'startup-failed'
    assert diagnosis['observed']['error_type'] == 'RuntimeError'
    assert diagnosis['observed']['quality'] is None
    assert diagnosis['observed']['objective']['candidate_value'] is None
    assert 'secret detail' not in str(diagnosis)


def test_request_errors_report_observed_count_and_preserve_unknown_underlying_cause():
    baseline, trial, decision = records()
    trial.update(status='request-errors', generation_errors=2)
    diagnosis = trial_diagnosis(baseline, trial, decision)
    assert diagnosis['failure_kind'] == 'measurement-failed'
    assert diagnosis['observed']['generation_errors'] == 2
    assert diagnosis['root_cause']['status'] == 'not-established'


@pytest.mark.parametrize('startup_failure', [False, True])
def test_saved_diagnosis_exports_before_review_and_reaches_next_round(tmp_path, monkeypatch, startup_failure):
    runners, calls, agent = install_fakes(monkeypatch, startup_failure=startup_failure)
    events = []
    def sink(name, payload):
        assert name == 'recorded_trial_diagnosis'
        assert (tmp_path/'run'/'result.json').exists()
        events.append(deepcopy(payload))
    original_review = agent.review
    def review(evidence):
        assert events[-1]['diagnosis'] == evidence['diagnosis']
        return original_review(evidence)
    agent.review = review
    with use_event_sink(sink), run(tmp_path, agent) as result:
        first = result.trials[1]
        assert first['diagnosis_trace_export']['status'] == 'complete'
        assert events[0]['config_hash'] == first['config_hash']
        assert events[0]['diagnosis']['failure_kind'] == ('startup-failed' if startup_failure else 'task-quality-rejected')
        later = [e for role, e in calls if role == 'proposal' and e['remaining_trials'] == 1][0]
        assert later['history'][0]['diagnosis'] == first['diagnosis']
        assert later['failure_diagnoses'][0]['trial_id'] == first['trial_id']
    assert not any(runner.ready for runner in runners)


def test_diagnosis_export_failure_does_not_change_gate_or_leak_runner(tmp_path, monkeypatch):
    runners, _, agent = install_fakes(monkeypatch)
    def sink(*_):
        raise RuntimeError('secret export error')
    with use_event_sink(sink), run(tmp_path, agent) as result:
        first = result.trials[1]
        assert first['task_quality']['passed'] is False
        assert first['diagnosis_trace_export']['status'] == 'failed'
        assert first['diagnosis_trace_export']['error_type'] == 'RuntimeError'
        assert result.report['decision']['selected'] == 'trial-2'
    assert not any(runner.ready for runner in runners)


def test_inspection_error_only_allows_static_safe_codes():
    error = InspectionReadError('incomplete-requests')
    assert error.reason_code == 'incomplete-requests'
    assert 'request' in error.safe_message
    with pytest.raises(ValueError):
        InspectionReadError('secret error body')


@pytest.mark.parametrize('stage', ['constructor', 'startup', 'measurement'])
def test_fit_failure_is_traced_with_actual_stage_and_no_bf16_comparison(tmp_path, monkeypatch, stage):
    from sera import fit
    runners, calls, agent = boundaries(monkeypatch)
    def fail(*args, **kwargs):
        raise RuntimeError('secret exception text')
    if stage == 'constructor':
        monkeypatch.setattr(fit, 'SeraModel', fail)
    elif stage == 'startup':
        monkeypatch.setattr(fit.SeraModel, 'start', fail)
    else:
        monkeypatch.setattr(fit, 'collect_trial', fail)
    events = []
    with use_event_sink(lambda name, payload: events.append(deepcopy(payload))), run_fit(tmp_path, agent) as result:
        trial = result.report['candidate_trial']
        assert trial['failure_stage'] == stage
        assert trial['diagnosis']['failure_kind'] == ('measurement-failed' if stage == 'measurement' else 'startup-failed')
        assert events[0]['config_hash'] == trial['config_hash']
        assert events[0]['diagnosis']['observed']['objective']['baseline_value'] is None
        assert result.report['agent_feedback']['diagnosis'] == trial['diagnosis']
        assert 'secret exception text' not in str(events)
    assert not any(runner.ready for runner in runners)
