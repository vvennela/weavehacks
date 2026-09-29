"""Native advisors choose only available recipe IDs; local code owns the gate."""

import json

import pytest

from sera.native_agent import NativeRecipeAgent


def evidence():
    return {'available_recipes': [{'recipe_id': 'int8', 'recipe': {'bits': 8, 'group_size': 64}}],
            'trials': [{'trial_id': 'baseline', 'peak_bytes': 1000}], 'remaining_trials': 1}


def response(recipe):
    return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
        'recipe_id': recipe, 'reason': 'Measured baseline uses 1000 bytes.',
        'prediction': 'Smaller weights may lower allocation; quality must still pass.'})}}]}


def test_native_agent_does_not_accept_unlisted_recipes(monkeypatch):
    agent = NativeRecipeAgent(project='test/project')
    monkeypatch.setattr(agent, '_complete', lambda payload: response('arbitrary-command'))
    assert agent.propose(evidence(), timeout_seconds=5) is None
    assert len(agent.history[0]['attempts']) == 2
    assert all(not item['schema_valid'] for item in agent.history[0]['attempts'])


def test_dynamic_schema_and_local_validation_agree(monkeypatch):
    agent = NativeRecipeAgent(project='test/project')
    def complete(payload):
        schema = payload['response_format']['json_schema']['schema']
        assert schema['properties']['recipe_id']['enum'] == ['int8', 'stop']
        return response('int8')
    monkeypatch.setattr(agent, '_complete', complete)
    proposal = agent.propose(evidence(), timeout_seconds=5)
    assert proposal.recipe_id == 'int8'
    assert agent.history[0]['attempts'][0]['schema_valid']


def test_expired_agent_budget_does_not_contact_provider(monkeypatch):
    agent = NativeRecipeAgent(project='test/project')
    monkeypatch.setattr(agent, '_complete', lambda payload: pytest.fail('Budget expired'))
    with pytest.raises(ValueError):
        agent.propose(evidence(), timeout_seconds=0)
