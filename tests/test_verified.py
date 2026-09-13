import pytest
from pydantic import ValidationError

from sera import Constraints, optimize
from sera.measurement import measured_frontier, select_candidate
from sera.quality import evaluate_quality


def trial(trial_id, text="correct", latency=100.0):
    output = {"prompt_index": 0, "text": text, "token_ids": [len(text)],
              "prompt_token_ids": [1], "error": None}
    return {"trial_id": trial_id, "status": "collected", "input_token_ids": [[1]],
            "quality": [output], "self_check": [output],
            "runtime": {"sampled_peak_memory_mib": 1000},
            "reduced": {"p95_latency_ms": latency, "output_tokens_per_second": 100.0}}


def evaluated(record, constraints, evaluator=lambda prompt, text: text in {"correct", "also correct"}):
    record["task_quality"] = evaluate_quality(record, ["question"], evaluator,
                                               version="test-v1", floor=constraints.quality_floor)
    return record


@pytest.mark.parametrize("values", [{}, {"quality_floor": -1}, {"quality_floor": 1.1},
    {"quality_floor": float("nan")}, {"quality_floor": "0.9"},
    {"quality_floor": 1.0, "p95_latency_ms": 0},
    {"quality_floor": 1.0, "max_memory_mib": -1}])
def test_invalid_constraints_rejected(values):
    with pytest.raises(ValidationError):
        Constraints(**values)


def test_verified_gate_can_accept_correct_different_tokens():
    constraints = Constraints(quality_floor=1.0, p95_latency_ms=150.0)
    baseline = evaluated(trial("baseline"), constraints)
    candidate = evaluated(trial("candidate", "also correct", 90.0), constraints)
    decision = select_candidate(baseline, candidate, constraints=constraints)
    assert decision["selected"] == "candidate"
    assert decision["candidate_quality"]["version"] == "test-v1"


def test_failed_baseline_is_not_returned_when_candidate_also_fails():
    constraints = Constraints(quality_floor=1.0)
    baseline = evaluated(trial("baseline", "wrong"), constraints)
    candidate = evaluated(trial("candidate", "wrong", 50.0), constraints)
    decision = select_candidate(baseline, candidate, constraints=constraints)
    assert decision["selected"] is None
    assert decision["outcome"] == "no-safe-configuration"
    assert measured_frontier(baseline, candidate, constraints=constraints) == []


def test_feasible_candidate_can_replace_faster_but_wrong_baseline():
    constraints = Constraints(quality_floor=1.0)
    baseline = evaluated(trial("baseline", "wrong"), constraints)
    candidate = evaluated(trial("candidate", "correct", 150.0), constraints)
    decision = select_candidate(baseline, candidate, constraints=constraints)
    assert decision["selected"] == "candidate"
    assert decision["reason"] == "candidate-meets-constraints-baseline-does-not"
    assert measured_frontier(baseline, candidate, constraints=constraints) == [candidate]


def test_latency_and_memory_are_hard_limits_even_for_correct_answers():
    constraints = Constraints(quality_floor=1.0, p95_latency_ms=105.0, max_memory_mib=1100)
    baseline = evaluated(trial("baseline"), constraints)
    for candidate in [trial("candidate", latency=110.0), trial("candidate", latency=50.0)]:
        if candidate["reduced"]["p95_latency_ms"] == 50.0:
            candidate["runtime"]["sampled_peak_memory_mib"] = 1200
        evaluated(candidate, constraints)
        decision = select_candidate(baseline, candidate, constraints=constraints)
        assert decision["selected"] == "baseline"
        assert measured_frontier(baseline, candidate, constraints=constraints) == [baseline]


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -1, 2, "1", None])
def test_invalid_evaluator_results_fail_closed(score):
    gate = evaluate_quality(trial("baseline"), ["question"], lambda p, t: score, version="test-v1", floor=0.0)
    assert not gate["passed"]
    assert not gate["valid_outputs"]


def test_evaluator_exception_is_saved_as_failure():
    def broken(prompt, text):
        raise RuntimeError("fixture exception")
    gate = evaluate_quality(trial("baseline"), ["question"], broken, version="test-v1", floor=0.0)
    assert not gate["passed"]
    assert gate["per_prompt"][0]["error"] == "evaluator-RuntimeError"


def test_missing_or_empty_output_cannot_pass_even_with_zero_floor():
    for outputs in [[], [dict(trial("baseline")["quality"][0], text="")]]:
        record = trial("baseline")
        record["quality"] = outputs
        gate = evaluate_quality(record, ["question"], lambda p, t: True, version="test-v1", floor=0.0)
        assert not gate["passed"]


@pytest.mark.parametrize("options", [
    {"constraints": Constraints(quality_floor=1.0)},
    {"evaluation": lambda p, t: True, "evaluation_version": "v1"},
    {"evaluation": lambda p, t: True, "constraints": Constraints(quality_floor=1.0)},
    {"evaluation": lambda p, t: True, "evaluation_version": "v1", "constraints": []},
])
def test_incomplete_verified_contract_is_rejected_before_model_loading(options):
    with pytest.raises(ValueError):
        optimize(models=["Qwen/Qwen3-0.6B"], prompts=["question"], **options)
