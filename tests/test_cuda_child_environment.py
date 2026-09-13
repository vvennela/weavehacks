"""CUDA wheel headers can live outside the compiler's virtual environment."""

import importlib.metadata
import os
from pathlib import Path
import shlex
from types import SimpleNamespace

import pytest

from sera.runtime import _child_environment


def wheel(root, name, files):
    entries = [Path(value) for value in files]
    for entry in entries:
        path = root / entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('test fixture')
    return SimpleNamespace(metadata={'Name': name}, files=entries,
                            locate_file=lambda entry: root / entry)


def installed_wheels(monkeypatch, tmp_path, *, curand=True, older_cuda=False):
    compiler_root = tmp_path / 'virtual environment'
    base_root = tmp_path / 'base environment'
    compiler = wheel(compiler_root, 'nvidia-cuda-nvcc', [
        'nvidia/cu13/bin/nvcc', 'nvidia/cu13/lib/libcudart.so.13',
        'nvidia/cu13/include/cuda.h'])
    wheels = [compiler]
    if curand:
        wheels.append(wheel(base_root, 'nvidia-curand', [
            'nvidia/cu13/include/curand.h', 'nvidia/cu13/include/curand_kernel.h']))
        # More than one distribution can own files in the same include directory.
        wheels.append(wheel(base_root, 'nvidia-cublas', ['nvidia/cu13/include/cublas.h']))
    if older_cuda:
        wheels.append(wheel(base_root, 'nvidia-curand-cu12', ['nvidia/cu12/include/curand.h']))
    monkeypatch.setattr(importlib.metadata, 'distribution', lambda name: compiler)
    monkeypatch.setattr(importlib.metadata, 'distributions', lambda: wheels)
    return compiler_root / 'nvidia/cu13', base_root / 'nvidia/cu13/include'


def test_split_wheel_headers_are_child_only_and_preserve_existing_flags(monkeypatch, tmp_path):
    compiler, extra_include = installed_wheels(monkeypatch, tmp_path, older_cuda=True)
    monkeypatch.setenv('NVCC_PREPEND_FLAGS', '-lineinfo -DUSER_SETTING=1')
    monkeypatch.setenv('CPATH', '/user/include')
    monkeypatch.setenv('CUDA_HOME', '/user/cuda')
    before = dict(os.environ)
    folder = tmp_path / 'run'
    folder.mkdir()

    env = _child_environment(folder, 'GPU-test')

    flags = shlex.split(env['NVCC_PREPEND_FLAGS'])
    assert flags == ['-I', str(compiler / 'include'), '-I', str(extra_include),
                     '-lineinfo', '-DUSER_SETTING=1']
    assert 'cu12' not in env['NVCC_PREPEND_FLAGS']
    assert env['CPATH'] == '/user/include'
    assert env['CUDA_HOME'] == str(compiler)
    assert env['CUDA_VISIBLE_DEVICES'] == 'GPU-test'
    assert dict(os.environ) == before
    assert (folder / 'cuda-link/libcudart.so').resolve() == compiler / 'lib/libcudart.so.13'
    assert not (compiler / 'include/curand.h').exists()  # No copied or linked system headers.


@pytest.mark.parametrize('older_cuda', [False, True])
def test_missing_cuda13_curand_fails_before_creating_links(monkeypatch, tmp_path, older_cuda):
    installed_wheels(monkeypatch, tmp_path, curand=False, older_cuda=older_cuda)
    folder = tmp_path / 'run'
    folder.mkdir()
    with pytest.raises(RuntimeError, match='CUDA 13.*curand.h'):
        _child_environment(folder, 'GPU-test')
    assert list(folder.iterdir()) == []


def test_uninstalled_or_missing_header_metadata_is_not_enough(monkeypatch, tmp_path):
    _, extra_include = installed_wheels(monkeypatch, tmp_path)
    (extra_include / 'curand.h').unlink()
    folder = tmp_path / 'run'
    folder.mkdir()
    with pytest.raises(RuntimeError, match='curand.h'):
        _child_environment(folder, 'GPU-test')


def test_no_compiler_wheel_keeps_existing_fallback(monkeypatch, tmp_path):
    def missing(name):
        raise importlib.metadata.PackageNotFoundError(name)

    def no_scan():
        pytest.fail('No compiler wheel must preserve the existing environment fallback')

    monkeypatch.setattr(importlib.metadata, 'distribution', missing)
    monkeypatch.setattr(importlib.metadata, 'distributions', no_scan)
    before = dict(os.environ)
    assert _child_environment(tmp_path, 'GPU-test') == {
        **before, 'CUDA_VISIBLE_DEVICES': 'GPU-test', 'OMP_NUM_THREADS': '2'}
    assert not (tmp_path / 'cuda-link').exists()
