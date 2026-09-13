"""The recorded notebook must show real evidence without upgrading its claims."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def saved_report():
    return json.loads((ROOT / 'evidence/live-investigation-v1/result.json').read_text())


def write_record(root, name, report):
    folder = root / 'evidence' / name
    folder.mkdir(parents=True)
    (folder / 'result.json').write_text(json.dumps(report))


def load(root):
    from experiments.investigation_demo import load_investigation_demo
    return load_investigation_demo(root)


def test_existing_real_run_is_prominent_but_labeled_batching_only(tmp_path):
    write_record(tmp_path, 'live-investigation-v1', saved_report())
    view = load(tmp_path)
    assert view['source'] == 'evidence/live-investigation-v1/result.json'
    assert 'Recorded real run' in view['banner']
    assert 'batching-only' in view['scope']
    assert len(view['rows']) == 2
    first, second = view['rows']
    assert first['Stage'] == 'Round 1'
    assert first['Specialist'] == 'batching'
    assert '2048' in first['Proposed change']
    assert 'passed' in first['Measured gates']
    assert '773.44 ms' in first['Measured gates']
    assert first['Prediction review'] == 'refuted'
    assert second['Stage'] == 'Round 2'
    assert '1024' in second['Proposed change']
    assert second['Arbiter'] == 'declined'
    assert second['Measured gates'] == 'not run'
    assert 'baseline' in view['runner'] and '4096' in view['runner']
    assert 'fresh request passed' in view['runner'] and 'closed' in view['runner']
    assert 'does not prove a search advantage' in view['limits']


def test_current_real_team_record_is_the_default_with_honest_staged_roles():
    view = load(ROOT)
    assert view['source'] == 'evidence/live-team-investigation-v1/result.json'
    assert 'status: closed' in view['banner']
    assert view['budget'] == '2/3'
    deployment, trial, stop = view['rows']
    assert deployment['Specialist'] == 'quantization'
    assert deployment['Proposed change'] == 'FP8 weights'
    assert trial['Prediction review'] == 'refuted'
    assert 'needs 5%' in trial['Measured gates']
    assert stop['Proposed change'] == 'no change'
    assert stop['Measured gates'] == 'not run'
    assert 'separate stages' in view['scope']
    assert 'fresh request passed' in view['runner']
    assert 'closed after the recorded run' in view['runner']


def test_preferred_team_record_shows_deployment_then_rounds(tmp_path):
    old = saved_report()
    write_record(tmp_path, 'live-investigation-v1', old)
    team = saved_report()
    team['deployment'] = {
        'planning_specialist': {'role': 'quantization', 'status': 'accepted',
                                'response': {'ranked_proposal_ids': ['fp8-weights']}},
        'planning_decision': {'ranked_proposal_ids': ['fp8-weights']},
        'candidate': {'config': {'quantization': 'fp8_per_tensor'}},
        'candidate_trial': old['baseline'],
        'agent_final': {'prediction_outcome': 'confirmed'},
    }
    write_record(tmp_path, 'live-team-investigation-v1', team)
    view = load(tmp_path)
    assert view['source'] == 'evidence/live-team-investigation-v1/result.json'
    assert view['rows'][0]['Stage'] == 'Deployment'
    assert view['rows'][0]['Specialist'] == 'quantization'
    assert view['rows'][0]['Proposed change'] == 'FP8 weights'
    assert view['rows'][0]['Prediction review'] == 'confirmed'
    assert 'separate stages' in view['scope']
    assert 'not competing proposals' in view['scope']


def test_partial_preferred_record_is_not_marked_complete_or_replaced_by_old_success(tmp_path):
    write_record(tmp_path, 'live-investigation-v1', saved_report())
    write_record(tmp_path, 'live-team-investigation-v1', {'status': 'running', 'search': {'rounds': []}})
    view = load(tmp_path)
    assert view['source'] == 'evidence/live-team-investigation-v1/result.json'
    assert 'not a completed result' in view['banner']
    assert 'not recorded' in view['runner']


def test_missing_real_record_never_uses_synthetic_rehearsal(tmp_path):
    write_record(tmp_path, 'demo-investigation-rehearsal-v1', saved_report())
    view = load(tmp_path)
    assert view['source'] is None
    assert view['rows'] == []
    assert 'No saved live investigation' in view['banner']


def test_explicit_synthetic_provenance_is_never_called_real(tmp_path):
    report = saved_report()
    report['provenance'] = {'kind': 'synthetic'}
    write_record(tmp_path, 'live-team-investigation-v1', report)
    view = load(tmp_path)
    assert 'SYNTHETIC' in view['banner']
    assert 'Recorded real run' not in view['banner']


def test_missing_gates_and_review_are_not_inferred_from_selection(tmp_path):
    report = saved_report()
    report['search_trials'][0] = {'trial_id': 'trial-1', 'proposal': report['search_trials'][0]['proposal']}
    write_record(tmp_path, 'live-investigation-v1', report)
    first = load(tmp_path)['rows'][0]
    assert 'not recorded' in first['Measured gates']
    assert first['Prediction review'] == 'not recorded'


def test_unreadable_preferred_record_does_not_claim_old_result_is_the_new_run(tmp_path):
    write_record(tmp_path, 'live-investigation-v1', saved_report())
    folder = tmp_path / 'evidence/live-team-investigation-v1'
    folder.mkdir()
    (folder / 'result.json').write_text('{')
    view = load(tmp_path)
    assert 'could not be read' in view['banner']
    assert view['rows'] == []


def test_swarm_view_links_only_the_selected_namespaced_proposal(tmp_path):
    report = saved_report()
    report['swarm_enabled'] = True
    proposal = {'proposal_id': 'same', 'agent_role': 'batching', 'action': 'trial',
                'changed_lever': 'max_num_batched_tokens', 'proposed_value': 2048}
    report['search']['rounds'] = [dict(round=1, trial_ids=['trial-1'],
        specialists=[dict(investigator_id=name, role='batching', proposal=proposal,
                          initial_proposal=proposal, arbiter_proposal_id=f'{name}:same',
                          inspections=[dict(query_id='latency_outliers', status='complete',
                                            result={'records': [{'call_id': 'source-call'}]})])
                     for name in ['scheduling', 'memory_context']],
        arbiter={'ranked_proposal_ids': ['scheduling:same']})]
    report['search_trials'] = [dict(trial_id='trial-1', proposal=proposal,
        arbiter_proposal_id='scheduling:same', investigator_id='scheduling',
        task_quality={'passed': True}, reduced={'p95_latency_ms': 90},
        review={'prediction_outcome': 'refuted'})]
    write_record(tmp_path, 'live-team-investigation-v1', saved_report())
    write_record(tmp_path, 'live-swarm-investigation-v1', report)
    view = load(tmp_path)
    assert view['source'] == 'evidence/live-swarm-investigation-v1/result.json'
    selected, other = view['rows']
    assert selected['Specialist'] == 'scheduling'
    assert selected['Control role'] == 'batching'
    assert 'quality passed' in selected['Measured gates']
    assert other['Measured gates'] == 'not run'
    assert 'latency_outliers' in selected['Inspections']
    assert 'source-call' in selected['Trace calls']
    assert 'Investigators recorded' in view['scope']
