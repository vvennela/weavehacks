"""Append-only record of every trial, including the ones that failed.

This file is the point of the project. A tuner that reports only its wins has thrown
away most of what it learned: which levers were dead, which predictions were wrong,
and which configs were fast but not good enough. All of that is decision-relevant.

Two queries matter downstream and neither is "what was fastest":

  - `frontier()`   Phase 2 re-reads this history asking for the *smallest* config
                   still clearing SLO, not the quickest. New knowledge, no new trials.
  - `calibration()` The arbiter weights each specialist by whether its past predictions
                   held, so budget flows toward the agents that have been right.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterator


class Verdict(str, Enum):
    ACCEPTED = "accepted"            # ran, cleared SLO and quality
    REVERTED_SLO = "reverted_slo"    # ran, breached latency/throughput
    REVERTED_QUALITY = "reverted_quality"  # ran, scored below the floor
    REJECTED_PAPER = "rejected_paper"      # never ran; validator killed it on arithmetic
    FAILED = "failed"                # trial errored (OOM, deploy failure, crash)

    @property
    def ran(self) -> bool:
        """Did this trial actually execute? Paper rejections cost no slot."""
        return self is not Verdict.REJECTED_PAPER

    @property
    def viable(self) -> bool:
        return self is Verdict.ACCEPTED


class Substrate(str, Enum):
    """Which machinery produced the measurement.

    Recorded per row so a mixed run is never silently conflated. A simulated number
    and a measured number must never be compared as if they were the same kind of thing.
    """

    VLLM = "vllm"
    SIM = "sim"


@dataclass
class Measurement:
    """What the trial actually did.

    `mem_bandwidth_util` is None when the substrate could not measure it. vLLM exposes
    no such metric and NVML memory-controller utilization is unavailable in many
    containers, so None is the common case on real hardware. The specification is
    explicit that this must not be papered over: "Unavailable metrics are recorded as
    unavailable. Sera must not replace missing measurements with agent estimates."
    Recording 0.0 would read to the quantization specialist as "bandwidth is idle",
    which is the opposite of "we do not know".
    """

    p50_latency_ms: float
    p95_latency_ms: float
    throughput_rps: float
    footprint_gb: float
    kv_occupancy: float = 0.0
    preemptions: int = 0
    mem_bandwidth_util: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Prediction:
    """What the proposing specialist claimed would happen, recorded before the trial.

    Held separately from the measurement so `prediction_held` is computable rather
    than asserted. An agent that cannot be wrong on the record cannot improve.
    """

    metric: str                # e.g. "p95_latency_ms", "footprint_gb"
    direction: str             # "decrease" | "increase"
    magnitude_pct: float | None = None
    confidence: float = 0.5
    rationale: str = ""

    def held(self, before: float, after: float, tolerance_pct: float = 2.0) -> bool:
        """Did reality move the way the specialist said it would?

        Tolerance absorbs measurement noise; a change smaller than it counts as
        'no movement', which fails a directional claim.
        """
        if before == 0:
            return False
        delta_pct = (after - before) / abs(before) * 100.0
        if abs(delta_pct) < tolerance_pct:
            return False
        return delta_pct < 0 if self.direction == "decrease" else delta_pct > 0


@dataclass
class TrialRecord:
    """One row. Written once, never mutated."""

    trial_id: str
    phase: int
    round: int
    models: list[str]
    config: dict[str, Any]
    verdict: Verdict
    substrate: Substrate
    proposing_specialist: str | None = None
    lever: str | None = None
    prediction: Prediction | None = None
    measurement: Measurement | None = None
    baseline_measurement: Measurement | None = None
    quality_score: float | None = None
    quality_floor: float | None = None
    prediction_held: bool | None = None
    reason: str = ""
    gpu_assignment: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        d = asdict(self)
        d["verdict"] = self.verdict.value
        d["substrate"] = self.substrate.value
        return json.dumps(d)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TrialRecord:
        d = dict(d)
        d["verdict"] = Verdict(d["verdict"])
        d["substrate"] = Substrate(d["substrate"])
        if d.get("prediction"):
            d["prediction"] = Prediction(**d["prediction"])
        for key in ("measurement", "baseline_measurement"):
            if d.get(key):
                d[key] = Measurement(**d[key])
        return cls(**d)


class Ledger:
    """Append-only JSONL store with the queries the loop actually asks."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: list[TrialRecord] = []
        if self.path.exists():
            self._cache = list(self._read())

    # ---- write -------------------------------------------------------------

    def append(self, record: TrialRecord) -> TrialRecord:
        with self.path.open("a") as fh:
            fh.write(record.to_json() + "\n")
        self._cache.append(record)
        return record

    # ---- read --------------------------------------------------------------

    def _read(self) -> Iterator[TrialRecord]:
        with self.path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield TrialRecord.from_dict(json.loads(line))

    def all(self) -> list[TrialRecord]:
        return list(self._cache)

    def for_model(self, model: str) -> list[TrialRecord]:
        return [r for r in self._cache if model in r.models]

    def reverts(self) -> list[TrialRecord]:
        return [r for r in self._cache if r.verdict.name.startswith("REVERTED")]

    # ---- the two queries that matter ---------------------------------------

    def viable(self, model: str) -> list[TrialRecord]:
        """Phase-1 rows for `model` that ran and cleared every gate."""
        return [
            r
            for r in self.for_model(model)
            if r.verdict.viable and r.measurement is not None and r.phase == 1
        ]

    @staticmethod
    def _dominates(a: Measurement, b: Measurement) -> bool:
        """Does `a` beat `b` outright on every axis that matters?

        Per the Sera specification a configuration is dominated when another is at
        least as fast, at least as memory efficient, AND at least as high throughput,
        with a strict improvement in at least one. Ties on all three dominate nothing,
        so identical configurations both survive rather than one arbitrarily winning.
        """
        at_least_as_good = (
            a.p95_latency_ms <= b.p95_latency_ms
            and a.footprint_gb <= b.footprint_gb
            and a.throughput_rps >= b.throughput_rps
        )
        strictly_better = (
            a.p95_latency_ms < b.p95_latency_ms
            or a.footprint_gb < b.footprint_gb
            or a.throughput_rps > b.throughput_rps
        )
        return at_least_as_good and strictly_better

    def pareto_frontier(self, model: str) -> list[TrialRecord]:
        """The non-dominated viable configurations, sorted smallest first.

        This is the set worth keeping. Sorting by one axis — which is what this used
        to do — throws away the configuration that is slightly larger but markedly
        faster, and that is frequently the one Phase 2 needs. A frontier is the answer
        to "what are the real choices", not "what won on my favourite metric".
        """
        rows = self.viable(model)
        front = [
            r
            for r in rows
            if not any(
                self._dominates(o.measurement, r.measurement)  # type: ignore[arg-type]
                for o in rows
                if o is not r
            )
        ]
        front.sort(key=lambda r: r.measurement.footprint_gb)  # type: ignore[union-attr]
        return front

    def frontier(
        self,
        model: str,
        objective: str = "footprint_gb",
        limit: int | None = None,
    ) -> list[TrialRecord]:
        """Non-dominated viable configs, ordered by `objective` ascending.

        Phase 1 optimizes for speed. Phase 2 calls this with the default objective and
        gets a different answer out of the same history — the smallest configuration
        that still clears SLO. Quality failures never appear here.
        """
        front = self.pareto_frontier(model)
        front.sort(key=lambda r: getattr(r.measurement, objective))
        return front[:limit] if limit else front

    def recommend(self, model: str, p95_budget_ms: float | None = None) -> TrialRecord | None:
        """Pick one configuration to recommend, per the specification's ordering.

        Quality is already guaranteed — nothing reaches the frontier without passing
        it. So: honour the latency requirement when there is one, then minimise p95,
        then use footprint as the tie-breaker.
        """
        front = self.pareto_frontier(model)
        if not front:
            return None
        if p95_budget_ms is not None:
            within = [
                r for r in front
                if r.measurement.p95_latency_ms <= p95_budget_ms  # type: ignore[union-attr]
            ]
            if within:
                front = within
        return min(
            front,
            key=lambda r: (r.measurement.p95_latency_ms, r.measurement.footprint_gb),  # type: ignore[union-attr]
        )

    def calibration(self, specialist: str) -> float:
        """Fraction of this specialist's ran-trial predictions that held.

        Returns 0.5 with no evidence — a new specialist is neither trusted nor
        distrusted, so its first proposal competes on argument alone.
        """
        scored = [
            r
            for r in self._cache
            if r.proposing_specialist == specialist and r.prediction_held is not None
        ]
        if not scored:
            return 0.5
        return sum(1 for r in scored if r.prediction_held) / len(scored)

    # ---- reporting ---------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        ran = [r for r in self._cache if r.verdict.ran]
        return {
            "total_rows": len(self._cache),
            "trials_run": len(ran),
            "paper_rejections": sum(
                1 for r in self._cache if r.verdict is Verdict.REJECTED_PAPER
            ),
            "accepted": sum(1 for r in self._cache if r.verdict.viable),
            "reverts": len(self.reverts()),
            "by_verdict": {
                v.value: sum(1 for r in self._cache if r.verdict is v) for v in Verdict
            },
            "calibration": {
                s: round(self.calibration(s), 3)
                for s in sorted(
                    {r.proposing_specialist for r in self._cache if r.proposing_specialist}
                )
            },
        }
