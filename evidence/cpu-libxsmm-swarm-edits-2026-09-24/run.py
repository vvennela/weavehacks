"""Fresh AC block while the user leaves the Mac idle; frozen scoring unchanged."""
import hashlib
import sys
from copy import deepcopy
from sera.storage import content_hash
from sera.kernel_swarm_plan import rank_experiments
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
prepare_only='--prepare-only' in sys.argv
initial_host=host_observation()
if not prepare_only:
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
# Transfer only the recorded swarm plan and spent budgets. Measurements below
# start fresh. This is an audited research continuation, not a public resume API.
previous=repo/'evidence/cpu-libxsmm-swarm-2026-09-24'
old_state=json.loads((previous/'agent/state.json').read_text())
old_result=json.loads((previous/'search/result.json').read_text())
assert old_state['calls']==32 and old_state['implementations']==1
assert len(old_state['rounds'])==1 and old_result['status']=='failed'
old_round=old_state['rounds'][0]
assert old_round['board_hash']==content_hash(old_round['board'])
ids=[item['experiment_id'] for item in old_round['board']]
assert len(old_round['ballots'])==15 and all(b['status']=='received' for b in old_round['ballots'])
assert rank_experiments(ids,[b['ranking'] for b in old_round['ballots']],limit=3)==old_round['experiment_order']
assert old_result['trials'][0]['source_hash']==hashlib.sha256(baseline.read_bytes()).hexdigest()
failed=old_round['implementations'][0]
assert failed['status']=='failed' and 'TimeoutExpired' in failed['error']
assert old_state['pending']==old_round['experiment_order'][1:]
team.rounds=deepcopy(old_state['rounds'])
team.rounds[0]['prior_phase_status']=team.rounds[0]['status']
team.rounds[0]['status']='selected'
team.pending=list(old_round['experiment_order'])
team.calls=old_state['calls']
team.proposal_count=old_state['implementations']
team._save()
save_json(folder/'plan-transfer.json',dict(previous_phase=str(previous),
    prior_state_sha256=hashlib.sha256((previous/'agent/state.json').read_bytes()).hexdigest(),
    board_hash=old_round['board_hash'],retained_order=team.pending,spent_calls=team.calls,
    spent_attempts=team.proposal_count,remaining_attempts=5,remaining_model_calls=76,
    measurements_imported=False,reason='Retry the unchanged swarm-selected experiment with guarded edits after full-file response timeout'))
modules=('kernel_advisory.py','kernel_swarm_plan.py','codex_agent.py','kernel_search.py',
         'cpu_kernel_validation.py','kernel_advisor_roles.py','kernel_tools.py','kernel_edits.py')
save_json(folder/'controls.json',dict(implementation_commit=subprocess.check_output(
    ['git','rev-parse','HEAD'],text=True).strip(),implementation_hashes={name:hashlib.sha256(
    (repo/'sera'/name).read_bytes()).hexdigest() for name in modules},
    baseline=str(baseline),baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
    target_gflops=1800,max_candidates=6,batch_size=3,max_model_calls=108,max_seconds=1200,
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
if prepare_only:
    # Generate and check code against prior public AC evidence. Never score here.
    candidate=team.propose(old_result['trials'],timeout=180)
    if candidate is None:
        raise RuntimeError('Swarm selected no new candidate')
    prepared=folder/'prepared'
    prepared.mkdir()
    source=prepared/'kernel.c'
    source.write_text(candidate.source)
    save_json(prepared/'candidate.json',dict(name=candidate.name,hypothesis=candidate.hypothesis,
        specialist_id=candidate.specialist_id,source_hash=hashlib.sha256(source.read_bytes()).hexdigest(),
        source=str(source.resolve()),performance_measured=False,host=initial_host))
    check=validate_cpu_kernel(source,prepared/'public-correctness.json',timeout=120)
    print('PREPARED',json.dumps(dict(source=str(source),correctness=check,performance_measured=False)),flush=True)
    raise SystemExit(0)
try:
    report=optimize_kernel(baseline=KernelCandidate('libxsmm-aot-reference',baseline.read_text(),'Pinned LIBXSMM SME reference adapted to the frozen row-major beta-zero ABI'),
        propose=team,evaluate=evaluate,validate=validate_cpu_kernel,output_dir=folder/'search',
        max_candidates=6,target_gflops=1800,max_seconds=1200)
    print('RESULT',json.dumps({key:report.get(key) for key in
        ('status','target_met','final_gflops','winner_source','stop_reason')}),flush=True)
finally:
    if (folder/'search/result.json').exists():
        team.observe(json.loads((folder/'search/result.json').read_text())['trials'])
