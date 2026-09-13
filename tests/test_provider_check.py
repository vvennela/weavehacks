"""The provider certificate must cover the expanded controls and actual evidence."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from sera.agent import AGENT_MODEL, schema_hash
from sera.config import MODEL_ID
from sera.provider_check import provider_cases, require_provider_check
from sera.storage import content_hash


def valid_response(case):
    evidence = case['evidence']
    if case['role'] == 'proposal':
        active = evidence['supported_changes'] and evidence['remaining_trials'] > 0
        lever, values = next(iter(evidence['supported_changes'].items())) if active else (None, [None])
        return dict(action='trial' if active else 'keep-baseline', proposal_id='p1',
                    agent_role='quantization' if lever == 'kv_cache_dtype' else 'batching',
                    parent_trial_id=evidence['trial_id'], model_id=MODEL_ID,
                    changed_lever=lever, proposed_value=values[0], evidence_used=['p95_latency_ms'],
                    predicted_metric_change='Lower latency', confidence=0.5,
                    expected_trial_cost=1 if active else 0,
                    falsification_condition='Latency does not improve', reason='Format fixture')
    if case['role'] == 'arbiter':
        return dict(ranked_proposal_ids=evidence['legal_proposal_ids'][:1], reason='Eligible')
    return dict(selected_trial_id=evidence['deterministic_selection'],
                prediction_outcome='confirmed' if evidence['candidate_quality_pass'] else
                    ('refuted' if evidence['candidate_tested'] else 'not-tested'), reason='Measured gate')


def certificate():
    cases = provider_cases()
    return dict(schema_version='sera-provider-check-v1', model=AGENT_MODEL, project='test/project',
                schema_hash=schema_hash(), cases_hash=content_hash(cases), requests=[
                    dict(role=case['role'], evidence=deepcopy(case['evidence']), attempts=[
                        dict(raw_response={'choices': [{'finish_reason': 'stop',
                              'message': {'content': json.dumps(valid_response(case))}}]})])
                    for case in cases])


def verify(tmp_path, record):
    path = tmp_path / 'result.json'
    path.write_text(json.dumps(record))
    return require_provider_check(path, SimpleNamespace(model=AGENT_MODEL, project='test/project'))


def test_thirty_cases_cover_each_control_and_nondefault_parent():
    cases = provider_cases()
    assert len(cases) == 30
    assert {role: sum(case['role'] == role for case in cases)
            for role in ('proposal', 'arbiter', 'frontier')} == dict(proposal=10, arbiter=10, frontier=10)
    proposals = [case['evidence'] for case in cases if case['role'] == 'proposal']
    assert any(e['supported_changes'] == {'max_num_seqs': [4]} for e in proposals)
    assert any(e['supported_changes'] == {'max_model_len': [2048]} for e in proposals)
    assert any(e.get('configuration', {}).get('max_num_batched_tokens') == 2048
               and e['supported_changes'] == {'max_num_batched_tokens': [4096]} for e in proposals)


def test_current_certificate_passes_and_stale_schema_fails(tmp_path):
    record = certificate()
    assert verify(tmp_path, record)['valid_with_one_retry'] == 30
    record['schema_hash'] = 'old-schema'
    with pytest.raises(ValueError, match='schemas'):
        verify(tmp_path, record)


def test_schema_valid_but_out_of_scope_response_does_not_certify_provider(tmp_path):
    record = certificate()
    entry = record['requests'][0]
    message = entry['attempts'][0]['raw_response']['choices'][0]['message']
    response = json.loads(message['content'])
    response['parent_trial_id'] = 'invented-parent'
    message['content'] = json.dumps(response)
    with pytest.raises(ValueError, match='context'):
        verify(tmp_path, record)
