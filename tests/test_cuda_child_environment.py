"""CUDA wheel headers can live outside the compiler's virtual environment."""

import importlib.metadata
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from sera.runtime import _child_environment


@pytest.mark.parametrize('compiler_wheel', [False, True])
def test_inference_child_receives_runtime_settings_without_optimizer_secrets(
        monkeypatch, tmp_path, compiler_wheel):
    if compiler_wheel:
        installed_wheels(monkeypatch, tmp_path)
    else:
        def missing(name):
            raise importlib.metadata.PackageNotFoundError(name)
        monkeypatch.setattr(importlib.metadata, 'distribution', missing)

    private_names = ('OPENAI_API_KEY', 'WANDB_API_KEY', 'AWS_SECRET_ACCESS_KEY',
                     'DATABASE_URL', 'SERA_RELAY_DIR', 'CODEX_HOME',
                     'UNRELATED_APPLICATION_CREDENTIAL', 'PYTHONPATH', 'LD_PRELOAD')
    for name in private_names:
        monkeypatch.setenv(name, 'private-test-value')
    runtime_settings = {'HF_TOKEN': 'model-download-test-token',
                        'HF_HOME': str(tmp_path / 'model-cache'),
                        'SSL_CERT_FILE': '/runtime/ca.pem',
                        'NCCL_SOCKET_IFNAME': 'eth0',
                        'TORCH_EXTENSIONS_DIR': str(tmp_path / 'extensions'),
                        'VLLM_WORKER_MULTIPROC_METHOD': 'spawn'}
    for name, value in runtime_settings.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', 'unassigned-gpu')
    monkeypatch.setenv('OMP_NUM_THREADS', '99')
    before = dict(os.environ)
    folder = tmp_path / 'run'
    folder.mkdir()

    environment = _child_environment(folder, 'GPU-test')
    # Inspect the actual child environment, not only the function's dictionary.
    result = subprocess.run(
        [sys.executable, '-I', '-c',
         'import json, os; print(json.dumps(dict(os.environ)))'],
        env=environment, capture_output=True, text=True, check=True, timeout=10)
    received = json.loads(result.stdout)

    assert not set(private_names).intersection(received)
    assert {name: received[name] for name in runtime_settings} == runtime_settings
    assert received['CUDA_VISIBLE_DEVICES'] == 'GPU-test'
    assert received['OMP_NUM_THREADS'] == '2'
    assert received['PATH'] == environment['PATH']
    assert dict(os.environ) == before


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
    assert flags == ['-isystem', str(compiler / 'include'), '-isystem', str(extra_include),
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


def test_no_compiler_wheel_preserves_runtime_paths_without_scanning(monkeypatch, tmp_path):
    def missing(name):
        raise importlib.metadata.PackageNotFoundError(name)

    def no_scan():
        pytest.fail('No compiler wheel must preserve configured runtime paths without a scan')

    monkeypatch.setattr(importlib.metadata, 'distribution', missing)
    monkeypatch.setattr(importlib.metadata, 'distributions', no_scan)
    settings = {'PATH': '/runtime/bin', 'CUDA_HOME': '/runtime/cuda',
                'LD_LIBRARY_PATH': '/runtime/lib', 'NVCC_PREPEND_FLAGS': '-lineinfo'}
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    env = _child_environment(tmp_path, 'GPU-test')
    assert {name: env[name] for name in settings} == settings
    assert env['CUDA_VISIBLE_DEVICES'] == 'GPU-test'
    assert env['OMP_NUM_THREADS'] == '2'
    assert not (tmp_path / 'cuda-link').exists()


def test_vllm_duplicate_system_include_does_not_let_base_headers_shadow_compiler(monkeypatch, tmp_path):
    host_compiler = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
    if host_compiler is None:
        pytest.skip('A local C preprocessor is required for the include-precedence regression')
    compiler, base_include = installed_wheels(monkeypatch, tmp_path)
    for include, macro in [(compiler / 'include', '#define __cudaLaunch(a,b) compiler_core'),
                           (base_include, '#define __cudaLaunch(a) wrong_base_core')]:
        (include / 'crt').mkdir()
        (include / 'crt/host_runtime.h').write_text(macro + '\n')
    (base_include / 'curand.h').write_text('curand_available\n')
    monkeypatch.setenv('NVCC_PREPEND_FLAGS', '')
    for name in ('CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH'):
        monkeypatch.delenv(name, raising=False)
    folder = tmp_path / 'run'
    folder.mkdir()
    child_env = _child_environment(folder, 'GPU-test')
    injected = shlex.split(child_env['NVCC_PREPEND_FLAGS'])
    # vLLM's build already marks the checked compiler headers as system headers.
    # A duplicate -I is ignored; any base -I then shadows that compiler directory.
    command = [host_compiler, *injected, '-isystem', str(compiler / 'include'),
               '-E', '-P', '-x', 'c', '-']
    result = subprocess.run(command, input='#include <crt/host_runtime.h>\n'
                            '#include <curand.h>\n__cudaLaunch(1,2)\n',
                            capture_output=True, text=True, timeout=10, env=child_env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ['curand_available', 'compiler_core']
