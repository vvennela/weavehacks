"""Measure one saved Sera candidate, then continue its unchanged ranked plan."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

from examples.optimize_cpu_kernel import host_observation, require_ac
from sera.cpu_kernel_validation import validate_cpu_kernel
from sera.kernel_advisory import KernelAdvisoryTeam
from sera.kernel_edits import candidate_source
from sera.kernel_search import KernelCandidate, optimize_kernel
from sera.kernel_swarm_plan import rank_experiments
from sera.kernel_tools import HillsKernelEvaluator
from sera.storage import content_hash, save_json

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parent.parent
PREVIOUS = REPO/'evidence/cpu-libxsmm-swarm-edits-2026-09-24'
REFERENCE = REPO/'evidence/cpu-libxsmm-reference-2026-09-24'


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def read_checkpoint():
    return dict(
        state=read_json(PREVIOUS/'agent/state.json'),
        metadata=read_json(PREVIOUS/'prepared/candidate.json'),
        source=(PREVIOUS/'prepared/kernel.c').read_text(),
        baseline=(REFERENCE/'editable/kernel.c').read_text(),
        response=read_json(PREVIOUS/'agent/implementation-002/call-001/response.json'),
        correctness=read_json(PREVIOUS/'prepared/public-correctness.json'))


def validate_checkpoint(*, state, metadata, source, baseline, response, correctness):
    if state['calls'] != 33 or state['implementations'] != 2 or len(state['rounds']) != 1:
        raise ValueError('Unexpected spent model/implementation budget')
    batch = state['rounds'][0]
    if len(batch['roles']) != 15 or len(set(batch['roles'])) != 15:
        raise ValueError('Incomplete specialist roster')
    if batch['board_hash'] != content_hash(batch['board']):
        raise ValueError('Changed proposal board')
    ballots = batch['ballots']
    if len(ballots) != 15 or any(v['status'] != 'received' for v in ballots):
        raise ValueError('Incomplete specialist rankings')
    order = rank_experiments([p['experiment_id'] for p in batch['board']],
        [v['ranking'] for v in ballots], limit=3)
    if batch['experiment_order'] != order or state['pending'] != order[1:]:
        raise ValueError('Changed swarm order')
    records = batch['implementations']
    if (len(records) != 2 or records[0]['status'] != 'failed' or
            records[1]['status'] != 'proposed' or records[1]['experiment_id'] != order[0]):
        raise ValueError('Unexpected implementation history')
    source_hash = digest(source)
    if source_hash != metadata['source_hash'] or source_hash != records[1]['source_hash']:
        raise ValueError('Changed prepared source')
    base = dict(source=baseline, source_hash=digest(baseline))
    if candidate_source(response, [base]) != source:
        raise ValueError('Saved edits do not reproduce the prepared source')
    if (correctness['passed'] is not True or correctness['source_hash'] != source_hash or
            correctness['seed'] != 20260924 or correctness['tolerance'] != .002 or
            len(correctness['sizes']) * len(correctness['input_kinds']) != 48):
        raise ValueError('Correctness evidence does not match prepared source')
    notice = (REFERENCE/'LICENSE.libxsmm.md').read_text()
    if notice not in source or notice not in baseline:
        raise ValueError('LIBXSMM license notice missing')
    return KernelCandidate(metadata['name'], source, metadata['hypothesis'], metadata['specialist_id'])


class PreparedThenSwarm:
    def __init__(self, team, candidate):
        self.team, self.candidate = team, candidate

    def propose(self, history, *, timeout):
        if self.candidate is not None:
            candidate, self.candidate = self.candidate, None
            return candidate
        return self.team.propose(history, timeout=timeout)

    def adjudicate(self, *args, **kwargs):
        return self.team.adjudicate(*args, **kwargs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args(argv)
    checkpoint = read_checkpoint()
    candidate = validate_checkpoint(**checkpoint)
    initial_host = host_observation()
    if args.check_only:
        print(json.dumps(dict(checkpoint_valid=True, candidate_sha256=digest(candidate.source),
            spent_calls=33, spent_attempts=2, remaining_calls=75, remaining_attempts=4,
            prepared_candidate_pending_measurement=True, measurements_imported=False,
            power=initial_host.get('battery'))), flush=True)
        return
    require_ac(initial_host)
    controls = read_json(PREVIOUS/'controls.json')
    task = '''Continue the user-approved LIBXSMM SME optimization. The first ranked experiment
has already been implemented and will receive fresh paired measurements before you continue.
Preserve the pending swarm order; Astra implements and reviews, while 15 Luna specialists
jointly rank new batches. Use Codex ChatGPT agents only.
Optimize single-thread row-major FP32 C=A@B, ABI void gemm(int n,const float*A,const float*B,float*C).
Fixed Apple clang21 flags: -O3 -march=native -ffast-math -shared -fPIC -lm. Main n512,
correct general n and tails, n<=0 no-op, tolerance .002. No external libraries, BLAS,
threads, answer caching, mixed precision or evaluator changes. Every packing/allocation
operation stays inside the timed call. Preserve the complete BSD license notice.
The pinned LIBXSMM baseline is an imported reference, not a Sera discovery. It contains
editable SME2 assembly; use small hash-bound edits. Preserve ABI and streaming-state
transitions. There are four FP32 ZA tiles and 16 FP32 lanes per streaming vector.
Unproven gains are valid hypotheses. Avoid identical implementations and claims of speed
from instruction counts. Use fresh live history for eligibility; prior evidence below is
research context only. Target >1800 GFLOP/s under unchanged gates.
Reference provenance and earlier baseline context:\n''' + json.dumps(controls['reference_evidence'])
    team = KernelAdvisoryTeam(work_dir=FOLDER/'agent', task=task, profile=controls['profile'],
        max_rounds=6, batch_size=3, max_calls=108)
    state = checkpoint['state']
    team.rounds = deepcopy(state['rounds'])
    team.pending = list(state['pending'])
    team.calls, team.proposal_count = state['calls'], state['implementations']
    team._save()
    modules = ('kernel_advisory.py','kernel_swarm_plan.py','codex_agent.py','kernel_search.py',
        'cpu_kernel_validation.py','kernel_advisor_roles.py','kernel_tools.py','kernel_edits.py')
    save_json(FOLDER/'controls.json', dict(host=initial_host, profile=controls['profile'],
        previous_phase=str(PREVIOUS), source_hash=digest(candidate.source),
        baseline_hash=digest(checkpoint['baseline']), imported_calls=33, imported_attempts=2,
        max_model_calls=108, max_attempts=6, max_candidates=5, max_seconds=1200,
        target_gflops=1800, measurements_imported=False, task=task,
        driver_sha256=digest(Path(__file__).read_text()),
        prior_state_sha256=digest((PREVIOUS/'agent/state.json').read_text()),
        implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        implementation_hashes={name:digest((REPO/'sera'/name).read_text()) for name in modules}))
    evaluator = HillsKernelEvaluator(workspace='/Users/vishnuv/Documents/Documents/kernel-opt')

    def evaluate(source_dir, report_path, *, final, timeout):
        before = host_observation()
        require_ac(before)
        if before['power_settings'] != initial_host['power_settings']:
            raise RuntimeError('Power settings changed')
        observations = dict(before=before)
        host_path = Path(report_path).with_suffix('.host.json')
        save_json(host_path, observations)
        try:
            report = evaluator(source_dir, report_path, final=final, timeout=timeout)
            print('SCORED', report_path, report.get('metrics'), flush=True)
            return report
        finally:
            after = host_observation()
            observations['after'] = after
            save_json(host_path, observations)
            require_ac(after)
            if after['power_settings'] != initial_host['power_settings']:
                raise RuntimeError('Power settings changed during scoring')

    def validate(source, output_path, *, timeout):
        if (REFERENCE/'LICENSE.libxsmm.md').read_text() not in Path(source).read_text():
            result = dict(passed=False, stage='license', error='LIBXSMM license notice removed')
            save_json(output_path, result)
            return result
        return validate_cpu_kernel(source, output_path, timeout=timeout)

    try:
        result = optimize_kernel(
            baseline=KernelCandidate('libxsmm-aot-reference', checkpoint['baseline'], 'Fresh unchanged LIBXSMM reference'),
            propose=PreparedThenSwarm(team, candidate), evaluate=evaluate, validate=validate,
            output_dir=FOLDER/'search', max_candidates=5, target_gflops=1800, max_seconds=1200)
        print('RESULT', json.dumps({key:result.get(key) for key in
            ('status','target_met','final_gflops','winner_source','stop_reason')}), flush=True)
    finally:
        result_path = FOLDER/'search/result.json'
        if result_path.exists():
            team.observe(read_json(result_path)['trials'])


if __name__ == '__main__':
    main()
