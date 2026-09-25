"""Verify the interrupted dataflow-board phase; never launch a benchmark."""
import hashlib
import json
from pathlib import Path
import subprocess
from statistics import median

from examples.optimize_cpu_kernel import check_power, power_source
from sera.kernel_search import _score

FOLDER = Path(__file__).resolve().parent
KERNEL_OPT = Path('/Users/vishnuv/Documents/Documents/kernel-opt')

result = json.loads((FOLDER / 'search/result.json').read_text())
controls = json.loads((FOLDER / 'controls.json').read_text())
state = json.loads((FOLDER / 'agent/state.json').read_text())

assert result['status'] == 'failed'
assert 'KeyboardInterrupt' in result.get('error', '')
assert result.get('winner_source') is None and result.get('final_report') is None
assert result['target_met'] is False
assert result['policy'] == dict(max_candidates=6, repeats=10,
                                min_improvement=0.05, max_seconds=1800)
assert controls['prior_scores_imported'] is False
assert controls['max_model_calls'] == state['max_model_calls'] == 108
assert state['calls'] == 1 and state['implementations'] == 0
assert len(state['rounds']) == 1
round_record = state['rounds'][0]
assert round_record['status'] == 'failed'
assert round_record['roles'] == []
assert round_record['advice'] == []
assert round_record['ballots'] == []
assert round_record['implementations'] == []
assert len(result['trials']) == 1
trial = result['trials'][0]
assert trial['status'] == 'passed'
assert trial['source_hash'] == controls['baseline_sha256']
assert trial['public_correctness']['passed'] is True
assert trial['public_correctness']['source_hash'] == trial['source_hash']
assert len(trial['scores']) == len(trial['reports']) == 10
assert trial['control_scores'] == [] and trial['control_reports'] == []

baseline = Path(controls['baseline']).resolve()
assert baseline.is_relative_to(FOLDER.resolve())
baseline_hash = hashlib.sha256(baseline.read_bytes()).hexdigest()
assert baseline_hash == controls['baseline_sha256'] == trial['source_hash']
assert baseline_hash == '8bb0113e377808a841819354296fa0ef02ff49e4188d57a091afc6463fc0ca18'
identity = result['comparison_identity']
initial_host = controls['host']
expected_power = power_source(initial_host)
assert expected_power == controls['profile']['power'] == state['profile']['power']

verified_reports = []
for name, score in zip(trial['reports'], trial['scores']):
    path = Path(name).resolve()
    assert path.is_relative_to(FOLDER.resolve())
    subprocess.run(['hills', 'verify', str(path)], check=True, capture_output=True,
                   timeout=15, cwd=KERNEL_OPT)
    report = json.loads(path.read_text())
    assert _score(report, final=False, identity=identity) == score
    assert report.get('signature')
    host_path = path.with_suffix('.host.json')
    host = json.loads(host_path.read_text())
    for observation in (host['before'], host['after']):
        check_power(observation, initial_host)
        assert power_source(observation) == expected_power
    verified_reports.append(dict(
        path=str(path.relative_to(FOLDER.resolve())),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        host_record_sha256=hashlib.sha256(host_path.read_bytes()).hexdigest(),
        signature_verified=True,
        power_source=expected_power,
    ))

assert len(verified_reports) == 10
correctness = json.loads((FOLDER / 'baseline-correctness.json').read_text())
numerical = json.loads((FOLDER / 'baseline-numerics.json').read_text())
assert correctness['passed'] is True and correctness['source_hash'] == baseline_hash
assert len(correctness['sizes']) * len(correctness['input_kinds']) == 48
assert numerical['passed'] is True and numerical['source_hash'] == baseline_hash
assert len(numerical['cases']) == 4

scores = trial['scores']
interruption = dict(
    phase='cpu-libxsmm-dataflow-board-2026-09-25',
    search_status='failed',
    cause='KeyboardInterrupt after baseline measurements, during first coordinator request',
    shell_exit_code=130,
    run_process_terminal=True,
    future_benchmark_live=False,
    model_calls=state['calls'],
    implementation_attempts=state['implementations'],
    candidate_sources=0,
    holdout_present=False,
    winner_source=None,
    signed_baseline_reports=len(verified_reports),
    baseline_source_sha256=baseline_hash,
    power_mode=expected_power,
    baseline_score_min=min(scores),
    baseline_score_median=median(scores),
    baseline_score_max=max(scores),
    no_performance_runs_launched_by_verifier=True,
    evidence='search/result.json, agent/state.json, and terminal run.log',
)
(FOLDER / 'interruption.json').write_text(json.dumps(interruption, indent=2) + '\n')
verification = dict(
    phase=interruption['phase'],
    status='interrupted_after_baseline',
    source_hash_verified=True,
    signed_report_count=len(verified_reports),
    signatures='hills verify passed for every baseline report',
    power_mode=expected_power,
    power_settings_unchanged=True,
    baseline_correctness=dict(standard_cases=48, numerical_stress_cases=4),
    baseline_scores=dict(min=min(scores), median=median(scores), max=max(scores)),
    model_calls=state['calls'],
    implementation_attempts=state['implementations'],
    candidate_sources=0,
    final_holdout_present=False,
    run_process_terminal=True,
    future_benchmark_live=False,
    reports=verified_reports,
)
(FOLDER / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
print(json.dumps({key: value for key, value in verification.items() if key != 'reports'}, indent=2))
