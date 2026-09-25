"""Next specialist-ranked batch with complete recent phase outcomes."""
import hashlib
import json
from pathlib import Path
import subprocess

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
        'cpu-libxsmm-ten-run-ac-2026-09-25'))
    primitives = repo/'evidence/cpu-libxsmm-transpose-primitives-2026-09-25'
    reviews = {name: (primitives/name).read_text() for name in
               ('mapping-luna.md', 'generator-paths-luna.md')}
    preparation = json.loads((folder/'preparation.json').read_text())
    if preparation['baseline_source_sha256'] != source_hash:
        raise ValueError('Prepared source hash changed')
    task = """Optimize standalone row-major FP32 C=A@B on Apple M4 Pro.
The user's current goal is to beat the imported baseline peak consistently over ten
runs. Recent imported peak was1685.6230608449698 GFLOP/s on AC Automatic; previous
Battery Automatic peak was1668.5964359101147. Measure ten validation reports and ten
fresh alternating paired controls for each candidate, not a lucky best sample.
Each report preserves the frozen hill's best-of-three timing rule. Historical scores
are context only. Whether the goal comparator is historical or fresh same-mode peak
awaits the user; report both, do not choose policy. Legacy internal1800 target remains
only an unresolved search setting; it does not define the new goal. Adoption still
requires the unchanged min(candidate)>1.05*max(paired controls) gate and held-out check.

Frozen ABI: void gemm(int n,const float*A,const float*B,float*C). Timing n512,
correct general sizes/tails/n<=0; clang21 -O3 -march=native -ffast-math -shared -fPIC -lm;
FP32 tolerance.002, single thread, no external library/runtime, no mixed precision,
input/result caching, scorer edits, precomputed transpose, or output-specific shortcut.
All input conversion, allocation/free, calls, SME transitions, and stores stay timed.
Preserve the complete LIBXSMM BSD notices. Inputs are fresh every call.

The baseline is unchanged full512 NN LIBXSMM gemm plus optional UNUSED helpers:
sera_libxsmm_panel32 and NEW full512 sera_libxsmm_ta, sera_libxsmm_tb,
sera_libxsmm_tt. Complete editable asm and declarations are in the supplied source.
They were imported offline from pinned LIBXSMM10490f10e79d4511f252c33279ef970a188cfab6,
not written by Sera. Their exact exported instruction bytes are verified in this
compiled source. Adding unused code changes binary layout; fresh baseline is mandatory.
The baseline still calls only sera_libxsmm_512. Augmented baseline passed48cases.
The three new primitives passed9 separate deterministic correctness tests with prepared
inputs, but no legal end-to-end wrapper has been measured. They are available options,
not selected experiments and not known speedups. The15specialists jointly rank proposals.

Each primitive accepts a zeroed const void*parameters[22], uses [4]=A_arg,[10]=B_arg,
[16]=C; full512cubed, FP32, beta0, lda/ldb/ldc512. To compute row-major C=A@B:
NN params4=B,params10=A; TA params4=transpose(B),params10=A;
TB params4=B,params10=transpose(A); TT params4=transpose(B),params10=transpose(A).
Here transpose(X) is a contiguous physical512x512FP32 transpose freshly computed inside
gemm; output C remains original. Each buffer is1MiB. New helpers own their SME
entry/exit. Existing sme_transpose can be inspected for possible reuse; no external
prototype or unavailable generator output can be invented. Preserve n!=512 fallback,
allocation-failure safety, original inputs, full overwrite and no persistent buffers.
TA retains generated B-stack packing and adds A-stack packing; TB skips B-stack
packing and does not add A-stack packing; TT skips B packing but adds A packing.
Do not infer performance from shorter code or one removed internal pack: required
external conversion costs are included, and traversal/layout/cache costs differ.

Astra chooses/replaces15Luna specialist roles. Each proposes a distinct legal change;
they review the shared board and jointly rank a batch. Astra implements that ranked
queue and reviews actual results. Root has not selected an experiment or descriptor.
Give exact blocks, pointer/layout mapping, conversion method, risks, and expected
measured effect. Distinguish complete algorithm/layout changes from redundant aliases.
Do not repeat prior16-panel-calls, one-SME-entry32-row-panels, reserve-scratch-once,
W32counters, FMOPA0132 order, padded272B, constant-shape-C, or prior pointer/prefetch/
pipeline variants without a genuinely different source change and hypothesis.
A descriptor change plus its required new timed conversion is a distinct experiment;
merely renaming a past rejected wrapper is not. If a ranked alias was already tested,
Astra should abstain rather than invent a new root-selected or unranked experiment.

Current block caps:6implementation attempts,108model calls,180seconds per agent call,
1800seconds total. Preserve initial power source and settings. No setting changes.
All prior phases (including timeouts/abstentions and both power modes):
""" + json.dumps(prior) + '\nVerified primitive mappings and generator behavior:\n' + json.dumps(reviews)
    profile = dict(cpu='Apple M4 Pro',power=power_source(initial),streaming_fp32_lanes=16,
        capabilities=['cpu','arm64','sme','sme2','neon','simd','single-thread'],
        sme2=True,p_core_l1d_bytes=131072,e_core_l1d_bytes=65536,cache_line_bytes=128)
    team = KernelAdvisoryTeam(work_dir=folder/'agent', task=task, profile=profile,
                             max_rounds=6, batch_size=3, max_calls=108, timeout=180)
    modules = ('kernel_search.py','kernel_advisory.py','kernel_tools.py','kernel_edits.py',
               'kernel_swarm_plan.py','kernel_advisor_roles.py','codex_agent.py','cpu_kernel_validation.py')
    save_json(folder/'controls.json', dict(host=initial,profile=profile,baseline=str(baseline),
        baseline_sha256=source_hash,target_gflops=1800,max_candidates=6,max_model_calls=108,
        repeats=10,min_improvement=0.05,goal="beat imported baseline peak consistently over ten runs",
        target_role="legacy internal setting; not new-goal adjudication",
        prior_imported_peak_gflops=1685.6230608449698,
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
        if (reference/'LICENSE.libxsmm.md').read_text() not in Path(source_path).read_text():
            result = dict(passed=False,stage='license',error='LIBXSMM notice removed')
            save_json(output_path,result)
            return result
        return validate_cpu_kernel(source_path,output_path,timeout=timeout)


    try:
        result = optimize_kernel(baseline=KernelCandidate('libxsmm-reference-with-unused-transpose-primitives',source,
            'Original full512 NN GEMM with optional unused verified panel and transpose primitives'),
            propose=team,evaluate=evaluate,validate=validate,output_dir=folder/'search',
            max_candidates=6,repeats=10,min_improvement=0.05,target_gflops=1800,max_seconds=1800)
        print('RESULT',json.dumps({key:result.get(key) for key in
            ('status','target_met','final_gflops','winner_source','stop_reason')}),flush=True)
    finally:
        if (folder/'search/result.json').exists():
            team.observe(json.loads((folder/'search/result.json').read_text())['trials'])


if __name__ == "__main__":
    main()
