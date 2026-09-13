"""Requested output types constrain syntax, never the correct answer."""

from copy import deepcopy
import json

import pytest

from benchmarks.grade import grade_case, load_cases
from sera.config import MODEL_ID
from tests.test_structured_quality_pilot import fake_runtime


def test_schema_uses_only_prompt_requested_types_not_answers():
    from experiments.requested_answer_types import response_format_for_prompt
    cases = load_cases('benchmarks/easy_cases.json')
    types = []
    for case in cases:
        original = response_format_for_prompt(case['prompt'])
        changed = deepcopy(case)
        changed.update(expected={'secret': 'SENTINEL'}, rationale='SENTINEL', id='SENTINEL')
        assert response_format_for_prompt(changed['prompt']) == original
        schema = original['json_schema']['schema']
        types.append(schema['properties']['answer'])
        assert schema['required'] == ['answer']
        assert schema['additionalProperties'] is False
        assert not any(key in json.dumps(schema) for key in ('SENTINEL', 'const', 'enum', 'maxItems', 'minItems'))
    assert types == [{'type': 'integer'}] * 6 + [
        {'type': 'array', 'items': {'type': 'string'}}, {'type': 'string'}]
    changed_input = cases[6]['prompt'].replace('"a"', '"different"').replace('"b"', '"other"')
    assert response_format_for_prompt(changed_input) == response_format_for_prompt(cases[6]['prompt'])


@pytest.mark.parametrize('prompt', ['Return JSON.', 'Return the array.',
    'Records: [{"id":1}]. Return the IDs. Put the array in a JSON object.'])
def test_unspecified_or_mixed_types_fail_without_guessing(prompt):
    from experiments.requested_answer_types import response_format_for_prompt
    with pytest.raises(ValueError):
        response_format_for_prompt(prompt)


def test_typed_profile_keeps_all_tasks_gate_and_one_request_per_case(monkeypatch, tmp_path):
    from experiments.run_structured_quality_pilot import run_pilot
    from experiments.requested_answer_types import response_format_for_prompt
    cases = load_cases('benchmarks/easy_cases.json')
    responses = [json.dumps({'answer': case['expected']}) for case in cases]
    responses[6] = '{"answer":["a","b"]}'
    state = fake_runtime(monkeypatch, responses)
    report = run_pilot(model_id=MODEL_ID, output_dir=tmp_path / 'typed', requested_types=True)
    assert report['profile_version'] == 'sera-easy-requested-types-v1'
    assert report['evaluation_cases'] == cases
    assert report['quality_floor'] == .99
    assert report['task_quality']['correct'] == 7
    assert report['status'] == 'fail'
    assert len(state['requests']) == 8
    for case, payload in zip(cases, state['requests']):
        assert payload['messages'][1]['content'] == case['prompt']
        assert payload['response_format'] == response_format_for_prompt(case['prompt'])
        assert 'expected' not in payload and 'rationale' not in payload
    assert report['requests'][6]['response']['text'] == responses[6]
    assert report['requests'][6]['grade'] == grade_case(cases[6], responses[6])
    assert len(state['started']) == len(state['closed']) == 1


def test_cli_selects_typed_profile_explicitly(monkeypatch, tmp_path):
    from experiments import run_structured_quality_pilot as pilot
    captured = {}

    def run(**kwargs):
        captured.update(kwargs)
        return {'status': 'pass', 'task_quality': {'correct': 8}}

    monkeypatch.setattr(pilot, 'run_pilot', run)
    assert pilot.main(['--model-id', MODEL_ID, '--output-dir', str(tmp_path / 'typed'),
                       '--requested-types']) == 0
    assert captured['requested_types'] is True
    assert captured['quantization'] is None
