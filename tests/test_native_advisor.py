import sys
import threading
from pathlib import Path

import pytest

from sera import native_advisor as advisor

TOKEN = 'fixture-advisor-key-with-more-than-32-bytes'


@pytest.fixture
def endpoint(tmp_path, monkeypatch):
    script = tmp_path / 'worker.py'
    script.write_text('''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[2])
sys.path.insert(0, sys.argv[3])
from test_native_board import SchemaAgent
from sera import native_advisor
native_advisor.NativeBoardFactory = lambda folder, **kw: __import__('sera.native_board', fromlist=['NativeBoard']).NativeBoard(folder, agent_factory=SchemaAgent, **kw)
native_advisor.run_worker(Path(sys.argv[1]))
''')
    monkeypatch.setattr(advisor, '_worker_command', lambda path: [sys.executable, str(script), str(path), str(Path(__file__).parent), str(Path(advisor.__file__).parent.parent)])
    server = advisor.make_server(tmp_path / 'boards', token=TOKEN, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()
    server.server_close()
    thread.join()


def client(tmp_path, endpoint, token=TOKEN):
    return advisor.NativeAdvisorClient(tmp_path / 'client', max_model_calls=64,
                                       endpoint=endpoint, token=token)


def test_remote_worker_uses_full_board_and_preserves_resume_budget(tmp_path, endpoint):
    board = client(tmp_path, endpoint)
    evidence = {'available_recipes': [{'recipe_id': x} for x in ['a', 'b', 'c']]}
    assert board.propose(evidence, timeout_seconds=10).recipe_id == 'a'
    assert len(board.model_calls) == 31
    assert len(board.history[0]['proposals']) == 15
    resumed = client(tmp_path, endpoint)
    assert resumed.propose(evidence, timeout_seconds=10).recipe_id == 'a'
    assert len(resumed.model_calls) == 31
    evidence['available_recipes'] = [{'recipe_id': 'b'}, {'recipe_id': 'c'}]
    assert resumed.propose(evidence, timeout_seconds=10).recipe_id == 'b'
    assert resumed.review({'software_gates_passed': True}, timeout_seconds=10)['decision'] == 'adopt'
    assert len(resumed.model_calls) == 32


def test_wrong_key_fails_before_board_creation(tmp_path, endpoint):
    with pytest.raises(RuntimeError, match='HTTP 401'):
        client(tmp_path, endpoint, token='wrong')
    assert not list((tmp_path / 'boards').glob('*/state.json'))


def test_remote_advisor_rejects_public_http_endpoint(tmp_path):
    with pytest.raises(ValueError, match='loopback'):
        client(tmp_path, 'http://example.com')


def test_deadline_terminates_local_advisor_worker(tmp_path, endpoint, monkeypatch):
    board = client(tmp_path, endpoint)
    marker = tmp_path / 'escaped'
    code = f'import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).touch()'
    monkeypatch.setattr(advisor, '_worker_command', lambda path: [sys.executable, '-c', code])
    with pytest.raises((RuntimeError, TimeoutError)):
        board.review({}, timeout_seconds=0.2)
    import time
    time.sleep(1.1)
    assert not marker.exists()


def test_advisor_token_is_not_written_into_request_or_board_records(tmp_path, endpoint):
    client(tmp_path, endpoint)
    for path in (tmp_path / 'boards').rglob('*.json'):
        assert TOKEN not in path.read_text()


def test_advisor_validates_timeout_before_transport(tmp_path, endpoint):
    board = client(tmp_path, endpoint)
    with pytest.raises(ValueError, match='deadline'):
        board.review({}, timeout_seconds=float('nan'))


def test_disconnected_controller_terminates_local_worker(tmp_path, endpoint, monkeypatch):
    import json
    import socket
    import time
    from urllib.parse import urlsplit
    marker = tmp_path / 'disconnected-worker-escaped'
    started = tmp_path / 'started'
    code = (f'from pathlib import Path; import time; Path({str(started)!r}).touch(); '
            f'time.sleep(1); Path({str(marker)!r}).touch()')
    monkeypatch.setattr(advisor, '_worker_command', lambda path: [sys.executable, '-c', code])
    body = json.dumps({'run_id': 'a' * 64, 'max_model_calls': 64, 'operation': 'state',
                      'evidence': {}, 'timeout_seconds': 10.0}).encode()
    with socket.create_connection(('127.0.0.1', urlsplit(endpoint).port)) as connection:
        connection.sendall((f'POST /v1/board HTTP/1.1\r\nHost: localhost\r\n'
            f'Authorization: Bearer {TOKEN}\r\nContent-Length: {len(body)}\r\n\r\n').encode() + body)
        deadline = time.monotonic() + 3
        while not started.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert started.exists()
    time.sleep(1.1)
    assert not marker.exists()


def test_cancelled_run_does_not_start_an_advisor_worker(tmp_path, monkeypatch):
    cancelled = threading.Event()
    cancelled.set()
    monkeypatch.setattr(advisor.NativeAdvisorClient, '_call',
                        lambda *args: pytest.fail('Cancelled run contacted the advisor'))
    board = advisor.NativeAdvisorClient(tmp_path, max_model_calls=48,
        endpoint='http://127.0.0.1:8766', token=TOKEN, cancelled=cancelled)
    assert board.propose({}, timeout_seconds=10, cancelled=cancelled) is None
