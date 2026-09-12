"""Is it still right, not just faster.

Two stages on purpose. The smoke check is cheap and catches the configurations that
are obviously broken — a quantization that produced garbage — before a full eval
spends real time on them. The full eval is the one that decides.

A config that clears the SLO and fails here is reverted, and the revert is recorded
with its score. That row is the most informative kind in the ledger: it marks exactly
where the speed/quality frontier sits for this model.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import DTYPE_QUALITY_PENALTY, InferenceConfig
from .spec import QualityFloor


@dataclass
class QualityResult:
    score: float
    floor: float
    passed: bool
    stage: str          # "smoke" | "full"
    detail: str = ""


def _simulated_score(cfg: InferenceConfig) -> float:
    """Model the accuracy cost of a configuration.

    Only precision changes accuracy: batching and parallelism are numerically neutral
    rearrangements of the same computation, and a model that pretended otherwise would
    teach the loop a false lesson. KV quantization is weighted at half of weight
    quantization because it degrades only attention history, not the parameters.
    """
    penalty = DTYPE_QUALITY_PENALTY.get(cfg.weight_dtype, 0.0)
    penalty += DTYPE_QUALITY_PENALTY.get(cfg.kv_cache_dtype, 0.0) * 0.5
    return max(0.0, 1.0 - penalty)


def smoke_check(cfg: InferenceConfig, floor: QualityFloor) -> QualityResult:
    """Fast sanity gate. Catches catastrophic breakage, not subtle regression."""
    score = _simulated_score(cfg)
    passed = score >= floor.smoke_min_score
    return QualityResult(
        score=score,
        floor=floor.smoke_min_score,
        passed=passed,
        stage="smoke",
        detail="" if passed else f"output is degraded beyond usability at {cfg.weight_dtype}",
    )


def full_eval(cfg: InferenceConfig, floor: QualityFloor) -> QualityResult:
    """The gate that decides. Scores against the model's declared floor."""
    score = _simulated_score(cfg)
    passed = score >= floor.min_score
    return QualityResult(
        score=score,
        floor=floor.min_score,
        passed=passed,
        stage="full",
        detail=(
            ""
            if passed
            else f"{score:.4f} is below the {floor.min_score:.4f} floor — reverting "
            f"despite the latency win"
        ),
    )
