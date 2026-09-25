"""Correctness-only checks: these tests make no performance claim."""
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
    library = tmp_path_factory.mktemp('transpose-primitives')/'probe.dylib'
    subprocess.run(['clang','-O3','-march=native','-ffast-math','-shared','-fPIC',
                    str(FOLDER/'probe.c'),'-lm','-o',str(library)],check=True)
    function = ctypes.CDLL(str(library)).probe
    function.argtypes = [ctypes.c_int]+[ctypes.c_void_p]*3
    function.restype = None
    return function


@pytest.mark.parametrize('variant', [1,2,3])
@pytest.mark.parametrize('kind', ['random','identity','zero'])
def test_descriptor_mapping_overwrites_full_product(primitive,variant,kind):
    rng=np.random.default_rng(20260924)
    a=rng.standard_normal((512,512)).astype(np.float32)
    b=rng.standard_normal((512,512)).astype(np.float32)
    if kind=='identity':b=np.eye(512,dtype=np.float32)
    if kind=='zero':a[:]=0
    # Column-major op(X) @ op(Y) = B.T @ A.T = C.T.
    x=np.ascontiguousarray(b.T) if variant & 1 else b.copy()
    y=np.ascontiguousarray(a.T) if variant & 2 else a.copy()
    original_x,original_y=x.copy(),y.copy()
    guarded=np.full(512*512+128,-98765.0,dtype=np.float32)
    c=guarded[64:-64].reshape(512,512)
    primitive(variant,x.ctypes.data,y.ctypes.data,c.ctypes.data)
    expected=a.astype(np.float64) @ b.astype(np.float64)
    assert np.isfinite(c).all()
    scale=max(float(np.max(np.abs(expected))),1e-30)
    assert float(np.max(np.abs(c-expected)))/scale<=.002
    assert np.all(guarded[:64]==-98765.0) and np.all(guarded[-64:]==-98765.0)
    assert np.array_equal(x,original_x) and np.array_equal(y,original_y)
