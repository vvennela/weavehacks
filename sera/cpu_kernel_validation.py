"""Public deterministic GEMM correctness checks, separate from hill scoring.

Compilation and native execution run in child processes with timeouts. These
are fault boundaries for trusted local code, not security sandboxes.
"""

import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

SEED = 20260924
SIZES = (0, 1, 3, 15, 16, 17, 31, 32, 33, 63, 64, 65, 96, 127, 129)
FLAGS = ("-O3", "-march=native", "-ffast-math", "-shared", "-fPIC", "-lm")


def _check_library(library):
    import numpy as np

    gemm = ctypes.CDLL(str(library)).gemm
    pointer = ctypes.POINTER(ctypes.c_float)
    gemm.argtypes = [ctypes.c_int, pointer, pointer, pointer]
    gemm.restype = None
    random = np.random.default_rng(SEED)
    worst_error = 0.0
    for n in SIZES:
        for kind in ("random", "identity", "zero"):
            a = random.standard_normal((n, n), dtype=np.float32)
            b = random.standard_normal((n, n), dtype=np.float32)
            if kind == "identity":
                b = np.eye(n, dtype=np.float32)
            elif kind == "zero":
                b.fill(0)
            before_a, before_b = a.copy(), b.copy()
            # Use a nonzero output to detect accidental C += A@B behavior.
            storage = np.full(n * n + 32, 12345.0, dtype=np.float32)
            c = storage[16:16 + n * n].reshape(n, n)
            c.fill(7)
            gemm(n, a.ctypes.data_as(pointer), b.ctypes.data_as(pointer), c.ctypes.data_as(pointer))
            if not (np.all(storage[:16] == 12345) and np.all(storage[-16:] == 12345)):
                raise ValueError(f"Output guard overwritten at n={n}")
            if not (np.array_equal(a, before_a) and np.array_equal(b, before_b)):
                raise ValueError(f"Input modified at n={n}")
            if n == 0:
                continue
            reference = a.astype(np.float64) @ b.astype(np.float64)
            error = float(np.max(np.abs(c - reference)) / (np.max(np.abs(reference)) + 1e-9))
            if not np.isfinite(c).all() or error > 0.002:
                raise ValueError(f"Incorrect {kind} product at n={n}; relative error={error}")
            worst_error = max(worst_error, error)
    return dict(passed=True, worst_relative_error=worst_error)


def validate_cpu_kernel(source, output_path, *, timeout=60):
    """Return public correctness evidence. No performance value is computed."""
    from .kernel_tools import run_command
    from .storage import save_json

    source, output_path = Path(source).resolve(), Path(output_path).resolve()
    if output_path.exists():
        raise FileExistsError("Refusing to overwrite correctness evidence")
    started = time.monotonic()
    report = dict(schema_version="sera-cpu-correctness-v1", seed=SEED,
                  sizes=list(SIZES), input_kinds=["random", "identity", "zero"],
                  tolerance=0.002, compiler_flags=list(FLAGS), timing_claim=False,
                  source_hash=hashlib.sha256(source.read_bytes()).hexdigest(),
                  passed=False, stage="compile")
    try:
        with tempfile.TemporaryDirectory(prefix="sera-cpu-check-") as scratch:
            library = Path(scratch) / "kernel.so"
            run_command(["cc", str(source), "-o", str(library), *FLAGS],
                        cwd=scratch, timeout=timeout,
                        log_path=output_path.with_suffix(".compile.log"))
            report["stage"] = "correctness"
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError("CPU correctness deadline reached")
            # Run this installed source file without importing the entire package.
            worker = Path(scratch) / "worker.json"
            run_command([sys.executable, str(Path(__file__).resolve()), str(library), str(worker)],
                        cwd=scratch, timeout=remaining,
                        log_path=output_path.with_suffix(".worker.log"))
            report.update(json.loads(worker.read_text()))
    except (subprocess.SubprocessError, OSError, TimeoutError) as error:
        report["error"] = type(error).__name__
    save_json(output_path, report)
    return report


if __name__ == "__main__":
    try:
        result = _check_library(Path(sys.argv[1]))
    except Exception as error:
        result = dict(passed=False, error=f"{type(error).__name__}: {error}")
    Path(sys.argv[2]).write_text(json.dumps(result))
