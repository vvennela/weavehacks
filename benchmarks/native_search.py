"""Equal-candidate-budget comparison using the production native executor."""
import argparse
import fcntl
import json
import os
import random
import shutil
import statistics
import subprocess
import sys
import time
from copy import deepcopy
from pathlib import Path

from sera.measurement import objective_value
from sera.model_artifact import verify_artifact
from sera.native_agent import NativeProposal
from sera.native_measurement import native_trial
from sera.native_optimizer import NativeProfile, _score, optimize_native
from sera.native_trace import trace_native_job
from sera.native_worker import run_native_job
from sera.storage import content_hash, save_json

POLICIES = ('sera', 'fixed', 'random')


class FixedPolicy:
    def __init__(self):
        self.history = []

    def choose(self, available):
        return min(available, key=lambda item: (item['recipe']['bits'],
                   -item['recipe']['group_size'], item['recipe_id']))

    def propose(self, evidence, *, timeout_seconds, cancelled=None):
        item = self.choose(evidence['available_recipes'])
        proposal = NativeProposal(recipe_id=item['recipe_id'],
            reason='Fixed memory-first recipe ordering; no hidden outcomes.',
            prediction='Lower bit width and larger groups use less weight memory; quality and speed must pass.')
        self.history.append({'policy': type(self).__name__, 'evidence': deepcopy(evidence),
                             'proposal': proposal.model_dump()})
        return proposal


class RandomPolicy(FixedPolicy):
    def __init__(self, seed):
        super().__init__()
        self.random = random.Random(seed)

    def choose(self, available):
        return self.random.choice(available)


def plan_blocks(blocks):
    return [list(POLICIES[index % 3:] + POLICIES[:index % 3]) for index in range(blocks)]


def summarize(rows, *, blocks):
    valid = {(r['block'], r['policy']): r for r in rows
             if r['status'] == 'completed' and r.get('heldout_passed')}
    complete = (len(rows) == blocks * 3 and len(valid) == blocks * 3
                and all((b, p) in valid for b in range(blocks) for p in POLICIES))
    result = {'complete': complete, 'sera_beats_fixed': None, 'sera_beats_random': None,
              'policy_summary': {}}
    for policy in POLICIES:
        selected = [r for r in valid.values() if r['policy'] == policy]
        if selected:
            result['policy_summary'][policy] = {
                'valid_blocks': len(selected),
                'median_memory_fraction': statistics.median(r['memory_fraction'] for r in selected),
                'memory_fraction_range': [min(r['memory_fraction'] for r in selected),
                                          max(r['memory_fraction'] for r in selected)],
                'median_wall_seconds': statistics.median(r['wall_seconds'] for r in selected)}
    if complete:
        for other in ('fixed', 'random'):
            result[f'sera_beats_{other}'] = all(
                valid[b, 'sera']['memory_fraction'] < valid[b, other]['memory_fraction'] * .95
                for b in range(blocks))
    return result


def measure_holdout(profile, artifact, folder):
    request = profile.measure_job(artifact['path'], artifact['artifact_id'])
    raw = run_native_job(request, output_dir=folder, timeout_seconds=profile.job_timeout_seconds)
    controls = {k: request[k] for k in ('seed', 'max_tokens', 'warmup', 'repetitions',
                                      'response_formats', 'response_format_version')}
    controls.update(sampling='greedy', concurrency=1)
    expected = {content_hash(t.prompt): t.expected_json for t in profile.tasks}
    return native_trial(raw, prompts=request['prompts'],
        evaluator=lambda prompt, text: _score(text, expected[content_hash(prompt)]),
        evaluation_version=profile.evaluation_version, floor=profile.constraints.quality_floor,
        artifact_id=artifact['artifact_id'], controls=controls, trial_id=folder.name)


def run_one(args):
    started = time.monotonic()
    profile = NativeProfile.model_validate_json(Path(args.profile).read_text())
    heldout = NativeProfile.model_validate_json(Path(args.heldout).read_text())
    folder = Path(args.output).resolve()
    agent = {'fixed': lambda: FixedPolicy(), 'random': lambda: RandomPolicy(args.seed),
             'sera': lambda: None}[args.policy]()
    report = optimize_native(profile=profile, output_dir=folder / 'research',
                             project=args.project, agent=agent)
    row = {'policy': args.policy, 'block': args.block, 'seed': args.seed,
           'status': report['status'], 'heldout_passed': False,
           'selected_recipe_id': report.get('selected_recipe_id'),
           'trace': report.get('trace'), 'candidate_trials': report['candidate_trials_used'],
           'native_jobs': len(report['jobs']), 'agent_calls': len(report['agent_calls'])}
    if report['status'] == 'completed':
        locations = report['artifact_locations']
        chosen = locations[report['selected_recipe_id']]
        def holdout_run():
            baseline = measure_holdout(heldout, locations['baseline'], folder / 'heldout-baseline')
            candidate = measure_holdout(heldout, chosen, folder / 'heldout-candidate')
            return {'baseline': baseline, 'candidate': candidate}
        checked = trace_native_job(project=args.project, run=holdout_run)
        save_json(folder / 'heldout.json', checked)
        baseline, candidate = checked['result']['baseline'], checked['result']['candidate']
        bq, cq = baseline['task_quality']['mean'], candidate['task_quality']['mean']
        bs, cs = objective_value(baseline, 'throughput'), objective_value(candidate, 'throughput')
        row.update(heldout_trace=checked['trace'], heldout_baseline_quality=bq,
            heldout_candidate_quality=cq, heldout_baseline_throughput=bs, heldout_candidate_throughput=cs,
            heldout_passed=bool(baseline['status'] == candidate['status'] == 'collected'
                and bq > 0 and bs and cs and cq >= bq * profile.retention.quality
                and cs >= bs * profile.retention.throughput),
            memory_fraction=objective_value(candidate, 'memory') / objective_value(baseline, 'memory'),
            baseline_peak_bytes=baseline['runtime']['memory']['peak_bytes'],
            selected_peak_bytes=candidate['runtime']['memory']['peak_bytes'],
            artifact_id=chosen['artifact_id'], artifact_path=chosen['path'])
        row['native_jobs'] += 2
    row['wall_seconds'] = time.monotonic() - started
    save_json(folder / 'row.json', row)


def retain_artifact(row, root, folder):
    """Keep one verified copy; remove only this benchmark's completed exports."""
    if row.get('artifact_path'):
        source = Path(row['artifact_path'])
        target = root / 'artifacts' / row['artifact_id']
        target.parent.mkdir(exist_ok=True)
        if target.exists():
            verify_artifact(target, expected_id=row['artifact_id'], backend='mlx')
        else:
            shutil.move(str(source), target)
        row['original_artifact_path'] = row['artifact_path']
        row['artifact_path'] = str(target)
    exports = folder / 'research' / 'artifacts'
    if exports.exists():
        shutil.rmtree(exports)
    row['intermediate_exports_removed'] = True


def run_comparison(args):
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    from sera.managed_service import _device_lock_path
    lock_path = _device_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.environ['SERA_LIFETIME_FD'] = str(lock.fileno())
        registration = {'profile': json.loads(Path(args.profile).read_text()),
            'heldout': json.loads(Path(args.heldout).read_text()), 'order': plan_blocks(3),
            'seed_by_block': [0, 1, 2], 'deadline_unix': args.deadline,
            'start_unix': time.time(), 'power': subprocess.check_output(['pmset', '-g', 'batt'], text=True),
            'claim_rule': 'All three paired blocks pass heldout gates and show >5% lower memory.'}
        registration['hash'] = content_hash(registration)
        save_json(root / 'registration.json', registration)
        rows = []
        for block, order in enumerate(plan_blocks(3)):
            for policy in order:
                remaining = args.deadline - time.time()
                if remaining <= 0:
                    break
                folder = root / f'block-{block}-{policy}'
                folder.mkdir()
                command = [sys.executable, '-m', 'benchmarks.native_search', '--one',
                    '--profile', args.profile, '--heldout', args.heldout, '--output', str(folder),
                    '--project', args.project, '--policy', policy, '--seed', str(block), '--block', str(block)]
                with (folder / 'controller.log').open('w') as log:
                    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                        start_new_session=True, pass_fds=(lock.fileno(),))
                    try:
                        process.wait(timeout=remaining)
                    except subprocess.TimeoutExpired:
                        from sera.process_ownership import terminate_group
                        terminate_group(process)
                path = folder / 'row.json'
                row = json.loads(path.read_text()) if path.exists() else {
                    'block': block, 'policy': policy, 'status': 'failed', 'exit_code': process.returncode}
                retain_artifact(row, root, folder)
                rows.append(row)
                save_json(root / 'results.json', {'rows': rows, 'summary': summarize(rows, blocks=3)})
                print(json.dumps(row), flush=True)
        save_json(root / 'results.json', {'rows': rows, 'summary': summarize(rows, blocks=3)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--one', action='store_true')
    for name in ('profile', 'heldout', 'output', 'project'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--policy', choices=POLICIES, default='sera')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--block', type=int, default=0)
    parser.add_argument('--deadline', type=float)
    args = parser.parse_args()
    if not args.one and args.deadline is None:
        parser.error('Comparison requires a global deadline')
    (run_one if args.one else run_comparison)(args)


if __name__ == '__main__':
    main()
