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
    assert len(branches) == 3
    assert branches[0]["properties"]["expected_trial_cost"] == {"const": 0}
    assert all(branch["properties"]["expected_trial_cost"] == {"const": 1} for branch in branches[1:])
    assert ArbiterDecision.model_json_schema()["properties"]["ranked_proposal_ids"]["maxItems"] == 1
