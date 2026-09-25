import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('compiler_board_run', Path(__file__).with_name('run.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_swarm_gets_verified_primitives_and_ten_repeat_search(monkeypatch):
    calls = {}
    def team(**kwargs):
        calls['team'] = kwargs
        return SimpleNamespace(observe=lambda history: None)
    def search(**kwargs):
        calls['search'] = kwargs
        return {}
    monkeypatch.setattr(module, 'KernelAdvisoryTeam', team)
    monkeypatch.setattr(module, 'optimize_kernel', search)
    monkeypatch.setattr(module, 'save_json', lambda *args: None)
    monkeypatch.setattr(module, 'HillsKernelEvaluator', lambda **kwargs: None)
    monkeypatch.setattr(module, 'host_observation', lambda: dict(
        battery="Now drawing from 'AC Power'",
        power_settings='Battery Power:\n powermode 1\nAC Power:\n powermode 0\n'))
    module.main()
    assert calls['search']['repeats'] == 10
    assert calls['search']['min_improvement'] == 0.05
    assert calls['team']['max_rounds'] == 6
    assert calls['team']['max_calls'] == 108
    assert calls['team']['timeout'] == 180
    source = calls['search']['baseline'].source
    for symbol in ('sera_libxsmm_ta', 'sera_libxsmm_tb', 'sera_libxsmm_tt'):
        assert symbol in source
    assert 'cpu-libxsmm-ten-run-ac-2026-09-25' in calls['team']['task']
    assert 'TA and TT full-call wrappers remain unmeasured' in calls['team']['task']
    assert '<_sme_transpose>:' in calls['team']['task']
    assert calls['search']['propose'].replay.name == 'libxsmm-n512-tb-with-timed-sme-a-transpose'


def test_exact_prior_candidate_is_replayed_before_new_swarm_proposals():
    events = []
    team = SimpleNamespace(propose=lambda history, timeout: events.append('propose') or 'new',
                           adjudicate=lambda *args, **kwargs: events.append('review') or 'reviewed')
    proposer = module.ReplayThenSwarm('saved', team)
    assert proposer.propose([], timeout=5) == 'saved'
    assert events == []
    assert proposer.adjudicate('history') == 'reviewed'
    assert proposer.propose([], timeout=5) == 'new'
    assert events == ['review', 'propose']
