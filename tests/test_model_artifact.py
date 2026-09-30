"""Artifact identity must bind every exported file and its source/recipe."""

import json

import pytest

from sera.model_artifact import seal_artifact, verify_artifact

SOURCE = {'model_id': 'Qwen/Qwen3-0.6B', 'revision': 'a' * 40}


def exported(tmp_path):
    root = tmp_path / 'model'
    root.mkdir()
    (root / 'config.json').write_text('{}')
    (root / 'model.safetensors').write_bytes(b'fixture only, not actual model weights')
    return root


def seal(root):
    return seal_artifact(root, backend='mlx', source=SOURCE,
                         recipe={'bits': 4, 'group_size': 64}, versions={'mlx': 'test'})


def test_artifact_identity_is_portable_and_detects_changed_weights(tmp_path):
    import shutil
    root = exported(tmp_path)
    manifest = seal(root)
    assert verify_artifact(root) == manifest
    copied = tmp_path / 'copied'
    shutil.copytree(root, copied)
    assert verify_artifact(copied)['artifact_id'] == manifest['artifact_id']
    (copied / 'model.safetensors').write_bytes(b'changed weights')
    with pytest.raises(ValueError, match='files'):
        verify_artifact(copied)


@pytest.mark.parametrize('change', ['recipe', 'source', 'extra-file', 'removed-file', 'symlink'])
def test_artifact_rejects_changed_provenance_or_file_tree(tmp_path, change):
    root = exported(tmp_path)
    seal(root)
    path = root / 'sera-artifact.json'
    manifest = json.loads(path.read_text())
    if change in ('recipe', 'source'):
        manifest[change] = {'forged': True}
        path.write_text(json.dumps(manifest))
    elif change == 'extra-file':
        (root / 'new-file').write_text('unrecorded')
    elif change == 'removed-file':
        (root / 'config.json').unlink()
    else:
        (root / 'link').symlink_to(root / 'config.json')
    with pytest.raises(ValueError):
        verify_artifact(root)


def test_cannot_seal_partial_or_unpinned_checkpoint(tmp_path):
    root = tmp_path / 'partial'
    root.mkdir()
    with pytest.raises(ValueError):
        seal(root)
    root = exported(tmp_path)
    with pytest.raises(ValueError):
        seal_artifact(root, backend='mlx', source=SOURCE | {'revision': 'main'},
                      recipe={}, versions={})
    assert not (root / 'sera-artifact.json').exists()


def test_sharded_checkpoint_hashing_is_bounded_and_keeps_exact_identity(tmp_path, monkeypatch):
    import hashlib
    import threading
    import time
    from contextlib import contextmanager
    from pathlib import Path

    from sera.model_artifact import _checkpoint_files

    root = exported(tmp_path)
    for index in range(12):
        (root / f'shard-{index:02}.safetensors').write_bytes(bytes([index]) * 4096)
    expected = {p.name: {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                         'bytes': p.stat().st_size} for p in root.iterdir()}
    original = Path.open
    lock = threading.Lock()
    active = peak = 0

    @contextmanager
    def tracked_open(path, *args, **kwargs):
        nonlocal active, peak
        with original(path, *args, **kwargs) as stream:
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                time.sleep(0.02)
                yield stream
            finally:
                with lock:
                    active -= 1

    monkeypatch.setattr(Path, 'open', tracked_open)
    assert _checkpoint_files(root) == expected
    assert 1 < peak <= 4
