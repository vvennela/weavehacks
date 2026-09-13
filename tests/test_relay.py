import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from sera.agent import WandbAgent
from sera.relay import RelayAgent, pending_requests, publish_response, response_status


def test_response_reconciliation_distinguishes_missing_matching_and_conflicting(tmp_path):
    request_id = 'a' * 32
    record = dict(request_id=request_id, provider='codex-relay', model='gpt-5.6-luna',
                  project='test/project', payload=payload(), expires_at=time.time() + 60)
    path = tmp_path / f'{request_id}.request.json'
    path.write_text(json.dumps(record))
    assert response_status(tmp_path, request_id, body=envelope()) == 'pending'
    publish_response(tmp_path, request_id, body=envelope())
    before = (tmp_path / f'{request_id}.response.json').read_bytes()
    assert response_status(tmp_path, request_id, body=envelope()) == 'published'
    assert response_status(tmp_path, request_id, error='timeout') == 'conflict'
    record['expires_at'] = 1
    path.write_text(json.dumps(record))
    assert response_status(tmp_path, request_id, body=envelope()) == 'published'
    assert (tmp_path / f'{request_id}.response.json').read_bytes() == before


def test_reconciliation_never_creates_expired_or_missing_response(tmp_path):
    request_id = 'a' * 32
    record = dict(request_id=request_id, provider='codex-relay', model='gpt-5.6-luna',
                  project='test/project', payload=payload(), expires_at=1)
    (tmp_path / f'{request_id}.request.json').write_text(json.dumps(record))
    assert response_status(tmp_path, request_id, error='timeout') == 'expired'
    assert not list(tmp_path.glob('*.response.json'))


def payload(model='gpt-5.6-luna'):
    return {'model': model, 'messages': [{'role': 'user', 'content': 'Measured evidence'}]}


def envelope(model='gpt-5.6-luna', content=None):
    return {'model': model, 'choices': [{'finish_reason': 'stop', 'message': {
        'role': 'assistant', 'content': json.dumps(content or {
            'ranked_proposal_ids': [], 'reason': 'No useful legal trial remains.'})}}]}


def wait_pending(path, count=1):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        records = pending_requests(path)
        if len(records) == count:
            return records
        time.sleep(.005)
    pytest.fail('Relay request was not published')


def test_relay_keeps_shared_prompt_parser_and_audit_without_wandb_key(tmp_path, monkeypatch):
    monkeypatch.delenv('WANDB_API_KEY', raising=False)
    seen = []
    baseline = WandbAgent(project='test/project', model='gpt-5.6-luna')
    monkeypatch.setattr(baseline, '_complete', lambda body: seen.append(body) or envelope())
    expected = baseline.request('arbiter', {'proposals': []}, 'Select a trial.')
    agent = RelayAgent(project='test/project', model='gpt-5.6-luna', relay_dir=tmp_path)
    with ThreadPoolExecutor() as pool:
        result = pool.submit(agent.request, 'arbiter', {'proposals': []}, 'Select a trial.')
        request = wait_pending(tmp_path)[0]
        assert request['payload'] == seen[0]
        publish_response(tmp_path, request['request_id'], body=envelope())
        assert result.result(timeout=2) == expected
    entry = agent.history[0]
    assert entry['provider'] == 'codex-relay'
    assert entry['messages'] == baseline.history[0]['messages']
    assert len(entry['attempts']) == 1
    assert entry['attempts'][0]['raw_response']['provider'] == 'codex-relay'
    assert entry['attempts'][0]['raw_response']['synthetic'] is True
    assert baseline.history[0]['provider'] == 'wandb'
    assert pending_requests(tmp_path) == []


def test_forks_publish_independent_concurrent_requests(tmp_path):
    parent = RelayAgent(project='test/project', model='gpt-6-astra', relay_dir=tmp_path)
    children = [parent.fork() for _ in range(3)]
    assert all(child.history == [] and child.history is not parent.history for child in children)
    with ThreadPoolExecutor() as pool:
        futures = [pool.submit(child.request, 'arbiter', {}, 'Select.') for child in children]
        requests = wait_pending(tmp_path, 3)
        assert len({record['request_id'] for record in requests}) == 3
        for record in requests:
            assert record['model'] == 'gpt-6-astra'
            publish_response(tmp_path, record['request_id'], body=envelope('gpt-6-astra'))
        assert all(future.result(timeout=2) is not None for future in futures)
    assert parent.history == []
    assert all(len(child.history) == 1 for child in children)


def test_invalid_structured_output_has_only_two_attempts(tmp_path):
    agent = RelayAgent(project='test/project', model='gpt-5.6-luna', relay_dir=tmp_path)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(agent.request, 'arbiter', {}, 'Select.')
        for _ in range(2):
            record = wait_pending(tmp_path)[0]
            publish_response(tmp_path, record['request_id'], body=envelope(content={'invalid': True}))
        assert future.result(timeout=2) is None
    assert len(agent.history[0]['attempts']) == 2
    assert pending_requests(tmp_path) == []


def test_timeout_excludes_stale_requests_and_rejects_late_response(tmp_path):
    agent = RelayAgent(project='test/project', model='gpt-5.6-luna', relay_dir=tmp_path,
                       timeout=.02, poll_interval=.001)
    with pytest.raises(TimeoutError):
        agent._complete(payload())
    assert pending_requests(tmp_path) == []
    request_id = next(tmp_path.glob('*.request.json')).name.split('.')[0]
    with pytest.raises(ValueError, match='expired'):
        publish_response(tmp_path, request_id, body=envelope())


@pytest.mark.parametrize('change', [
    {'request_id': 'a' * 32, 'body': envelope()},
    {'body': envelope('gpt-6-astra')},
    {'body': {'model': 'gpt-5.6-luna', 'choices': []}},
    {'error': 'arbitrary secret stderr'},
])
def test_complete_rejects_malformed_or_mismatched_response(tmp_path, change):
    agent = RelayAgent(project='test/project', model='gpt-5.6-luna', relay_dir=tmp_path)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(agent._complete, payload())
        record = wait_pending(tmp_path)[0]
        response = {'request_id': record['request_id']} | change
        (tmp_path / f"{record['request_id']}.response.json").write_text(json.dumps(response))
        with pytest.raises(ValueError):
            future.result(timeout=2)


def test_publish_is_atomic_non_overwriting_and_validates_model(tmp_path):
    agent = RelayAgent(project='test/project', model='gpt-5.6-luna', relay_dir=tmp_path)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(agent._complete, payload())
        record = wait_pending(tmp_path)[0]
        request_id = record['request_id']
        with pytest.raises(ValueError):
            publish_response(tmp_path, request_id, body=envelope('gpt-6-astra'))
        publish_response(tmp_path, request_id, body=envelope())
        with pytest.raises(FileExistsError):
            publish_response(tmp_path, request_id, body=envelope())
        assert future.result(timeout=2)['synthetic'] is True


@pytest.mark.parametrize('request_id', ['../escape', '/tmp/escape', 'A' * 32, 'z' * 32, ''])
def test_publish_rejects_paths_and_unknown_request(tmp_path, request_id):
    with pytest.raises(ValueError):
        publish_response(tmp_path, request_id, body=envelope())


def test_helpers_reject_symlinks_and_ignore_malformed_requests(tmp_path):
    outside = tmp_path / 'outside.json'
    outside.write_text('{}')
    (tmp_path / f"{'a' * 32}.request.json").symlink_to(outside)
    (tmp_path / f"{'b' * 32}.request.json").write_text('not-json')
    os.mkfifo(tmp_path / f"{'c' * 32}.request.json")
    assert pending_requests(tmp_path) == []
    with pytest.raises((ValueError, OSError)):
        publish_response(tmp_path, 'a' * 32, body=envelope())
    linked_dir = tmp_path / 'linked'
    linked_dir.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        RelayAgent(project='test/project', model='gpt-5.6-luna', relay_dir=linked_dir)


def test_response_symlink_is_not_read(tmp_path):
    agent = RelayAgent(project='test/project', model='gpt-5.6-luna', relay_dir=tmp_path)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(agent._complete, payload())
        request = wait_pending(tmp_path)[0]
        outside = tmp_path / 'outside.json'
        outside.write_text(json.dumps({'request_id': request['request_id'], 'body': envelope()}))
        (tmp_path / f"{request['request_id']}.response.json").symlink_to(outside)
        with pytest.raises(OSError):
            future.result(timeout=2)


@pytest.mark.parametrize('kwargs', [
    {'model': 'openai/gpt-oss-120b'}, {'timeout': 0}, {'timeout': float('inf')},
    {'poll_interval': 0},
])
def test_relay_rejects_unsupported_model_or_unbounded_wait(tmp_path, kwargs):
    with pytest.raises(ValueError):
        RelayAgent(**({'project': 'test/project', 'model': 'gpt-5.6-luna',
                       'relay_dir': tmp_path} | kwargs))


@pytest.mark.parametrize('status, attempts', [(401, 1), (403, 1), (404, 1), (500, 2)])
def test_wandb_transport_preserves_safe_http_errors_and_retry_limits(monkeypatch, status, attempts):
    class APIStatusError(Exception):
        status_code = status

    class APIConnectionError(Exception):
        pass

    def fail(**kwargs):
        raise APIStatusError('Secret headers and arbitrary provider body must not be logged')

    monkeypatch.setenv('WANDB_API_KEY', 'secret-fixture-not-a-real-key')
    monkeypatch.setitem(sys.modules, 'openai', SimpleNamespace(
        OpenAI=fail, APIStatusError=APIStatusError, APIConnectionError=APIConnectionError))
    agent = WandbAgent(project='test/project')
    assert agent.request('arbiter', {}, 'Select.') is None
    records = agent.history[0]['attempts']
    assert len(records) == attempts
    assert all(record['http_status'] == status and record['error'] == f'Provider HTTP {status}'
               for record in records)
    assert 'secret' not in json.dumps(agent.history).lower()


def test_safe_controller_error_is_recorded_without_raw_stderr(tmp_path):
    agent = RelayAgent(project='test/project', model='gpt-5.6-luna', relay_dir=tmp_path)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(agent.request, 'arbiter', {}, 'Select.')
        for _ in range(2):
            record = wait_pending(tmp_path)[0]
            publish_response(tmp_path, record['request_id'], error='model-unavailable')
        assert future.result(timeout=2) is None
    assert [attempt['error'] for attempt in agent.history[0]['attempts']] == [
        'Codex relay model-unavailable', 'Codex relay model-unavailable']
