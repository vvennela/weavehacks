"""Fresh AC block while the user leaves the Mac idle; frozen scoring unchanged."""
import hashlib
import json
from pathlib import Path
import subprocess
from examples.optimize_cpu_kernel import host_observation, require_ac
from sera.cpu_kernel_validation import validate_cpu_kernel
from sera.kernel_advisory import KernelAdvisoryTeam
from sera.kernel_search import KernelCandidate, optimize_kernel
from sera.kernel_tools import HillsKernelEvaluator
from sera.storage import save_json

folder=Path(__file__).resolve().parent
repo=folder.parent.parent
baseline=repo/'evidence/cpu-specialists-codex-2026-09-24/search/trial-000/source/kernel.c'
initial_host=host_observation()
require_ac(initial_host)
prior=json.loads((repo/'evidence/cpu-swarm-ac-idle-2026-09-24/prior-evidence.json').read_text())
research=json.loads((repo/'evidence/cpu-sme2-load-probe-2026-09-24/research.json').read_text())
probe_dir=repo/'evidence/cpu-sme2-load-probe-2026-09-24'
probes={name:(probe_dir/name).read_text() for name in ('probe.c','probe.s','correctness.json','indirect-store.c','indirect-store.s','indirect-store-correctness.json')}
task='''Optimize single-thread row-major FP32 C=A@B on Apple M4 Pro toward 1800 GFLOP/s.
ABI void gemm(int n,const float *A,const float *B,float *C). Frozen Apple clang21 flags:
-O3 -march=native -ffast-math -shared -fPIC -lm. Main n512; retain correct general n,
odd tails and n<=0. No mixed precision, external libraries, threads, cached answers,
or benchmark edits. All allocation and packing stays inside gemm. Fixed tolerance .002.
Runtime hardware probe established 16 FP32 lanes (512bits) per streaming vector.
The FP32 SME MOPA selector range is0..3. There are four ZA accumulators, not eight.

Specialists jointly select experiments, then Astra implements them and reviews actual
results. Each proposal must identify its base source by name/hash and the concrete change.
You may build on any correct prior source, even if it was not promoted: experiments may
combine a useful existing fast path with one new change. Acceptance still needs the fixed
gates. Inspect the supplied source AND actual compiler output before proposing an optimization.
Do not recommend a transformation already emitted by the compiler or already present in source.
Avoid repeating identical source under another name. Uncertain speedups are valid research
hypotheses: experiments resolve uncertainty. Do not abstain merely because a speedup is
unproven. A new combination of existing correct code with a new change is useful.
The earlier idle round over-abstained and generated no new source. Propose distinct,
falsifiable changes and use the new supplied primary-source and locally verified compiler
facts. No instruction count or external benchmark is evidence of a gain on this hill.
The prior A-reuse candidate spilled/reloaded partial C every k and measured only48-50GFLOP/s;
do not repeat that tradeoff. Pointer advancement and two-step unrolling did not establish
an accepted gain in the noisy prior block. The swarm should seek useful new evidence.

The user will leave the Mac idle for THIS new AC block. Historical AC results below came
from the previous block and are research context only. Do not mix them into current paired
controls or promotion eligibility. Use fresh measurements in the supplied live history.
Compiler blocks are STATIC generated instructions, not measured cycle counts or speedups.
A body's instruction count does not by itself establish a performance gain.

Historical AC evidence and fixed-flag compiler output:
'''+json.dumps(prior)+'\nNew research evidence and hypotheses:\n'+json.dumps(research)+'\nLocally compiled and correctness-tested instruction probes (NOT GEMM timing):\n'+json.dumps(probes)
profile=dict(cpu='Apple M4 Pro',power='AC',user_idle_requested=True,streaming_fp32_lanes=16,
             sme2=True,p_core_l1d_bytes=131072,e_core_l1d_bytes=65536,cache_line_bytes=128,
             capabilities=['cpu','arm64','sme','sme2','neon','simd','single-thread'])
team=KernelAdvisoryTeam(work_dir=folder/'agent',task=task,profile=profile,
                       max_rounds=6,batch_size=3,max_calls=108)
modules=('kernel_advisory.py','kernel_swarm_plan.py','codex_agent.py','kernel_search.py',
         'cpu_kernel_validation.py','kernel_advisor_roles.py','kernel_tools.py')
save_json(folder/'controls.json',dict(implementation_commit=subprocess.check_output(
    ['git','rev-parse','HEAD'],text=True).strip(),implementation_hashes={name:hashlib.sha256(
    (repo/'sera'/name).read_bytes()).hexdigest() for name in modules},
    baseline=str(baseline),baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
    target_gflops=1800,max_candidates=6,batch_size=3,max_model_calls=108,max_seconds=1800,
    host=initial_host,profile=profile,user_idle_confirmation='I can leave it idle for measurements',
    historical_evidence_sha256=hashlib.sha256((repo/'evidence/cpu-swarm-ac-idle-2026-09-24/prior-evidence.json').read_bytes()).hexdigest(),
    research_sha256=hashlib.sha256((probe_dir/'research.json').read_bytes()).hexdigest(),
    probe_source_hashes={name:hashlib.sha256((probe_dir/name).read_bytes()).hexdigest() for name in ('probe.c','indirect-store.c')},
    scoring='Frozen hill; 3validation repeats; paired controls; separated ranges plus5%; Astra adjudication; finalholdout'))
evaluator=HillsKernelEvaluator(workspace='/Users/vishnuv/Documents/Documents/kernel-opt')
def evaluate(source_dir,report_path,*,final,timeout):
    before=host_observation()
    require_ac(before)
    if before['power_settings']!=initial_host['power_settings']:
        raise RuntimeError('Power settings changed')
    observations=dict(before=before)
    host_path=Path(report_path).with_suffix('.host.json')
    save_json(host_path,observations)
    try:
        report=evaluator(source_dir,report_path,final=final,timeout=timeout)
        print('SCORED',report_path,report.get('passed'),report.get('metrics'),flush=True)
        return report
    finally:
        after=host_observation()
        observations['after']=after
        save_json(host_path,observations)
        require_ac(after)
        if after['power_settings']!=initial_host['power_settings']:
            raise RuntimeError('Power settings changed during scoring')
try:
    report=optimize_kernel(baseline=KernelCandidate('existing-sme',baseline.read_text(),'Fresh AC idle baseline with SME2 research context'),
        propose=team,evaluate=evaluate,validate=validate_cpu_kernel,output_dir=folder/'search',
        max_candidates=6,target_gflops=1800,max_seconds=1800)
    print('RESULT',json.dumps({key:report.get(key) for key in
        ('status','target_met','final_gflops','winner_source','stop_reason')}),flush=True)
finally:
    if (folder/'search/result.json').exists():
        team.observe(json.loads((folder/'search/result.json').read_text())['trials'])
