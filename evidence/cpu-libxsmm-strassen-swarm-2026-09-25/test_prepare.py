import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('strassen_prepare', Path(__file__).with_name('prepare.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_unused_256_helper_preserves_current_baseline_and_full_sources():
    source, original, helper = module.compose(Path(__file__).resolve().parents[1])
    assert source.count(original) == 1
    assert source.count(helper) == 1
    assert source.count('void gemm(') == 1
    assert len(source.encode()) <= 256000
    assert 'extern void sera_libxsmm_256(const void *parameters);' in source


@pytest.mark.parametrize('filename', ['kernel.c', 'primitive.c'])
def test_changed_imports_are_rejected(monkeypatch, filename):
    read_text = Path.read_text
    def changed(path, *args, **kwargs):
        text = read_text(path, *args, **kwargs)
        return text + '\n' if path.name == filename else text
    monkeypatch.setattr(Path, 'read_text', changed)
    with pytest.raises(ValueError, match='hash'):
        module.compose(Path(__file__).resolve().parents[1])
