"""Exercise the customer boundary and its real controller process lifecycle."""
import hashlib
import json
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from test_native_optimizer import profile

from sera import managed_service as service

TOKEN = 'fixture-customer-token-with-at-least-32-bytes'
OTHER_TOKEN = 'other-customer-token-with-at-least-32-bytes'


def wait_for(predicate, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.02)
    raise AssertionError('Condition was not met before deadline')


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setattr(service, '_device_lock_path', lambda: tmp_path / 'gpu.lock')
    monkeypatch.setenv('WANDB_API_KEY', 'operator-test-key')
    monkeypatch.setenv('SERA_ACCESS_KEY', TOKEN)
    # This is a real process, but it uses deterministic model/agent fixtures.
    script = tmp_path / 'controller.py'
    script.write_text('''
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[2])
import pytest
from test_native_optimizer import native, runtime, Agent
from sera.native_worker import _parent_watchdog
_parent_watchdog()
folder = Path(sys.argv[1])
request = json.loads((folder / 'request.json').read_text())
(folder / 'environment.json').write_text(json.dumps(sorted(os.environ)))
if (folder.parent / 'stall').exists():
    time.sleep(60)
runtime.__wrapped__(pytest.MonkeyPatch())
native.optimize_native(profile=request['profile'], output_dir=folder / 'research',
                       project=request['project'], agent=Agent(),
                       resume=(folder / 'research' / 'ledger.sqlite3').exists())
''')
    monkeypatch.setattr(service, '_controller_command', lambda folder: [
        sys.executable, str(script), str(folder), str(Path(__file__).parent)])
    clients = {hashlib.sha256(TOKEN.encode()).hexdigest(): {'id': 'one', 'profiles': ['fixture']},
               hashlib.sha256(OTHER_TOKEN.encode()).hexdigest(): {'id': 'two', 'profiles': ['fixture']}}
    instance = service.ManagedService(folder=tmp_path / 'service', profiles=[profile()],
                                      clients=clients, project='fixture/project')
    yield instance
    instance.close()


def test_one_job_idempotency_ownership_and_private_credentials(manager):
    first = manager.submit('one', 'fixture', 'request-1')
    again = manager.submit('one', 'fixture', 'request-1')
    assert first['job_id'] == again['job_id']
    with pytest.raises(service.ServiceError) as error:
        manager.get('two', first['job_id'])
    assert error.value.status == 404
    result = wait_for(lambda: (value if (value := manager.get('one', first['job_id']))['status'] == 'completed' else None))
    assert result['result']['selected_recipe_id'] == 'q8'
    assert result['result']['trace']['remote_verified'] is True
    assert 'expected_json' not in json.dumps(result)
    environment = json.loads((manager.folder / first['job_id'] / 'environment.json').read_text())
    assert 'WANDB_API_KEY' in environment
    assert 'SERA_ACCESS_KEY' not in environment
    assert TOKEN not in (manager.folder / first['job_id'] / 'request.json').read_text()


def test_only_one_gpu_job_runs_and_cancel_is_durable(manager):
    (manager.folder / 'stall').touch()
    job = manager.submit('one', 'fixture', 'request-1')
    wait_for(lambda: manager.get('one', job['job_id'])['status'] == 'running')
    with pytest.raises(service.ServiceError) as error:
        manager.submit('two', 'fixture', 'request-2')
    assert error.value.status == 429
    manager.cancel('one', job['job_id'])
    result = wait_for(lambda: (value if (value := manager.get('one', job['job_id']))['status'] == 'cancelled' else None))
    assert result['result'] is None
    assert manager.submit('one', 'fixture', 'request-1')['status'] == 'cancelled'


def test_deadline_includes_a_stalled_controller(manager):
    (manager.folder / 'stall').touch()
    manager.profiles['fixture'] = manager.profiles['fixture'].model_copy(update={'max_run_seconds': 0.3})
    job = manager.submit('one', 'fixture', 'timeout')
    result = wait_for(lambda: (value if (value := manager.get('one', job['job_id']))['status'] == 'timed-out' else None))
    assert result['result'] is None


def test_another_service_cannot_use_same_device(manager, tmp_path):
    with pytest.raises(RuntimeError, match='device'):
        service.ManagedService(folder=tmp_path / 'other', profiles=[profile()],
                               clients=manager.clients, project='fixture/project')


def test_http_requires_auth_rejects_unknown_inputs_and_hides_other_jobs(manager):
    server = service.make_server(manager, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f'http://127.0.0.1:{server.server_port}'
    def send(path, body=None, token=TOKEN):
        request = Request(endpoint + path, data=json.dumps(body).encode() if body is not None else None,
                          headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        return urlopen(request, timeout=2)
    try:
        with pytest.raises(HTTPError) as error:
            send('/v1/jobs', {'profile_id': 'fixture', 'request_id': 'abc'}, token='wrong')
        assert error.value.code == 401
        with pytest.raises(HTTPError) as error:
            send('/v1/jobs', {'profile_id': 'fixture', 'request_id': 'abc', 'profile': profile()})
        assert error.value.code == 400
        with send('/v1/jobs', {'profile_id': 'fixture', 'request_id': 'abc'}) as response:
            job = json.load(response)
        with pytest.raises(HTTPError) as error:
            send('/v1/jobs/' + job['job_id'], token=OTHER_TOKEN)
        assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_cancel_waits_for_descendant_ownership_release(manager, monkeypatch):
    code = '''
import os, subprocess, sys, time
from pathlib import Path
from sera.native_worker import _parent_watchdog
from sera.process_ownership import inherit_lifetime
_parent_watchdog()
folder = Path(sys.argv[1])
env = {}
descriptors = inherit_lifetime(env, ())
child = "import sys,time; from pathlib import Path; p=Path(sys.argv[1]); (p/'child-ready').touch(); end=time.monotonic()+5; exec(\\"while not (p/'release-child').exists() and time.monotonic()<end: time.sleep(.02)\\")"
subprocess.Popen([sys.executable, '-c', child, str(folder)], env=env,
                 pass_fds=descriptors, start_new_session=True)
time.sleep(60)
'''
    monkeypatch.setattr(service, '_controller_command',
                        lambda folder: [sys.executable, '-c', code, str(folder)])
    job = manager.submit('one', 'fixture', 'nested')
    folder = manager.folder / job['job_id']
    wait_for(lambda: (folder / 'child-ready').exists())
    manager.cancel('one', job['job_id'])
    time.sleep(0.1)
    assert manager.get('one', job['job_id'])['status'] == 'running'
    with pytest.raises(service.ServiceError) as error:
        manager.submit('two', 'fixture', 'too-soon')
    assert error.value.status == 429
    (folder / 'release-child').touch()
    wait_for(lambda: manager.get('one', job['job_id'])['status'] == 'cancelled')


def test_service_restart_resumes_same_job_without_extending_deadline(manager):
    (manager.folder / 'stall').touch()
    job = manager.submit('one', 'fixture', 'restart')
    wait_for(lambda: manager.get('one', job['job_id'])['status'] == 'running')
    deadline = manager._all()[0]['deadline']
    manager.close()
    assert manager.get('one', job['job_id'])['status'] == 'interrupted'
    (manager.folder / 'stall').unlink()
    restored = service.ManagedService(folder=manager.folder, profiles=[profile()],
                                      clients=manager.clients, project=manager.project)
    try:
        wait_for(lambda: restored.get('one', job['job_id'])['status'] == 'completed')
        assert restored._all()[0]['deadline'] == deadline
        assert restored.submit('one', 'fixture', 'restart')['job_id'] == job['job_id']
    finally:
        restored.close()


def test_abrupt_service_exit_releases_descendants_and_recovers_job(manager, monkeypatch):
    import subprocess

    from sera.process_ownership import tree_is_alive
    manager.close()
    (manager.folder / 'stall').touch()
    config = {'folder': str(manager.folder), 'profiles': [profile()],
              'clients': manager.clients, 'project': manager.project}
    config_path = manager.folder / 'restart-test.json'
    config_path.write_text(json.dumps(config))
    # Reconstruct the fixture controller command, retaining its tests path.
    template = service._controller_command(manager.folder)
    script = '''
import json,sys,time
from pathlib import Path
from sera import managed_service as service
config=json.loads(Path(sys.argv[1]).read_text())
service._device_lock_path=lambda:Path(sys.argv[2])
template=json.loads(sys.argv[3])
service._controller_command=lambda folder:template[:2]+[str(folder)]+template[3:]
manager=service.ManagedService(**config)
job=manager.submit('one','fixture','crashed-service')
(Path(config['folder'])/'submitted.json').write_text(json.dumps(job))
time.sleep(60)
'''
    process = subprocess.Popen([sys.executable, '-c', script, str(config_path),
                                str(service._device_lock_path()), json.dumps(template)])
    try:
        wait_for(lambda: (manager.folder / 'submitted.json').exists())
        job = json.loads((manager.folder / 'submitted.json').read_text())
        folder = manager.folder / job['job_id']
        wait_for(lambda: (folder / 'environment.json').exists())
        process.kill()
        process.wait(timeout=5)
        wait_for(lambda: not tree_is_alive(folder))
        (manager.folder / 'stall').unlink()
        restored = service.ManagedService(**config)
        try:
            wait_for(lambda: restored.get('one', job['job_id'])['status'] == 'completed')
        finally:
            restored.close()
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)


def test_changed_job_contract_never_reaches_controller(manager):
    with manager._mutex:
        job = manager.submit('one', 'fixture', 'changed-contract')
        folder = manager.folder / job['job_id']
        request = json.loads((folder / 'request.json').read_text())
        request['profile']['constraints']['quality_floor'] = 0.1
        (folder / 'request.json').write_text(json.dumps(request))
    wait_for(lambda: manager.get('one', job['job_id'])['status'] not in service.ACTIVE)
    assert manager.get('one', job['job_id'])['status'] == 'failed'
    assert not (folder / 'environment.json').exists()


def test_customer_measurements_include_latency_and_fresh_control():
    def measured(peak, latency):
        return {'runtime': {'memory': {'peak_bytes': peak}},
                'task_quality': {'mean': 1.0},
                'reduced': {'p95_latency_ms': latency, 'output_tokens_per_second': 42.0}}
    report = {'baseline': measured(100, 20), 'trials': [{
        'recipe_id': 'fp8', 'status': 'measured', 'measurement': measured(60, 30),
        'confirmation': {'baseline': measured(90, 21), 'candidate': measured(65, 31)},
        'repeated_decision': {'selected': 'candidate'}}]}
    result = service._measurements(report)
    assert result['baseline']['p95_latency_ms'] == 20
    assert result['trials'][0]['baseline_control']['peak_bytes'] == 90
    assert result['trials'][0]['confirmation']['p95_latency_ms'] == 31
    assert result['trials'][0]['measurement']['output_tokens_per_second'] == 42.0


def test_customer_progress_does_not_call_rejected_checkpoint_accepted():
    report = {'selected_recipe_id': 'baseline', 'trials': [{
        'recipe_id': 'q8', 'status': 'measured',
        'repeated_decision': {'selected': 'candidate'},
        'advisor_review': {'decision': 'reject'}}]}
    assert service._measurements(report)['trials'][0]['accepted'] is False


def test_customer_progress_waits_for_committed_adoption():
    report = {'selected_recipe_id': 'baseline', 'trials': [{
        'recipe_id': 'q8', 'status': 'measured',
        'repeated_decision': {'selected': 'candidate'}}]}
    assert service._measurements(report)['trials'][0]['accepted'] is False
