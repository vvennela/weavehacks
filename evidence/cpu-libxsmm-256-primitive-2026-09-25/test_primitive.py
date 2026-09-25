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
    library = tmp_path_factory.mktemp('gemm256-primitive')/'probe.dylib'
    subprocess.run(['clang','-O3','-march=native','-ffast-math','-shared','-fPIC',
                    str(FOLDER/'probe.c'),'-lm','-o',str(library)],check=True)
    function = ctypes.CDLL(str(library)).probe
    function.argtypes = [ctypes.c_void_p]*3
    function.restype = None
    return function


@pytest.mark.parametrize('kind', ['random','identity','zero','asymmetric'])
def test_dense_row_major_256_product_overwrites_all_outputs(primitive,kind):
    rng=np.random.default_rng(20260924)
    a=rng.standard_normal((256,256)).astype(np.float32)
    b=rng.standard_normal((256,256)).astype(np.float32)
    if kind=='identity':b=np.eye(256,dtype=np.float32)
    if kind=='zero':a[:]=0
    if kind=='asymmetric':
        a=((np.arange(256*256).reshape(256,256)%13)-6).astype(np.float32)
        b=((np.arange(256*256).reshape(256,256)%17)-8).astype(np.float32)
    original_a, original_b = a.copy(), b.copy()
    guarded=np.full(256*256+128,-98765.0,dtype=np.float32)
    c=guarded[64:-64].reshape(256,256)
    primitive(a.ctypes.data,b.ctypes.data,c.ctypes.data)
    expected=a.astype(np.float64) @ b.astype(np.float64)
    assert np.isfinite(c).all()
    scale=max(float(np.max(np.abs(expected))),1e-30)
    assert float(np.max(np.abs(c-expected)))/scale<=.002
    assert np.all(guarded[:64]==-98765.0) and np.all(guarded[-64:]==-98765.0)
    assert np.array_equal(a,original_a) and np.array_equal(b,original_b)
