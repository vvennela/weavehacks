"""Native experiments run in disposable processes without service credentials."""

import json
import os
import sys
import threading

import pytest

from sera import native_worker


def job():
    return {'operation': 'measure', 'backend': 'mlx', 'artifact': '/fixture/checkpoint',
            'artifact_id': 'a' * 64, 'prompts': ['question'], 'max_tokens': 64,
            'seed': 0, 'warmup': 1, 'repetitions': 3}


def command(monkeypatch, script):
    monkeypatch.setattr(native_worker, '_command', lambda path: [sys.executable, '-c', script, str(path)])


def test_service_secrets_are_not_in_worker_environment(tmp_path, monkeypatch):
    monkeypatch.setenv('WANDB_API_KEY', 'private-fixture-key')
    monkeypatch.setenv('OPENAI_API_KEY', 'private-fixture-key')
    monkeypatch.setenv('SERA_SERVICE_TOKEN', 'private-fixture-key')
    command(monkeypatch, '''
import os, sys, json
from pathlib import Path
from sera.storage import content_hash
path = Path(sys.argv[1]); request = json.loads(path.read_text())
assert not any(name in os.environ for name in ('WANDB_API_KEY','OPENAI_API_KEY','SERA_SERVICE_TOKEN'))
(path.parent/'output.json').write_text(json.dumps({'job_hash':content_hash(request),'result':{'checked':True}}))
''')
    result = native_worker.run_native_job(job(), output_dir=tmp_path/'job', timeout_seconds=10)
    assert result == {'checked': True}
    record = json.loads((tmp_path/'job'/'status.json').read_text())
    assert record['status'] == 'completed'
    assert record['cleanup_pass'] is True


def test_worker_finds_tools_installed_beside_its_python(tmp_path, monkeypatch):
    monkeypatch.setenv('PATH', '/usr/bin:/bin')
    command(monkeypatch, '''
import json, subprocess, sys
from pathlib import Path
from sera.storage import content_hash
path = Path(sys.argv[1]); request = json.loads(path.read_text())
version = subprocess.check_output(['pytest', '--version'], text=True).strip()
(path.parent/'output.json').write_text(json.dumps({'job_hash':content_hash(request),
    'result':{'tool_found':version.startswith('pytest ')}}))
''')
    result = native_worker.run_native_job(job(), output_dir=tmp_path/'job', timeout_seconds=10)
    assert result['tool_found']


def test_timeout_stops_process_and_retains_failed_attempt(tmp_path, monkeypatch):
    command(monkeypatch, 'import time; time.sleep(30)')
    with pytest.raises(native_worker.NativeWorkerError, match='timeout'):
        native_worker.run_native_job(job(), output_dir=tmp_path/'job', timeout_seconds=0.1)
    record = json.loads((tmp_path/'job'/'status.json').read_text())
    assert record['status'] == 'timeout' and record['cleanup_pass'] is True
    with pytest.raises(ProcessLookupError):
        os.kill(record['pid'], 0)


def test_worker_output_must_match_job_identity(tmp_path, monkeypatch):
    command(monkeypatch, '''
from pathlib import Path
import sys
(Path(sys.argv[1]).parent/'output.json').write_text('{"job_hash":"wrong","result":{}}')
''')
    with pytest.raises(native_worker.NativeWorkerError, match='identity'):
        native_worker.run_native_job(job(), output_dir=tmp_path/'job', timeout_seconds=10)


@pytest.mark.parametrize('change', [{'backend': 'unknown'}, {'repetitions': 0},
                                  {'artifact_id': 'main'}, {'extra': 'untrusted'}])
def test_invalid_job_fails_before_creating_files(tmp_path, change):
    with pytest.raises(ValueError):
        native_worker.run_native_job(job() | change, output_dir=tmp_path/'job', timeout_seconds=10)
    assert not (tmp_path/'job').exists()


def test_cancelled_job_stops_the_worker(tmp_path, monkeypatch):
    cancelled = threading.Event()
    command(monkeypatch, 'import time; time.sleep(30)')
    timer = threading.Timer(0.1, cancelled.set)
    timer.start()
    try:
        with pytest.raises(native_worker.NativeWorkerError, match='cancelled'):
            native_worker.run_native_job(job(), output_dir=tmp_path/'job', timeout_seconds=10,
                                         cancelled=cancelled)
    finally:
        timer.join()
    status = json.loads((tmp_path/'job'/'status.json').read_text())
    assert status['status'] == 'cancelled' and status['cleanup_pass']


def test_worker_watchdog_exits_when_parent_pipe_closes(tmp_path):
    import subprocess
    read_fd, write_fd = os.pipe()
    env = dict(os.environ, SERA_PARENT_FD=str(read_fd))
    process = subprocess.Popen([sys.executable, '-c',
        ('from sera.native_worker import _parent_watchdog; import time; '
         '_parent_watchdog(); print("READY", flush=True); time.sleep(30)')], env=env,
        pass_fds=(read_fd,), start_new_session=True, stdout=subprocess.PIPE, text=True)
    os.close(read_fd)
    try:
        assert process.stdout.readline().strip() == 'READY'
        os.close(write_fd)
        assert process.wait(timeout=5) != 0
    finally:
        try:
            os.close(write_fd)
        except OSError:
            pass
        if process.poll() is None:
            process.kill()
        process.wait()


def test_rocm_jobs_validate_their_own_recipe_and_dispatch(monkeypatch):
    from sera import native_worker as worker
    calls = []
    class Backend:
        def prepare(self, **kwargs):
            calls.append(kwargs)
            return {'backend': 'rocm'}
    monkeypatch.setattr(worker, 'ROCmBackend', Backend)
    request = {'operation':'prepare','backend':'rocm',
               'source':{'model_id':'Qwen/Qwen3-0.6B','revision':'a'*40},
               'destination':'/not-written','recipe':{'bits':4,'double_quant':True}}
    job = worker.JOB.validate_python(request)
    assert worker._execute(job) == {'backend':'rocm'}
    assert calls[0]['recipe'].bits == 4
    request['recipe']['bits'] = 8
    with pytest.raises(ValueError):
        worker.JOB.validate_python(request)


def test_cuda_export_dispatch_uses_modelopt_recipe(monkeypatch):
    from test_cuda_backend import UUID

    from sera import native_worker as worker
    monkeypatch.setattr(worker, 'prepare_modelopt', lambda **kwargs:{'recipe':kwargs['recipe'].format})
    assigned = []
    monkeypatch.setattr(worker, 'assign_device', lambda uuid: assigned.append(uuid))
    job = worker.JOB.validate_python({'operation':'prepare','backend':'cuda',
        'source':{'model_id':'Qwen/Qwen3-0.6B','revision':'a'*40},
        'destination':'/not-written','recipe':{'format':'bf16'}, 'gpu_uuid': UUID})
    assert worker._execute(job) == {'recipe':'bf16'}
    assert assigned == [UUID]


def test_cuda_measure_dispatch_keeps_runtime_controls(monkeypatch):
    from test_cuda_backend import options
    calls = []
    class Backend:
        def __init__(self, runtime):
            assert runtime.model_dump() == options()
        def load(self, artifact, *, expected_id):
            calls.append((artifact, expected_id))
            return self
        def __enter__(self):
            return self
        def __exit__(self, *args):
            calls.append('closed')
        def measure(self, prompts, **kwargs):
            return {'controls': kwargs}
    monkeypatch.setattr(native_worker, 'CUDABackend', Backend)
    request = job() | {'backend': 'cuda', 'runtime': options()}
    result = native_worker._execute(native_worker.JOB.validate_python(request))
    assert result['controls']['max_tokens'] == 64
    assert calls == [('/fixture/checkpoint', 'a' * 64), 'closed']
    request.pop('runtime')
    with pytest.raises(ValueError):
        native_worker.JOB.validate_python(request)
