"""Ten-run AC replay of the saved swarm-selected sources; no power-setting changes."""
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


def require_automatic_ac(observation):
    ac_settings = observation['power_settings'].split('AC Power:',1)[-1]
    if (power_source(observation) != 'AC Power' or
            re.search(r'^\s*powermode\s+0\s*$', ac_settings, re.MULTILINE) is None):
        raise RuntimeError('This block requires the unchanged Automatic AC profile')


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
    old = json.loads((previous/'search/result.json').read_text())
    state = json.loads((previous/'agent/state.json').read_text())
    proposed = [x['source_hash'] for b in state['rounds'] for x in b['implementations'] if x['status']=='proposed']
    if proposed != [x['source_hash'] for x in old['trials'][1:]]:
        raise ValueError('Saved source order differs from the swarm implementation order')
    candidates = []
    for trial in old['trials']:
        source = Path(trial['source']).read_text()
        if hashlib.sha256(source.encode()).hexdigest() != trial['source_hash']:
            raise ValueError('Saved source hash changed')
        if not trial['public_correctness']['passed']:
            raise ValueError('Saved source did not pass correctness')
        candidates.append(KernelCandidate(trial['name'],source,trial['hypothesis'],trial.get('specialist_id')))
    initial = host_observation()
    require_automatic_ac(initial)
    baseline = candidates.pop(0)
    profile = dict(cpu='Apple M4 Pro',power='AC Power',energy_mode='Automatic',
        capabilities=['cpu','arm64','sme','sme2','single-thread'])
    task = """Remeasure the exact baseline and four previously swarm-selected kernels
on AC Automatic with ten repetitions and fresh alternating paired controls.
The user goal is to beat the imported baseline peak consistently over ten runs.
The saved imported peak is 1668.5964359101147 GFLOP/s (Battery Automatic).
The choice between that historical peak and a fresh same-profile peak is pending;
report both comparisons without treating either as an approved replacement gate.
Source hashes and swarm-selected order are preserved. No new proposals are needed.
Astra reviews ONLY fresh history using the existing separated-ranges-plus-5% gate.
The internal search target remains the legacy 1800 setting solely to avoid silently
changing acceptance policy. Its target_met flag does not decide the new user goal.
Keep the frozen full FP32 row-major GEMM, compiler, single thread, tolerance and
held-out checks. No previous timings enter eligibility. Imported baseline code is
not a Sera improvement. Do not change system settings."""
    team = KernelAdvisoryTeam(work_dir=folder/'agent',task=task,profile=profile,
                             max_rounds=6,max_calls=108,timeout=180,batch_size=3)
    save_json(folder/'controls.json',dict(host=initial,profile=profile,task=task,
        prior_phase=str(previous),prior_calls=state['calls'],prior_attempts=state['implementations'],
        prior_state_sha256=hashlib.sha256((previous/'agent/state.json').read_bytes()).hexdigest(),
        source_hashes=[t['source_hash'] for t in old['trials']],prior_scores_imported=False,
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
        require_automatic_ac(before)
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
            require_automatic_ac(after)

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
