import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('best_kernel_repeat',Path(__file__).with_name('run.py'))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
PREVIOUS=Path(__file__).resolve().parents[1]/'cpu-libxsmm-editable-panel-2026-09-25'


def test_replay_uses_only_exact_best_source_and_original_imported_control():
    baseline,candidates,_,_=module.selected_sources(PREVIOUS)
    assert len(candidates)==1
    assert module.source_hash(baseline.source)=='04fc3ff86669c2ca123e3b390b662637cd69c21f3d63fa26f7a5f0f0a882317c'
    assert module.source_hash(candidates[0].source)=='eb091b1eca431f0760d0d61e4c0c6e748c1a9e34466a87ac15ad9cb238b5aecf'


def test_mutated_saved_source_is_rejected(monkeypatch):
    read=Path.read_text
    def changed(path,*args,**kwargs):
        result=read(path,*args,**kwargs)
        return result+'\n' if path.name=='kernel.c' else result
    monkeypatch.setattr(Path,'read_text',changed)
    with pytest.raises(ValueError,match='hash'):
        module.selected_sources(PREVIOUS)


def test_saved_best_is_measured_before_swarm_can_modify_it():
    calls=[]
    class Team:
        def propose(self,history,*,timeout):
            calls.append((history,timeout))
            return 'ranked proposal'
    proposer=module.ReplayedBestThenSwarm(['saved best'],Team())
    assert proposer.propose([],timeout=10)=='saved best'
    assert not calls
    assert proposer.propose(['fresh best evidence'],timeout=9)=='ranked proposal'
    assert calls==[(['fresh best evidence'],9)]


def test_preflight_keeps_frozen_gates_and_supplies_technique_evidence(monkeypatch):
    captured={}
    class Team:
        def __init__(self,**kwargs):captured['team']=kwargs
        def observe(self,*args):pass
    monkeypatch.setattr(module,'KernelAdvisoryTeam',Team)
    monkeypatch.setattr(module,'save_json',lambda path,value:None)
    monkeypatch.setattr(module,'host_observation',lambda:dict(battery="Now drawing from 'Battery Power'",power_settings='unchanged'))
    def optimize(**kwargs):
        captured['search']=kwargs
        return dict(status='offline-preflight')
    monkeypatch.setattr(module,'optimize_kernel',optimize)
    module.main()
    assert captured['team']['max_calls']==108 and captured['team']['timeout']==180
    assert captured['team']['max_rounds']==6 and captured['team']['batch_size']==3
    assert 'Technique map:' in captured['team']['task'] and 'Local diagnostic ONLY:' in captured['team']['task']
    assert len(captured['team']['task'])<500000
    assert captured['search']['repeats']==10 and captured['search']['min_improvement']==.05
    assert captured['search']['max_seconds']==1800 and captured['search']['max_candidates']==6
    assert module.source_hash(captured['search']['baseline'].source)==module.BASELINE_HASH
