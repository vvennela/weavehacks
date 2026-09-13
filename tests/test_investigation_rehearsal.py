import json

from experiments.rehearse_investigation import run_rehearsal
from sera import pipeline


def test_offline_rehearsal_saves_feedback_gates_fresh_runner_and_cleanup(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Offline rehearsal must not call a network or GPU process')

    monkeypatch.setattr('socket.socket', forbidden)
    monkeypatch.setattr('subprocess.Popen', forbidden)
    real_runner, real_collector = pipeline.SeraModel, pipeline.collect_trial
    report = run_rehearsal(tmp_path / 'rehearsal')
    assert pipeline.SeraModel is real_runner
    assert pipeline.collect_trial is real_collector
    assert report['provenance']['kind'] == 'synthetic'
    assert report['provenance']['gpu_trials'] == 0
    assert report['provenance']['provider_calls'] == 0
    assert report['decision']['selected'] == 'trial-2'
    first, second = report['search_trials']
    initial = report['search']['rounds'][0]
    assert {row['role'] for row in initial['specialists'] if row['status'] == 'accepted'} == {
        'quantization', 'batching'}
    assert len(initial['arbiter_evidence']['legal_proposal_ids']) == 2
    assert first['proposal']['agent_role'] == 'quantization'
    assert second['proposal']['agent_role'] == 'batching'
    assert not first['task_quality']['passed']
    assert first['reduced']['p95_latency_ms'] < second['reduced']['p95_latency_ms']
    assert second['task_quality']['passed']
    later = report['search']['rounds'][1]['specialists'][0]
    assert later['evidence']['history'][0]['review']['prediction_outcome'] == 'refuted'
    assert 'trial_1_p95_latency_ms' in later['proposal']['evidence_used']
    assert report['rehearsal']['fresh_response'] == '{"answer": 15}'
    assert report['returned_runner_closed']
    saved = json.loads((tmp_path / 'rehearsal/result.json').read_text())
    assert saved == report
    text = (tmp_path / 'rehearsal/investigation.md').read_text()
    assert 'SYNTHETIC' in text
    assert 'quantization and batching' in text
    assert 'Two specialist proposals competed' in text
    assert 'Quality gate: failed' in text
    assert 'Quality gate: passed' in text
    assert 'History supplied: trial-1' in text
    assert 'refuted' in text
    assert 'Raw evidence: result.json' in text
