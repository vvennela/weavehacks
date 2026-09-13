from pathlib import Path

import pytest

from benchmarks.release_audit import audit_release, audit_task_outputs


ROOT = Path(__file__).resolve().parents[1]


def test_saved_real_answers_and_loads_are_rechecked_without_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Audit must be offline')

    monkeypatch.setattr('socket.socket', forbidden)
    monkeypatch.setattr('subprocess.Popen', forbidden)
    report = audit_release(ROOT)
    scores = {row['source'] + ':' + row['trial']: row for row in report['task_evaluations']}
    small = scores['evidence/verified-agent-v1/result.json:baseline']
    assert (small['passed'], small['total'], small['gate_passed']) == (2, 8, False)
    assert scores['evidence/glm-bf16-v1/result.json:trial']['passed'] == 0
    assert scores['evidence/qwen-fp8-placement-quality-v1/result.json:trial']['passed'] == 1
    assert all(row['saved_gate_matches'] for row in scores.values())
    comparison = report['performance_comparison']
    assert comparison['identity_matches']
    assert comparison['saved_metrics_match']
    assert comparison['candidate_throughput_gain_fraction'] == pytest.approx(.000238196955)
    assert comparison['meets_required_gain'] is False
    assert len(comparison['loads']) == 4
    assert report['search_replay']['status'] == 'blocked'
    assert report['search_replay']['grid_runs'] == report['search_replay']['random_runs'] == 0
    assert report['pressure']['scenario'] == 'not-established'
    assert all(len(source['sha256']) == 64 for source in report['sources'])


def test_regrading_keeps_format_and_output_errors_as_failures():
    cases = [{'id': 'one', 'expected': 5}]
    trial = {'quality': [{'prompt_index': 0, 'text': '```json\n{"answer": 5}\n```'}],
             'task_quality': {'floor': .99, 'mean': 0.0, 'passed': False}}
    assert audit_task_outputs(cases, trial)['passed'] == 0
    trial['quality'] = [{'prompt_index': 0, 'text': '{"answer": 5}', 'error': 'request-failed'}]
    assert audit_task_outputs(cases, trial)['passed'] == 0


def test_regrading_rejects_missing_or_duplicate_prompt_slots():
    cases = [{'id': 'one', 'expected': 5}, {'id': 'two', 'expected': 6}]
    trial = {'quality': [{'prompt_index': 0, 'text': '{"answer": 5}'},
                         {'prompt_index': 0, 'text': '{"answer": 6}'}],
             'task_quality': {'floor': .99, 'mean': 1.0, 'passed': True}}
    result = audit_task_outputs(cases, trial)
    assert result['gate_passed'] is False
    assert result['saved_gate_matches'] is False
