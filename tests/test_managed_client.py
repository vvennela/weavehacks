import threading

import pytest
from test_managed_service import TOKEN, wait_for
from test_managed_service import manager as manager_fixture

manager = manager_fixture
from sera import managed_service
from sera.managed_client import Optimize, SeraClient, SeraServiceError


@pytest.fixture
def endpoint(manager):
    server = managed_service.make_server(manager, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()
    server.server_close()
    thread.join()


def test_one_call_returns_verified_checkpoint(manager, endpoint):
    result = Optimize('fixture', api_key=TOKEN, endpoint=endpoint,
                      request_id='one-call', poll_interval=0.02)
    assert result.selected_recipe_id == 'q8'
    assert result.verify()['artifact_id'] == result.artifact_id
    repeated = Optimize('fixture', api_key=TOKEN, endpoint=endpoint,
                        request_id='one-call', poll_interval=0.02)
    assert repeated.job_id == result.job_id
    assert 'fixture-trace' == result.trace_url


def test_client_rejects_wrong_key(endpoint):
    with pytest.raises(SeraServiceError, match='401'):
        Optimize('fixture', api_key='wrong', endpoint=endpoint)


def test_keyboard_interrupt_requests_cancellation(manager, endpoint):
    (manager.folder / 'stall').touch()
    jobs = []
    def stop(job):
        jobs.append(job['job_id'])
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        Optimize('fixture', api_key=TOKEN, endpoint=endpoint, on_update=stop)
    wait_for(lambda: manager.get('one', jobs[0])['status'] == 'cancelled')


def test_progress_callback_failure_cancels_owned_job(manager, endpoint):
    (manager.folder / 'stall').touch()
    jobs = []
    def fail(job):
        jobs.append(job['job_id'])
        raise RuntimeError('Display failed')
    with pytest.raises(RuntimeError, match='Display failed'):
        Optimize('fixture', api_key=TOKEN, endpoint=endpoint, on_update=fail)
    wait_for(lambda: manager.get('one', jobs[0])['status'] == 'cancelled')


def test_client_never_sends_key_to_unencrypted_remote_host():
    with pytest.raises(ValueError, match='loopback'):
        SeraClient(api_key=TOKEN, endpoint='http://example.com')


def test_cuda_result_reloads_with_registered_runtime(monkeypatch):
    from test_cuda_backend import options

    from sera.backends import cuda
    calls = []
    class Backend:
        def __init__(self, runtime):
            assert runtime == options()
        def load(self, artifact, *, expected_id):
            calls.append((artifact, expected_id))
            return 'loaded'
    monkeypatch.setattr(cuda, 'CUDABackend', Backend)
    monkeypatch.setattr(SeraClient, 'submit', lambda *a, **k: {
        'job_id': 'a'*32, 'status': 'completed', 'result': {
            'backend': 'cuda', 'runtime': options(), 'selected_recipe_id': 'fp8',
            'selected_artifact_id': 'b'*64, 'artifact_path': '/checkpoint',
            'elapsed_seconds': 1., 'trace': {'remote_verified': True, 'url': 'fixture-trace'}}})
    result = Optimize('fixture', api_key=TOKEN)
    assert result.load() == 'loaded'
    assert calls == [('/checkpoint', 'b'*64)]


def test_customer_receives_reason_when_confirmed_search_stops_at_budget(monkeypatch):
    monkeypatch.setattr(SeraClient, 'submit', lambda *a, **k: {
        'job_id': 'a'*32, 'status': 'completed', 'result': {
            'selected_recipe_id': 'q8', 'selected_artifact_id': 'b'*64,
            'artifact_path': '/checkpoint', 'elapsed_seconds': 55.,
            'stop_reason': 'budget-exhausted',
            'trace': {'remote_verified': True, 'url': 'fixture-trace'}}})
    result = Optimize('fixture', api_key=TOKEN)
    assert result.stop_reason == 'budget-exhausted'
