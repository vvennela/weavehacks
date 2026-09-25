"""Apply published SME techniques to the exact best source through the15-agent board."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

from examples.optimize_cpu_kernel import host_observation, check_power, power_source
from sera.cpu_kernel_validation import validate_cpu_kernel
from sera.kernel_advisory import KernelAdvisoryTeam
from sera.kernel_search import KernelCandidate, optimize_kernel
from sera.kernel_tools import HillsKernelEvaluator
from sera.storage import save_json


BEST_HASH='eb091b1eca431f0760d0d61e4c0c6e748c1a9e34466a87ac15ad9cb238b5aecf'
BASELINE_HASH='04fc3ff86669c2ca123e3b390b662637cd69c21f3d63fa26f7a5f0f0a882317c'


def source_hash(source):
    return hashlib.sha256(source.encode()).hexdigest()


def selected_sources(previous):
    old=json.loads((previous/'search/result.json').read_text())
    state=json.loads((previous/'agent/state.json').read_text())
    proposed={x['source_hash'] for b in state['rounds'] for x in b['implementations'] if x['status']=='proposed'}
    if BEST_HASH not in proposed:
        raise ValueError('Best source was not implemented by the saved swarm')
    selected=[]
    for expected in (BASELINE_HASH,BEST_HASH):
        trial=next(t for t in old['trials'] if t['source_hash']==expected)
        source=Path(trial['source']).read_text()
        if source_hash(source)!=expected:
            raise ValueError('Saved source hash changed')
        if not trial['public_correctness']['passed']:
            raise ValueError('Saved source did not pass correctness')
        selected.append(KernelCandidate(trial['name'],source,trial['hypothesis'],trial.get('specialist_id')))
    return selected[0],selected[1:],old,state


class ReplayedBestThenSwarm:
    def __init__(self, candidates, team):
        self.candidates = iter(candidates)
        self.team = team

    def propose(self, history, *, timeout):
        candidate=next(self.candidates,None)
        return candidate if candidate is not None else self.team.propose(history,timeout=timeout)

    def adjudicate(self, *args, **kwargs):
        return self.team.adjudicate(*args, **kwargs)


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
    previous = repo/'evidence/cpu-libxsmm-editable-panel-2026-09-25'
    baseline,candidates,old,state = selected_sources(previous)
    initial = host_observation()
    check_power(initial,initial)
    profile = dict(cpu='Apple M4 Pro',power=power_source(initial),
        capabilities=['cpu','arm64','sme','sme2','single-thread'])
    phase_names=(
        'cpu-libxsmm-measure-prepared-2026-09-24','cpu-libxsmm-next-2026-09-25',
        'cpu-libxsmm-next-continue-2026-09-25','cpu-libxsmm-panel-swarm-2026-09-25',
        'cpu-libxsmm-automatic-2026-09-25','cpu-libxsmm-next-board-2026-09-25',
        'cpu-libxsmm-editable-panel-2026-09-25','cpu-libxsmm-ten-run-ac-2026-09-25',
        'cpu-libxsmm-transpose-swarm-2026-09-25','cpu-libxsmm-compiler-board-2026-09-25',
        'cpu-libxsmm-strassen-swarm-2026-09-25','cpu-best-kernel-repeatability-2026-09-25')
    prior=load_prior(repo/'evidence',phase_names)
    calibration_folder=repo/'evidence/cpu-sme-peak-calibration-2026-09-25'
    calibration=json.loads((calibration_folder/'results.json').read_text())
    calibration_summary={key:calibration[key] for key in ('kind','cpu','power','host','summary','limitation')}
    technique_map=(repo/'docs/sera-sme-peak-technique-map-2026-09-25.md').read_text()
    references=(repo/'docs/sera-sme-throughput-references-2026-09-25.md').read_text()
    task = """Optimize repeatability and throughput of the exact best Sera panel32 kernel.
The user requested implementation of applicable techniques behind published~2000GFLOP/s
SME performance and estimates. Stay on the existing classical panel32 implementation.
No Strassen, descriptor swaps, newalgorithm search, altered power/QoS/affinity settings,
mixed precision, external library, thread changes, input caches or scorer edits.

Fresh current-mode baseline is original imported04fc3ff...; the user-selected exact
best source eb091b1eca431f0760d0d61e4c0c6e748c1a9e34466a87ac15ad9cb238b5aecf is replayed
first and enters measured history before proposals. Modify THAT active panel32 path,
not the unused full512 NN assembly. Its gemm calls sera_libxsmm_panel32. Do not silently
replace it with the imported reference and label that a new improvement. Preserve
correct fallback behavior, all BSD notices, FP32 and timed input packing/allocation.
The baseline/control remains the imported source; no historical scores enter eligibility.

Astra-high selects15relevant Luna specialists. The15specialists propose distinct
changes, review and jointly rank the shared board. Astra implements that queue and
reviews measured results. Focus advice on the requested SME techniques as applied to
the active best kernel; root has not selected an experiment/order. Avoid proposals
that merely restate already-present optimizations or change only inactive assembly.

The active panel loop already uses all FOUR independent ZA tiles once per K step,
reuses each A/B vector twice, has one SME region for all16 row bands and64KiB reusable
scratch. Its stack alignment mask is0xffffffffffffffc0:64BYTES, not64KiB alignment.
More tile independence or one-entry-one-exit is not a new change. It has no explicit
K lookahead and no K-loop unrolling. Earlier2/4-step unroll experiments changed the
full512 NN body; inspect prior source/mechanism before claiming duplication or novelty.
Wider loads require legal contiguous operand layouts: packedA advances128bytes/K,
B advances2048bytes/K. Do not invent gather/post-index encodings or support for strides.
Every real input load, packing step and output store must remain in the full timedcall.
Preserve per-output FP32 update order where possible and the existing.002tolerance.
SME transitions affect vector registers: preserve ABI state, no x18clobber, valid stack.

The diagnostic calibration uses register-only FP32 operands and64FMOPA periteration.
It is not a GEMM, performance promotion or theoretical ceiling. Its saved setting is
BatteryLowPower; compare only matching settings. PublishedbaseM4~2008 is also a
compute microbenchmark, not thisM4Pro's certifiedlimit. Do not report the diagnostic
or operation-count estimates as a Sera GEMM gain. No new benchmark rule is authorized.
A microbenchmark hotloop without inputloads cannot replace the actualmatrixproduct.

Frozen workload: row-major FP32 C=A@B; void gemm(int n,const float*A,const float*B,float*C).
Official timing n512; correctness general sizes/tails/n<=0; clang21
-O3 -march=native -ffast-math -shared -fPIC -lm; singlethread; allconversion/allocation
insidegemm. Preserve48publiccases and officialtol.002, tenvalidationreports andten
alternatingpairedcontrols per candidate, min(candidate)>1.05*max(control), thenholdout.
Goal remains consistently beating importedpeakover10runs. Report savedBatteryAutomatic
1668.5964359101147, savedACinitial1685.6230608449698, laterACcontrol1687.3925479742732
andfreshsame-modepeaks separately. The historical-vs-fresh policy remainspending;
legacyinternal1800flag does not define success. No claims from peaks alone.
PriorbestAC1701.65 had5/10pairedwins and1/10abovefreshpeak. LatestexactLowPowerreplay
714.79–1108.66 had7/10pairedwins but failedpromotion. Bothmode histories remain evidence.

Keep caps6candidate slots,108modelcalls,180seconds/agentcall,1800seconds/block.
One slot replays the user-selectedbest; proposals follow until the existingcaps stop
search. Do not change timeout/budgets or claim impossible ceilings from limiteddata.
""" + '\nTechnique map:\n'+technique_map+'\nPrimary references:\n'+references
    task += '\nLocal diagnostic ONLY:\n'+json.dumps(calibration_summary)+'\nPrior measured outcomes:\n'+json.dumps(prior)
    team = KernelAdvisoryTeam(work_dir=folder/'agent',task=task,profile=profile,
                             max_rounds=6,max_calls=108,timeout=180,batch_size=3)
    save_json(folder/'controls.json',dict(host=initial,profile=profile,task=task,
        prior_phase=str(previous),prior_calls=state['calls'],prior_attempts=state['implementations'],
        prior_state_sha256=hashlib.sha256((previous/'agent/state.json').read_bytes()).hexdigest(),
        source_hashes=[BASELINE_HASH,BEST_HASH],prior_scores_imported=False,
        prior_ac_initial_baseline_peak_gflops=1685.6230608449698,
        prior_ac_control_peak_gflops=1687.3925479742732,
        preserve_raw_timing_triplets=True,
        reusing_selected_sources=True,new_proposals=True,focus_source_sha256=BEST_HASH,
        technique_map_sha256=hashlib.sha256(technique_map.encode()).hexdigest(),
        calibration_sha256=hashlib.sha256((calibration_folder/'results.json').read_bytes()).hexdigest(),
        prior_phase_outcomes=prior,max_candidates=6,max_model_calls=108,
        max_seconds=1800,agent_timeout=180,target_gflops=1800,
        target_role="legacy internal search gate; not new-goal adjudication",
        goal="beat the imported baseline peak consistently over 10 runs",
        repeats=10,min_improvement=0.05,
        historical_imported_peak_gflops=1668.5964359101147,
        implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    evaluator = HillsKernelEvaluator(workspace='/Users/vishnuv/Documents/Documents/kernel-opt')

    def evaluate(source_dir, report_path, *, final, timeout):
        before = host_observation()
        check_power(before, initial)
        observations = dict(before=before)
        host_path = Path(report_path).with_suffix('.host.json')
        save_json(host_path,observations)
        try:
            report = evaluator(source_dir,report_path,final=final,timeout=timeout)
            print('SCORED',report_path,report.get('metrics'),flush=True)
            return report
        finally:
            after = host_observation()
            observations['after'] = after
            save_json(host_path,observations)
            check_power(after, initial)

    def validate(source_path,output_path,*,timeout):
        notice = (repo/'evidence/cpu-libxsmm-reference-2026-09-24/LICENSE.libxsmm.md').read_text()
        if notice not in Path(source_path).read_text():
            raise ValueError('LIBXSMM notice missing')
        return validate_cpu_kernel(source_path,output_path,timeout=timeout)

    try:
        result = optimize_kernel(baseline=baseline,propose=ReplayedBestThenSwarm(candidates,team),
            evaluate=evaluate,validate=validate,output_dir=folder/'search',
            max_candidates=6,repeats=10,min_improvement=0.05,
            target_gflops=1800,max_seconds=1800)
        print('RESULT',json.dumps({key:result.get(key) for key in
            ('status','target_met','final_gflops','winner_source','stop_reason')}),flush=True)
    finally:
        if (folder/'search/result.json').exists():
            team.observe(json.loads((folder/'search/result.json').read_text())['trials'])


if __name__=='__main__':
    main()
