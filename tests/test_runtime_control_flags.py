"""Check the actual runner launch arguments without starting a GPU process."""

import pytest

from sera import runtime
from sera.config import RuntimeConfig


@pytest.mark.parametrize('changes,expected,absent', [
    ({'enable_prefix_caching': True}, '--enable-prefix-caching', '--no-enable-prefix-caching'),
    ({'enable_chunked_prefill': False}, '--no-enable-chunked-prefill', '--enable-chunked-prefill'),
    ({'enforce_eager': False}, '--no-enforce-eager', '--enforce-eager'),
])
def test_selected_execution_flag_reaches_owned_server(tmp_path, monkeypatch, changes, expected, absent):
    captured = []
    monkeypatch.setattr(runtime.sys, 'platform', 'linux')
    monkeypatch.setattr(runtime.importlib.metadata, 'version', lambda name: '0.26.0')
    monkeypatch.setattr(runtime, 'gpu_snapshot', lambda: {'used_mib': 0, 'uuid': 'fixture', 'compute_capability': '12.0'})
    monkeypatch.setattr(runtime, '_child_environment', lambda *_: {})

    def capture(command, **kwargs):
        captured.extend(command)
        raise RuntimeError('Stopped before spawning a real process')

    monkeypatch.setattr(runtime.subprocess, 'Popen', capture)
    model = runtime.SeraModel(artifact_dir=tmp_path/'trial', configuration=RuntimeConfig(**changes))
    with pytest.raises(RuntimeError, match='Stopped before spawning'):
        model.start()
    assert expected in captured
    assert absent not in captured
    assert model.record['configuration'] == model.configuration.model_dump()


def test_disabling_chunking_rejects_insufficient_token_budget():
    with pytest.raises(ValueError, match='Without chunked prefill'):
        RuntimeConfig(enable_chunked_prefill=False, max_num_batched_tokens=2048)
