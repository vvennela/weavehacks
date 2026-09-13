"""The ledger's two queries are what Phase 2 stands on, so they get tested directly."""

from __future__ import annotations

import pytest

from sera.ledger import Ledger, Measurement, Prediction, Substrate, TrialRecord, Verdict


def _meas(p99: float, footprint: float, tput: float = 10.0) -> Measurement:
    return Measurement(
        p50_latency_ms=p99 / 3, p95_latency_ms=p99, throughput_rps=tput,
        footprint_gb=footprint,
    )


def _row(tid: str, verdict: Verdict, p99: float, fp: float, **kw) -> TrialRecord:
    return TrialRecord(
        trial_id=tid, phase=kw.pop("phase", 1), round=1, models=["m"],
        config={"model": "m"}, verdict=verdict, substrate=Substrate.SIM,
        measurement=_meas(p99, fp) if verdict.ran else None, **kw,
    )


def test_roundtrip_survives_reload(tmp_path):
    path = tmp_path / "l.jsonl"
    led = Ledger(path)
    led.append(_row("a", Verdict.ACCEPTED, 100, 2.0,
                    prediction=Prediction("p95_latency_ms", "decrease", 20.0)))
    reread = Ledger(path)
    assert len(reread.all()) == 1
    row = reread.all()[0]
    assert row.verdict is Verdict.ACCEPTED
    assert row.substrate is Substrate.SIM
    assert row.measurement.p95_latency_ms == 100
    assert row.prediction.direction == "decrease"


def test_frontier_orders_by_footprint_not_speed(tmp_path):
    """The whole point of Phase 2: the smallest config, not the fastest one."""
    led = Ledger(tmp_path / "l.jsonl")
    led.append(_row("fast-big", Verdict.ACCEPTED, p99=100, fp=8.0))
    led.append(_row("slow-small", Verdict.ACCEPTED, p99=900, fp=1.0))
    front = led.frontier("m", objective="footprint_gb")
    assert [r.trial_id for r in front] == ["slow-small", "fast-big"]


def test_frontier_excludes_every_non_viable_row(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append(_row("ok", Verdict.ACCEPTED, 100, 2.0))
    led.append(_row("slo", Verdict.REVERTED_SLO, 50, 1.0))
    led.append(_row("qual", Verdict.REVERTED_QUALITY, 40, 0.5))
    led.append(_row("paper", Verdict.REJECTED_PAPER, 0, 0))
    assert [r.trial_id for r in led.frontier("m")] == ["ok"]


def test_frontier_ignores_phase_2_rows(tmp_path):
    """Phase 2 must re-read Phase 1's evidence, not its own joint results."""
    led = Ledger(tmp_path / "l.jsonl")
    led.append(_row("p1", Verdict.ACCEPTED, 100, 2.0, phase=1))
    led.append(_row("p2", Verdict.ACCEPTED, 100, 0.1, phase=2))
    assert [r.trial_id for r in led.frontier("m")] == ["p1"]


def test_calibration_is_neutral_without_evidence(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    assert led.calibration("nobody") == 0.5


def test_calibration_tracks_prediction_accuracy(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    for i, held in enumerate([True, True, True, False]):
        led.append(_row(f"t{i}", Verdict.ACCEPTED, 100, 2.0,
                        proposing_specialist="quantization", prediction_held=held))
    assert led.calibration("quantization") == 0.75


def test_reverts_are_retained_not_discarded(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    led.append(_row("a", Verdict.ACCEPTED, 100, 2.0))
    led.append(_row("b", Verdict.REVERTED_QUALITY, 50, 1.0))
    led.append(_row("c", Verdict.REVERTED_SLO, 900, 1.0))
    assert len(led.reverts()) == 2
    assert led.summary()["accepted"] == 1


@pytest.mark.parametrize(
    "direction,before,after,expected",
    [
        ("decrease", 100.0, 50.0, True),
        ("decrease", 100.0, 150.0, False),
        ("increase", 100.0, 150.0, True),
        ("decrease", 100.0, 99.5, False),   # inside tolerance: no movement
        ("decrease", 0.0, 50.0, False),     # undefined baseline
    ],
)
def test_prediction_held_is_computed_not_asserted(direction, before, after, expected):
    assert Prediction("p95_latency_ms", direction).held(before, after) is expected


def test_paper_rejection_costs_no_trial(tmp_path):
    assert Verdict.REJECTED_PAPER.ran is False
    assert Verdict.REVERTED_SLO.ran is True
    assert Verdict.ACCEPTED.viable is True
    assert Verdict.REVERTED_SLO.viable is False
