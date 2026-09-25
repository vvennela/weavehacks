from pathlib import Path
import importlib.util
import pytest

spec = importlib.util.spec_from_file_location('ten_run_ac', Path(__file__).with_name('run.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('source,mode,valid', [
    ('AC Power', 0, True), ('AC Power', 1, False),
    ('Battery Power', 0, False), ('AC Power', None, False),
])
def test_only_approved_initial_energy_profile_can_run(source, mode, valid):
    observation = dict(battery=f"Now drawing from '{source}'",
        power_settings=f'Battery Power:\n powermode 1\nAC Power:\n powermode {mode}\n')
    if valid:
        module.require_automatic_ac(observation)
    else:
        with pytest.raises(RuntimeError):
            module.require_automatic_ac(observation)


def test_replay_sends_ten_repeats_and_exact_saved_sources_to_search(monkeypatch):
    import json
    from types import SimpleNamespace
    previous = Path(__file__).resolve().parents[1] / 'cpu-libxsmm-editable-panel-2026-09-25'
    saved = json.loads((previous / 'search/result.json').read_text())
    captured = {}
    def search(**kwargs):
        captured.update(kwargs)
        return {}
    monkeypatch.setattr(module, 'optimize_kernel', search)
    monkeypatch.setattr(module, 'save_json', lambda *args: None)
    monkeypatch.setattr(module, 'KernelAdvisoryTeam', lambda **kwargs: SimpleNamespace(observe=lambda history: None))
    monkeypatch.setattr(module, 'HillsKernelEvaluator', lambda **kwargs: object())
    monkeypatch.setattr(module, 'host_observation', lambda: dict(
        battery="Now drawing from 'AC Power'",
        power_settings='Battery Power:\n powermode 1\nAC Power:\n powermode 0\n'))
    module.main()
    assert captured['repeats'] == 10
    assert captured['min_improvement'] == 0.05
    baseline = captured['baseline']
    candidates = list(captured['propose'].candidates)
    assert [module.hashlib.sha256(x.source.encode()).hexdigest()
            for x in [baseline] + candidates] == [x['source_hash'] for x in saved['trials']]
