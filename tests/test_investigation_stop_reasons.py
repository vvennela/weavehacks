"""Distinguish valid decisions not to run from rejected agent output."""

import json

import pytest

from sera.agent import ArbiterDecision
from test_investigation import install_fakes, run


def test_valid_empty_arbiter_ranking_reports_decline_without_trial(tmp_path, monkeypatch):
    runners, seen, agent = install_fakes(monkeypatch)
    request = agent.request

    def decline(role, evidence, instruction):
        response = request(role, evidence, instruction)
        if role == 'arbiter':
            return ArbiterDecision(ranked_proposal_ids=[], reason='No useful next experiment')
        return response

    agent.request = decline
    with run(tmp_path, agent) as result:
        assert result.report['search']['stop_reason'] == 'arbiter-declined'
        assert result.report['search']['trials_used'] == 0
        assert result.report['decision']['selected'] == 'baseline'
        assert len(runners) == 1 and runners[0].ready
        assert result.rejected == []
        assert any(role == 'arbiter' for role, _ in seen)
        saved = json.loads((tmp_path/'run'/'result.json').read_text())
        assert saved['decision']['reason'] == 'arbiter-declined'


def test_all_valid_specialist_abstentions_report_abstention(tmp_path, monkeypatch):
    runners, seen, agent = install_fakes(monkeypatch, abstain=True)
    with run(tmp_path, agent) as result:
        assert result.report['search']['stop_reason'] == 'specialists-abstained'
        assert result.report['search']['trials_used'] == 0
        assert result.report['decision']['selected'] == 'baseline'
        assert len(runners) == 1 and runners[0].ready
        assert result.rejected == []
        assert all(role != 'arbiter' for role, _ in seen)


@pytest.mark.parametrize('failure', ['missing-specialist', 'invalid-specialist',
                                    'missing-arbiter', 'invalid-empty-arbiter', 'unknown-ranking'])
def test_invalid_or_missing_response_keeps_failure_reason_and_budget(tmp_path, monkeypatch, failure):
    runners, _, agent = install_fakes(monkeypatch)
    request = agent.request

    def invalid(role, evidence, instruction):
        response = request(role, evidence, instruction)
        if role == 'proposal':
            if failure == 'missing-specialist':
                return None
            if failure == 'invalid-specialist':
                return response.model_copy(update={'parent_trial_id': 'unknown'})
        if role == 'arbiter':
            if failure == 'missing-arbiter':
                return None
            if failure == 'invalid-empty-arbiter':
                return response.model_copy(update={'ranked_proposal_ids': [], 'reason': ''})
            if failure == 'unknown-ranking':
                return response.model_copy(update={'ranked_proposal_ids': ['unknown']})
        return response

    agent.request = invalid
    with run(tmp_path, agent) as result:
        assert result.report['search']['stop_reason'] == 'no-valid-selected-proposal'
        assert result.report['search']['trials_used'] == 0
        assert result.report['decision']['selected'] == 'baseline'
        assert len(runners) == 1 and runners[0].ready
        assert result.rejected


def test_abstention_mixed_with_missing_response_is_not_all_abstention(tmp_path, monkeypatch):
    runners, _, agent = install_fakes(monkeypatch, abstain=True)
    request = agent.request

    def missing_batching(role, evidence, instruction):
        response = request(role, evidence, instruction)
        if role == 'proposal' and evidence['specialist_role'] == 'batching':
            return None
        return response

    agent.request = missing_batching
    with run(tmp_path, agent) as result:
        assert result.report['search']['stop_reason'] == 'no-valid-selected-proposal'
        assert result.report['search']['trials_used'] == 0
        assert len(runners) == 1
        assert len(result.rejected) == 1


def test_second_round_decline_preserves_measured_failure_and_unused_budget(tmp_path, monkeypatch):
    runners, seen, agent = install_fakes(monkeypatch)
    request = agent.request

    def decline_after_failure(role, evidence, instruction):
        response = request(role, evidence, instruction)
        if role == 'arbiter' and evidence['history']:
            assert evidence['history'][0]['trial']['task_quality']['passed'] is False
            return ArbiterDecision(ranked_proposal_ids=[], reason='Stop after measured quality failure')
        return response

    agent.request = decline_after_failure
    with run(tmp_path, agent) as result:
        assert result.report['search']['stop_reason'] == 'arbiter-declined'
        assert result.report['search']['trials_used'] == 1
        assert len(result.report['search']['rounds']) == 2
        assert len(result.trials) == 2
        assert result.trials[1]['review']['prediction_outcome'] == 'refuted'
        assert result.report['decision']['selected'] == 'baseline'
        assert sum(model.ready for model in runners) == 1
        assert sum(role == 'arbiter' for role, _ in seen) == 2
