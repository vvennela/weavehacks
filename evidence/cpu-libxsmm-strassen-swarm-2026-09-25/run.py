"""Approved one-level Strassen and classical methods, ranked by the15-specialist board."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

import numerics

from examples.optimize_cpu_kernel import host_observation, check_power, power_source
from sera.cpu_kernel_validation import validate_cpu_kernel
from sera.kernel_advisory import KernelAdvisoryTeam
from sera.kernel_search import KernelCandidate, optimize_kernel
from sera.kernel_tools import HillsKernelEvaluator
from sera.storage import save_json

def load_prior(evidence, names):
    """Keep phase identity, all scored trials, and failed/skipped attempts separate."""
    prior = []
    for name in names:
        folder = evidence / name
        state = json.loads((folder/'agent/state.json').read_text())
        result = json.loads((folder/'search/result.json').read_text())
        controls = json.loads((folder/'controls.json').read_text())
        attempts = []
        for batch in state['rounds']:
            for attempt in batch['implementations']:
                item = {key: attempt[key] for key in
                        ('experiment_id', 'status', 'name', 'hypothesis', 'reason', 'source_hash')
                        if key in attempt}
                if 'error' in attempt:
                    item['error_type'] = attempt['error'].split(':', 1)[0]
                attempts.append(item)
        trials = [{key: trial.get(key) for key in
                   ('name', 'hypothesis', 'source_hash', 'status', 'scores', 'control_scores',
                    'promoted', 'adjudication')} for trial in result['trials']]
        prior.append(dict(phase=name, calls=state['calls'], implementations=state['implementations'],
                          profile=controls.get('profile', {}), host=controls.get('host'),
                          status=result['status'], attempts=attempts, trials=trials))
    return prior


def main():
    folder = Path(__file__).resolve().parent
    repo = folder.parent.parent
    prepared = folder
    reference = repo/'evidence/cpu-libxsmm-reference-2026-09-24'
    baseline = prepared/'baseline/kernel.c'
    source = baseline.read_text()
    source_hash = hashlib.sha256(source.encode()).hexdigest()
    correctness = json.loads((prepared/'baseline-correctness.json').read_text())
    if correctness['source_hash'] != source_hash or not correctness['passed']:
        raise ValueError('Prepared baseline does not match its correctness record')
    initial = host_observation()
    check_power(initial, initial)
    prior = load_prior(repo/'evidence', (
        'cpu-libxsmm-measure-prepared-2026-09-24',
        'cpu-libxsmm-next-2026-09-25',
        'cpu-libxsmm-next-continue-2026-09-25',
        'cpu-libxsmm-panel-swarm-2026-09-25',
        'cpu-libxsmm-automatic-2026-09-25',
        'cpu-libxsmm-next-board-2026-09-25',
        'cpu-libxsmm-editable-panel-2026-09-25',
        'cpu-libxsmm-ten-run-ac-2026-09-25',
        'cpu-libxsmm-transpose-swarm-2026-09-25',
        'cpu-libxsmm-compiler-board-2026-09-25'))
    preparation = json.loads((prepared/'preparation.json').read_text())
    if preparation['baseline_source_sha256'] != source_hash:
        raise ValueError('Prepared source hash changed')
    primitive = repo/'evidence/cpu-libxsmm-256-primitive-2026-09-25'
    previous = repo/'evidence/cpu-libxsmm-transpose-swarm-2026-09-25'
    reviews = dict(approved_proposal=(repo/'docs/sera-strassen-research-proposal-2026-09-25.md').read_text(),
        mapping=(primitive/'mapping-luna.md').read_text(),
        primitive_verification=json.loads((primitive/'verification.json').read_text()),
        compiler_provenance=json.loads((previous/'compiler-evidence.json').read_text()))
    task = """Optimize standalone row-major FP32 C=A@B on Apple M4 Pro.
The user approved one-level FP32 Strassen alongside current classical methods.
The existing 15 Luna specialists propose and jointly rank experiments. Astra-high
selects/replaces specialist roles, implements the ranked queue, and reviews measured
outcomes. The strassen_one_level role is now available in the catalog. Select exactly
15 appropriate specialists. Root has not selected an experiment or its order.

The goal is to beat the imported baseline peak consistently over ten runs. Report
both historical imported peaks and fresh same-mode baseline/control peaks. Historical
Battery Automatic peak1668.5964359101147; AC initial-baseline peak1685.6230608449698;
later AC unchanged-control peak1687.3925479742732. Best Sera candidate sample1701.6509826
was unpromoted and is not an imported control. Historical-vs-fresh goal definition
awaits the user. Internal1800 target is a legacy setting, not new-goal adjudication.
Each candidate receives ten validations and ten alternating paired controls. The
promotion gate remains min(candidate)>1.05*max(control), followed by held-out checking.

Frozen ABI: void gemm(int n,const float*A,const float*B,float*C). Timing n512;
correct general shapes/tails/n<=0. clang21 -O3 -march=native -ffast-math -shared -fPIC -lm.
Single thread, FP32 tolerance.002, no external library/runtime, mixed precision,
persistent input/result buffers, precomputed transposes, evaluator edits, or shortcuts.
Every extraction/packing/sum, allocation/free, subproduct, SME transition, recombination
and output store is inside the timed gemm call. Fresh inputs every call. Preserve
all LIBXSMM BSD notices. Other sizes and allocation failure keep a correct fallback.
No deeper recursion or Winograd schedule is approved.

Baseline's active path is unchanged imported full512 NN. Optional UNUSED exact
imported helpers in the complete source: sera_libxsmm_panel32, full512 TA/TB/TT,
and NEW sera_libxsmm_256. The new helper is not a Sera optimization and its unused
addition changes binary layout, so this phase measures a fresh baseline.
All five NN/TA/TB/TT/n256 compiled bodies match their pinned exported bytes. Prepared
baseline passed48 public cases plus four cancellation/scale cases. The standalone
n256 primitive passed dense random, identity, zero and asymmetric integer checks.
These do not establish correctness or performance of a future Strassen wrapper.

The exact n256 helper implements beta-zero NN FP32 M=N=K=256 with lda/ldb/ldc256.
Call sera_libxsmm_256 with zeroed const void*parameters[22], [4]=Y,[10]=X,[16]=P
for dense row-major P=X@Y. It owns its SME entry/exit. Parent512 quadrants are NOT
dense256: copy/combine into dense buffers before calling, and recombine/scatter the
dense output into C with stride512. Do not pass strided quadrants to this descriptor.
The seven standard products and signs are in the user-approved proposal below.
Use only one level. Exact workspace strategy is a board choice, all costs timed.
Full512 NN/TA/TB/TT use LD512: NN[4]=B,[10]=A; TA[4]=transpose(B),[10]=A;
TB[4]=B,[10]=transpose(A); TT[4]=transpose(B),[10]=transpose(A); all [16]=C.
A physical transpose is T[k*512+i]=X[i*512+k], never an identity linear copy.

Updated measured inventory: timed SME A-transpose TB wrapper was tested on both
AC and Battery LowPower and failed promotion. NEON A-transpose TB was also tested
on LowPower and failed. TA with timed SME B-transpose was NOW tested on LowPower
and failed. TT remains unmeasured. Four-step full512 K-unroll and288-byte A-slice
padding were measured and failed promotion. General-size direct SME A-gather FAILED
COMPILATION; no timing result exists. Prior phase then failed on a1108459-character
review prompt. Sera now losslessly shares source text in prompts, with exact source
hashes/metadata preserved. Failed phase remains failed and has no final holdout.
Do not mistake a compile failure, abstention, low ranking or timeout for a measurement.

All older phases and source changes are listed below. Avoid alias repetitions of
previous rejects; a new implementation must make a distinct legal source change.
Actual NN/TB compiler evidence exists in the supplied provenance; full disassembly
was provided in the preceding phase. This task does not append redundant disassembly.
Do not claim unmeasured component speedups. No measured Strassen wrapper exists yet.
Correctness now also includes deterministic cancellation (opposite blocks with small
FP32 perturbations) and scale-separated powers-of-two with perturbations at n512,
using float64 reference from actual FP32 inputs and unchanged .002 error formula.
Numerical accuracy, finite output, no input mutation, full overwrite and output guards
are mandatory before timing. All prior general-size correctness cases remain.

Caps unchanged:6implementation attempts,108model calls,180seconds per agent call,
1800seconds total. Preserve initial power source/settings; no power-setting changes.
""" + '\nPrior phase outcomes:\n' + json.dumps(prior) + '\nApproved scope and verified mappings:\n' + json.dumps(reviews)
    profile = dict(cpu='Apple M4 Pro',power=power_source(initial),streaming_fp32_lanes=16,
        capabilities=['cpu','arm64','sme','sme2','neon','simd','single-thread'],
        sme2=True,p_core_l1d_bytes=131072,e_core_l1d_bytes=65536,cache_line_bytes=128)
    team = KernelAdvisoryTeam(work_dir=folder/'agent', task=task, profile=profile,
                             max_rounds=6, batch_size=3, max_calls=108, timeout=180)
    modules = ('kernel_search.py','kernel_advisory.py','kernel_tools.py','kernel_edits.py',
               'kernel_swarm_plan.py','kernel_advisor_roles.py','codex_agent.py','cpu_kernel_validation.py','kernel_prompt.py')
    save_json(folder/'controls.json', dict(host=initial,profile=profile,baseline=str(baseline),
        baseline_sha256=source_hash,target_gflops=1800,max_candidates=6,max_model_calls=108,
        repeats=10,min_improvement=0.05,goal="beat imported baseline peak consistently over ten runs",
        target_role="legacy internal setting; not new-goal adjudication",
        prior_imported_peak_gflops=1685.6230608449698,
        replay_prior_selected_candidate=False, approved_one_level_strassen=True,
        preparation=preparation,numerical_checks_sha256=hashlib.sha256((folder/'numerics.py').read_bytes()).hexdigest(),
        max_seconds=1800,agent_timeout=180,prior_scores_imported=False,task=task,
        prior_phases=prior,implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        implementation_hashes={name:hashlib.sha256((repo/'sera'/name).read_bytes()).hexdigest() for name in modules},
        driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    evaluator = HillsKernelEvaluator(workspace='/Users/vishnuv/Documents/Documents/kernel-opt')


    def evaluate(source_dir, report_path, *, final, timeout):
        before = host_observation()
        check_power(before, initial)
        host_path = Path(report_path).with_suffix('.host.json')
        observations = dict(before=before)
        save_json(host_path, observations)
        try:
            report = evaluator(source_dir, report_path, final=final, timeout=timeout)
            print('SCORED', report_path, report.get('metrics'), flush=True)
            return report
        finally:
            after = host_observation()
            observations['after'] = after
            save_json(host_path, observations)
            check_power(after, initial)


    def validate(source_path, output_path, *, timeout):
        started = time.monotonic()
        if (reference/'LICENSE.libxsmm.md').read_text() not in Path(source_path).read_text():
            result = dict(passed=False,stage='license',error='LIBXSMM notice removed')
            save_json(output_path,result)
            return result
        standard_path = Path(output_path).with_suffix('.standard.json')
        result = validate_cpu_kernel(source_path,standard_path,timeout=timeout)
        if result['passed']:
            remaining = timeout-(time.monotonic()-started)
            if remaining <= 0:
                result.update(passed=False,stage='numerical-correctness',error='TimeoutError')
            else:
                extra = numerics.validate(source_path,Path(output_path).with_suffix('.numerics.json'),timeout=remaining)
                result['numerical_stress'] = extra
                if not extra['passed']:
                    result.update(passed=False,stage='numerical-correctness',error=extra.get('error','Numerical check failed'))
        save_json(output_path,result)
        return result


    try:
        result = optimize_kernel(baseline=KernelCandidate('libxsmm-reference-with-unused-256-primitive',source,
            'Unchanged full512 NN GEMM with optional unused verified panel, transpose and256 primitives'),
            propose=team,evaluate=evaluate,validate=validate,output_dir=folder/'search',
            max_candidates=6,repeats=10,min_improvement=0.05,target_gflops=1800,max_seconds=1800)
        print('RESULT',json.dumps({key:result.get(key) for key in
            ('status','target_met','final_gflops','winner_source','stop_reason')}),flush=True)
    finally:
        if (folder/'search/result.json').exists():
            team.observe(json.loads((folder/'search/result.json').read_text())['trials'])


if __name__ == "__main__":
    main()
