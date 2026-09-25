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
