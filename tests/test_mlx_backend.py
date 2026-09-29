"""Validate MLX requests before model loading or file mutation."""

from pathlib import Path

import pytest

from sera.backends.mlx import MLXBackend, MLXRecipe


@pytest.mark.parametrize('recipe', [{'bits': 3}, {'bits': True}, {'group_size': 7}, {'unknown': 1}])
def test_invalid_recipe_is_rejected(recipe):
    with pytest.raises(ValueError):
        MLXRecipe.model_validate(recipe)


def test_export_rejects_existing_destination_before_loading(tmp_path):
    with pytest.raises(FileExistsError):
        MLXBackend().prepare(source={'model_id': 'Qwen/Qwen3-0.6B', 'revision': 'a' * 40},
                             destination=tmp_path, recipe={'bits': 4})


def test_loading_requires_a_verified_artifact_before_importing_mlx(tmp_path, monkeypatch):
    import builtins
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name.startswith('mlx'):
            pytest.fail('Unsealed checkpoints must not reach MLX')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    with pytest.raises(FileNotFoundError):
        MLXBackend().load(tmp_path)


def test_no_runtime_or_model_dependencies_on_import():
    import subprocess, sys
    result = subprocess.run([sys.executable, '-c',
        'import sys; from sera.backends.mlx import MLXBackend; '
        'assert "mlx.core" not in sys.modules; assert "mlx_lm" not in sys.modules'],
        capture_output=True, text=True, check=True)
    assert not result.stdout


def test_conversion_uses_the_pinned_local_snapshot_for_all_export_files(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    source = {'model_id': 'Qwen/Qwen3-0.6B', 'revision': 'a' * 40}
    snapshot = tmp_path / 'snapshot'
    snapshot.mkdir()
    seen = []
    def download(**kwargs):
        assert kwargs['repo_id'] == source['model_id']
        assert kwargs['revision'] == source['revision']
        return str(snapshot)
    def convert(path, **kwargs):
        assert path == str(snapshot), 'Saving from a repo ID can reopen the unpinned main snapshot'
        seen.append(kwargs)
        destination = Path(kwargs['mlx_path'])
        destination.mkdir()
        (destination / 'config.json').write_text('{}')
        (destination / 'model.safetensors').write_bytes(b'fixture')
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(snapshot_download=download))
    monkeypatch.setitem(sys.modules, 'mlx_lm', SimpleNamespace(convert=convert))
    monkeypatch.setattr(MLXBackend, 'capabilities', lambda self: {'versions': {'mlx': 'fixture'}})
    result = MLXBackend().prepare(source=source, destination=tmp_path / 'export', recipe={'bits': 4})
    assert seen[0]['trust_remote_code'] is False
    assert seen[0]['quantize'] is True
    assert result['artifact']['source'] == source
