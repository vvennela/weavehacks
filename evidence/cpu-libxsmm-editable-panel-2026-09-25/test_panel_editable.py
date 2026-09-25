"""Correctness-only ABI checks for the optional generated 32-row primitive."""
import ctypes
import os
from pathlib import Path
import subprocess

os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['VECLIB_MAXIMUM_THREADS'] = '1'
import numpy as np
import pytest

FOLDER = Path(__file__).resolve().parent


@pytest.fixture(scope='module')
def primitive(tmp_path_factory):
    library = tmp_path_factory.mktemp('panel')/'panel.dylib'
    subprocess.run(['clang', '-O3', '-march=native', '-ffast-math', '-shared', '-fPIC',
                    str(FOLDER/'panel_probe.c'), '-lm', '-o', str(library)], check=True)
    loaded = ctypes.CDLL(str(library))
    function = loaded.panel_probe
    function.argtypes = [ctypes.c_void_p]*3
    function.restype = None
    return function


@pytest.mark.parametrize('row', [0, 31, 127, 480])
@pytest.mark.parametrize('kind', ['random', 'identity', 'zero'])
def test_panel_product_overwrites_only_selected_rows(primitive, row, kind):
    rng = np.random.default_rng(20260924)
    a = rng.standard_normal((512, 512)).astype(np.float32)
    b = rng.standard_normal((512, 512)).astype(np.float32)
    if kind == 'identity':
        b = np.eye(512, dtype=np.float32)
    elif kind == 'zero':
        a[:] = 0
    original_a, original_b = a.copy(), b.copy()
    guarded = np.full(512*512+128, -98765.0, dtype=np.float32)
    c = guarded[64:-64].reshape(512, 512)
    primitive(a[row:].ctypes.data, b.ctypes.data, c[row:].ctypes.data)
    expected = a[row:row+32].astype(np.float64) @ b.astype(np.float64)
    actual = c[row:row+32]
    assert np.isfinite(actual).all()
    scale = max(float(np.max(np.abs(expected))), 1e-30)
    assert float(np.max(np.abs(actual-expected)))/scale <= .002
    assert np.all(c[:row] == -98765.0) and np.all(c[row+32:] == -98765.0)
    assert np.all(guarded[:64] == -98765.0) and np.all(guarded[-64:] == -98765.0)
    assert np.array_equal(a, original_a) and np.array_equal(b, original_b)
