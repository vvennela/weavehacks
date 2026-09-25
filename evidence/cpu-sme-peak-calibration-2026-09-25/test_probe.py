import ctypes
from pathlib import Path
import subprocess
import pytest

FOLDER=Path(__file__).resolve().parent

@pytest.fixture(scope='module')
def library(tmp_path_factory):
    path=tmp_path_factory.mktemp('sme-peak')/'probe.so'
    subprocess.run(['clang','-O3','-march=native','-shared','-fPIC',str(FOLDER/'probe.S'),str(FOLDER/'abi_check.S'),'-o',str(path)],check=True)
    return ctypes.CDLL(str(path))

@pytest.mark.parametrize('tiles',[1,2,4])
@pytest.mark.parametrize('iterations',[0,1,17])
def test_exact_fp32_accumulation_and_output_bounds(library,tiles,iterations):
    probe=getattr(library,f'sera_peak_{tiles}')
    probe.argtypes=[ctypes.c_uint64,ctypes.POINTER(ctypes.c_float)]
    probe.restype=ctypes.c_uint64
    output=(ctypes.c_float*258)(*([12345.0]*258))
    address=ctypes.cast(ctypes.byref(output,4),ctypes.POINTER(ctypes.c_float))
    lanes=probe(iterations,address)
    assert lanes==16
    expected=iterations*64//tiles
    assert list(output)[1:1+tiles*lanes]==[float(expected)]*(tiles*lanes)
    assert output[0]==12345.0
    assert all(v==12345.0 for v in list(output)[1+tiles*lanes:])


def test_streaming_transitions_preserve_callee_saved_vector_registers(library):
    function=library.sera_peak_abi_check
    function.argtypes=[ctypes.c_uint64,ctypes.POINTER(ctypes.c_float)]
    function.restype=ctypes.c_uint64
    output=(ctypes.c_float*256)()
    assert function(1,output)==0
