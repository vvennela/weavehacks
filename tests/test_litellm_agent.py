"""The LiteLLM route changes transport, not Sera's decision authority."""

import json
import sys
from types import SimpleNamespace

import pytest

from sera.agent import request_schema, schema_hash
from sera.litellm_agent import LiteLLMAgent
from sera.provider_check import check_provider, provider_cases, require_provider_check
from test_provider_check import valid_response


def agent(**kwargs):
    return LiteLLMAgent(project='test/project', api_key='instance-secret', **kwargs)


def install_transport(monkeypatch, complete):
    monkeypatch.setitem(sys.modules, 'litellm', SimpleNamespace(completion=complete))


def body(case):
    return {'choices': [{'finish_reason': 'stop', 'message': {
        'content': json.dumps(valid_response(case))}}]}


def test_fixed_openai_route_profile_and_fork_isolation(monkeypatch):
    case = provider_cases()[0]
    calls = []
    def complete(**kwargs):
        calls.append(kwargs)
        return body(case)
    install_transport(monkeypatch, complete)
    monkeypatch.setenv('OPENAI_API_KEY', 'ambient-secret')
    current = agent()
    children = [current.fork() for _ in range(3)]
    for child in children:
        assert child.request(case['role'], case['evidence'], 'Inspect') is not None
    assert not current.history
    assert len({id(child.history) for child in children}) == 3
    for call in calls:
        assert call['model'] == 'openai/gpt-6-astra'
        assert call['api_base'] == 'https://api.openai.com/v1'
        assert call['api_key'] == 'instance-secret'
        assert call['max_completion_tokens'] == 2048
        assert call['reasoning_effort'] == 'low'
        assert call['allowed_openai_params'] == ['reasoning_effort']
        assert call['num_retries'] == 0 and call['timeout'] == 90
        assert 'temperature' not in call and 'max_tokens' not in call
        assert call['response_format']['json_schema']['strict'] is True
    assert 'instance-secret' not in repr(current.__dict__)
    assert 'instance-secret' not in json.dumps([child.history for child in children])


def test_key_source_is_openai_only(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setenv('WANDB_API_KEY', 'not-openai')
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        LiteLLMAgent(project='test/project')
    monkeypatch.setenv('OPENAI_API_KEY', 'openai-secret')
    assert LiteLLMAgent(project='test/project', model='other-openai-id').model == 'other-openai-id'


@pytest.mark.parametrize('model', ['', 'openai/model', 'anthropic/model', ' model ', None])
def test_model_id_cannot_override_provider_route(model):
    with pytest.raises(ValueError, match='model'):
        agent(model=model)


def test_wire_schema_removes_only_root_anyof_and_keeps_local_validation(monkeypatch):
    case = provider_cases()[0]
    current = agent()
    original = request_schema('proposal', case['evidence'])
    expected = dict(original)
    expected.pop('anyOf')
    assert current.wire_schema('proposal', case['evidence']) == expected
    assert 'anyOf' in request_schema('proposal', case['evidence'])
    invalid = valid_response(case) | {'expected_trial_cost': 0}
    install_transport(monkeypatch, lambda **kwargs: {'choices': [{'finish_reason': 'stop',
        'message': {'content': json.dumps(invalid)}}]})
    assert current.request('proposal', case['evidence'], 'Inspect') is None
    assert all(not row['schema_valid'] for row in current.history[0]['attempts'])
    assert current.history[0]['request_schema'] == expected


@pytest.mark.parametrize('status, count', [(401, 1), (403, 1), (429, 2), (500, 2), (None, 2)])
def test_provider_errors_are_safe_and_bounded(monkeypatch, status, count):
    calls = []
    def complete(**kwargs):
        calls.append(kwargs)
        error = RuntimeError('instance-secret arbitrary provider body')
        error.status_code = status
        raise error
    install_transport(monkeypatch, complete)
    current = agent()
    assert current.request('arbiter', {'legal_proposal_ids': []}, 'Inspect') is None
    assert len(calls) == count
    assert 'instance-secret' not in json.dumps(current.history)


@pytest.mark.parametrize('response', ['instance-secret', [], {'debug': 'instance-secret'},
    {'choices': [{'finish_reason': 'stop', 'message': {'content': 'instance-secret'}}]}])
def test_malformed_or_secret_response_is_not_saved(monkeypatch, response):
    install_transport(monkeypatch, lambda **kwargs: response)
    current = agent()
    assert current.request('arbiter', {'legal_proposal_ids': []}, 'Inspect') is None
    assert 'instance-secret' not in json.dumps(current.history)


def test_certificate_binds_actual_wire_schema_and_wrapper(monkeypatch, tmp_path):
    cases = iter(provider_cases())
    install_transport(monkeypatch, lambda **kwargs: body(next(cases)))
    current = agent()
    record = check_provider(project=current.project, model=current.model, agent=current,
                            output_dir=tmp_path/'certificate')
    assert record['passed'] and record['schema_hash'] == schema_hash()
    path = tmp_path/'certificate'/'result.json'
    from sera.weave_integration import TracedInvestigationAgent
    weave = SimpleNamespace(op=lambda fn=None, **kwargs: fn if fn else lambda actual: actual)
    wrapped = TracedInvestigationAgent(agent(), weave)
    assert wrapped.fork().wire_schema('proposal', provider_cases()[0]['evidence']) == (
        current.wire_schema('proposal', provider_cases()[0]['evidence']))
    assert require_provider_check(path, wrapped)['valid_with_one_retry'] == 34
    record['requests'][0]['request_schema'] = request_schema('proposal', provider_cases()[0]['evidence'])
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='schema'):
        require_provider_check(path, agent())
