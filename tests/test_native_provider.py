"""Provider calls have a wall-clock deadline outside the SDK process."""

import sys

import pytest

from sera import native_provider
from sera.agent import ProviderTransportError


def test_provider_hard_deadline_terminates_stalled_process(monkeypatch):
    monkeypatch.setenv('WANDB_API_KEY', 'fixture')
    monkeypatch.setattr(native_provider, '_command', lambda path:
        [sys.executable, '-c', 'import time; time.sleep(30)'])
    with pytest.raises(ProviderTransportError, match='deadline'):
        native_provider.complete({}, project='fixture/project', timeout_seconds=0.1)


def test_provider_child_receives_only_its_own_service_key(monkeypatch):
    monkeypatch.setenv('WANDB_API_KEY', 'fixture')
    monkeypatch.setenv('OPENAI_API_KEY', 'other-private-key')
    monkeypatch.setenv('HF_TOKEN', 'other-private-key')
    monkeypatch.setattr(native_provider, '_command', lambda path: [sys.executable, '-c', '''
import os,json,sys
from pathlib import Path
assert os.environ['WANDB_API_KEY'] == 'fixture'
assert 'OPENAI_API_KEY' not in os.environ and 'HF_TOKEN' not in os.environ
path=Path(sys.argv[1])
(path.parent/'response.json').write_text(json.dumps({'body':{'checked':True}}))
''',str(path)])
    assert native_provider.complete({},project='fixture/project',timeout_seconds=5) == {'checked':True}
