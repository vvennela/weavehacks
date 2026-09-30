import json
import time

import pytest
from test_native_optimizer import profile

from sera.rag_intake import IntakeNeedsInput
from sera.workload_intake import prepare_workload, read_examples


class Planner:
    def __init__(self, **kwargs):
        assert kwargs['model'] == 'gpt-6-astra'
        assert kwargs['reasoning_effort'] == 'high'
    def request(self, prompt, schema, **kwargs):
        assert 'PRIVATE_LABEL' not in prompt
        return {'status': 'ready', 'profile_id': 'fixture', 'questions': [],
                'reason': 'Use the supplied examples to measure this inference workload.'}


@pytest.fixture(autouse=True)
def trace(monkeypatch):
    monkeypatch.setattr('sera.workload_intake.trace_native_job', lambda project, run:
                        {'result': run(), 'trace': {'remote_verified': True, 'url': 'fixture'}})


def request(intent='Classify support tickets'):
    return {'intent': intent, 'profiles': [profile()], 'project': 'fixture/project',
            'deadline': time.time() + 60, 'examples': [
                {'prompt': 'Classify: my package arrived broken', 'expected_json': 'PRIVATE_LABEL'}]}


@pytest.mark.parametrize('intent', ['Classify support tickets', 'Extract invoice fields',
                                  'Answer chat messages', 'Summarize product reviews'])
def test_intent_compiles_supplied_workload_without_documents(tmp_path, intent):
    accepted = request(intent)
    value = prepare_workload(accepted, tmp_path, agent_factory=Planner, hardware={'backends': ['mlx']})
    assert len(value['profile']['tasks']) == len(accepted['examples'])
    assert value['profile']['tasks'][0]['expected_json'] == 'PRIVATE_LABEL'
    assert value['profile']['tasks'][0]['prompt'] == accepted['examples'][0]['prompt']
    from sera.native_optimizer import validate_native_profile
    original = validate_native_profile(profile()).model_dump()
    for key in ('source', 'constraints', 'objective', 'recipes', 'budget', 'seed', 'repetitions'):
        assert value['profile'][key] == original[key]
    assert value['workload']['quality_scope'] == 'supplied-evaluation-examples'
    assert value['profile']['workload_description'] == intent
    assert value['profile']['max_run_seconds'] <= 60
    assert prepare_workload(accepted, tmp_path, agent_factory=lambda **kw: pytest.fail('replanned')) == value


def test_template_requires_examples_instead_of_inventing_quality(tmp_path):
    accepted = request()
    accepted['profiles'][0].update(tasks=[], requires_examples=True)
    accepted['examples'] = None
    with pytest.raises(IntakeNeedsInput, match='examples'):
        prepare_workload(accepted, tmp_path, agent_factory=Planner, hardware={'backends': ['mlx']})


def test_intake_rejects_changed_compiled_contract(tmp_path):
    accepted = request()
    prepare_workload(accepted, tmp_path, agent_factory=Planner, hardware={'backends': ['mlx']})
    path = tmp_path / 'workload-compiled.json'
    saved = json.loads(path.read_text())
    saved['profile']['tasks'][0]['expected_json'] = 'another label'
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match='changed'):
        prepare_workload(accepted, tmp_path, agent_factory=Planner)


def test_examples_file_is_bounded_and_validated(tmp_path):
    path = tmp_path / 'examples.json'
    path.write_text(json.dumps(request()['examples']))
    assert read_examples(path)[0]['expected_json'] == 'PRIVATE_LABEL'
    path.write_text('[]')
    with pytest.raises(ValueError):
        read_examples(path)


def test_free_text_checks_grade_customer_requirements():
    from sera.native_optimizer import NativeTask, score_task
    task = NativeTask(prompt='Summarize the incident', expected_json=None,
                      text_checks={'required': ['outage', 'restored'], 'forbidden': ['data loss'], 'max_words': 20})
    assert score_task(task, 'The outage was restored in ten minutes.')
    assert not score_task(task, 'The outage involved data loss and was restored.')
    assert not score_task(task, 'No details available.')
    exact = NativeTask(prompt='Translate hello', expected_json=None, text_checks={'exact': 'bonjour'})
    assert score_task(exact, 'bonjour')
    assert not score_task(exact, 'bonjour!')
    with pytest.raises(ValueError):
        NativeTask(prompt='test', expected_json=None, text_checks={'max_words': 20})


def test_requested_int4_restricts_experiments_without_weakening_checks(tmp_path):
    class Int4(Planner):
        def request(self, *args, **kwargs):
            return super().request(*args, **kwargs) | {'required_precision': 'int4', 'throughput_retention': .95}
    accepted = request('Quantize to INT4 and retain at least 95% of throughput')
    result = prepare_workload(accepted, tmp_path, agent_factory=Int4, hardware={'backends': ['mlx']})
    assert set(result['profile']['recipes']) == {'q4'}
    assert result['profile']['required_precision'] == 'int4'
    assert result['profile']['constraints']['quality_floor'] == .99
    assert result['profile']['retention']['throughput'] == .95


def test_fp4_is_not_silently_replaced_with_integer_four_bit(tmp_path):
    class FP4(Planner):
        def request(self, *args, **kwargs):
            return super().request(*args, **kwargs) | {'required_precision': 'nvfp4'}
    with pytest.raises(IntakeNeedsInput, match='nvfp4'):
        prepare_workload(request('Run at FP4'), tmp_path, agent_factory=FP4, hardware={'backends': ['mlx']})


def test_one_workload_can_mix_json_and_plain_text_checks(tmp_path):
    accepted = request()
    accepted['examples'] = [
        {'prompt': 'Extract a JSON record', 'expected_json': {'count': 2}, 'response_format': {
            'type': 'json_schema', 'json_schema': {'name': 'count', 'schema': {
                'type': 'object', 'properties': {'count': {'type': 'integer'}},
                'required': ['count'], 'additionalProperties': False}}}},
        {'prompt': 'Summarize the report', 'expected_json': None,
         'text_checks': {'required': ['delivery']}}]
    result = prepare_workload(accepted, tmp_path, agent_factory=Planner, hardware={'backends': ['mlx']})
    from sera.native_optimizer import validate_native_profile
    compiled = validate_native_profile(result['profile'])
    job = compiled.measure_job('/checkpoint', 'a'*64)
    assert job['response_formats'][1] is None
    assert job['response_formats'][0]['type'] == 'json_schema'


def test_explicit_format_cannot_be_dropped_by_planner(tmp_path):
    with pytest.raises(IntakeNeedsInput, match='precision'):
        prepare_workload(request('Run at FP4'), tmp_path, agent_factory=Planner, hardware={'backends': ['mlx']})


@pytest.mark.parametrize('intent', ['Do not run at FP4; minimize memory', 'Compare INT4 and INT8 for memory'])
def test_format_mentions_do_not_invent_a_hard_requirement(tmp_path, intent):
    result = prepare_workload(request(intent), tmp_path, agent_factory=Planner, hardware={'backends': ['mlx']})
    assert result['profile'].get('required_precision') is None


@pytest.mark.parametrize('intent', ['Use INT4', 'Keep the model in INT4', 'Do not use FP4 but must use INT4'])
def test_direct_format_commands_survive_nearby_negation(tmp_path, intent):
    with pytest.raises(IntakeNeedsInput, match='precision'):
        prepare_workload(request(intent), tmp_path, agent_factory=Planner, hardware={'backends': ['mlx']})
