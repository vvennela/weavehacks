"""The public contract: what a user passes in, and what comes back.

This module is the integration boundary. The notebook, the demo, and any user
code import from `sera` and nothing else — backend internals (phase1, phase2,
runner, arbiter) are deliberately not re-exported.

The types here compose the internal `InferenceConfig` and `Measurement` rather
than duplicating them, so a value that crosses the boundary is the same object
the backend recorded. Only the vocabulary is new: this module owns the words the
user reads, and the backend owns the numbers.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from .config import InferenceConfig
from .ledger import Measurement, Verdict

# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Constraints:
    """What the user requires of a configuration before it can be recommended.

    A constraint is a gate, never a score to trade away. `quality_floor` defaults
    to the documented tolerance so quick mode has a floor even when the user
    supplies nothing.
    """

    p95_latency_ms: float | None = None
    quality_floor: float = 0.99
    max_error_rate: float = 0.0


@dataclass(frozen=True)
class Workload:
    """The traffic shape configurations are measured under."""

    concurrency: Sequence[int] = (1, 2, 4, 8)
    max_output_tokens: int = 64


@dataclass(frozen=True)
class Budget:
    """How much GPU time the search may spend.

    Reserving phase-two trials up front stops phase one from consuming the whole
    budget and leaving joint placement untested.
    """

    max_candidate_trials: int = 8
    phase2_reserved_trials: int = 2


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------


class RunState(str, Enum):
    """How a run ended, in the user's terms.

    NO_SAFE_IMPROVEMENT is a success path, not an error: Sera looked and reports
    honestly that nothing beat the baseline within the budget.
    """

    IMPROVED = "improved"
    NO_SAFE_IMPROVEMENT = "no_safe_improvement"
    CANCELLED = "cancelled"
    FAILED = "failed"


RUN_STATE_HEADLINES: dict[RunState, str] = {
    RunState.IMPROVED: "Sera found a faster configuration and verified it.",
    RunState.NO_SAFE_IMPROVEMENT: "Sera found no configuration that was both faster and safe. Your baseline is unchanged.",
    RunState.CANCELLED: "Run cancelled. Completed trials were kept.",
    RunState.FAILED: "Sera could not finish the run.",
}

VERDICT_LABELS: dict[Verdict, str] = {
    Verdict.ACCEPTED: "Accepted",
    Verdict.REVERTED_SLO: "Too slow — rolled back",
    Verdict.REVERTED_QUALITY: "Quality dropped — rolled back",
    Verdict.REJECTED_PAPER: "Ruled out before running",
    Verdict.FAILED: "Failed to run",
}

METRIC_LABELS: dict[str, str] = {
    "p50_latency_ms": "Median latency",
    "p95_latency_ms": "p95 latency",
    "throughput_rps": "Throughput",
    "footprint_gb": "GPU memory",
}

# The order result sections appear in, in the summary and in the notebook.
# Every section renders on every path: a run that found nothing still owes the
# user the same account of what it tried and why it stopped.
REPORT_SECTIONS: tuple[str, ...] = (
    "What Sera did",
    "Recommended configuration",
    "Measured improvement",
    "Quality",
    "What Sera tried",
    "Other good configurations",
    "What was ruled out",
    "Run details",
)


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class QualityResult:
    """The quality gate's finding.

    `verified` is the honest distinction between the two modes: quick mode checks
    that behavior did not change, which is not a claim that the task is still done
    well. The notebook must surface this rather than imply verification.
    """

    score: float
    floor: float
    passed: bool
    verified: bool
    method: str

    @property
    def caveat(self) -> str:
        if self.verified:
            return "Task quality was checked with your evaluation function."
        return "Task quality was not verified. This checks behavior preservation only."


@dataclass(frozen=True)
class Trial:
    """One candidate Sera considered, executed or not.

    `ran` separates deterministic rejections from GPU failures so the progress
    view can show them as different things.
    """

    trial_id: str
    phase: int
    model_id: str
    configuration: InferenceConfig
    verdict: Verdict
    specialist: str | None = None
    lever: str | None = None
    measurement: Measurement | None = None
    quality: QualityResult | None = None
    note: str = ""

    @property
    def ran(self) -> bool:
        return self.verdict.ran

    @property
    def label(self) -> str:
        return VERDICT_LABELS[self.verdict]


@dataclass(frozen=True)
class RejectedCandidate:
    """A candidate the validator killed on arithmetic, before it cost GPU time.

    Kept in the result because 'what Sera did not waste time on' is part of the
    argument that the search is cheaper than a grid.
    """

    model_id: str
    configuration: InferenceConfig
    reason: str
    specialist: str | None = None


@dataclass(frozen=True)
class FrontierEntry:
    """A viable configuration that nothing else dominates."""

    model_id: str
    configuration: InferenceConfig
    measurement: Measurement
    quality: QualityResult
    label: str = ""


@dataclass(frozen=True)
class Recommendation:
    """The configuration Sera selected, with the baseline it beat."""

    model_id: str
    configuration: InferenceConfig
    baseline: Measurement
    optimized: Measurement
    quality: QualityResult
    trials_used: int
    rationale: str = ""

    @property
    def latency_change_pct(self) -> float:
        """Negative means faster. p95 is the headline metric per the spec."""
        before = self.baseline.p95_latency_ms
        if before == 0:
            return 0.0
        return (self.optimized.p95_latency_ms - before) / before * 100.0

    @property
    def memory_change_pct(self) -> float:
        before = self.baseline.footprint_gb
        if before == 0:
            return 0.0
        return (self.optimized.footprint_gb - before) / before * 100.0

    @property
    def throughput_change_pct(self) -> float:
        before = self.baseline.throughput_rps
        if before == 0:
            return 0.0
        return (self.optimized.throughput_rps - before) / before * 100.0


@dataclass
class SeraModel:
    """A ready-to-use model, configured as Sera recommends.

    Sera owns loading, so this wrapper hides whether vLLM runs in-process or as a
    managed server. `generate` is injected by the backend; the fixture supplies a
    canned one so the notebook works before any GPU exists.
    """

    model_id: str
    revision: str
    configuration: InferenceConfig
    metrics_snapshot: Measurement
    _generate: Callable[[Any], str] | None = field(default=None, repr=False)

    def generate(self, prompt: Any) -> str:
        if self._generate is None:
            raise SeraBackendUnavailable(
                f"{self.model_id} is not backed by a running engine. "
                "This result came from a fixture."
            )
        return self._generate(prompt)

    def close(self) -> None:
        """Release the engine. Safe to call on a fixture-backed model."""
        self._generate = None


@dataclass
class SeraResult:
    """Everything one optimization run produced.

    Field order matches section 6.3 of the spec so the contract reads the same in
    prose and in code.
    """

    state: RunState
    models: list[SeraModel] = field(default_factory=list)
    recommended: Recommendation | None = None
    frontier: list[FrontierEntry] = field(default_factory=list)
    baselines: dict[str, Measurement] = field(default_factory=dict)
    trials: list[Trial] = field(default_factory=list)
    rejected: list[RejectedCandidate] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)
    weave_url: str | None = None
    mode: str = "quick"

    @property
    def headline(self) -> str:
        return RUN_STATE_HEADLINES[self.state]

    @property
    def trials_run(self) -> int:
        return sum(1 for t in self.trials if t.ran)

    def print_summary(self) -> None:
        """The readable report, in REPORT_SECTIONS order."""
        for line in self.summary_lines():
            print(line)

    def summary_lines(self) -> list[str]:
        """Summary as text, so the notebook can render it without re-deriving it."""
        out: list[str] = [self.headline, ""]

        out.append("What Sera did")
        out.append(
            f"  Mode: {self.mode}   "
            f"Trials run: {self.trials_run}   "
            f"Ruled out before running: {len(self.rejected)}"
        )
        out.append("")

        rec = self.recommended

        out.append("Recommended configuration")
        if rec is None:
            out.append("  None. Sera found no change that was both faster and safe.")
            out.append("  Your models are returned on their baseline configuration.")
        else:
            out.append(f"  {rec.model_id}")
            for lever, value in _changed_levers(rec).items():
                out.append(f"    {lever}: {value}")
        out.append("")

        out.append("Measured improvement")
        if rec is None:
            out.extend(self._baseline_lines())
        else:
            out.append(
                f"  {METRIC_LABELS['p95_latency_ms']}: "
                f"{rec.baseline.p95_latency_ms:.0f} ms -> {rec.optimized.p95_latency_ms:.0f} ms "
                f"({rec.latency_change_pct:+.1f}%)"
            )
            out.append(
                f"  {METRIC_LABELS['footprint_gb']}: "
                f"{rec.baseline.footprint_gb:.1f} GB -> {rec.optimized.footprint_gb:.1f} GB "
                f"({rec.memory_change_pct:+.1f}%)"
            )
            out.append(
                f"  {METRIC_LABELS['throughput_rps']}: "
                f"{rec.baseline.throughput_rps:.1f} -> {rec.optimized.throughput_rps:.1f} req/s "
                f"({rec.throughput_change_pct:+.1f}%)"
            )
        out.append("")

        out.append("Quality")
        if rec is None:
            out.append("  No candidate cleared the quality floor while also being faster.")
            failed = [t for t in self.trials if t.verdict is Verdict.REVERTED_QUALITY]
            for trial in failed:
                q = trial.quality
                if q is not None:
                    out.append(
                        f"  {trial.trial_id}: scored {q.score:.3f} against a floor of {q.floor:.3f}"
                    )
        else:
            q = rec.quality
            out.append(
                f"  {q.method}: {q.score:.3f} (floor {q.floor:.3f}) "
                f"{'PASS' if q.passed else 'FAIL'}"
            )
            out.append(f"  {q.caveat}")
        out.append("")

        # The trials that ran are the evidence. They matter most on the path where
        # nothing was recommended, which is exactly where they used to be omitted.
        out.append("What Sera tried")
        executed = [t for t in self.trials if t.ran]
        if executed:
            for trial in executed:
                lever = f" [{trial.lever}]" if trial.lever else ""
                out.append(f"  {trial.trial_id}{lever}: {trial.label}")
                if trial.note:
                    out.append(f"      {trial.note}")
        else:
            out.append("  No candidate reached execution.")
        out.append("")

        out.append("Other good configurations")
        if self.frontier:
            for entry in self.frontier:
                out.append(
                    f"  {entry.label or entry.model_id}: "
                    f"p95 {entry.measurement.p95_latency_ms:.0f} ms, "
                    f"{entry.measurement.footprint_gb:.1f} GB"
                )
        elif rec is None:
            out.append("  None. No configuration passed every gate.")
        else:
            out.append("  None besides the recommendation.")
        out.append("")

        out.append("What was ruled out")
        if self.rejected:
            for r in self.rejected[:5]:
                out.append(f"  {r.reason}")
            if len(self.rejected) > 5:
                out.append(f"  ... and {len(self.rejected) - 5} more")
        else:
            out.append("  Nothing was ruled out before running.")
        out.append("")

        out.append("Run details")
        if self.weave_url:
            out.append(f"  Full trace: {self.weave_url}")
        for key, value in self.report.items():
            out.append(f"  {key}: {value}")

        return out

    def _baseline_lines(self) -> list[str]:
        """Baseline numbers, shown when there is no improvement to compare against."""
        if not self.baselines:
            return ["  No baseline was measured."]
        lines = ["  None. Baseline measurements, unchanged:"]
        for model_id, m in self.baselines.items():
            lines.append(
                f"    {model_id}: "
                f"p95 {m.p95_latency_ms:.0f} ms, "
                f"{m.throughput_rps:.1f} req/s, "
                f"{m.footprint_gb:.1f} GB"
            )
        return lines

    def as_dict(self) -> dict[str, Any]:
        """Plain data, for serialization and for the notebook's tables."""
        return {
            "state": self.state.value,
            "mode": self.mode,
            "recommended": asdict(self.recommended) if self.recommended else None,
            "frontier": [asdict(f) for f in self.frontier],
            "baselines": {k: asdict(v) for k, v in self.baselines.items()},
            "trials": [asdict(t) for t in self.trials],
            "rejected": [asdict(r) for r in self.rejected],
            "report": dict(self.report),
            "weave_url": self.weave_url,
        }


def _changed_levers(rec: Recommendation) -> dict[str, Any]:
    """The levers the recommendation moved, for display.

    Falls back to the full config when there is no baseline config to diff
    against, which is the case for a recommendation that is the baseline.
    """
    cfg = rec.configuration
    baseline_cfg = InferenceConfig(model=cfg.model)
    diff = baseline_cfg.diff(cfg)
    if not diff:
        return {"configuration": "unchanged from baseline"}
    return {lever: f"{was} -> {now}" for lever, (was, now) in diff.items()}


class SeraError(Exception):
    """Base for every error the public API raises."""


class SeraBackendUnavailable(SeraError):
    """No engine is connected, so this call cannot produce real measurements."""
