"""Recheck this completed replay; never run a timing measurement."""
import hashlib
import json
from pathlib import Path
from statistics import median
import subprocess

from examples.optimize_cpu_kernel import check_power
from sera.kernel_search import _score
from sera.kernel_swarm_plan import rank_experiments

folder = Path(__file__).resolve().parent
result = json.loads((folder / 'search/result.json').read_text())
controls = json.loads((folder / 'controls.json').read_text())
state = json.loads((folder / 'agent/state.json').read_text())
assert result['status'] == 'completed'
assert result['policy']['repeats'] == 10
assert result['policy']['min_improvement'] == 0.05
trials = result['trials']
assert len(trials) == 2
assert state['calls'] == 83 and state['implementations'] == 4
proposed = [i['source_hash'] for r in state['rounds'] for i in r.get('implementations', []) if i['status'] == 'proposed']
assert proposed == [t['source_hash'] for t in trials[1:]]
assert trials[0]['source_hash'] == controls['baseline_sha256']
for board in state['rounds']:
    assert len(board['roles']) == len(board['advice']) == 15
    if board['status'] == 'selected':
        ballots = [b['ranking'] for b in board['ballots']]
        assert len(ballots) == 15
        order = rank_experiments([b['experiment_id'] for b in board['board']], ballots, limit=3)
        assert order == board['experiment_order']
    else:
        assert board['status'] == 'abstained' and all(a['abstain'] for a in board['advice'])
assert not any(t.get('promoted') for t in trials)
assert result['selected_source'] == trials[0]['source']
reports = []


def verify_report(name, score, *, final=False):
    path = Path(name)
    subprocess.run(['hills', 'verify', str(path)], check=True, capture_output=True,
                   timeout=10, cwd='/Users/vishnuv/Documents/Documents/kernel-opt')
    report = json.loads(path.read_text())
    assert _score(report, final=final, identity=result['comparison_identity']) == score
    host = json.loads(path.with_suffix('.host.json').read_text())
    for observation in (host['before'], host['after']):
        check_power(observation, controls['host'])
    reports.append(dict(path=str(path.relative_to(folder)),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(), signature_verified=True))


fresh_peak = max(trials[0]['scores'])
historical_peak = controls['prior_imported_peak_gflops']
comparisons = []
for index, trial in enumerate(trials):
    assert hashlib.sha256(Path(trial['source']).read_bytes()).hexdigest() == trial['source_hash']
    assert trial['public_correctness']['passed']
    assert trial['public_correctness']['source_hash'] == trial['source_hash']
    assert len(trial['scores']) == len(trial['reports']) == 10
    for path, score in zip(trial['reports'], trial['scores']):
        verify_report(path, score)
    if index:
        assert len(trial['control_scores']) == len(trial['control_reports']) == 10
        for path, score in zip(trial['control_reports'], trial['control_scores']):
            verify_report(path, score)
        eligible = min(trial['scores']) > max(trial['control_scores']) * 1.05
        assert eligible == trial['eligible_for_promotion']
        comparisons.append(dict(name=trial['name'], source_hash=trial['source_hash'],
            minimum=min(trial['scores']), median=median(trial['scores']), maximum=max(trial['scores']),
            above_historical_peak=sum(s > historical_peak for s in trial['scores']),
            above_fresh_baseline_peak=sum(s > fresh_peak for s in trial['scores']),
            paired_wins=sum(s > c for s, c in zip(trial['scores'], trial['control_scores'])),
            eligible_for_promotion=eligible, promoted=trial['promoted']))
verify_report(result['final_report'], result['final_gflops'], final=True)
assert len(reports) == 31
assert result['final_gflops'] >= result['final_minimum_gflops']
verification = dict(report_count=len(reports), reports=reports,
    source_hashes_verified=True, correctness_passed=True, power_unchanged=True,
    scoring_unit='One signed Hill report; each retains the frozen best-of-three timing rule',
    historical_imported_peak_gflops=historical_peak, fresh_baseline_peak_gflops=fresh_peak,
    comparisons=comparisons, model_calls=state['calls'], implementation_attempts=state['implementations'],
    board_rankings_verified=True, advisory_rounds=len(state['rounds']),
    final_source='unchanged imported baseline', final_gflops=result['final_gflops'],
    ten_of_ten_above_historical_peak=any(c['above_historical_peak'] == 10 for c in comparisons),
    ten_of_ten_above_fresh_peak=any(c['above_fresh_baseline_peak'] == 10 for c in comparisons),
    goal_complete=False)
(folder / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
print(json.dumps({k: v for k, v in verification.items() if k != 'reports'}, indent=2))
