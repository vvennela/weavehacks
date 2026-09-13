"""Example imports are safe; real work starts only when the script is run."""

import runpy
from pathlib import Path

import pytest


@pytest.mark.parametrize('name', ['latency.py', 'latency_then_throughput.py', 'replay_saved_run.py'])
def test_example_import_does_not_start_work(monkeypatch, name):
    import sera
    from sera import demo
    def unexpected(*args, **kwargs):
        pytest.fail('Importing an example must not start setup, inference, or a replay')
    monkeypatch.setattr(sera, 'optimize', unexpected)
    monkeypatch.setattr(demo, 'prepare_demo', unexpected)
    namespace = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'examples' / name))
    assert callable(namespace['main'])
