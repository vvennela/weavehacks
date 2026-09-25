"""Verify saved artifacts for the failed compiler-board phase; never benchmark."""
import hashlib
import json
from pathlib import Path
import subprocess

from examples.optimize_cpu_kernel import check_power, power_source
from sera.kernel_search import _score
from sera.kernel_swarm_plan import rank_experiments
from sera.storage import content_hash

FOLDER = Path(__file__).resolve().parent
KERNEL_OPT = Path('/Users/vishnuv/Documents/Documents/kernel-opt')

result = json.loads((FOLDER / 'search/result.json').read_text())
controls = json.loads((FOLDER / 'controls.json').read_text())
state = json.loads((FOLDER / 'agent/state.json').read_text())
prompt_repair = json.loads((FOLDER / 'prompt-repair-verification.json').read_text())

assert result['status'] == 'failed'
assert result['winner_source'] is None and result['target_met'] is False
assert result['policy'] == dict(max_candidates=6, repeats=10,
                                min_improvement=0.05, max_seconds=1800)
assert controls['max_candidates'] == 6
assert controls['max_model_calls'] == state['max_model_calls'] == 108
assert controls['repeats'] == result['policy']['repeats'] == 10
assert controls['min_improvement'] == result['policy']['min_improvement'] == 0.05
assert controls['max_seconds'] == result['policy']['max_seconds'] == 1800
assert controls['prior_scores_imported'] is False
assert state['calls'] == 73 and state['implementations'] == 5
assert len(result['trials']) == 7
assert len(result['trials']) - 1 == controls['max_candidates']

initial_host = controls['host']
expected_power = power_source(initial_host)
expected_baseline = controls['baseline_sha256']
assert hashlib.sha256(Path(controls['baseline']).read_bytes()).hexdigest() == expected_baseline
assert result['comparison_identity']['tree_hash']
assert result['comparison_identity']['config']['n'] == 512
assert result['comparison_identity']['config']['tolerance'] == 0.002

verified_reports = []
power_sources = set()
score_count = 0
control_count = 0


def verify_report(report_name, recorded_score, *, final=False):
    path = Path(report_name).resolve()
    assert path.is_relative_to(FOLDER.resolve()), f'report escaped phase folder: {path}'
    subprocess.run(['hills', 'verify', str(path)], check=True, capture_output=True,
                   timeout=15, cwd=KERNEL_OPT)
    report = json.loads(path.read_text())
    actual_score = _score(report, final=final,
                          identity=result['comparison_identity'])
    assert actual_score == recorded_score, (path, actual_score, recorded_score)
    assert report['signature']
    host_path = path.with_suffix('.host.json')
    host = json.loads(host_path.read_text())
    for observation in (host['before'], host['after']):
        check_power(observation, initial_host)
        power_sources.add(power_source(observation))
    verified_reports.append(dict(
        path=str(path.relative_to(FOLDER.resolve())),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        signature_verified=True,
        power_source=expected_power,
    ))


trial_summaries = []
for index, trial in enumerate(result['trials']):
    source_path = Path(trial['source']).resolve()
    assert source_path.is_relative_to(FOLDER.resolve())
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    assert source_hash == trial['source_hash']
    if index == 0:
        assert source_hash == expected_baseline
    if trial['status'] == 'passed':
        correctness = trial['public_correctness']
        assert correctness['passed'] is True
        assert correctness['source_hash'] == source_hash
        assert len(trial['scores']) == len(trial['reports']) == 10
        assert len(trial['control_scores']) == len(trial['control_reports'])
        for name, score in zip(trial['reports'], trial['scores']):
            verify_report(name, score)
            score_count += 1
        if index:
            assert len(trial['control_scores']) == 10
            for name, score in zip(trial['control_reports'], trial['control_scores']):
                verify_report(name, score)
                control_count += 1
            eligible = min(trial['scores']) > max(trial['control_scores']) * 1.05
            assert eligible is trial['eligible_for_promotion']
            assert trial['promoted'] is False
        trial_summaries.append(dict(
            trial=index,
            name=trial['name'],
            source_sha256=source_hash,
            score_count=len(trial['scores']),
            control_count=len(trial['control_scores']),
            score_min=min(trial['scores']),
            score_max=max(trial['scores']),
            control_min=min(trial['control_scores']) if trial['control_scores'] else None,
            control_max=max(trial['control_scores']) if trial['control_scores'] else None,
            eligible=trial.get('eligible_for_promotion'),
            promoted=trial.get('promoted'),
        ))
    else:
        assert index == 6
        assert trial['status'] == 'rejected'
        assert trial['scores'] == trial['reports'] == []
        assert trial['control_scores'] == trial['control_reports'] == []
        assert trial['eligible_for_promotion'] is False
        assert trial['promoted'] is False
        assert trial.get('public_correctness', {}).get('passed') is not True
        trial_summaries.append(dict(
            trial=index, name=trial['name'], source_sha256=source_hash,
            status='rejected_before_scoring', score_count=0, control_count=0,
            error_type='recorded_error' if trial.get('error') else None,
        ))

assert score_count == 60
assert control_count == 50
assert len(verified_reports) == 110
assert power_sources == {expected_power}

round_summaries = []
for round_record in state['rounds']:
    board_ids = [proposal['experiment_id'] for proposal in round_record['board']]
    assert round_record['status'] == 'selected'
    assert len(set(board_ids)) == len(board_ids)
    assert round_record['board_hash'] == content_hash(round_record['board'])
    assert len(round_record['ballots']) == 15
    assert len({ballot['role'] for ballot in round_record['ballots']}) == 15
    ballots = []
    for ballot in round_record['ballots']:
        assert ballot['status'] == 'received'
        ballots.append(ballot['ranking'])
    expected_order = rank_experiments(board_ids, ballots, limit=state['batch_size'])
    assert expected_order == round_record['experiment_order']
    round_summaries.append(dict(
        round=round_record['round'], ballot_count=len(ballots),
        board_ids=board_ids, ranked_order=expected_order,
        order_matches=True,
    ))

assert len(state['rounds']) == 2
assert prompt_repair['old_prompt_characters'] == 1_108_459
assert prompt_repair['limit_characters'] == 1_048_576
assert prompt_repair['old_prompt_characters'] > prompt_repair['limit_characters']
assert prompt_repair['no_failed_phase_records_rewritten'] is True
assert result['winner_source'] is None

verification = dict(
    phase='cpu-libxsmm-compiler-board-2026-09-25',
    status='failed_final_review',
    source_hashes_verified=True,
    baseline_sha256=expected_baseline,
    signed_report_count=len(verified_reports),
    baseline_score_count=len(result['trials'][0]['scores']),
    candidate_validation_score_count=sum(len(t['scores']) for t in result['trials'][1:]),
    paired_control_score_count=control_count,
    all_validation_and_control_scores=score_count + control_count,
    signature_verification='hills verify passed for every listed report',
    power_source=expected_power,
    power_settings_unchanged=True,
    performance_runs_executed_by_verifier=False,
    calls=state['calls'],
    implementation_attempts=state['implementations'],
    trials=len(result['trials']),
    rejected_unscored_trials=1,
    board_rounds=round_summaries,
    trial_summaries=trial_summaries,
    final_review=dict(
        failed=True,
        original_input_characters=prompt_repair['old_prompt_characters'],
        configured_limit_characters=prompt_repair['limit_characters'],
        exceeded_by_characters=(prompt_repair['old_prompt_characters'] -
                                prompt_repair['limit_characters']),
        holdout_report_present=False,
        promoted_candidate=False,
    ),
    no_candidate_promoted=True,
    reports=verified_reports,
)
(FOLDER / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
print(json.dumps({k: v for k, v in verification.items() if k != 'reports'}, indent=2))
