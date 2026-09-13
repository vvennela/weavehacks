"""A new decoding profile must not change the questions or repair answers."""

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from benchmarks.grade import SYSTEM_PROMPT, grade_case, load_cases
from sera.config import GLM_MODEL_ID, GLM_MODEL_REVISION, MODEL_ID, MODEL_REVISION, RuntimeConfig
from sera.runtime import GENERATION, SeraModel


def pilot_module():
    from experiments import run_structured_quality_pilot
    return run_structured_quality_pilot


def fake_runtime(monkeypatch, responses=None, *, startup_error=False, cleanup_error=False,
                 invalid_tokens=False, finish_reason='stop'):
    cases = load_cases(Path(__file__).resolve().parents[1] / 'benchmarks/easy_cases.json')
    outputs = responses or [json.dumps({'answer': case['expected']}) for case in cases]
    state = {'started': [], 'closed': [], 'requests': [], 'bodies': []}

    def start(self):
        state['started'].append(self)
        if startup_error:
            raise RuntimeError('Startup failed')
        self._ready = True
        self.process = SimpleNamespace(poll=lambda: None)
        self.record['status'] = 'ready'
        return self

    def close(self):
        state['closed'].append(self)
        self.record['cleanup_pass'] = not cleanup_error
        if cleanup_error:
            raise RuntimeError('Cleanup failed')
        return self.record

    def request(self, route, payload=None, timeout=90):
        if route == '/tokenize':
            return {'tokens': [1, 2, 3]}
        assert route == '/v1/chat/completions'
        state['requests'].append(deepcopy(payload))
        output = outputs[len(state['requests']) - 1]
        if isinstance(output, Exception):
            raise output
        body = {'choices': [{'message': {'content': output}, 'token_ids': None if invalid_tokens else [4, 5],
                             'finish_reason': finish_reason}], 'prompt_token_ids': [1, 2, 3],
                'prompt_text': 'rendered prompt',
                'usage': {'prompt_tokens': 3, 'completion_tokens': 2}, 'extra_field': 'retain me'}
        state['bodies'].append(deepcopy(body))
        return body

    monkeypatch.setattr(SeraModel, 'start', start)
    monkeypatch.setattr(SeraModel, 'close', close)
    monkeypatch.setattr(SeraModel, '_request', request)
    return state


@pytest.mark.parametrize('model_id,revision', [(MODEL_ID, MODEL_REVISION), (GLM_MODEL_ID, GLM_MODEL_REVISION)])
def test_pilot_keeps_original_eight_questions_generation_and_pinned_bf16(monkeypatch, tmp_path, model_id, revision):
    pilot = pilot_module()
    state = fake_runtime(monkeypatch)
    report = pilot.run_pilot(model_id=model_id, output_dir=tmp_path / 'new-profile')
    cases = load_cases(Path(__file__).resolve().parents[1] / 'benchmarks/easy_cases.json')
    assert report['profile_version'] == 'sera-easy-structured-json-v1'
    assert report['evaluation_cases'] == cases
    assert len(report['requests']) == len(state['requests']) == 8
    assert report['quality_floor'] == .99
    assert report['status'] == 'pass'
    assert len(state['started']) == len(state['closed']) == 1
    model = state['started'][0]
    assert model.model_id == model_id and model.revision == revision
    assert model.configuration == RuntimeConfig()
    for case, payload, saved, body in zip(cases, state['requests'], report['requests'], state['bodies']):
        assert payload['messages'] == [{'role': 'system', 'content': SYSTEM_PROMPT},
                                        {'role': 'user', 'content': case['prompt']}]
        assert {key: payload[key] for key in GENERATION} == GENERATION
        assert payload['chat_template_kwargs'] == {'enable_thinking': False}
        assert payload['response_format'] == pilot.response_format()
        assert saved['exchange']['raw_response'] == body
        assert saved['exchange']['request'] == payload
        assert saved['response']['text'] == body['choices'][0]['message']['content']
        assert saved['response']['latency_ms'] >= 0
        assert saved['grade'] == grade_case(case, saved['response']['text'])
    assert json.loads((tmp_path / 'new-profile/result.json').read_text()) == report


def test_schema_is_general_and_answer_key_independent():
    pilot = pilot_module()
    before = pilot.response_format()
    schema = before['json_schema']['schema']
    assert schema['required'] == ['answer'] and schema['additionalProperties'] is False
    assert set(schema['properties']) == {'answer'}
    serialized = json.dumps(schema)
    assert 'const' not in serialized and 'enum' not in serialized
    assert schema['properties']['answer']['type'] == ['string', 'number', 'boolean', 'null', 'array', 'object']
    before['json_schema']['schema']['properties']['answer'] = {'const': 'leaked answer'}
    assert pilot.response_format()['json_schema']['schema'] == schema | {
        'properties': {'answer': {'type': ['string', 'number', 'boolean', 'null', 'array', 'object']}}}


@pytest.mark.parametrize('output,format_valid', [
    ('```json\n{"answer": 5}\n```', False),
    ('{"answer": 5}"}', False),
    ('{"answer": 4}', True),
])
def test_wrong_and_malformed_outputs_fail_without_repair(monkeypatch, tmp_path, output, format_valid):
    pilot = pilot_module()
    state = fake_runtime(monkeypatch, [output] * 8)
    report = pilot.run_pilot(model_id=MODEL_ID, output_dir=tmp_path / 'pilot')
    first = report['requests'][0]
    assert first['response']['text'] == output
    assert first['grade']['passed'] is False
    assert first['grade']['format_valid'] is format_valid
    assert first['failure_kind'] == ('semantic' if format_valid else 'format')
    assert report['status'] == 'fail'
    assert len(state['closed']) == 1


@pytest.mark.parametrize('startup_error,cleanup_error', [(True, False), (False, True)])
def test_owned_runtime_cleanup_failure_or_startup_failure_cannot_pass(monkeypatch, tmp_path, startup_error, cleanup_error):
    pilot = pilot_module()
    state = fake_runtime(monkeypatch, startup_error=startup_error, cleanup_error=cleanup_error)
    report = pilot.run_pilot(model_id=MODEL_ID, output_dir=tmp_path / 'pilot')
    assert report['status'] == 'fail'
    assert len(state['started']) == len(state['closed']) == 1
    assert (tmp_path / 'pilot/result.json').exists()


def test_generation_failure_is_preserved_and_never_retried(monkeypatch, tmp_path):
    pilot = pilot_module()
    state = fake_runtime(monkeypatch, [RuntimeError('Bad response')] * 8)
    report = pilot.run_pilot(model_id=MODEL_ID, output_dir=tmp_path / 'pilot')
    assert report['status'] == 'fail'
    assert len(state['requests']) == len(report['requests']) == 8
    assert all(row['failure_kind'] == 'generation' for row in report['requests'])
    assert len(state['closed']) == 1


def test_existing_evidence_and_unapproved_model_are_rejected_before_start(monkeypatch, tmp_path):
    pilot = pilot_module()
    state = fake_runtime(monkeypatch)
    with pytest.raises(FileExistsError):
        pilot.run_pilot(model_id=MODEL_ID, output_dir=tmp_path)
    with pytest.raises(ValueError, match='model'):
        pilot.run_pilot(model_id='different/model', output_dir=tmp_path / 'other')
    assert not state['started']


def test_invalid_runtime_response_is_saved_before_runtime_validation_fails(monkeypatch, tmp_path):
    pilot = pilot_module()
    state = fake_runtime(monkeypatch, invalid_tokens=True)
    report = pilot.run_pilot(model_id=MODEL_ID, output_dir=tmp_path / 'pilot')
    assert report['status'] == 'fail'
    assert report['requests'][0]['exchange']['raw_response'] == state['bodies'][0]
    assert report['requests'][0]['failure_kind'] == 'generation'


def test_token_limit_finish_cannot_pass_even_when_raw_json_is_correct(monkeypatch, tmp_path):
    pilot = pilot_module()
    fake_runtime(monkeypatch, finish_reason='length')
    report = pilot.run_pilot(model_id=MODEL_ID, output_dir=tmp_path / 'pilot')
    assert report['status'] == 'fail'
    assert report['requests'][0]['grade']['passed'] is True
    assert report['requests'][0]['task_pass'] is False
    assert report['requests'][0]['failure_kind'] == 'generation'


def test_http_error_body_is_saved_without_retry(monkeypatch, tmp_path):
    import io
    import urllib.error
    pilot = pilot_module()
    errors = [urllib.error.HTTPError('http://localhost', 400, 'Bad Request', {},
              io.BytesIO(b'{"error":"unsupported schema"}')) for _ in range(8)]
    state = fake_runtime(monkeypatch, errors)
    report = pilot.run_pilot(model_id=MODEL_ID, output_dir=tmp_path / 'pilot')
    assert report['status'] == 'fail'
    exchange = report['requests'][0]['exchange']
    assert exchange['http_status'] == 400
    assert exchange['raw_error_body'] == '{"error":"unsupported schema"}'
    assert len(state['requests']) == 8


def test_changed_answer_key_requires_new_profile_and_no_start(monkeypatch, tmp_path):
    pilot = pilot_module()
    state = fake_runtime(monkeypatch)
    cases = load_cases(Path(__file__).resolve().parents[1] / 'benchmarks/easy_cases.json')
    cases[0]['expected'] = 99
    monkeypatch.setattr(pilot, 'load_cases', lambda _: cases)
    with pytest.raises(ValueError, match='dataset changed'):
        pilot.run_pilot(model_id=MODEL_ID, output_dir=tmp_path / 'pilot')
    assert not state['started']
