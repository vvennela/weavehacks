"""Candidate eligibility and selection under explicit user priorities."""

import pytest
from pydantic import ValidationError

from sera import Constraints, Objective
from sera.measurement import measured_frontier, select_candidate


def trial(trial_id, *, latency=100.0, throughput=100.0, memory=1000, token=7):
    output = {"prompt_index": 0, "text": "answer", "token_ids": [token],
              "prompt_token_ids": [1], "error": None}
    return {"trial_id": trial_id, "status": "collected", "input_token_ids": [[1]],
            "quality": [output], "self_check": [output],
            "runtime": {"sampled_peak_memory_mib": memory, "telemetry_errors": 0},
            "reduced": {"p95_latency_ms": latency, "output_tokens_per_second": throughput}}


@pytest.mark.parametrize("values", [
    {"priority": "cost"}, {"priority": "fast"}, {"min_improvement_fraction": -0.1},
    {"min_improvement_fraction": 1.0}, {"min_improvement_fraction": float("nan")},
    {"min_improvement_fraction": "0.05"}, {"unknown": True},
])
def test_objective_rejects_unsupported_or_invalid_requirements(values):
    with pytest.raises(ValidationError):
        Objective(**values)


def test_same_measured_candidates_produce_different_recommendations_by_priority():
    baseline = trial("baseline")
    candidate = trial("candidate", latency=110.0, throughput=120.0, memory=800)
    assert select_candidate(baseline, candidate)["selected"] == "baseline"
    for priority in ("throughput", "memory"):
        decision = select_candidate(baseline, candidate, objective=Objective(priority=priority))
        assert decision["selected"] == "candidate"
        assert decision["objective_improvement_fraction"] == pytest.approx(.2)
    assert {t["trial_id"] for t in measured_frontier(baseline, candidate)} == {"baseline", "candidate"}


def test_quality_failure_cannot_be_traded_for_throughput():
    baseline = trial("baseline")
    candidate = trial("candidate", throughput=200.0, token=8)
    decision = select_candidate(baseline, candidate, objective=Objective(priority="throughput"))
    assert decision["reason"] == "candidate-quality-failed"
    assert measured_frontier(baseline, candidate) == [baseline]


@pytest.mark.parametrize("memory", [None, float("nan"), -1])
def test_missing_or_invalid_objective_metric_does_not_approve_candidate(memory):
    decision = select_candidate(trial("baseline"), trial("candidate", memory=memory),
                                objective=Objective(priority="memory"))
    assert decision["selected"] == "baseline"
    assert decision["reason"] == "objective-metric-unavailable"


@pytest.mark.parametrize('telemetry', [{}, {'telemetry_errors': None},
    {'telemetry_errors': 1}, {'telemetry_errors': -1}, {'telemetry_errors': False},
    {'telemetry_errors': 0.0}, {'telemetry_errors': '0'}])
def test_unverified_memory_cannot_approve_a_smaller_or_faster_candidate(telemetry):
    baseline = trial('baseline')
    candidate = trial('candidate', memory=500, latency=50.0)
    candidate['runtime'] = {'sampled_peak_memory_mib': 500, **telemetry}

    decision = select_candidate(baseline, candidate, objective=Objective(priority='memory'))
    assert decision['selected'] == 'baseline'
    assert decision['reason'] == 'objective-metric-unavailable'
    assert decision['objective_improvement_fraction'] is None

    for record in (baseline, candidate):
        record['task_quality'] = {'valid_outputs': True, 'mean': 1.0}
    constraints = Constraints(quality_floor=1.0, max_memory_mib=1100)
    decision = select_candidate(baseline, candidate, constraints=constraints)
    assert decision['selected'] == 'baseline'
    assert 'memory-requirement-failed' in decision['constraint_failures']['candidate']
    assert measured_frontier(baseline, candidate, constraints=constraints) == [baseline]


def test_memory_sampling_failure_does_not_invalidate_unconstrained_latency_measurement():
    baseline, candidate = trial('baseline'), trial('candidate', latency=50.0)
    candidate['runtime']['telemetry_errors'] = 1
    assert select_candidate(baseline, candidate)['selected'] == 'candidate'


def test_frontier_excludes_dominated_candidates_but_keeps_incomplete_evidence():
    baseline = trial("baseline")
    assert measured_frontier(baseline, trial("candidate", latency=110.0)) == [baseline]
    incomplete = trial("candidate", memory=None)
    assert len(measured_frontier(baseline, incomplete)) == 2


def test_invalid_reference_is_not_a_viable_frontier_entry():
    baseline = trial("baseline")
    baseline["self_check"][0] = dict(baseline["self_check"][0], token_ids=[99])
    assert measured_frontier(baseline, trial("candidate")) == []


def test_declared_threshold_is_applied_and_reported():
    objective = Objective(priority="throughput", min_improvement_fraction=.1)
    decision = select_candidate(trial("baseline"), trial("candidate", throughput=105.0),
                                objective=objective)
    assert decision["selected"] == "baseline"
    assert decision["objective"] == objective.model_dump()
