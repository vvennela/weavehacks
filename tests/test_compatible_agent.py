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


def mock_http_transport(monkeypatch, handler):
    """Exercise the installed SDK and HTTP client without opening a socket."""
    httpx = pytest.importorskip('httpx')
    pytest.importorskip('openai')
    clients = []
    requests = []

    def handle(request):
        requests.append(request)
        return handler(request)

    class MockClient(httpx.Client):
        def __init__(self, **kwargs):
            super().__init__(transport=httpx.MockTransport(handle), **kwargs)
            clients.append(self)

    monkeypatch.setattr(httpx, 'Client', MockClient)
    return httpx, requests, clients


def completion_body(case):
    return {'id': 'mock-completion', 'object': 'chat.completion', 'created': 0,
        'model': 'gateway-model', 'choices': [{'index': 0, 'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': json.dumps(valid_response(case))}}]}


def test_real_sdk_sends_only_instance_auth_and_bounded_strict_request(monkeypatch):
    case = provider_cases()[0]
    httpx, requests, clients = mock_http_transport(monkeypatch,
        lambda request: httpx.Response(200, json=completion_body(case)))
    monkeypatch.setenv('OPENAI_API_KEY', 'ambient-openai-secret')
    monkeypatch.setenv('OPENAI_ORG_ID', 'ambient-organization')
    monkeypatch.setenv('OPENAI_PROJECT_ID', 'ambient-project')
    monkeypatch.setenv('WANDB_API_KEY', 'weave-only-secret')
    for key in ['first-instance-secret', 'second-instance-secret']:
        assert agent(api_key=key).request(case['role'], case['evidence'], 'Inspect') is not None
    assert [request.headers['authorization'] for request in requests] == [
        'Bearer first-instance-secret', 'Bearer second-instance-secret']
    for request in requests:
        assert str(request.url) == 'https://gateway.example/v1/chat/completions'
        assert not request.headers.get('openai-project')
        assert not request.headers.get('openai-organization')
        assert 'ambient-' not in str(request.headers)
        assert 'weave-only-secret' not in str(request.headers)
        assert json.loads(request.content)['response_format']['json_schema']['strict'] is True
        assert all(0 < value <= 90 for value in request.extensions['timeout'].values())
    assert all(client.is_closed for client in clients)


@pytest.mark.parametrize('destination', [
    'https://elsewhere.example/stolen', 'https://gateway.example/uncertified-route'])
def test_real_sdk_does_not_follow_redirects(monkeypatch, destination):
    httpx, requests, clients = mock_http_transport(monkeypatch,
        lambda request: httpx.Response(307, headers={'location': destination}))
    current = agent()
    assert current.request('arbiter', {'legal_proposal_ids': []}, 'Inspect') is None
    assert len(requests) == 2  # Sera's single retry, never an SDK retry or redirect.
    assert {str(request.url) for request in requests} == {
        'https://gateway.example/v1/chat/completions'}
    assert all(attempt['http_status'] == 307 for attempt in current.history[0]['attempts'])
    assert all(client.is_closed for client in clients)


@pytest.mark.parametrize('status, attempts', [(401, 1), (403, 1), (404, 1), (429, 2), (500, 2)])
def test_real_sdk_http_errors_are_bounded_and_secret_free(monkeypatch, status, attempts):
    httpx, requests, clients = mock_http_transport(monkeypatch,
        lambda request: httpx.Response(status, json={'error': {
            'message': 'test-private-key-a must not enter an audit'}}))
    current = agent()
    assert current.request('arbiter', {'legal_proposal_ids': []}, 'Inspect') is None
    assert len(requests) == attempts
    assert 'test-private-key-a' not in json.dumps(current.history)
    assert all(row['error'] == f'Provider HTTP {status}'
               for row in current.history[0]['attempts'])
    assert all(client.is_closed for client in clients)


def test_real_sdk_timeout_is_bounded_and_secret_free(monkeypatch):
    def timeout(request):
        raise httpx.ReadTimeout('test-private-key-a timeout', request=request)
    httpx, requests, clients = mock_http_transport(monkeypatch, timeout)
    current = agent()
    assert current.request('arbiter', {'legal_proposal_ids': []}, 'Inspect') is None
    assert len(requests) == 2
    assert 'test-private-key-a' not in json.dumps(current.history)
    assert all(row['error'] == 'APITimeoutError' for row in current.history[0]['attempts'])
    assert all(client.is_closed for client in clients)


@pytest.mark.parametrize('echoed_secret', ['test-private-key-a', 'weave-only-secret'])
def test_real_sdk_success_does_not_record_echoed_credentials(monkeypatch, echoed_secret):
    case = provider_cases()[0]
    body = completion_body(case)
    body['gateway_debug'] = echoed_secret
    monkeypatch.setenv('WANDB_API_KEY', 'weave-only-secret')
    httpx, requests, clients = mock_http_transport(monkeypatch,
        lambda request: httpx.Response(200, json=body))
    current = agent()
    assert current.request(case['role'], case['evidence'], 'Inspect') is None
    assert len(requests) == 2
    assert echoed_secret not in json.dumps(current.history)
    assert all(row['error'] == 'Provider response contains a credential'
               for row in current.history[0]['attempts'])
    assert all(client.is_closed for client in clients)


@pytest.mark.parametrize('response_kind', ['html', 'json-array', 'json-string'])
def test_real_sdk_malformed_success_fails_closed_without_secret_leak(monkeypatch, response_kind):
    def response(request):
        if response_kind == 'html':
            return httpx.Response(200, text='<html>test-private-key-a</html>')
        body = [] if response_kind == 'json-array' else 'test-private-key-a'
        return httpx.Response(200, json=body)
    httpx, requests, clients = mock_http_transport(monkeypatch, response)
    current = agent()
    assert current.request('arbiter', {'legal_proposal_ids': []}, 'Inspect') is None
    assert len(requests) == 2
    assert 'test-private-key-a' not in json.dumps(current.history)
    assert all(client.is_closed for client in clients)
