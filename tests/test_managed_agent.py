"""Managed W&B transport preserves Sera's local proposal gates."""

import json

from test_provider_check import valid_response

from sera.agent import request_schema
from sera.managed_agent import ManagedWandbAgent
from sera.provider_check import provider_cases


def test_managed_wire_schema_avoids_incompatible_root_union_and_retains_local_rules(monkeypatch):
    current=ManagedWandbAgent(project='test/project')
    case=provider_cases()[0]
    wire=current.wire_schema(case['role'],case['evidence'])
    expected=request_schema(case['role'],case['evidence'])
    expected.pop('anyOf')
    assert wire == expected
    invalid=valid_response(case) | {'expected_trial_cost': 0}
    monkeypatch.setattr(current,'_complete',lambda payload: {'choices':[{
        'finish_reason':'stop','message':{'content':json.dumps(invalid)}}]})
    assert current.request(case['role'],case['evidence'],'Test') is None
    assert all(not a['schema_valid'] for a in current.history[0]['attempts'])


def test_managed_forks_keep_transport_identity_and_separate_history():
    current=ManagedWandbAgent(project='test/project')
    child=current.fork()
    assert type(child) is ManagedWandbAgent
    assert child.endpoint_fingerprint == current.endpoint_fingerprint
    assert child.history is not current.history
