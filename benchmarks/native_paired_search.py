"""Paired mixed-precision search with shared bracketing BF16 controls."""
import argparse
import fcntl
import json
import math
import os
import time
from pathlib import Path

from benchmarks.native_search import heldout_passes, measure_holdout, power_state
from sera.backends.mlx import MLXRecipe
from sera.measurement import objective_value
from sera.model_artifact import verify_artifact
from sera.native_board import NativeBoard
from sera.native_optimizer import NativeProfile
from sera.native_trace import trace_native_job
from sera.native_worker import run_native_job
from sera.storage import content_hash, save_json

CATALOG = {
    'int2-g128': {'bits': 2, 'group_size': 128},
    'int3-g128': {'bits': 3, 'group_size': 128},
    'int4-g128': {'bits': 4, 'group_size': 128},
    'mixed2-3-g128': {'bits': 2, 'protected_bits': 3, 'group_size': 128},
    'mixed2-4-g128': {'bits': 2, 'protected_bits': 4, 'group_size': 128},
    'mixed2-6-g128': {'bits': 2, 'protected_bits': 6, 'group_size': 128},
    'mixed3-4-g128': {'bits': 3, 'protected_bits': 4, 'group_size': 128},
}
FIXED = ['int4-g128', 'int3-g128']
WORKLOAD = ('Short document field extraction into constrained JSON, one request at a time, '
            '32-token output limit, greedy decoding. Minimize memory while retaining 95% of '
            'BF16 extraction accuracy and throughput. User wants to fit AI on current hardware. '
            'Mixed recipes protect token embeddings, output head, and value/down projections '
            'in the first/last eighth of layers and every third middle layer. Other layers use base bits.')


def same_contract_passes(baseline, candidate, profile):
    if baseline.get('input_token_ids') != candidate.get('input_token_ids'):
        return False
    if any(baseline.get('runtime', {}).get(key) != candidate.get('runtime', {}).get(key)
           for key in ('device', 'versions')):
        return False
    return heldout_passes(baseline, candidate, profile)


def choose_confirmed(controls, trials, profile, *, gate=same_contract_passes, metric=objective_value):
    if len(controls) != 2:
        return None
    valid = {name: max(metric(item, 'memory') for item in measurements)
             for name, measurements in trials.items() if len(measurements) >= 2
             and all(gate(control, item, profile) for control in controls for item in measurements)}
    return min(valid, key=lambda name: (valid[name], name)) if valid else None


def comparison_summary(rows):
    complete = (len(rows) == 3 and {r['block'] for r in rows} == {0, 1, 2}
                and all(r.get('qualified') and all(type(r.get(key)) in (int, float)
                    and math.isfinite(r[key]) and r[key] > 0
                    for key in ('sera_peak_mib', 'fixed_peak_mib')) for r in rows))
    return {'complete': complete, 'sera_beats_fixed':
            all(r['sera_peak_mib'] < .95 * r['fixed_peak_mib'] for r in rows) if complete else None}


def run(args):
    from dotenv import load_dotenv

    from sera.managed_service import _device_lock_path
    load_dotenv(override=False)
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    profile = NativeProfile.model_validate_json(Path(args.profile).read_text())
    heldout = NativeProfile.model_validate_json(Path(args.heldout).read_text())
    catalog = json.loads(Path(args.catalog).read_text()) if args.catalog else CATALOG
    fixed = args.fixed or FIXED
    profile = NativeProfile.model_validate(profile.model_dump() | {'recipes': catalog})
    if len(fixed) != 2 or len(set(fixed)) != 2 or any(name not in catalog for name in fixed):
        raise ValueError('Fixed search requires two distinct listed recipes')
    prior = json.loads(Path(args.prior_evidence).read_text()) if args.prior_evidence else (
        'Previous 4-bit group128 passed 20 extraction tasks and heldout; measured 2.43GB vs BF16 8.17GB. No 2/3-bit measurements exist.')
    artifacts = json.loads(Path(args.artifacts).read_text())
    artifacts = {name: {k: item[k] for k in ('path', 'artifact_id')} for name, item in artifacts.items()
                 if name == 'baseline' or name in catalog}
    registration = {'profile': profile.model_dump(), 'heldout': heldout.model_dump(),
        'catalog': catalog, 'fixed_order': fixed, 'candidate_trials_per_policy': 2,
        'blocks': 3, 'policy_order': [['fixed', 'sera'], ['sera', 'fixed'], ['fixed', 'sera']],
        'power': power_state(), 'deadline_unix': args.deadline, 'start_unix': time.time(),
        'workload_description': WORKLOAD,
        'controls': 'Fresh shared BF16 before and after each paired block; each selected candidate independently confirmed.',
        'claim_rule': 'All 3 blocks and independent heldout pass 95% quality/speed gates; Sera uses >5% less peak memory in every block.',
        'time_rule': 'Report full board + own candidate + own confirmation seconds; all catalog exports are shared setup, reported separately. Shared BF16 controls excluded symmetrically.',
        'heldout_rule': 'Validate each unique selected artifact after all choices freeze; no heldout feedback to search.',
        'prior': prior}
    registration['hash'] = content_hash(registration)
    save_json(root / 'registration.json', registration)
    rows, blocks, boards, traces = [], [], [], []
    setup = []

    def remaining():
        left = args.deadline - time.time()
        if left <= 0:
            raise TimeoutError('Global comparison deadline reached')
        return left

    def traced(name, operation):
        remaining()
        started = time.monotonic()
        result = trace_native_job(project=args.project, run=operation)
        result['wall_seconds'] = time.monotonic() - started
        save_json(root / (name + '.json'), result)
        traces.append({'name': name, **result['trace']})
        return result['result'], result['wall_seconds']

    def measure(name, recipe, contract=profile):
        bounded = contract.model_copy(update={'job_timeout_seconds': min(contract.job_timeout_seconds, remaining())})
        record, seconds = traced(name, lambda: measure_holdout(bounded, artifacts[recipe], root / name))
        print(json.dumps({'event': 'measurement', 'name': name, 'recipe': recipe,
            'quality': record['task_quality']['mean'], 'throughput': objective_value(record, 'throughput'),
            'peak_mib': objective_value(record, 'memory'), 'wall_seconds': seconds}), flush=True)
        return record, seconds

    lock_path = _device_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.environ['SERA_LIFETIME_FD'] = str(lock.fileno())
        try:
            for name, artifact in artifacts.items():
                manifest = verify_artifact(artifact['path'], expected_id=artifact['artifact_id'], backend='mlx')
                if manifest['source'] != profile.source.model_dump():
                    raise ValueError('Shared artifact source differs from frozen model')
                expected = MLXRecipe() if name == 'baseline' else MLXRecipe(**catalog[name])
                if manifest['recipe'] != expected.model_dump():
                    raise ValueError('Shared artifact recipe mismatch')
            for name, recipe in catalog.items():
                if name in artifacts:
                    continue
                destination = root / 'artifacts' / name
                destination.parent.mkdir(exist_ok=True)
                result, seconds = traced('prepare-' + name, lambda r=recipe, d=destination, n=name:
                    run_native_job(profile.prepare_job(d, MLXRecipe(**r)),
                        output_dir=root / ('prepare-' + n), timeout_seconds=min(180, remaining())))
                artifacts[name] = {'path': str(destination), 'artifact_id': result['artifact']['artifact_id']}
                setup.append({'recipe': name, 'seconds': seconds})
                save_json(root / 'artifacts.json', artifacts)
                print(json.dumps({'event': 'prepared', 'recipe': name, 'seconds': seconds}), flush=True)
            for block, order in enumerate(registration['policy_order']):
                if power_state() != registration['power']:
                    raise RuntimeError('Power mode changed')
                evidence = {'workload': WORKLOAD, 'prior': registration['prior'],
                    'available_recipes': [{'recipe_id': key, 'recipe': value} for key, value in catalog.items()],
                    'candidate_budget': 2, 'quality_retention': .95, 'throughput_retention': .95,
                    'pattern_definitions': {'all-v-down': 'All value and down projections plus embedding/head use protected bits; other modules use base bits.', 'all-except-mlp-expansion': 'Only MLP gate_proj and up_proj use base bits; all other quantizable modules use protected bits.', 'default': 'Sparse boundary/every-third v/down plus embedding/head protection.'},
                    'selection': 'Jointly rank all recipes, top two will be measured with identical software gates.'}
                board = NativeBoard(root / f'board-{block}')
                boards.append(board)
                plan, board_seconds = traced(f'board-{block}', lambda b=board, e=evidence: {
                    'selected': b.plan(e, timeout_seconds=min(180, remaining())),
                    'history': b.history})
                plans = {'fixed': fixed, 'sera': plan['selected']}
                print(json.dumps({'event': 'plan', 'block': block, 'plans': plans, 'board_seconds': board_seconds}), flush=True)
                before, _ = measure(f'block-{block}-control-before', 'baseline')
                data = {'block': block, 'plans': plans, 'controls': [before], 'policies': {}}
                for policy in order:
                    started = time.monotonic()
                    trials, checkpoints = {}, []
                    for i, name in enumerate(plans[policy]):
                        trial, _ = measure(f'block-{block}-{policy}-trial-{i}', name)
                        trials[name] = [trial]
                        checkpoints.append({'recipe': name, 'elapsed_seconds': time.monotonic() - started
                            + (board_seconds if policy == 'sera' else 0),
                            'passes_initial_control': same_contract_passes(before, trial, profile)})
                    data['policies'][policy] = {'trials': trials, 'checkpoints': checkpoints,
                        'search_seconds': time.monotonic() - started + (board_seconds if policy == 'sera' else 0)}
                after, _ = measure(f'block-{block}-control-after', 'baseline')
                data['controls'].append(after)
                for policy in order:
                    arm = data['policies'][policy]
                    eligible = sorted((name for name, values in arm['trials'].items()
                        if all(same_contract_passes(control, values[0], profile) for control in data['controls'])),
                        key=lambda name: objective_value(arm['trials'][name][0], 'memory'))
                    arm['selected'] = None
                    for index, name in enumerate(eligible):
                        confirmation, seconds = measure(f'block-{block}-{policy}-confirm-{index}', name)
                        arm['search_seconds'] += seconds
                        arm['trials'][name].append(confirmation)
                        arm['selected'] = choose_confirmed(data['controls'], arm['trials'], profile)
                        if arm['selected'] is not None:
                            break
                    arm['peak'] = (max(objective_value(t, 'memory') for t in arm['trials'][arm['selected']])
                                   if arm['selected'] else None)
                data['power_unchanged'] = power_state() == registration['power']
                blocks.append(data)
                save_json(root / 'blocks.json', blocks)
                print(json.dumps({'event': 'block-complete', 'block': block,
                    'selections': {p: {'recipe': a['selected'], 'peak': a['peak'], 'seconds': a['search_seconds']}
                                   for p, a in data['policies'].items()}}), flush=True)
            selected = sorted({a['selected'] for b in blocks for a in b['policies'].values() if a['selected']})
            validation = {}
            baseline, _ = measure('heldout-control-before', 'baseline', heldout)
            for name in selected:
                trial, _ = measure('heldout-' + name, name, heldout)
                validation[name] = trial
            baseline_after, _ = measure('heldout-control-after', 'baseline', heldout)
            for block, board in zip(blocks, boards):
                arms = block['policies']
                passed = {p: a['selected'] is not None and all(same_contract_passes(c, validation[a['selected']], heldout)
                    for c in (baseline, baseline_after)) for p, a in arms.items()}
                review, review_seconds = traced(f'review-{block["block"]}', lambda b=board, a=arms, p=passed:
                    b.review({'sera': {'recipe': a['sera']['selected'], 'peak_mib': a['sera']['peak']}, 'heldout_passed': p['sera'],
                              'software_gates_passed': bool(a['sera']['selected']) and p['sera']},
                             timeout_seconds=min(180, remaining())))
                arms['sera']['search_seconds'] += review_seconds
                rows.append({'block': block['block'], 'qualified': all(passed.values())
                    and block['power_unchanged'] and power_state() == registration['power']
                    and review['decision'] == 'adopt',
                    'sera_peak_mib': arms['sera']['peak'], 'fixed_peak_mib': arms['fixed']['peak'],
                    'sera_recipe': arms['sera']['selected'], 'fixed_recipe': arms['fixed']['selected'],
                    'sera_seconds': arms['sera']['search_seconds'], 'fixed_seconds': arms['fixed']['search_seconds'],
                    'heldout_passed': passed, 'coordinator_review': review})
                save_json(root / 'results.json', {'rows': rows, 'summary': comparison_summary(rows),
                    'setup': setup, 'traces': traces, 'registration_hash': registration['hash']})
        finally:
            os.environ.pop('SERA_LIFETIME_FD', None)
            save_json(root / 'progress.json', {'blocks': blocks, 'rows': rows, 'setup': setup, 'traces': traces})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', default='benchmarks/profiles/qwen3-4b-search.json')
    parser.add_argument('--heldout', default='benchmarks/profiles/qwen3-4b-heldout.json')
    parser.add_argument('--artifacts', default='.local/sera-customer-pilot/retained-candidates/index.json')
    parser.add_argument('--catalog')
    parser.add_argument('--fixed', nargs=2)
    parser.add_argument('--prior-evidence')
    parser.add_argument('--output', required=True)
    parser.add_argument('--project', default='vvennela-n-a/wandb_agent_default_project')
    parser.add_argument('--deadline', type=float, required=True)
    run(parser.parse_args())


if __name__ == '__main__':
    main()
