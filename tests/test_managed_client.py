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
    assert result.measurements['baseline']['peak_bytes'] == 100
    selected = next(t for t in result.measurements['trials'] if t['recipe_id'] == 'q8')
    assert selected['accepted'] is True
    assert selected['confirmation']['peak_bytes'] == 60
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


def test_lost_submit_response_preserves_generated_request_id(monkeypatch):
    submitted = []
    def lost(self, profile_id, *, request_id):
        submitted.append(request_id)
        raise SeraServiceError('Connection lost after acceptance')
    monkeypatch.setattr(SeraClient, 'submit', lost)
    with pytest.raises(SeraServiceError) as caught:
        Optimize('fixture', api_key=TOKEN)
    assert caught.value.request_id == submitted[0]
    assert submitted[0] in str(caught.value)
    assert TOKEN not in str(caught.value)


def test_required_format_failure_is_explicit_and_keeps_baseline_access(monkeypatch):
    from sera import SeraRequirementsNotMet
    monkeypatch.setattr(SeraClient, 'submit_intent', lambda *args, **kwargs: {
        'job_id': 'a'*32, 'status': 'completed', 'result': {
            'selected_recipe_id': 'baseline', 'selected_artifact_id': 'b'*64,
            'artifact_path': '/baseline', 'trace': {'remote_verified': True, 'url': 'fixture'},
            'elapsed_seconds': 1., 'requirements': {'required_precision': 'int4', 'met': False}}})
    with pytest.raises(SeraRequirementsNotMet) as error:
        Optimize('Run at INT4', api_key=TOKEN)
    assert error.value.result.selected_recipe_id == 'baseline'


def test_baseline_failure_explains_the_customer_action(monkeypatch):
    monkeypatch.setattr(SeraClient, 'submit_intent', lambda *args, **kwargs: {
        'job_id': 'a'*32, 'status': 'failed', 'progress': {'research_status': 'baseline-failed'}})
    with pytest.raises(SeraServiceError, match='Baseline failed the workload checks'):
        Optimize('Optimize ticket classification', api_key=TOKEN)
