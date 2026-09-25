"""Verify saved Strassen-swarm evidence only; never compile or benchmark kernels."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
from statistics import median

from examples.optimize_cpu_kernel import check_power, power_source
from sera.kernel_search import _score
from sera.kernel_swarm_plan import rank_experiments
from sera.storage import content_hash

FOLDER = Path(__file__).resolve().parent
KERNEL_OPT = Path('/Users/vishnuv/Documents/Documents/kernel-opt')
STANDARD_SIZES = [0, 1, 3, 15, 16, 17, 31, 32, 33, 63, 64, 65, 96, 127, 129, 512]
INPUT_KINDS = ['random', 'identity', 'zero']
NUMERICAL_KINDS = [
    'cancellation-0.03125', 'cancellation-0.0625', 'scale-8', 'scale-12'
]


def read_json(path):
    return json.loads(Path(path).read_text())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_correctness_record(standard, numerical, source_hash, *, label):
    assert standard['schema_version'] == 'sera-cpu-correctness-v1', label
    assert standard['source_hash'] == source_hash, label
    assert standard['passed'] is True, label
    assert standard['timing_claim'] is False, label
    assert standard['sizes'] == STANDARD_SIZES, label
    assert standard['input_kinds'] == INPUT_KINDS, label
    assert len(standard['sizes']) * len(standard['input_kinds']) == 48, label
    assert standard['tolerance'] == 0.002, label

    assert numerical['schema_version'] == 'sera-strassen-numerics-v1', label
    assert numerical['source_hash'] == source_hash, label
    assert numerical['passed'] is True, label
    assert numerical['timing_claim'] is False, label
    assert numerical['n'] == 512 and numerical['tolerance'] == 0.002, label
    cases = numerical['cases']
    assert [case['kind'] for case in cases] == NUMERICAL_KINDS, label
    for case in cases:
        value = case['relative_error']
        assert type(value) in (int, float) and math.isfinite(value), label
        assert 0 <= value <= 0.002, label
    return dict(standard_cases=48, numerical_stress_cases=len(cases),
                standard_record_sha256=None, numerical_record_sha256=None)


result = read_json(FOLDER / 'search/result.json')
controls = read_json(FOLDER / 'controls.json')
state = read_json(FOLDER / 'agent/state.json')

assert result['status'] in {
    'running', 'failed', 'completed', 'holdout-failed', 'final-performance-unconfirmed'
}
assert result['policy']['max_candidates'] == controls['max_candidates'] == 6
assert result['policy']['repeats'] == controls['repeats'] == 10
assert result['policy']['min_improvement'] == controls['min_improvement'] == 0.05
assert result['policy']['max_seconds'] == controls['max_seconds'] == 1800
assert controls['max_model_calls'] == state['max_model_calls'] == 108
assert controls['agent_timeout'] == 180
assert controls['max_seconds'] == 1800
assert state['max_model_calls'] == 108 and state['max_rounds'] == 6
assert state['advisor_count'] == 15 and state['batch_size'] == 3
assert controls['prior_scores_imported'] is False
assert state['calls'] <= 108 and state['implementations'] <= 6
assert len(state['rounds']) <= state['max_rounds'] <= 6
assert len(result['trials']) <= controls['max_candidates'] + 1
assert controls['baseline_sha256'] == '8bb0113e377808a841819354296fa0ef02ff49e4188d57a091afc6463fc0ca18'
assert sha256(controls['baseline']) == controls['baseline_sha256']
assert state['profile']['power'] == controls['profile']['power']

initial_host = controls['host']
expected_power = power_source(initial_host)
assert expected_power == controls['profile']['power']
identity = result.get('comparison_identity')
if identity is None and result['trials']:
    identity = result['trials'][0].get('comparison_identity')

# Preserve historical comparisons as separate source/mode records.
historical_peaks = {
    'battery_automatic_gflops': controls['historical_battery_automatic_peak_gflops'],
    'ac_initial_baseline_gflops': controls['prior_ac_initial_baseline_peak_gflops'],
    'ac_unchanged_control_gflops': controls['prior_ac_control_peak_gflops'],
}
assert all(type(value) in (int, float) and math.isfinite(value)
           for value in historical_peaks.values())

baseline_hash = controls['baseline_sha256']
base_standard = read_json(FOLDER / 'baseline-correctness.json')
base_numerical = read_json(FOLDER / 'baseline-numerics.json')
baseline_correctness_summary = verify_correctness_record(
    base_standard, base_numerical, baseline_hash, label='prepared baseline correctness')
baseline_correctness_summary.update(
    standard_record_sha256=sha256(FOLDER / 'baseline-correctness.json'),
    numerical_record_sha256=sha256(FOLDER / 'baseline-numerics.json'))

verified_reports = []
power_sources = set()


def verify_report(report_name, recorded_score, *, final=False):
    path = Path(report_name).resolve()
    assert path.is_relative_to(FOLDER.resolve()), f'report escaped phase folder: {path}'
    subprocess.run(['hills', 'verify', str(path)], check=True, capture_output=True,
                   timeout=15, cwd=KERNEL_OPT)
    report = read_json(path)
    actual_score = _score(report, final=final, identity=identity)
    assert actual_score == recorded_score, (path, actual_score, recorded_score)
    assert report.get('signature')
    host_path = path.with_suffix('.host.json')
    host = read_json(host_path)
    observations = []
    for observation in (host['before'], host['after']):
        check_power(observation, initial_host)
        power_sources.add(power_source(observation))
        observations.append(observation)
    verified_reports.append(dict(
        path=str(path.relative_to(FOLDER.resolve())),
        sha256=sha256(path), signature_verified=True,
        final=final, power_source=expected_power,
        host_record_sha256=sha256(host_path)))


trial_summaries = []
validation_score_count = 0
control_score_count = 0
correctness_summaries = []
for index, trial in enumerate(result['trials']):
    source_path = Path(trial['source']).resolve()
    assert source_path.is_relative_to(FOLDER.resolve())
    source_hash = sha256(source_path)
    assert source_hash == trial['source_hash']
    if index == 0:
        assert source_hash == baseline_hash

    # Validate on-disk 48-case and four-case reports when present. The nested
    # records in the search result must match their saved sidecars.
    trial_dir = source_path.parent.parent
    correctness_path = trial_dir / 'correctness.json'
    standard_path = trial_dir / 'correctness.standard.json'
    numerical_path = trial_dir / 'correctness.numerics.json'
    if correctness_path.exists():
        correctness = read_json(correctness_path)
        assert correctness.get('source_hash') == source_hash
        if standard_path.exists() and numerical_path.exists():
            standard = read_json(standard_path)
            numerical = read_json(numerical_path)
            if correctness.get('passed') is True:
                assert {k: v for k, v in correctness.items() if k != 'numerical_stress'} == standard
                assert correctness.get('numerical_stress') == numerical
                summary = verify_correctness_record(
                    standard, numerical, source_hash, label=f'trial {index} correctness')
                summary.update(
                    trial=index,
                    standard_record_sha256=sha256(standard_path),
                    numerical_record_sha256=sha256(numerical_path))
                correctness_summaries.append(summary)
        elif trial['status'] == 'passed':
            raise AssertionError(f'missing standard/numerical correctness records for trial {index}')

    public = trial.get('public_correctness')
    if trial['status'] == 'passed':
        assert correctness_path.exists() and standard_path.exists() and numerical_path.exists()
    if public is not None:
        assert public.get('source_hash') == source_hash
        if correctness_path.exists():
            assert public == read_json(correctness_path)
        if trial['status'] == 'passed':
            assert public.get('passed') is True
            assert public.get('numerical_stress', {}).get('passed') is True
            assert len(public['numerical_stress'].get('cases', [])) == 4
    elif trial['status'] == 'passed':
        raise AssertionError(f'missing correctness record for passed trial {index}')

    reports = trial.get('reports', [])
    scores = trial.get('scores', [])
    control_reports = trial.get('control_reports', [])
    control_scores = trial.get('control_scores', [])
    assert len(reports) == len(scores), f'trial {index} validation score/report mismatch'
    assert len(control_reports) == len(control_scores), f'trial {index} control score/report mismatch'
    for report_path, score in zip(reports, scores):
        verify_report(report_path, score)
        validation_score_count += 1
    for report_path, score in zip(control_reports, control_scores):
        verify_report(report_path, score)
        control_score_count += 1

    if trial['status'] == 'passed':
        assert len(scores) == 10, f'passed trial {index} does not have ten validations'
        assert trial.get('median_gflops') == median(scores)
        if index:
            assert len(control_scores) == 10, f'candidate {index} lacks ten paired controls'
            eligible = min(scores) > max(control_scores) * 1.05
            if 'eligible_for_promotion' in trial:
                assert trial['eligible_for_promotion'] is eligible
            if trial.get('promoted'):
                assert eligible
    elif index > 0 and trial.get('eligible_for_promotion'):
        raise AssertionError(f'unscored/rejected candidate {index} marked eligible')

    trial_summaries.append(dict(
        trial=index, name=trial['name'], status=trial['status'], source_sha256=source_hash,
        validation_count=len(scores), control_count=len(control_scores),
        validation_min=min(scores) if scores else None,
        validation_median=median(scores) if scores else None,
        validation_max=max(scores) if scores else None,
        control_min=min(control_scores) if control_scores else None,
        control_max=max(control_scores) if control_scores else None,
        paired_wins=sum(score > control for score, control in zip(scores, control_scores)),
        promotion_threshold=(max(control_scores) * 1.05 if control_scores else None),
        eligible=trial.get('eligible_for_promotion'), promoted=trial.get('promoted')))

# Every saved board is immutable and each accepted ballot is a complete ranking.
round_summaries = []
selected_ids = []
for round_record in state['rounds']:
    board = round_record.get('board', [])
    ballots = round_record.get('ballots', [])
    if board:
        board_ids = [proposal['experiment_id'] for proposal in board]
        assert len(set(board_ids)) == len(board_ids)
        if round_record.get('status') in ('selected', 'implementing', 'completed'):
            assert round_record.get('board_hash') == content_hash(board)
        elif round_record.get('board_hash'):
            assert round_record['board_hash'] == content_hash(board)
        roles = round_record.get('roles', [])
        if round_record.get('status') in ('selected', 'implementing', 'completed'):
            assert len(roles) == 15 and len(set(roles)) == 15
            assert len(ballots) == 15
            assert len({ballot['role'] for ballot in ballots}) == 15
            assert all(ballot['status'] == 'received' for ballot in ballots)
            expected_order = rank_experiments(
                board_ids, [ballot['ranking'] for ballot in ballots],
                limit=min(state['batch_size'], state['max_rounds'] - len(selected_ids)))
            assert round_record.get('experiment_order') == expected_order
            selected_ids.extend(expected_order)
        elif round_record.get('experiment_order'):
            expected_order = rank_experiments(
                board_ids, [ballot['ranking'] for ballot in ballots],
                limit=min(state['batch_size'], state['max_rounds'] - len(selected_ids)))
            assert round_record['experiment_order'] == expected_order
            selected_ids.extend(expected_order)
        for ballot in ballots:
            if ballot.get('status') == 'received':
                assert len(ballot['ranking']) == len(board_ids)
                assert set(ballot['ranking']) == set(board_ids)
                assert len(set(ballot['ranking'])) == len(board_ids)
    attempts = round_record.get('implementations', [])
    order = round_record.get('experiment_order', [])
    assert [item['experiment_id'] for item in attempts] == order[:len(attempts)]
    trial_by_hash = {trial['source_hash']: trial for trial in result['trials']}
    for attempt in attempts:
        if attempt.get('status') == 'proposed':
            measured_trial = trial_by_hash[attempt['source_hash']]
            assert measured_trial['name'] == attempt['name']
    round_summaries.append(dict(
        round=round_record.get('round'), status=round_record.get('status'),
        roster_count=len(round_record.get('roles', [])), ballot_count=len(ballots),
        board_count=len(board), ranked_order=order,
        attempted_ids=[item['experiment_id'] for item in attempts]))

attempt_count = sum(len(batch.get('implementations', [])) for batch in state['rounds'])
assert attempt_count == state['implementations']

# Check the held-out report if the search wrote one. This can be absent when the
# run failed or stopped before final evaluation; absence is reported as such.
final_report_path = result.get('final_report')
final_score = result.get('final_gflops')
if final_report_path:
    assert result.get('selected_source')
    selected_source = Path(result['selected_source']).resolve()
    assert selected_source.is_relative_to(FOLDER.resolve())
    selected_hash = sha256(selected_source)
    assert selected_hash in {trial['source_hash'] for trial in result['trials']}
    verify_report(final_report_path, final_score, final=True)
    assert result.get('final_minimum_gflops') is not None
    selected_record = next(trial for trial in result['trials']
                           if Path(trial['source']).resolve() == selected_source)
    assert result['final_minimum_gflops'] == min(selected_record['scores']) * 0.95
    if result.get('winner_source'):
        assert Path(result['winner_source']).resolve() == selected_source
        assert final_score is not None
else:
    assert final_score is None
    assert result.get('winner_source') is None

assert power_sources <= {expected_power}
terminal = result['status'] != 'running'
if terminal and verified_reports:
    assert power_sources == {expected_power}
if result['status'] == 'completed':
    assert final_report_path and final_score is not None
if result['status'] in ('holdout-failed', 'final-performance-unconfirmed'):
    assert final_report_path
if result['status'] == 'failed' and result.get('winner_source'):
    raise AssertionError('failed search cannot claim a winner')

verification = dict(
    phase='cpu-libxsmm-strassen-swarm-2026-09-25',
    status=result['status'],
    terminal=terminal,
    source_hashes_verified=True,
    baseline_source_sha256=baseline_hash,
    baseline_preparation_correctness=baseline_correctness_summary,
    validated_sources=correctness_summaries,
    signed_report_count=len(verified_reports),
    validation_score_count=validation_score_count,
    paired_control_score_count=control_score_count,
    signatures='hills verify passed for every listed report',
    report_power_mode=expected_power,
    power_settings_unchanged=True,
    no_cross_mode_score_pooling=True,
    historical_peaks_by_mode=historical_peaks,
    calls=state['calls'],
    implementation_attempts=state['implementations'],
    caps=dict(max_calls=state['max_model_calls'], max_implementations=state['max_rounds'],
              max_call_seconds=controls['agent_timeout'], max_run_seconds=controls['max_seconds'],
              max_candidate_slots=controls['max_candidates']),
    board_rounds=round_summaries,
    trials=trial_summaries,
    final_holdout=dict(
        present=bool(final_report_path),
        report=final_report_path,
        gflops=final_score,
        winner_source=result.get('winner_source'),
        target_met=result.get('target_met', False)),
    no_benchmark_executed_by_verifier=True,
    reports=verified_reports,
)
(FOLDER / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
print(json.dumps({key: value for key, value in verification.items() if key != 'reports'}, indent=2))
