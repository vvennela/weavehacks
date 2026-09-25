import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('transpose_swarm_prepare', Path(__file__).with_name('prepare.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_optional_helpers_preserve_original_source_and_exact_imported_bytes():
    source, original, helpers = module.compose(Path(__file__).resolve().parents[1])
    assert source.count(original) == 1
    assert len(source.encode()) <= 256000
    assert source.count('void gemm(') == 1
    for helper in helpers.values():
        assert source.count(helper) == 1
    old_gemm = original[original.index('void gemm('):original.index('\n/*', original.index('void gemm('))]
    assert old_gemm in source


def test_changed_imported_source_is_rejected(monkeypatch):
    read_text = Path.read_text
    def changed(path, *args, **kwargs):
        value = read_text(path, *args, **kwargs)
        return value + '\n' if path.name == 'tb.c' else value
    monkeypatch.setattr(Path, 'read_text', changed)
    with pytest.raises(ValueError, match='hash'):
        module.compose(Path(__file__).resolve().parents[1])
