import shutil

import pytest

from sera.cpu_kernel_validation import validate_cpu_kernel


pytestmark = pytest.mark.skipif(shutil.which("cc") is None, reason="C compiler required")

GOOD = '''
void gemm(int n, const float *a, const float *b, float *c) {
  for (int i=0; i<n; ++i) for (int j=0; j<n; ++j) {
    float s=0; for (int k=0; k<n; ++k) s += a[i*n+k]*b[k*n+j];
    c[i*n+j]=s;
  }
}
'''


def check(tmp_path, source):
    path = tmp_path / "kernel.c"
    path.write_text(source)
    return validate_cpu_kernel(path, tmp_path / "correctness.json", timeout=30)


def test_correct_kernel_passes_fixed_odd_and_tile_edge_shapes(tmp_path):
    report = check(tmp_path, GOOD)
    assert report["passed"] is True
    assert 33 in report["sizes"] and 65 in report["sizes"]
    assert report["seed"] == 20260924
    assert report["timing_claim"] is False


def test_kernel_correct_only_on_hill_shapes_fails(tmp_path):
    source = GOOD.replace("for (int i=0;", "if(n != 96 && n != 512) return; for (int i=0;", 1)
    assert check(tmp_path, source)["passed"] is False


def test_output_overrun_is_rejected(tmp_path):
    source = GOOD.replace("c[i*n+j]=s;", "c[i*n+j]=s; c[n*n]=0;")
    report = check(tmp_path, source)
    assert report["passed"] is False
    assert "guard" in report["error"]


def test_compiler_failure_is_recorded(tmp_path):
    report = check(tmp_path, "not valid c")
    assert report["passed"] is False
    assert report["stage"] == "compile"


def test_broken_512_fast_path_is_rejected(tmp_path):
    source = GOOD.replace('for (int i=0;', 'if(n == 512) return; for (int i=0;', 1)
    report = check(tmp_path, source)
    assert report['passed'] is False
    assert 'n=512' in report['error']
