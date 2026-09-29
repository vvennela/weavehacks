"""Native experiments run in disposable processes without service credentials."""

import json
import os
import sys

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
