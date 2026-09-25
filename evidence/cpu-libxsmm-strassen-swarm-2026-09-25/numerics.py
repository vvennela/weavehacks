"""Approved Strassen stress checks; correctness only, frozen .002 error metric."""
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

SEED = 20260924
FLAGS = ('-O3','-march=native','-ffast-math','-shared','-fPIC','-lm')


def cases():
    import numpy as np
    random = np.random.default_rng(SEED)
    for delta in (.03125,.0625):
        x,y,u,v = [random.standard_normal((256,256),dtype=np.float32) for _ in range(4)]
        noise = [random.standard_normal((256,256),dtype=np.float32)*np.float32(delta) for _ in range(4)]
        a = np.block([[x,x+noise[0]],[y,y+noise[1]]])
        b = np.block([[u,v],[-u+noise[2],-v+noise[3]]])
        yield f'cancellation-{delta}',np.ascontiguousarray(a),np.ascontiguousarray(b)
    for spread in (8,12):
        inputs = []
        for _ in range(2):
            exponent = random.integers(-spread,spread+1,size=(512,512))
            sign = random.choice(np.array([-1,1],dtype=np.float32),size=(512,512))
            mantissa = 1+random.standard_normal((512,512),dtype=np.float32)*np.float32(2**-10)
            inputs.append(np.ascontiguousarray(np.ldexp(sign*mantissa,exponent),dtype=np.float32))
        yield f'scale-{spread}',*inputs


def check_library(library):
    import numpy as np
    gemm = ctypes.CDLL(str(library)).gemm
    pointer = ctypes.POINTER(ctypes.c_float)
    gemm.argtypes = [ctypes.c_int,pointer,pointer,pointer]
    gemm.restype = None
    outcomes = []
    for kind,a,b in cases():
        before_a,before_b = a.copy(),b.copy()
        storage = np.full(512*512+32,12345,dtype=np.float32)
        c = storage[16:-16].reshape(512,512)
        c.fill(7)
        gemm(512,a.ctypes.data_as(pointer),b.ctypes.data_as(pointer),c.ctypes.data_as(pointer))
        if not (np.all(storage[:16] == 12345) and np.all(storage[-16:] == 12345)):
            raise ValueError(f'Output guard overwritten: {kind}')
        if not (np.array_equal(a,before_a) and np.array_equal(b,before_b)):
            raise ValueError(f'Input modified: {kind}')
        reference = a.astype(np.float64)@b.astype(np.float64)
        error = float(np.max(np.abs(c-reference))/(np.max(np.abs(reference))+1e-9))
        if not np.isfinite(c).all() or error > .002:
            raise ValueError(f'Incorrect {kind}; relative error={error}')
        outcomes.append(dict(kind=kind,relative_error=error))
    return dict(passed=True,cases=outcomes)


def validate(source,output_path,*,timeout):
    from sera.kernel_tools import run_command
    from sera.storage import save_json
    source,output_path = Path(source).resolve(),Path(output_path).resolve()
    if output_path.exists():
        raise FileExistsError('Refusing to overwrite numerical evidence')
    start = time.monotonic()
    report = dict(schema_version='sera-strassen-numerics-v1',seed=SEED,n=512,
        tolerance=.002,compiler_flags=list(FLAGS),timing_claim=False,
        source_hash=hashlib.sha256(source.read_bytes()).hexdigest(),passed=False,stage='compile')
    try:
        with tempfile.TemporaryDirectory(prefix='sera-strassen-check-') as scratch:
            library = Path(scratch)/'kernel.so'
            run_command(['cc',str(source),'-o',str(library),*FLAGS],cwd=scratch,
                timeout=timeout,log_path=output_path.with_suffix('.compile.log'))
            report['stage'] = 'numerical-correctness'
            remaining = timeout-(time.monotonic()-start)
            if remaining <= 0:
                raise TimeoutError('Numerical correctness deadline reached')
            worker = Path(scratch)/'worker.json'
            run_command([sys.executable,str(Path(__file__).resolve()),str(library),str(worker)],
                cwd=scratch,timeout=remaining,log_path=output_path.with_suffix('.worker.log'))
            report.update(json.loads(worker.read_text()))
    except (subprocess.SubprocessError,OSError,TimeoutError) as error:
        report['error'] = type(error).__name__
    save_json(output_path,report)
    return report


if __name__ == '__main__':
    try:
        result = check_library(Path(sys.argv[1]))
    except Exception as error:
        result = dict(passed=False,error=f'{type(error).__name__}: {error}')
    Path(sys.argv[2]).write_text(json.dumps(result))
