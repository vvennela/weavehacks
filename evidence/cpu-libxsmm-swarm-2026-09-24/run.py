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
baseline=repo/'evidence/cpu-libxsmm-reference-2026-09-24/editable/kernel.c'
initial_host=host_observation()
require_ac(initial_host)
reference_dir=repo/'evidence/cpu-libxsmm-reference-2026-09-24'
reference_result=json.loads((reference_dir/'baseline-run/search/result.json').read_text())
reference_evidence=dict(provenance=json.loads((reference_dir/'source-provenance.json').read_text()),
    roundtrip=json.loads((reference_dir/'assembly-roundtrip.json').read_text()),
    prior_validation=reference_result['trials'][0]['scores'],prior_final=reference_result['final_gflops'],
    algorithm=(reference_dir/'algorithm-luna.md').read_text(),
    comparability=(reference_dir/'benchmark-contract-luna.md').read_text())
task="""The user selected LIBXSMM's published SME approach as the starting point, then asked Sera
to make it faster. Optimize the supplied standalone, ahead-of-time LIBXSMM reference kernel
for single-thread row-major FP32 C=A@B on Apple M4 Pro toward >1800 GFLOP/s.
The reference's editable inline assembly roundtrips to exactly the 2500 bytes generated
by pinned LIBXSMM10490f10 for colmajorNN512 alpha1beta0. Its wrapper swaps operands so
C_row=A_row*B_row. Its general-size fallback retains the previous predicated SME kernel.
This imported baseline is NOT a Sera discovery. All source carries the BSD3Clause notice;
preserve it in every candidate. No LIBXSMM library is linked at execution time.

ABI void gemm(int n,const float *A,const float *B,float *C). Fixed Apple clang21 flags
-O3 -march=native -ffast-math -shared -fPIC -lm. Main n512; retain correct general n,
odd tails and n<=0. FP32 tolerance.002. No mixed precision, external libraries, threads,
cached matrix values/answers or benchmark edits. All packing and allocation remains
inside gemm, including the generated reference's stack packing. Do not hoist work outside
the timed call. This is normal code optimization, never input-specific specialization.

Hardware verified:SME2,16FP32 lanes per streaming vector, four FP32ZA tiles (0..3),
PcoreL1D131072bytes,EcoreL1D65536bytes,cacheline128bytes. Do not infer which core a
measurement used. AC power is checked around every score; user has agreed to idle the Mac.
Runtime conditions still vary. Historical scores are context, not current paired controls.

Fifteen Luna specialists jointly rank experiments; Astra-high implements exactly the
selected experiments and reviews measured results. You may edit the actual assembly,
its C wrapper or packing implementation within this contract. Keep correct register/stack
lifetimes, platform ABI, labels, balanced streaming-state transitions and safe bounds.
Use the supplied current source, not generic guesses about how LIBXSMM works. There are
already SME2 paired loads and grouped ZA-to-SVE transfers; merely proposing those again
is not a change. Differentiate the two K loops and transpose/store blocks as needed.
Do not replace this with the earlier ad hoc baseline and call that an optimization.

Each specialist should propose a concrete falsifiable change within its own role, naming
the exact source/block to change, expected benefit, risks and validation. Unproven gains
are normal hypotheses; abstain only for no legal distinct proposal. Avoid all roles
recommending the same generic load tweak. Do not claim a measured cause from instruction
counts. Astra may combine a prior correct unpromoted source with the selected new change,
but must not combine unrelated experiments or repeat an identical source.

Pinned reference evidence and historical local baseline:
"""+json.dumps(reference_evidence)
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
    reference_evidence=reference_evidence,driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
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
    report=optimize_kernel(baseline=KernelCandidate('libxsmm-aot-reference',baseline.read_text(),'Pinned LIBXSMM SME reference adapted to the frozen row-major beta-zero ABI'),
        propose=team,evaluate=evaluate,validate=validate_cpu_kernel,output_dir=folder/'search',
        max_candidates=6,target_gflops=1800,max_seconds=1800)
    print('RESULT',json.dumps({key:report.get(key) for key in
        ('status','target_met','final_gflops','winner_source','stop_reason')}),flush=True)
finally:
    if (folder/'search/result.json').exists():
        team.observe(json.loads((folder/'search/result.json').read_text())['trials'])
