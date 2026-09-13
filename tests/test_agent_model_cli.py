"""Model selection reaches the existing provider boundary without external calls."""

import json
from pathlib import Path
import pytest

from experiments import replay_failure_investigation as replay
from experiments import run_investigation as live
from sera import provider_check
from sera.agent import AGENT_MODEL, schema_hash
from sera.config import MODEL_ID
from sera.storage import content_hash


def arguments(module, tmp_path):
    common = ['--project', 'test/project', '--output-dir', str(tmp_path/'output'),
              '--provider-check', str(tmp_path/'certificate.json')]
    if module is live:
        return common + ['--model', MODEL_ID, '--budget', '2', '--batching-values', '2048']
    return common + ['--source-dir', str(tmp_path/'source')]


@pytest.fixture(autouse=True)
def no_execution(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail('No optimization or replay is allowed in this CLI test')
    monkeypatch.setattr(live.sera, 'optimize', forbidden)
    monkeypatch.setattr(replay, 'run_replay', forbidden)
    monkeypatch.setattr(replay, 'load_source', lambda path: {'folder': Path(path).resolve()})


@pytest.mark.parametrize('module', [live, replay])
@pytest.mark.parametrize('chosen', [None, 'test/replaceable-investigator'])
def test_cli_passes_explicit_or_default_model_to_constructed_agent(module, chosen, tmp_path, monkeypatch):
    seen = []
    class BoundaryReached(Exception):
        pass
    def stop_at_certificate(path, agent):
        seen.append((agent.model, agent.project))
        raise BoundaryReached
    monkeypatch.setattr(module, 'require_provider_check', stop_at_certificate)
    args = arguments(module, tmp_path) + (['--agent-model', chosen] if chosen else [])
    with pytest.raises(BoundaryReached):
        module.main(args)
    assert seen == [(chosen or AGENT_MODEL, 'test/project')]
    assert not (tmp_path/'output').exists()


@pytest.mark.parametrize('module', [live, replay])
def test_other_model_certificate_stops_before_execution(module, tmp_path, monkeypatch, capsys):
    (tmp_path/'certificate.json').write_text(json.dumps({
        'schema_version': 'sera-provider-check-v1', 'model': AGENT_MODEL, 'project': 'test/project',
        'schema_hash': schema_hash(), 'cases_hash': content_hash(provider_check.provider_cases())}))
    monkeypatch.setattr(module, 'require_provider_check', provider_check.require_provider_check)
    with pytest.raises(SystemExit) as error:
        module.main(arguments(module, tmp_path) + ['--agent-model', 'test/other-model'])
    assert error.value.code == 2
    assert 'does not match this model' in capsys.readouterr().err
    assert not (tmp_path/'output').exists()


@pytest.mark.parametrize('chosen', [None, 'test/replaceable-investigator'])
def test_provider_check_cli_passes_model_to_agent_creation(chosen, tmp_path, monkeypatch):
    seen = []
    class BoundaryReached(Exception):
        pass
    def stop_at_creation(**kwargs):
        seen.append(kwargs)
        raise BoundaryReached
    monkeypatch.setattr(provider_check, 'WandbAgent', stop_at_creation)
    args = ['--project', 'test/project', '--output-dir', str(tmp_path/'check')]
    if chosen:
        args += ['--model', chosen]
    with pytest.raises(BoundaryReached):
        provider_check.main(args)
    assert seen == [{'project': 'test/project', 'model': chosen or AGENT_MODEL}]
