"""Participation is declared eligibility, not an invented agent call."""

import sera
from test_investigation import install_fakes, run


def participation(record):
    return {item['role']: item for item in record['specialist_participation']}


def test_both_legal_specialists_are_active_and_parallelism_is_not_called(tmp_path, monkeypatch):
    _, seen, agent = install_fakes(monkeypatch)
    with run(tmp_path, agent) as result:
        first = result.report['search']['rounds'][0]
        roles = participation(first)
        assert set(roles) == {'quantization', 'batching', 'parallelism'}
        for role in ('quantization', 'batching'):
            assert roles[role]['status'] == 'active'
            assert roles[role]['legal_candidate_count'] == 1
        assert roles['parallelism']['status'] == 'inactive'
        assert roles['parallelism']['legal_candidate_count'] == 0
        assert 'Single-GPU' in roles['parallelism']['reason']
        assert 'tensor_parallel_size' in roles['parallelism']['reason']
        assert all(check['role'] != 'parallelism' for check in first['specialists'])
        assert all(evidence.get('specialist_role') != 'parallelism' for _, evidence in seen)


def test_batching_only_space_does_not_claim_quantization_participated(tmp_path, monkeypatch):
    _, seen, agent = install_fakes(monkeypatch)
    space = sera.InvestigationSpace(supported_changes={'max_num_batched_tokens': [2048, 1024]})
    with run(tmp_path, agent, investigation_space=space) as result:
        first = result.report['search']['rounds'][0]
        roles = participation(first)
        assert roles['batching']['status'] == 'active'
        assert roles['batching']['legal_candidate_count'] == 2
        assert roles['quantization']['status'] == 'inactive'
        assert 'No control values' in roles['quantization']['reason']
        assert [check['role'] for check in first['specialists']] == ['batching']
        assert all(evidence['specialist_role'] == 'batching'
                   for role, evidence in seen if role == 'proposal')


def test_exhausted_specialist_is_inactive_and_history_keeps_prior_participation(tmp_path, monkeypatch):
    _, seen, agent = install_fakes(monkeypatch)
    with run(tmp_path, agent) as result:
        first, second = result.report['search']['rounds']
        roles = participation(second)
        assert roles['quantization']['status'] == 'inactive'
        assert 'No legal untested candidate' in roles['quantization']['reason']
        assert roles['quantization']['legal_candidate_count'] == 0
        assert roles['batching']['status'] == 'active'
        assert [check['role'] for check in second['specialists']] == ['batching']
        later = next(evidence for role, evidence in seen
                     if role == 'proposal' and evidence['remaining_trials'] == 1)
        assert later['previous_rounds'][0]['specialist_participation'] == first['specialist_participation']


def test_active_specialist_can_abstain_without_becoming_inactive(tmp_path, monkeypatch):
    _, _, agent = install_fakes(monkeypatch, abstain=True)
    with run(tmp_path, agent) as result:
        first = result.report['search']['rounds'][0]
        roles = participation(first)
        assert roles['quantization']['status'] == roles['batching']['status'] == 'active'
        assert all(check['status'] == 'abstained' for check in first['specialists'])
        assert result.report['search']['stop_reason'] == 'specialists-abstained'
        assert result.report['search']['trials_used'] == 0


def test_failed_active_request_is_rejected_not_inactive(tmp_path, monkeypatch):
    _, _, agent = install_fakes(monkeypatch)
    agent.request = lambda *args: None
    with run(tmp_path, agent) as result:
        first = result.report['search']['rounds'][0]
        roles = participation(first)
        assert roles['quantization']['status'] == roles['batching']['status'] == 'active'
        assert all(check['status'] == 'rejected' for check in first['specialists'])
        assert result.report['search']['stop_reason'] == 'no-valid-selected-proposal'
        assert result.report['search']['trials_used'] == 0
