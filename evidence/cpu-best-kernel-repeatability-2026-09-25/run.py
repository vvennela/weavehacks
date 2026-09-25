"""Exact best-kernel replay on current power; preserve all raw timing triplets."""
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


class ReplaySelected:
    def __init__(self, candidates, team):
        self.candidates = iter(candidates)
        self.team = team

    def propose(self, history, *, timeout):
        return next(self.candidates, None)

    def adjudicate(self, *args, **kwargs):
        return self.team.adjudicate(*args, **kwargs)


def main():
    folder = Path(__file__).resolve().parent
    repo = folder.parent.parent
    previous = repo/'evidence/cpu-libxsmm-editable-panel-2026-09-25'
    baseline,candidates,old,state = selected_sources(previous)
    initial = host_observation()
    check_power(initial,initial)
    profile = dict(cpu='Apple M4 Pro',power=power_source(initial),
        capabilities=['cpu','arm64','sme','sme2','single-thread'])
    task = """Remeasure ONLY the exact best prior Sera kernel eb091b1e... against its
original imported control04fc3ff... under the CURRENT unchanged power profile.
The user redirected research toward making this source repeatable, not Strassen
or alternative algorithms. No new proposals, source edits or roster calls are needed.
Astra reviews the one fresh ten-pair replay under the existing separated-range-plus-5%
gate. Save all three raw timings behind each official best-of-three report unchanged.
Do not redefine the official metric, change warmup/compiler/tolerance/thread settings,
claim causality for noise, discard slow samples or pool scores across power modes.
The previous AC peak1701.6509826 exceeded that phase's imported initial peak1685.6230608
only1/10 times, with5/10pairedwins. It does not establish repeatability or system-wide
optimality. The historical Battery Automatic imported peak is1668.5964359101147;
later AC controlpeak1687.3925479742732 is a separate observation. Report all relevant
comparators and fresh same-mode peaks without deciding the still-pending goal policy.
The legacy internal1800target does not redefine the user's ten-run goal.
Preserve frozen FP32 C=A@B, all timed allocation/packing, exactsourcehashes, singlethread,
correctness.002,10 alternatingpairs and held-outconfirmation. No power-setting changes.
Imported baseline code is not a Sera improvement. Prior scores do not enter eligibility.
"""
    team = KernelAdvisoryTeam(work_dir=folder/'agent',task=task,profile=profile,
                             max_rounds=6,max_calls=108,timeout=180,batch_size=3)
    save_json(folder/'controls.json',dict(host=initial,profile=profile,task=task,
        prior_phase=str(previous),prior_calls=state['calls'],prior_attempts=state['implementations'],
        prior_state_sha256=hashlib.sha256((previous/'agent/state.json').read_bytes()).hexdigest(),
        source_hashes=[BASELINE_HASH,BEST_HASH],prior_scores_imported=False,
        prior_ac_initial_baseline_peak_gflops=1685.6230608449698,
        prior_ac_control_peak_gflops=1687.3925479742732,
        preserve_raw_timing_triplets=True,
        reusing_selected_sources=True,new_proposals=False,max_candidates=6,max_model_calls=108,
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
        result = optimize_kernel(baseline=baseline,propose=ReplaySelected(candidates,team),
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
