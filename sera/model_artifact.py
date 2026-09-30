"""Immutable, portable identities for locally exported model checkpoints."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .hardware import ModelDescriptor
from .storage import content_hash, save_json

MANIFEST = 'sera-artifact.json'
SCHEMA = 'sera-model-artifact-v1'


def _checkpoint_files(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Artifact must be a real checkpoint directory')
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Artifact files cannot contain symlinks')
        if path.is_file() and path != root / MANIFEST:
            files.append(path)

    def hash_file(path):
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return path.relative_to(root).as_posix(), {
            'sha256': digest.hexdigest(), 'bytes': path.stat().st_size}

    files.sort(key=lambda path: (-path.stat().st_size, path.as_posix()))
    records = {}
    # Start large shards together so small metadata files do not delay them.
    # Bound open files, queued work, and read buffers while hashing large shards.
    # Ordered results preserve the existing portable manifest and artifact ID.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for offset in range(0, len(files), 4):
            records.update(pool.map(hash_file, files[offset:offset + 4]))
    if 'config.json' not in records or not any(name.endswith('.safetensors') for name in records):
        raise ValueError('Checkpoint requires config.json and safetensors weights')
    return dict(sorted(records.items()))


def seal_artifact(folder, *, backend, source, recipe, versions):
    """Bind a completed export to source, recipe, versions, and all file bytes.

    This proves identity, not model quality, compatibility, or a performance gain.
    Existing manifests cannot be replaced by this function.
    """
    root = Path(folder)
    if (root / MANIFEST).exists():
        raise ValueError('Artifact is already sealed')
    source = ModelDescriptor.model_validate(source).model_dump()
    if backend not in {'mlx', 'cuda', 'rocm'}:
        raise ValueError('Unsupported artifact backend')
    record = {'schema_version': SCHEMA, 'backend': backend, 'source': source,
                  'recipe': recipe, 'versions': versions, 'files': _checkpoint_files(root)}
    record['artifact_id'] = content_hash(record)
    save_json(root / MANIFEST, record)
    return record


def verify_artifact(folder, *, expected_id=None, backend=None):
    """Reject edited provenance, missing/extra files, symlinks, or changed bytes."""
    root = Path(folder)
    if root.is_symlink() or (root / MANIFEST).is_symlink():
        raise ValueError('Artifact and manifest cannot be symlinks')
    record = json.loads((root / MANIFEST).read_text())
    fields = {'schema_version', 'backend', 'source', 'recipe', 'versions', 'files', 'artifact_id'}
    if not isinstance(record, dict) or set(record) != fields or record['schema_version'] != SCHEMA:
        raise ValueError('Unsupported artifact manifest')
    ModelDescriptor.model_validate(record['source'])
    if record['backend'] not in {'mlx', 'cuda', 'rocm'}:
        raise ValueError('Unsupported artifact backend')
    identity = content_hash({key: value for key, value in record.items() if key != 'artifact_id'})
    if identity != record['artifact_id'] or (expected_id is not None and identity != expected_id):
        raise ValueError('Artifact identity does not match its manifest')
    if backend is not None and record['backend'] != backend:
        raise ValueError('Artifact backend does not match the selected runtime')
    if _checkpoint_files(root) != record['files']:
        raise ValueError('Artifact files changed after export')
    return record
