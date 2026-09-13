"""Opt-in integration preserves the fixed gates, owner, and total trial budget."""

from copy import deepcopy

import pytest

import sera
from sera import pipeline
from sera.agent import ArbiterDecision
from sera.config import MODEL_ID
from test_investigation import install_fakes, run
from test_fit_investigation import boundaries, run as run_fit


def forkable(agent):
    base_request = agent.request

    def request(role, evidence, instruction):
        if evidence.get('swarm_phase') == 'inspect':
            agent.history.append(dict(role=role, evidence=deepcopy(evidence)))
            return ArbiterDecision(ranked_proposal_ids=evidence['legal_proposal_ids'][:1], reason='Read')
        supplied = deepcopy(evidence)
        if role == 'proposal':
            from sera.config import CONTROL_ROLES
            supplied['specialist_role'] = CONTROL_ROLES[next(iter(supplied['supported_changes']))]
        return base_request(role, supplied, instruction)

    agent.request = request
    agent.fork = lambda: forkable(type(agent)())
    return agent


@pytest.mark.parametrize('overrides', [dict(swarm=1), dict(swarm=True),
    dict(swarm=True, agent=object(), budget=sera.Budget()),
    dict(trace_reader=lambda *_: {})])
def test_invalid_swarm_options_fail_before_directory_or_runner(tmp_path, monkeypatch, overrides):
    monkeypatch.setattr(pipeline, 'SeraModel', lambda **kwargs: pytest.fail('Must not start'))
    with pytest.raises(ValueError):
        sera.optimize(models=[MODEL_ID], prompts=['question'], output_dir=tmp_path/'run', **overrides)
    assert not (tmp_path/'run').exists()


def test_swarm_keeps_rejected_quality_and_next_round_history_and_unique_trials(tmp_path, monkeypatch):
    runners, seen, agent = install_fakes(monkeypatch)
    reads = []
    def reader(query_id, supplied):
        reads.append(deepcopy(supplied))
        return {'source': 'fixture persisted trace', 'query_id': query_id}
    with run(tmp_path, forkable(agent), swarm=True, trace_reader=reader) as result:
        assert result.report['swarm_enabled'] is True
        assert result.report['search']['trials_used'] == 2
        assert len(result.report['search']['rounds']) == 2
        assert all(len(item['trial_ids']) == 1 for item in result.report['search']['rounds'])
        assert len({trial['config_hash'] for trial in result.trials}) == 3
        assert result.trials[1]['task_quality']['passed'] is False
        assert result.report['decision']['selected'] == 'trial-2'
        assert result.trials[1]['investigator_id'] == 'scheduling'
        assert result.trials[1]['arbiter_proposal_id'].startswith('scheduling:')
        later = [e for e in reads if e['remaining_trials'] == 1][0]
        assert later['history'][0]['trial']['task_quality']['passed'] is False
        assert later['previous_rounds'][0]['shared_findings']
        assert [scope['trial_id'] for scope in later['trace_scope']] == ['baseline', 'trial-1']
        assert later['trace_scope'][1]['task_quality']['per_prompt'][0]['score'] == 0
        assert 'trace_reader' not in result.report
    assert not any(runner.ready for runner in runners)


@pytest.mark.parametrize('budget', [1, 2])
def test_fit_swarm_preserves_deployment_source_and_total_budget(tmp_path, monkeypatch, budget):
    runners, calls, agent = boundaries(monkeypatch)
    reads = []
    def reader(query_id, supplied):
        reads.append(deepcopy(supplied))
        return {'query_id': query_id}
    with run_fit(tmp_path, forkable(agent), budget=budget, swarm=True, trace_reader=reader) as result:
        assert result.report['swarm_enabled'] is True
        assert result.report['search']['trials_used'] == budget
        assert result.report['baseline']['source_trial_id'] == 'candidate'
        assert result.report['deployment']['candidate_trial']['trial_id'] == 'candidate'
        if budget == 1:
            assert len(runners) == 1 and reads == []
        else:
            scope = reads[0]['trace_scope'][0]
            assert scope['trial_id'] == 'candidate'
            assert scope['config_hash'] == result.report['baseline']['config_hash']
            assert scope['task_quality']['passed'] is True
            assert result.report['search']['initial_trials_used'] == 1
