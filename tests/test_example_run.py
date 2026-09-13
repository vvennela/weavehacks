"""The recording notebook starts blank and never starts GPU work implicitly."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.example_run import ExampleRun


def test_blank_session_ignores_ambient_keys(monkeypatch, tmp_path):
    monkeypatch.setenv('WANDB_API_KEY', 'ambient-secret')
    demo = ExampleRun(output_root=tmp_path)
    assert demo.status() == {'weave_configured': False, 'agent_configured': False,
                             'provider_verified': False}
    for call in (demo.check_weave, demo.check_agent, demo.baseline, demo.optimize):
        with pytest.raises(ValueError, match='Configure'):
            call()
    assert not list(tmp_path.iterdir())


def test_gpu_absence_gives_runtime_instruction(monkeypatch, tmp_path):
    from sera import runtime
    monkeypatch.setattr(runtime, 'gpu_snapshot', lambda: (_ for _ in ()).throw(FileNotFoundError()))
    assert ExampleRun(output_root=tmp_path).gpu()['message'] == 'Change runtime to GPU'


def test_key_setup_never_prints_or_persists_and_restores_environment(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv('WANDB_API_KEY', 'original-key')
    demo = ExampleRun(output_root=tmp_path)
    demo.configure_weave('private-runtime-key', project='test/project')
    demo.configure_agent(provider='wandb', model='chosen-model')
    with demo._credentials():
        import os
        assert os.environ['WANDB_API_KEY'] == 'private-runtime-key'
    assert os.environ['WANDB_API_KEY'] == 'original-key'
    assert 'private-runtime-key' not in repr(demo.__dict__)
    assert capsys.readouterr().out == '' and not list(tmp_path.iterdir())


def test_baseline_requires_idle_gpu_and_certificate(monkeypatch, tmp_path):
    demo = ExampleRun(output_root=tmp_path)
    demo.configure_weave('private-runtime-key', project='test/project')
    demo.configure_agent(provider='wandb', model='chosen-model')
    with pytest.raises(ValueError, match='provider check'):
        demo.baseline()


def test_failed_baseline_stops_and_closes_runner(monkeypatch, tmp_path):
    from sera import measurement, quality
    import sera
    demo = ExampleRun(output_root=tmp_path)
    monkeypatch.setattr(demo, '_ready', lambda: None)
    monkeypatch.setattr(demo, '_tasks', lambda: (['question'], lambda p, o: False))
    events = []
    monkeypatch.setattr(sera, 'SeraModel', lambda **kwargs: SimpleNamespace(
        start=lambda: events.append('start'), close=lambda: events.append('close')))
    monkeypatch.setattr(measurement, 'collect_trial', lambda *args, **kwargs: {'trial_id': 'baseline'})
    monkeypatch.setattr(quality, 'evaluate_quality', lambda *args, **kwargs: {'passed': False})
    with pytest.raises(RuntimeError, match='Baseline quality'):
        demo.baseline()
    assert events == ['start', 'close']
    assert len(list(tmp_path.glob('baseline-*/result.json'))) == 1


def test_comparison_uses_same_run_baseline_not_the_earlier_display(tmp_path):
    demo = ExampleRun(output_root=tmp_path)
    def trial(name, latency):
        return {'trial_id': name, 'reduced': {'p95_latency_ms': latency,
                    'output_tokens_per_second': 10},
                'runtime': {'sampled_peak_memory_mib': 100, 'startup_seconds': 60},
                'task_quality': {'mean': 1.0, 'passed': True}}
    result = SimpleNamespace(report={'baseline': trial('baseline', 100),
        'search_trials': [trial('trial-2', 80)],
        'decision': {'selected': 'trial-2'}, 'weave_url': 'saved-trace'})
    report = demo.compare(result)
    assert report['p95_improvement_pct'] == pytest.approx(20)
    assert report['baseline']['p95_ms'] == 100


def test_no_safe_result_is_not_reported_as_improvement(tmp_path):
    demo = ExampleRun(output_root=tmp_path)
    result = SimpleNamespace(report={'baseline': {}, 'decision': {'selected': None}})
    report = demo.compare(result)
    assert report['p95_improvement_pct'] is None and report['selected'] is None


def test_notebook_is_blank_and_code_compiles():
    notebook = json.loads((Path(__file__).resolve().parents[1]/'notebooks'/'Example run.ipynb').read_text())
    assert notebook['nbformat'] == 4
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            assert cell['outputs'] == [] and cell['execution_count'] is None
            compile(''.join(cell['source']), '<example-cell>', 'exec')
    source = json.dumps(notebook)
    assert 'getpass' in source and 'wandb_v1_' not in source
