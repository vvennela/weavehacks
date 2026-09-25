"""Exercise joint swarm planning without timing on battery power."""
import hashlib
import json
from pathlib import Path
import subprocess
from sera.kernel_advisory import KernelAdvisoryTeam
from sera.cpu_kernel_validation import validate_cpu_kernel
from sera.storage import save_json

folder=Path(__file__).resolve().parent
repo=folder.parent.parent
previous=repo/'evidence/cpu-specialists-codex-2026-09-24/search/result.json'
history=json.loads(previous.read_text())['trials']
prepared=repo/'evidence/cpu-astra-luna-2026-09-24'
source_info=json.loads((prepared/'candidate.json').read_text())
# Public correctness is distinct from signed performance validation.
history.append(dict(name=source_info['name'],source=source_info['source'],
    source_hash=source_info['source_hash'],hypothesis=source_info['hypothesis'],
    status='public-correctness-only',scores=[],control_scores=[],promoted=False,
    error='48 public correctness cases passed; no AC timing exists for this source.'))
task='''Optimize single-thread row-major FP32 C=A@B on Apple M4 Pro toward 1800 GFLOP/s.
ABI void gemm(int n,const float *A,const float *B,float *C). Fixed Apple clang21:
-O3 -march=native -ffast-math -shared -fPIC -lm. Main shape n512; handle general
n including odd tails and n<=0. Packing and scratch allocation stay timed inside gemm.
No external libraries, threads, answer caching or mixed precision. Fixed error limit .002
max absolute error / max absolute reference. Only four FP32 ZA MOPA selectors 0..3.
HISTORICAL SCORES BELOW ARE BATTERY MEASUREMENTS WITH LARGE VARIANCE, not an AC baseline.
No prior candidate established a gain. The last constant-loop 512 source passed public
correctness only; it has NOT been timed. The swarm jointly chooses a batch of distinct
experiments. Prefer informative, legal FP32 changes and avoid repeating existing source.
Astra implements the swarm ranking, then each actual experiment is measured serially
against fresh AC controls. No acceptance or speedup claim may precede those measurements.
'''
modules=('kernel_advisory.py','kernel_swarm_plan.py','codex_agent.py','kernel_search.py',
         'cpu_kernel_validation.py','kernel_advisor_roles.py','kernel_tools.py')
save_json(folder/'preparation.json',dict(implementation_commit=subprocess.check_output(
    ['git','rev-parse','HEAD'],text=True).strip(),implementation_hashes={name:hashlib.sha256(
    (repo/'sera'/name).read_bytes()).hexdigest() for name in modules},
    target_gflops=1800,max_implementations=3,batch_size=3,max_model_calls=108,
    performance_measurements=False,power=subprocess.check_output(['pmset','-g','batt'],text=True)))
team=KernelAdvisoryTeam(work_dir=folder/'agent',task=task,max_rounds=3,batch_size=3,max_calls=108,
    profile=dict(cpu='Apple M4 Pro',capabilities=['cpu','arm64','sme','neon','simd','single-thread']))
candidate=team.propose(history,timeout=1800)
if candidate is None:
    raise RuntimeError('Swarm produced no implementable experiment')
source_dir=folder/'candidate'
source_dir.mkdir()
source=source_dir/'kernel.c'
source.write_text(candidate.source)
save_json(folder/'candidate.json',dict(name=candidate.name,hypothesis=candidate.hypothesis,
    source_hash=hashlib.sha256(candidate.source.encode()).hexdigest(),source=str(source)))
result=validate_cpu_kernel(source,folder/'correctness.json',timeout=120)
print(json.dumps(dict(candidate=candidate.name,correctness=result),indent=2))
