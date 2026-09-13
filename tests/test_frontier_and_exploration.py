"""The Pareto frontier and the exploration slot.

Both exist for the same reason: a ranking that only ever follows its own best guess
stops learning. The frontier keeps configurations that lost on one axis but won on
another; exploration spends a slot on the lever the ranking would never reach.
"""

from __future__ import annotations

from sera_loop.arbiter import EXPLORATION_MIN_BUDGET, Arbiter
from sera_loop.config import InferenceConfig
from sera_loop.ledger import Ledger, Measurement, Prediction, Substrate, TrialRecord, Verdict
from sera_loop.specialists.base import Proposal


def _row(tid, p95, fp, tput, verdict=Verdict.ACCEPTED, model="m", phase=1):
    return TrialRecord(
        trial_id=tid, phase=phase, round=1, models=[model], config={"model": model},
        verdict=verdict, substrate=Substrate.SIM,
        measurement=Measurement(
            p50_latency_ms=p95 / 3, p95_latency_ms=p95,
            throughput_rps=tput, footprint_gb=fp,
        ),
    )


# ---- Pareto frontier ------------------------------------------------------


def test_dominated_config_is_excluded(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append(_row("good", p95=100, fp=2.0, tput=10.0))
    led.append(_row("worse-on-everything", p95=200, fp=4.0, tput=5.0))
    assert [r.trial_id for r in led.pareto_frontier("m")] == ["good"]


def test_tradeoff_configs_both_survive(tmp_path):
    """Slower but smaller is a real choice, not a loser. A single-axis sort loses it."""
    led = Ledger(tmp_path / "l.jsonl")
    led.append(_row("fast-big", p95=100, fp=8.0, tput=10.0))
    led.append(_row("slow-small", p95=900, fp=1.0, tput=10.0))
    ids = {r.trial_id for r in led.pareto_frontier("m")}
    assert ids == {"fast-big", "slow-small"}


def test_throughput_alone_can_keep_a_config_on_the_frontier(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append(_row("low-latency", p95=100, fp=2.0, tput=5.0))
    led.append(_row("high-throughput", p95=120, fp=2.0, tput=40.0))
    assert len(led.pareto_frontier("m")) == 2


def test_identical_measurements_do_not_dominate_each_other(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append(_row("a", p95=100, fp=2.0, tput=10.0))
    led.append(_row("b", p95=100, fp=2.0, tput=10.0))
    assert len(led.pareto_frontier("m")) == 2


def test_frontier_excludes_reverts_and_phase_2(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append(_row("ok", 100, 2.0, 10.0))
    led.append(_row("slo", 50, 1.0, 20.0, verdict=Verdict.REVERTED_SLO))
    led.append(_row("qual", 40, 0.5, 30.0, verdict=Verdict.REVERTED_QUALITY))
    led.append(_row("joint", 10, 0.1, 99.0, phase=2))
    assert [r.trial_id for r in led.pareto_frontier("m")] == ["ok"]


def test_recommend_minimises_p95(tmp_path):
    """Phase 1's recommendation is the fastest configuration on the frontier.

    Note this makes the latency budget redundant in the success case: minimising p95
    already satisfies any budget that is satisfiable at all. The budget matters only
    as the fallback below. Choosing the SMALLEST config that meets a requirement is a
    different question, and it is Phase 2's, not this one's.
    """
    led = Ledger(tmp_path / "l.jsonl")
    led.append(_row("tiny-slow", p95=900, fp=0.5, tput=10.0))
    led.append(_row("mid", p95=300, fp=2.0, tput=10.0))
    led.append(_row("fast-huge", p95=100, fp=40.0, tput=10.0))
    assert led.recommend("m").trial_id == "fast-huge"
    assert led.recommend("m", p95_budget_ms=500).trial_id == "fast-huge"


def test_recommend_falls_back_when_nothing_meets_the_budget(tmp_path):
    """An impossible latency budget should surface the best available, not nothing."""
    led = Ledger(tmp_path / "l.jsonl")
    led.append(_row("slow", p95=900, fp=0.5, tput=10.0))
    led.append(_row("less-slow", p95=600, fp=2.0, tput=10.0))
    assert led.recommend("m", p95_budget_ms=10).trial_id == "less-slow"


def test_recommend_breaks_p95_ties_on_memory(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append(_row("big", p95=100, fp=40.0, tput=12.0))
    led.append(_row("small", p95=100, fp=2.0, tput=10.0))
    assert led.recommend("m").trial_id == "small"


def test_recommend_returns_none_without_a_viable_config(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append(_row("bad", 100, 2.0, 10.0, verdict=Verdict.REVERTED_SLO))
    assert led.recommend("m") is None


# ---- exploration slot -----------------------------------------------------


def _prop(name, delta, conf):
    return Proposal(
        specialist=name, lever=name, delta=delta,
        prediction=Prediction("p95_latency_ms", "decrease", 30.0, conf),
        rationale="test",
    )


def _three():
    return [
        _prop("quantization", {"weight_dtype": "fp8"}, 0.95),
        _prop("batching", {"max_num_seqs": 512}, 0.90),
        _prop("parallelism", {"tensor_parallel_size": 2}, 0.10),
    ]


def test_exploration_promotes_an_untried_lever_when_budget_allows(tmp_path):
    arb = Arbiter(Ledger(tmp_path / "l.jsonl"), slots=2)
    res = arb.arbitrate(_three(), InferenceConfig(model="m"),
                        remaining_budget=EXPLORATION_MIN_BUDGET)
    levers = {p.lever for p in res.selected}
    assert "parallelism" in levers, "the weakest unexplored lever should take a slot"
    assert any(p.exploration for p in res.selected)
    assert any("exploration slot" in n for n in res.notes)


def test_no_exploration_when_budget_is_nearly_spent(tmp_path):
    arb = Arbiter(Ledger(tmp_path / "l.jsonl"), slots=2)
    res = arb.arbitrate(_three(), InferenceConfig(model="m"),
                        remaining_budget=EXPLORATION_MIN_BUDGET - 1)
    assert [p.specialist for p in res.selected] == ["quantization", "batching"]
    assert not any(p.exploration for p in res.selected)


def test_no_exploration_when_budget_is_not_supplied(tmp_path):
    """Callers that do not track budget keep the old pure-ranking behaviour."""
    arb = Arbiter(Ledger(tmp_path / "l.jsonl"), slots=2)
    res = arb.arbitrate(_three(), InferenceConfig(model="m"))
    assert not any(p.exploration for p in res.selected)


def test_exploration_never_duplicates_a_lever_already_selected(tmp_path):
    arb = Arbiter(Ledger(tmp_path / "l.jsonl"), slots=2)
    props = [
        _prop("quantization", {"weight_dtype": "fp8"}, 0.95),
        _prop("quantization", {"kv_cache_dtype": "fp8"}, 0.90),
        _prop("batching", {"max_num_seqs": 512}, 0.50),
    ]
    res = arb.arbitrate(props, InferenceConfig(model="m"), remaining_budget=8)
    assert {p.lever for p in res.selected} == {"quantization", "batching"}


def test_exploration_keeps_the_slot_count(tmp_path):
    arb = Arbiter(Ledger(tmp_path / "l.jsonl"), slots=2)
    res = arb.arbitrate(_three(), InferenceConfig(model="m"), remaining_budget=8)
    assert len(res.selected) == 2
    assert len(res.selected) + len(res.declined) == 3
