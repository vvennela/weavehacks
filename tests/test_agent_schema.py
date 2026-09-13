"""Candidate-schema checks for the recommendation boundary."""

import pytest
from pydantic import ValidationError

from sera.agent import Proposal, ArbiterDecision, FrontierDecision, validate_proposal
from sera.config import MODEL_ID


def proposal_data():
    return dict(action="trial", proposal_id="p1", agent_role="quantization",
                parent_trial_id="baseline", model_id=MODEL_ID,
                changed_lever="kv_cache_dtype", proposed_value="fp8",
                evidence_used=["p95_latency_ms"], predicted_metric_change="Lower p95 latency",
                confidence=0.5, expected_trial_cost=1,
                falsification_condition="Quality fails or p95 does not improve by 5%",
                reason="Test the supported cache change against measured p95")


def test_proposal_becomes_one_validated_candidate():
    proposal = Proposal(**proposal_data())
    candidate = validate_proposal(proposal, {
        "trial_id": "baseline", "model_id": MODEL_ID,
        "metrics": {"p95_latency_ms": 100}, "remaining_trials": 1,
        "supported_changes": {"kv_cache_dtype": ["fp8"]},
    })
    assert candidate.config.kv_cache_dtype == "fp8"
    assert candidate.name == "p1"


@pytest.mark.parametrize("change", [
    {"proposed_value": "int4"}, {"changed_lever": "dtype"},
    {"confidence": 1.1}, {"expected_trial_cost": True},
    {"action": "keep-baseline"}, {"agent_role": "batching"},
    {"reason": " "}, {"approval": True},
])
def test_invalid_proposals_fail_closed(change):
    with pytest.raises(ValidationError):
        Proposal(**(proposal_data() | change))


@pytest.mark.parametrize("change", [
    {"remaining_trials": 0}, {"supported_changes": {}},
    {"trial_id": "another-baseline"}, {"metrics": {"p95_latency_ms": None}},
])
def test_proposal_must_reference_available_evidence_and_budget(change):
    evidence = dict(trial_id="baseline", model_id=MODEL_ID, metrics={"p95_latency_ms": 100},
                    remaining_trials=1, supported_changes={"kv_cache_dtype": ["fp8"]})
    with pytest.raises(ValueError):
        validate_proposal(Proposal(**proposal_data()), evidence | change)


def test_keep_baseline_needs_no_candidate_or_gpu_budget():
    data = proposal_data() | dict(action="keep-baseline", changed_lever=None,
                                 proposed_value=None, expected_trial_cost=0)
    evidence = dict(trial_id="baseline", model_id=MODEL_ID, metrics={"p95_latency_ms": 100},
                    remaining_trials=0, supported_changes={})
    assert validate_proposal(Proposal(**data), evidence) is None


def test_rankings_cannot_repeat_proposals():
    with pytest.raises(ValidationError):
        ArbiterDecision(ranked_proposal_ids=["p1", "p1"], reason="Duplicate")


def test_frontier_reader_cannot_add_an_approval_field():
    with pytest.raises(ValidationError):
        FrontierDecision(selected_trial_id="baseline", prediction_outcome="refuted",
                         reason="Quality failed", quality_pass=True)


def test_wire_schema_expresses_action_cost_and_value_constraints():
    schema = Proposal.model_json_schema()
    branches = schema["anyOf"]
    assert len(branches) == 5
    assert branches[0]["properties"]["expected_trial_cost"] == {"const": 0}
    assert all(branch["properties"]["expected_trial_cost"] == {"const": 1} for branch in branches[1:])
    assert ArbiterDecision.model_json_schema()["properties"]["ranked_proposal_ids"]["maxItems"] == 1


@pytest.mark.parametrize('lever,value', [
    ('max_num_batched_tokens', 1), ('max_num_batched_tokens', 65536),
    ('max_num_seqs', 1), ('max_num_seqs', 256),
    ('max_model_len', 65), ('max_model_len', 4096),
])
def test_expanded_controls_have_strict_standalone_bounds(lever, value):
    proposal = Proposal(**(proposal_data() | dict(agent_role='batching', changed_lever=lever,
                                                proposed_value=value)))
    assert proposal.proposed_value == value


@pytest.mark.parametrize('lever,value', [
    ('max_num_batched_tokens', True), ('max_num_batched_tokens', 65537),
    ('max_num_batched_tokens', 0), ('max_num_batched_tokens', 2048.0),
    ('max_num_seqs', 257), ('max_num_seqs', '8'), ('max_num_seqs', False),
    ('max_model_len', 64), ('max_model_len', 4097), ('max_model_len', 'fp8'),
    ('kv_cache_dtype', 2048), ('kv_cache_dtype', 'auto'),
])
def test_expanded_controls_reject_wrong_values_and_types(lever, value):
    role = 'quantization' if lever == 'kv_cache_dtype' else 'batching'
    with pytest.raises(ValidationError):
        Proposal(**(proposal_data() | dict(agent_role=role, changed_lever=lever, proposed_value=value)))


def test_parsing_does_not_assume_default_parent_and_validation_uses_actual_parent():
    from sera.config import RuntimeConfig
    proposal = Proposal(**(proposal_data() | dict(agent_role='batching',
        changed_lever='max_num_batched_tokens', proposed_value=1)))
    evidence = dict(trial_id='baseline', model_id=MODEL_ID, metrics={'p95_latency_ms': 100},
                    remaining_trials=1, supported_changes={'max_num_batched_tokens': [1]},
                    configuration=RuntimeConfig(max_num_seqs=1).model_dump())
    candidate = validate_proposal(proposal, evidence)
    assert candidate.config.max_num_batched_tokens == 1
    with pytest.raises(ValueError):
        validate_proposal(proposal, evidence | {'configuration': RuntimeConfig().model_dump()})


def test_no_op_and_frozen_universe_are_checked_against_actual_parent():
    from sera.config import RuntimeConfig
    proposal = Proposal(**(proposal_data() | dict(agent_role='batching',
        changed_lever='max_num_seqs', proposed_value=8)))
    evidence = dict(trial_id='baseline', model_id=MODEL_ID, metrics={'p95_latency_ms': 100},
                    remaining_trials=1, supported_changes={'max_num_seqs': [8]},
                    configuration=RuntimeConfig(max_num_seqs=4).model_dump())
    candidate = validate_proposal(proposal, evidence)
    assert candidate.config.max_num_seqs == 8
    assert validate_proposal(proposal, evidence | {'frozen_candidate_hashes': [candidate.config.config_hash]}) == candidate
    with pytest.raises(ValueError, match='frozen'):
        validate_proposal(proposal, evidence | {'frozen_candidate_hashes': []})
    with pytest.raises(ValueError, match='one'):
        validate_proposal(proposal, evidence | {'configuration': RuntimeConfig().model_dump()})


def test_expansion_requires_explicit_per_run_scope_and_correct_role():
    proposal = Proposal(**(proposal_data() | dict(agent_role='batching',
        changed_lever='max_model_len', proposed_value=2048)))
    evidence = dict(trial_id='baseline', model_id=MODEL_ID, metrics={'p95_latency_ms': 100},
                    remaining_trials=1, supported_changes={'kv_cache_dtype': ['fp8']})
    with pytest.raises(ValueError, match='active'):
        validate_proposal(proposal, evidence)
    with pytest.raises(ValidationError):
        Proposal(**(proposal_data() | dict(changed_lever='max_model_len', proposed_value=2048)))


def test_wire_schema_matches_each_integer_control_bounds_and_role():
    from pydantic import TypeAdapter
    from sera.config import RuntimeConfig
    branches = Proposal.model_json_schema()['anyOf']
    for lever in ('max_num_batched_tokens', 'max_num_seqs', 'max_model_len'):
        branch = next(branch['properties'] for branch in branches
                      if branch['properties']['changed_lever'].get('const') == lever)
        assert branch['agent_role'] == {'const': 'batching'}
        expected = TypeAdapter(RuntimeConfig.model_fields[lever].rebuild_annotation()).json_schema()
        assert branch['proposed_value'] == expected


def test_request_schema_has_only_exact_non_null_metrics_without_mutating_base():
    from sera.agent import request_schema
    original = Proposal.model_json_schema()
    schema = request_schema('proposal', {'metrics': {'zero': 0, 'missing': None, 'latency': 12}})
    assert schema['properties']['evidence_used']['items'] == {
        'type': 'string', 'enum': ['latency', 'zero']}
    assert Proposal.model_json_schema() == original
    assert 'enum' not in original['properties']['evidence_used']['items']
    assert request_schema('frontier', {}) == FrontierDecision.model_json_schema()


@pytest.mark.parametrize('metrics', [{}, {'missing': None}])
def test_no_metric_fails_closed_before_provider_call(monkeypatch, metrics):
    import sys
    from types import SimpleNamespace
    from sera.agent import WandbAgent

    def unexpected_call(**kwargs):
        pytest.fail('No metric must fail before constructing an API client')

    monkeypatch.setenv('WANDB_API_KEY', 'not-a-real-test-key')
    monkeypatch.setitem(sys.modules, 'openai', SimpleNamespace(OpenAI=unexpected_call))
    agent = WandbAgent(project='test/project')
    with pytest.raises(ValueError, match='available metric'):
        agent.request('proposal', {'metrics': metrics}, 'Propose')
    assert agent.history == []


@pytest.mark.parametrize('citation', ['metrics.p95_latency_ms', 'p95_latency_ms=100', 'missing', ' p95_latency_ms '])
def test_dynamic_response_validation_rejects_unavailable_citations(citation):
    import json
    from sera.agent import parse_response
    evidence = {'metrics': {'p95_latency_ms': 100, 'missing': None}}
    with pytest.raises(ValueError, match='evidence'):
        parse_response('proposal', json.dumps(proposal_data() | {'evidence_used': [citation]}), evidence)


def test_dynamic_validation_does_not_replace_parent_and_specialist_context_validation():
    import json
    from sera.agent import parse_response
    # This is schema-valid data, but the real parent/budget validator must still reject it later.
    parsed = parse_response('proposal', json.dumps(proposal_data()),
                            {'metrics': {'p95_latency_ms': 100}})
    assert parsed == Proposal(**proposal_data())
