"""Immutable, portable identities for locally exported model checkpoints."""

import hashlib
import json
from pathlib import Path

from .hardware import ModelDescriptor
from .storage import content_hash, save_json

MANIFEST = 'sera-artifact.json'
SCHEMA = 'sera-model-artifact-v1'


def _checkpoint_files(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Artifact must be a real checkpoint directory')
    records = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Artifact files cannot contain symlinks')
        if not path.is_file() or path == root / MANIFEST:
            continue
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        records[path.relative_to(root).as_posix()] = {
            'sha256': digest.hexdigest(), 'bytes': path.stat().st_size}
    if 'config.json' not in records or not any(name.endswith('.safetensors') for name in records):
        raise ValueError('Checkpoint requires config.json and safetensors weights')
    return records


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
