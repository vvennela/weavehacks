"""Verify the completed saved SME-techniques phase without running benchmarks."""
import hashlib
import json
from pathlib import Path
from statistics import median
import subprocess

from examples.optimize_cpu_kernel import check_power, power_source
from sera.kernel_search import _score
from sera.kernel_swarm_plan import rank_experiments
from sera.storage import content_hash

FOLDER = Path(__file__).resolve().parent
KERNEL_OPT = Path('/Users/vishnuv/Documents/Documents/kernel-opt')
BASELINE_SHA256 = '04fc3ff86669c2ca123e3b390b662637cd69c21f3d63fa26f7a5f0f0a882317c'
REPLAY_SHA256 = 'eb091b1eca431f0760d0d61e4c0c6e748c1a9e34466a87ac15ad9cb238b5aecf'


def read_json(path):
    return json.loads(Path(path).read_text())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def phase_path(value):
    path = Path(value).resolve()
    assert path.is_relative_to(FOLDER.resolve()), f'path escaped phase folder: {path}'
    return path


def main():
    result = read_json(FOLDER / 'search/result.json')
    controls = read_json(FOLDER / 'controls.json')
    state = read_json(FOLDER / 'agent/state.json')

    assert result['status'] != 'running', 'Do not run verification during the live phase.'
    assert result['policy'] == dict(max_candidates=6, repeats=10,
                                    min_improvement=0.05, max_seconds=1800.0)
    assert result['target_gflops'] == 1800
    assert state['coordinator'] == 'gpt-6-astra'
    assert state['coordinator_reasoning'] == 'high'
    assert state['advisor_model'] == 'gpt-6-luna' and state['advisor_count'] == 15
    assert state['max_model_calls'] == controls['max_model_calls'] == 108
    assert state['batch_size'] == 3
    assert state['calls'] <= 108
    assert state['implementations'] <= 6
    assert controls['max_candidates'] == 6
    assert controls['max_seconds'] == 1800
    assert controls['agent_timeout'] == 180
    assert controls['repeats'] == 10 and controls['min_improvement'] == 0.05
    assert controls['prior_scores_imported'] is False
    assert controls['focus_source_sha256'] == REPLAY_SHA256
    assert controls['source_hashes'] == [BASELINE_SHA256, REPLAY_SHA256]

    initial_host = controls['host']
    expected_power = power_source(initial_host)
    identity = result.get('comparison_identity')
    if identity is not None:
        assert identity['tree_hash']
        assert identity['config']['n'] == 512
        assert identity['config']['tolerance'] == 0.002

    reports = []
    observed_power_sources = set()
    successful_score_reports = 0
    timing_samples = 0
    submission_by_source = {}
    source_by_submission = {}

    def verify_report(report_name, recorded_score=None, *, final=False,
                      expected_source_hash=None):
        nonlocal successful_score_reports, timing_samples
        path = phase_path(report_name)
        subprocess.run(['hills', 'verify', str(path)], cwd=KERNEL_OPT,
                       capture_output=True, check=True, timeout=15)
        report = read_json(path)
        assert report.get('signature'), f'missing signature: {path}'
        submission_hash = report.get('submission_hash')
        assert isinstance(submission_hash, str) and submission_hash.startswith('sha256:')
        if expected_source_hash is not None:
            prior_submission = submission_by_source.setdefault(
                expected_source_hash, submission_hash)
            assert submission_hash == prior_submission, (
                f'signed report does not match expected source {expected_source_hash}: {path}')
            prior_source = source_by_submission.setdefault(submission_hash, expected_source_hash)
            assert prior_source == expected_source_hash, (
                f'submission hash is mapped to multiple sources: {path}')
        actual_score = _score(report, final=final, identity=identity)
        if recorded_score is not None:
            assert actual_score == recorded_score, (path, actual_score, recorded_score)
        elif report.get('passed') is True:
            raise AssertionError(f'scored report has no matching saved score: {path}')

        timings = report.get('details', {}).get('timings_seconds', [])
        if actual_score is not None:
            assert len(timings) == 3 and all(
                type(value) in (int, float) and value > 0 for value in timings
            ), f'expected all three raw timing samples: {path}'
            assert min(timings) == report['details']['seconds_best_of_3']
            expected = 2 * 512**3 / min(timings) / 1e9
            assert abs(expected - actual_score) < 1e-8
            successful_score_reports += 1
            timing_samples += len(timings)
        elif timings:
            assert len(timings) == 3 and all(value > 0 for value in timings)
            timing_samples += len(timings)

        host_path = path.with_suffix('.host.json')
        assert host_path.exists(), f'missing power provenance: {host_path}'
        host = read_json(host_path)
        assert set(host) == {'before', 'after'}
        for observation in (host['before'], host['after']):
            check_power(observation, initial_host)
            observed_power_sources.add(power_source(observation))
        reports.append(dict(
            path=str(path.relative_to(FOLDER.resolve())),
            sha256=sha256(path),
            submission_hash=submission_hash,
            expected_source_hash=expected_source_hash,
            score=actual_score,
            final=final,
            raw_timings_seconds=timings,
            signature_verified=True,
            power_source=expected_power,
        ))
        return actual_score

    trial_summaries = []
    total_candidate_validations = 0
    total_control_scores = 0
    incumbent_hash = BASELINE_SHA256
    for index, trial in enumerate(result['trials']):
        source_path = phase_path(trial['source'])
        source_hash = sha256(source_path)
        assert source_hash == trial['source_hash']
        if index == 0:
            assert source_hash == BASELINE_SHA256
        elif index == 1:
            assert source_hash == REPLAY_SHA256

        correctness = trial.get('public_correctness')
        correctness_summary = None
        if correctness is not None:
            assert correctness['source_hash'] == source_hash
            correctness_path = source_path.parent.parent / 'correctness.json'
            assert correctness_path.exists()
            saved_correctness = read_json(correctness_path)
            assert saved_correctness == correctness
            if trial['status'] == 'passed':
                assert correctness['passed'] is True
            assert len(correctness['sizes']) * len(correctness['input_kinds']) == 48
            assert correctness['tolerance'] == 0.002
            correctness_summary = dict(
                passed=correctness['passed'],
                cases=len(correctness['sizes']) * len(correctness['input_kinds']),
                source_hash=source_hash,
            )
        elif trial['status'] == 'passed':
            raise AssertionError(f'passed trial lacks correctness record: {trial["name"]}')

        scores = trial.get('scores', [])
        control_scores = trial.get('control_scores', [])
        score_paths = trial.get('reports', [])
        control_paths = trial.get('control_reports', [])
        assert len(score_paths) >= len(scores)
        assert len(control_paths) >= len(control_scores)
        if trial['status'] == 'passed':
            assert len(scores) == len(score_paths) == 10
            if index > 0:
                assert len(control_scores) == len(control_paths) == 10
                eligible = min(scores) > max(control_scores) * 1.05
                assert trial['eligible_for_promotion'] is eligible
                assert trial['promoted'] is False or eligible
                if trial['promoted']:
                    assert trial.get('adjudication', {}).get('decision') == 'adopt'
            else:
                assert not control_scores and not control_paths

        for path, score in zip(score_paths, scores):
            verify_report(path, score, expected_source_hash=source_hash)
            if index > 0:
                total_candidate_validations += 1
        for path, score in zip(control_paths, control_scores):
            verify_report(path, score, expected_source_hash=incumbent_hash)
            total_control_scores += 1
        # Preserve and authenticate any failed/partial reports too.
        for path in score_paths[len(scores):]:
            verify_report(path, expected_source_hash=source_hash)
        for path in control_paths[len(control_scores):]:
            verify_report(path, expected_source_hash=incumbent_hash)

        if index == 0:
            incumbent_hash = source_hash
        elif trial.get('promoted'):
            incumbent_hash = source_hash

        trial_summaries.append(dict(
            index=index,
            name=trial['name'],
            status=trial['status'],
            source_sha256=source_hash,
            correctness=correctness_summary,
            validation_count=len(scores),
            control_count=len(control_scores),
            score_min=min(scores) if scores else None,
            score_median=median(scores) if scores else None,
            score_max=max(scores) if scores else None,
            control_min=min(control_scores) if control_scores else None,
            control_max=max(control_scores) if control_scores else None,
            eligible=trial.get('eligible_for_promotion'),
            promoted=trial.get('promoted'),
        ))

    assert result['trials'], 'completed search must retain its baseline trial'
    assert len(result['trials']) <= 7  # fresh baseline, replay, and at most five proposals
    assert observed_power_sources <= {expected_power}
    assert observed_power_sources, 'no reports had host power provenance'

    round_summaries = []
    for round_record in state.get('rounds', []):
        board = round_record['board']
        board_ids = [item['experiment_id'] for item in board]
        assert len(set(board_ids)) == len(board_ids)
        assert round_record['board_hash'] == content_hash(board)
        if round_record['status'] == 'selected':
            ballots = round_record['ballots']
            assert len(ballots) == 15
            assert len({ballot['role'] for ballot in ballots}) == 15
            assert all(ballot['status'] == 'received' for ballot in ballots)
            expected_order = rank_experiments(
                board_ids, [ballot['ranking'] for ballot in ballots],
                limit=state['batch_size'])
            assert round_record['experiment_order'] == expected_order
            order_verified = True
            ballot_count = len(ballots)
        else:
            order_verified = False
            ballot_count = len(round_record.get('ballots', []))
        round_summaries.append(dict(
            round=round_record.get('round'),
            status=round_record['status'],
            ballot_count=ballot_count,
            board_ids=board_ids,
            ranked_order=round_record.get('experiment_order', []),
            order_verified=order_verified,
        ))

    final_path_value = result.get('final_report')
    final_score = result.get('final_gflops')
    final_summary = dict(present=False, source_hash=None, score=None)
    if final_path_value:
        assert result.get('selected_source')
        selected_path = phase_path(result['selected_source'])
        selected_hash = sha256(selected_path)
        selected_trial = next(t for t in result['trials'] if t['source'] == result['selected_source'])
        assert selected_trial['source_hash'] == selected_hash
        actual_final_score = verify_report(
            final_path_value, final_score, final=True,
            expected_source_hash=selected_hash)
        final_summary = dict(
            present=True,
            source_hash=selected_hash,
            score=actual_final_score,
            status=result['status'],
            target_met=result['target_met'],
            winner_source=result['winner_source'],
            final_minimum_gflops=result.get('final_minimum_gflops'),
            holdout_path=str(phase_path(final_path_value).relative_to(FOLDER.resolve())),
        )
        if result['status'] == 'final-performance-unconfirmed':
            assert result['winner_source'] is None and result['target_met'] is False
            assert result['final_minimum_gflops'] == min(selected_trial['scores']) * 0.95
            assert actual_final_score < result['final_minimum_gflops']
        elif result['status'] in ('completed', 'holdout-failed'):
            if actual_final_score is None:
                assert result['status'] == 'holdout-failed'
                assert result['winner_source'] is None and result['target_met'] is False
            else:
                assert result['status'] == 'completed'
                assert result['final_minimum_gflops'] == min(selected_trial['scores']) * 0.95
                assert actual_final_score >= result['final_minimum_gflops']
                assert result['winner_source'] == result['selected_source']
                expected_target = min(selected_trial['scores'] + [actual_final_score]) > result['target_gflops']
                assert result['target_met'] is expected_target
    else:
        assert result['winner_source'] is None and result['target_met'] is False

    verification = dict(
        phase=FOLDER.name,
        status=result['status'],
        target_gflops=result['target_gflops'],
        target_met=result['target_met'],
        winner_source=result['winner_source'],
        stop_reason=result.get('stop_reason'),
        source_hashes_verified=True,
        baseline_sha256=BASELINE_SHA256,
        replay_sha256=REPLAY_SHA256,
        signed_report_count=len(reports),
        scored_report_count=successful_score_reports,
        raw_timing_sample_count=timing_samples,
        baseline_validation_count=len(result['trials'][0]['scores']),
        replay_and_candidate_validation_count=total_candidate_validations,
        paired_control_score_count=total_control_scores,
        public_correctness_case_count=sum(
            item['correctness']['cases'] for item in trial_summaries
            if item['correctness'] and item['correctness']['passed']),
        signature_verification='hills verify passed for every retained report',
        power_source=expected_power,
        power_settings_unchanged=observed_power_sources == {expected_power},
        calls=state['calls'],
        implementation_attempts=state['implementations'],
        round_summaries=round_summaries,
        trials=trial_summaries,
        final=final_summary,
        performance_runs_executed_by_verifier=False,
        reports=reports,
    )
    (FOLDER / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
    print(json.dumps({key: value for key, value in verification.items()
                      if key != 'reports'}, indent=2))


if __name__ == '__main__':
    main()
