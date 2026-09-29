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


def audit_fixture(tmp_path):
    from benchmarks.release_audit import TASK_SOURCES

    paths = [f'evidence/{name}/result.json' for name in TASK_SOURCES]
    paths += ['evidence/pressure-v1/result.json', 'benchmarks/grade.py',
              'benchmarks/search.py', 'benchmarks/release_audit.py', 'sera/measurement.py']
    for relative in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    return tmp_path


def test_manifest_discovery_reports_broken_evidence_without_hiding_it(tmp_path):
    import hashlib

    root = audit_fixture(tmp_path)
    broken = root / 'evidence/failed-response.json'
    broken.write_bytes(b'')
    report = audit_release(root)
    scan = report['search_replay']
    assert scan['manifest_scan_complete'] is False
    assert scan['manifest_scan_errors'] == [{
        'path': 'evidence/failed-response.json', 'error': 'JSONDecodeError',
        'bytes': 0, 'sha256': hashlib.sha256(b'').hexdigest()}]
    assert scan['status'] == 'blocked'
    assert broken.read_bytes() == b''


def test_corrupt_required_source_still_fails_the_audit(tmp_path):
    import json

    root = audit_fixture(tmp_path)
    (root / 'evidence/verified-agent-v1/result.json').write_bytes(b'')
    with pytest.raises(json.JSONDecodeError):
        audit_release(root)
