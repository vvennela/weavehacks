"""Release constraints match recorded GPU evidence; no GPU packages are imported."""

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS = ROOT/'constraints/gpu-sm120-tested.txt'


def _constraint_versions():
    lines = [line.strip() for line in CONSTRAINTS.read_text().splitlines()]
    return dict(line.split('==') for line in lines if line and not line.startswith('#'))


def test_constraints_match_recorded_environment_not_guessed_versions():
    environment = json.loads((ROOT/'evidence/qwen-baseline-cuda-link/environment.json').read_text())
    actual = _constraint_versions()
    expected = {name: version for name, version in environment['packages'].items() if name != 'marimo'}
    assert actual == expected


@pytest.mark.parametrize('service', ['joint-0', 'joint-1'])
def test_core_runtime_constraints_match_both_passing_joint_services(service):
    record = json.loads((ROOT/f'evidence/live-placement-total-v1/trial-001/{service}/runtime.json').read_text())
    assert record['cleanup_pass'] is True
    assert {name: _constraint_versions()[name] for name in record['versions']} == record['versions']


@pytest.mark.parametrize('version', ['0.6.0', '0.25.0', '0.27.0'])
def test_unchecked_vllm_version_fails_before_gpu_or_process_access(tmp_path, monkeypatch, version):
    from sera import runtime
    monkeypatch.setattr(runtime.sys, 'platform', 'linux')
    monkeypatch.setattr(runtime.importlib.metadata, 'version', lambda _: version)
    monkeypatch.setattr(runtime, 'gpu_snapshot', lambda: pytest.fail('GPU access before version rejection'))
    monkeypatch.setattr(runtime.subprocess, 'Popen', lambda *args, **kwargs: pytest.fail('GPU process launched'))
    model = runtime.SeraModel(artifact_dir=tmp_path/'trial')
    with pytest.raises(RuntimeError, match='checked runtime is vLLM 0.26.0'):
        model.start()
    assert model.record['cleanup_pass'] is True
