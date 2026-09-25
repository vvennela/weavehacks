import importlib.util
from pathlib import Path
import numpy as np

spec = importlib.util.spec_from_file_location('strassen_numerics', Path(__file__).with_name('numerics.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

GOOD = '''
void gemm(int n,const float*a,const float*b,float*c) {
  for(int i=0;i<n;i++) for(int j=0;j<n;j++) {
    float s=0; for(int k=0;k<n;k++) s+=a[i*n+k]*b[k*n+j];
    c[i*n+j]=s;
  }
}
'''


def test_stress_inputs_are_deterministic_fp32_and_exercise_cancellation_and_scale():
    first, second = list(module.cases()), list(module.cases())
    assert len(first) == 4
    for (kind,a,b),(again,x,y) in zip(first,second):
        assert kind == again
        assert a.shape == b.shape == (512,512)
        assert a.dtype == b.dtype == np.float32
        assert a.flags.c_contiguous and b.flags.c_contiguous
        assert np.array_equal(a,x) and np.array_equal(b,y)
        if kind.startswith('cancellation'):
            ref = a.astype(np.float64)@b.astype(np.float64)
            uncancelled = abs(a.astype(np.float64))@abs(b.astype(np.float64))
            assert np.max(abs(ref)) < .02*np.max(uncancelled)
        else:
            assert np.max(abs(a))/np.min(abs(a)) > 10000


def check(tmp_path, source):
    path = tmp_path/'kernel.c'
    path.write_text(source)
    return module.validate(path,tmp_path/'numerics.json',timeout=30)


def test_correct_dense_fp32_kernel_passes_stress_suite(tmp_path):
    result = check(tmp_path,GOOD)
    assert result['passed']
    assert len(result['cases']) == 4
    assert result['tolerance'] == .002
    assert not result['timing_claim']


def test_accumulating_kernel_is_rejected(tmp_path):
    result = check(tmp_path,GOOD.replace('c[i*n+j]=s;', 'c[i*n+j]+=s;'))
    assert not result['passed']


def test_guard_overwrite_is_rejected(tmp_path):
    result = check(tmp_path,GOOD.replace('c[i*n+j]=s;', 'c[i*n+j]=s; c[n*n]=0;'))
    assert not result['passed']
    assert 'guard' in result['error']
