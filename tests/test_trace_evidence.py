"""Agents inspect bounded saved requests without replaying inference."""

from copy import deepcopy

from sera.trace_evidence import request_evidence


def test_failed_quality_precedes_passed_outputs_and_preserves_source():
    trial = dict(trial_id='trial-2', config_hash='config', quality=[
        dict(prompt_index=i, text=f'output-{i}', error=None) for i in range(8)],
        task_quality=dict(per_prompt=[dict(prompt_index=i, score=0 if i == 7 else 1,
                                          error=None) for i in range(8)]))
    original = deepcopy(trial)
    evidence = request_evidence(trial, [f'question-{i}' for i in range(8)])
    assert evidence['quality_examples'][0]['output'] == 'output-7'
    assert evidence['quality_examples'][0]['input'] == 'question-7'
    assert evidence['quality_examples'][0]['task_score'] == 0
    assert evidence['quality_examples'][0]['source_path'] == 'quality/7'
    assert evidence['trial_id'] == 'trial-2'
    assert len(evidence['quality_examples']) == 4
    assert evidence['quality_omitted'] == 4
    assert evidence['failed_task_count'] == 1
    assert trial == original


def test_slow_requests_keep_load_and_latency_and_strip_unrelated_data():
    trial = dict(trial_id='baseline', loads=[dict(concurrency=4, requests=[
        dict(prompt_index=0, text='x' * 3000, latency_ms=ms, error=None,
             usage=dict(completion_tokens=4), authorization='SECRET')
        for ms in [1, 500, 100]])])
    evidence = request_evidence(trial, ['input'])
    slow = evidence['slow_request_examples']
    assert [item['latency_ms'] for item in slow] == [500, 100]
    assert slow[0]['concurrency'] == 4
    assert slow[0]['source_path'] == 'loads/0/requests/1'
    assert slow[0]['output_truncated'] is True
    assert len(slow[0]['output']) == 1000
    assert 'SECRET' not in str(evidence)
    assert evidence['measured_request_count'] == 3


def test_missing_or_failed_measurement_does_not_invent_requests_or_scores():
    evidence = request_evidence(dict(trial_id='trial-1', status='startup-failed'))
    assert evidence['quality_examples'] == []
    assert evidence['slow_request_examples'] == []
    assert evidence['failed_task_count'] is None
    assert evidence['measured_request_count'] == 0


def test_errors_are_bounded_and_prompts_are_only_role_content():
    evidence = request_evidence(dict(quality=[dict(prompt_index=0, text='',
        error='RuntimeError: secret detail')]),
        [[dict(role='user', content='question', secret='not exported')]])
    item = evidence['quality_examples'][0]
    assert item['error'] == 'RuntimeError'
    assert item['input'] == [{'role': 'user', 'content': 'question'}]
    assert item['task_score'] is None
    assert 'secret' not in str(evidence)
