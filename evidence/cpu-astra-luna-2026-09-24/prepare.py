"""Prepare one advised FP32 candidate; no performance scores are produced here."""
import hashlib
import json
from pathlib import Path
import subprocess
from sera.kernel_advisory import KernelAdvisoryTeam
from sera.cpu_kernel_validation import validate_cpu_kernel
from sera.storage import save_json

folder=Path(__file__).resolve().parent
repo=folder.parent.parent
old=repo/'evidence/cpu-specialists-codex-2026-09-24/search/result.json'
history=json.loads(old.read_text())['trials']
task='''Optimize single-thread row-major FP32 C=A@B on Apple M4 Pro CPU toward 1800 GFLOP/s.
ABI void gemm(int n,const float *A,const float *B,float *C). Fixed compiler Apple clang21,
-O3 -march=native -ffast-math -shared -fPIC -lm. Main shape n512, general n including
odd tails and n<=0 must work. All scratch setup, packing and allocation is timed.
No libraries, threads, answer caching, or mixed precision. Fixed correctness tolerance .002
max absolute error / max reference. Four FP32 SME ZA tile selectors only: 0..3.
Prior measurements below were ON BATTERY with large variance. They are historical context,
not an AC baseline. No prior candidate established a gain. Preserve FP32 semantics.
Consider a constant-loop n512 fast path retaining a correct general fallback, or another
coherent FP32 change supported by advice. Actual measurement will use a fresh AC baseline
and unchanged frozen hill and repeated paired controls. Do not claim performance yet.
'''
save_json(folder/'preparation.json',dict(implementation_commit=subprocess.check_output(
    ['git','rev-parse','HEAD'],text=True).strip(), target_gflops=1800,
    prior_evidence=str(old), prior_conditions='Battery; historical context only',
    current_power=subprocess.check_output(['pmset','-g','batt'],text=True),
    max_rounds=1,max_model_calls=17,performance_measurements=False))
team=KernelAdvisoryTeam(work_dir=folder/'agent',task=task,max_rounds=1,
    profile=dict(cpu='Apple M4 Pro',capabilities=['cpu','arm64','sme','neon','simd','single-thread']))
candidate=team.propose(history,timeout=1800)
if candidate is None:
    raise RuntimeError('Coordinator abstained')
source_dir=folder/'candidate'
source_dir.mkdir()
source=source_dir/'kernel.c'
source.write_text(candidate.source)
save_json(folder/'candidate.json',dict(name=candidate.name,hypothesis=candidate.hypothesis,
    source_hash=hashlib.sha256(candidate.source.encode()).hexdigest(),source=str(source)))
result=validate_cpu_kernel(source,folder/'correctness.json',timeout=120)
print(json.dumps(dict(candidate=candidate.name,correctness=result),indent=2))
