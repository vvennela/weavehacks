"""Compatible providers keep the same swarm contract without sharing user keys."""

import json
import sys
from types import SimpleNamespace

import pytest

from sera.agent import OpenAICompatibleAgent
from sera.provider_check import check_provider, provider_cases, require_provider_check
from test_provider_check import valid_response


def agent(**options):
    return OpenAICompatibleAgent(project='test/project', model='gateway-model',
        base_url=options.pop('base_url', 'https://gateway.example/v1'),
        api_key=options.pop('api_key', 'test-private-key-a'), **options)


def sdk(monkeypatch, response):
    seen = []
    class Client:
        def __init__(self, **kwargs):
            seen.append(kwargs)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        def create(self, **payload):
            seen[-1]['payload'] = payload
            return SimpleNamespace(model_dump=lambda **_: response)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    monkeypatch.setitem(sys.modules, 'openai', SimpleNamespace(OpenAI=Client,
        APIStatusError=type('StatusError', (Exception,), {}),
        APIConnectionError=type('ConnectionError', (Exception,), {})))
    monkeypatch.setitem(sys.modules, 'httpx', SimpleNamespace(Client=lambda **kwargs: kwargs))
    return seen


def test_instances_and_forks_keep_keys_separate_and_preserve_strict_schema(monkeypatch):
    case = provider_cases()[0]
    response = {'choices': [{'finish_reason': 'stop',
                            'message': {'content': json.dumps(valid_response(case))}}]}
    seen = sdk(monkeypatch, response)
    first, second = agent(), agent(api_key='test-private-key-b')
    children = [first.fork() for _ in range(3)]
    for child in [*children, second]:
        assert child.request(case['role'], case['evidence'], 'Investigate') is not None
    assert [row['api_key'] for row in seen] == ['test-private-key-a'] * 3 + ['test-private-key-b']
    assert all(row['base_url'] == 'https://gateway.example/v1' for row in seen)
    assert all(row['project'] == row['organization'] == '' for row in seen)
    assert all(row['http_client']['follow_redirects'] is False for row in seen)
    assert all(row['payload']['response_format']['json_schema']['strict'] for row in seen)
    assert first.history == [] and len({id(child.history) for child in children}) == 3
    assert 'test-private-key' not in repr(first.__dict__)
    assert 'test-private-key' not in json.dumps([child.history for child in children])


@pytest.mark.parametrize('url', ['http://gateway.example/v1', 'https://u:secret@gateway.example/v1',
    'https://gateway.example/v1?api_key=secret', 'https://gateway.example/v1#secret',
    'file:///secret', 'https://', 'https://gateway.example:bad/v1'])
def test_unsafe_endpoint_rejected_before_request(url):
    with pytest.raises(ValueError):
        agent(base_url=url)


def test_missing_key_fails_before_any_request(monkeypatch):
    monkeypatch.delenv('SERA_AGENT_API_KEY', raising=False)
    with pytest.raises(ValueError, match='SERA_AGENT_API_KEY'):
        agent(api_key=None)


def test_echoed_secret_never_enters_audit(monkeypatch):
    response = {'choices': [{'finish_reason': 'stop', 'message': {
        'content': '{"ranked_proposal_ids": [], "reason": "test-private-key-a"}'}}]}
    sdk(monkeypatch, response)
    current = agent()
    current.request('arbiter', {'legal_proposal_ids': []}, 'Inspect')
    assert 'test-private-key-a' not in json.dumps(current.history)


def test_certificate_binds_endpoint_and_each_request(monkeypatch, tmp_path):
    current = agent()
    cases = iter(provider_cases())
    monkeypatch.setattr(current, '_complete', lambda payload: {'choices': [{'finish_reason': 'stop',
        'message': {'content': json.dumps(valid_response(next(cases)))}}]})
    record = check_provider(project=current.project, model=current.model, agent=current,
                            output_dir=tmp_path/'check')
    path = tmp_path/'check'/'result.json'
    assert record['passed']
    assert require_provider_check(path, agent())['valid_with_one_retry'] == 34
    from sera.weave_integration import TracedInvestigationAgent
    weave = SimpleNamespace(op=lambda fn=None, **kwargs: fn if fn else lambda actual: actual)
    wrapped = TracedInvestigationAgent(agent(), weave)
    assert require_provider_check(path, wrapped)['endpoint_fingerprint'] == current.endpoint_fingerprint
    assert wrapped.fork().endpoint_fingerprint == current.endpoint_fingerprint
    with pytest.raises(ValueError, match='endpoint'):
        require_provider_check(path, agent(base_url='https://other.example/v1'))
    record['requests'][0]['endpoint_fingerprint'] = 'another-endpoint'
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='endpoint'):
        require_provider_check(path, agent())


def test_configured_route_reads_own_key_not_weave_key(monkeypatch):
    from sera.api import _configured_agent
    for key, value in {'SERA_AGENT_PROVIDER': 'openai-compatible', 'SERA_AGENT_MODEL': 'chosen',
        'SERA_PROJECT': 'test/project', 'SERA_AGENT_BASE_URL': 'https://gateway.example/v1',
        'SERA_AGENT_API_KEY': 'test-private-key-a', 'WANDB_API_KEY': 'weave-only'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv('SERA_RELAY_DIR', raising=False)
    current = _configured_agent()
    assert isinstance(current, OpenAICompatibleAgent) and current.model == 'chosen'


def test_cli_selects_compatible_route_without_key_argument(monkeypatch, tmp_path):
    from sera import provider_check
    monkeypatch.setenv('SERA_AGENT_API_KEY', 'test-private-key-a')
    seen = {}
    monkeypatch.setattr(provider_check, 'check_provider', lambda **kwargs: seen.update(kwargs) or
        dict(passed=True, first_pass_valid=34, valid_with_one_retry=34))
    assert provider_check.main(['--provider', 'openai-compatible', '--base-url',
        'https://gateway.example/v1', '--model', 'chosen', '--project', 'test/project',
        '--output-dir', str(tmp_path/'check')]) == 0
    assert isinstance(seen['agent'], OpenAICompatibleAgent)
