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


def test_client_never_sends_key_to_unencrypted_remote_host():
    with pytest.raises(ValueError, match='loopback'):
        SeraClient(api_key=TOKEN, endpoint='http://example.com')
