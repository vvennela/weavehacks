"""Sera: fast model inference without inference-engineering knowledge.

    import sera

    result = sera.optimize(
        models=["Qwen/Qwen3-0.6B", "zai-org/glm-4-9b-chat-hf"],
        prompts=prompts,
    )

    result.print_summary()
    model_a, model_b = result.models

Everything a user or the notebook needs is exported here. Backend modules are
reachable but are not part of the contract — import from `sera` directly.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from .config import InferenceConfig
from .ledger import Measurement, Verdict
from .types import (
    METRIC_LABELS,
    REPORT_SECTIONS,
    RUN_STATE_HEADLINES,
    VERDICT_LABELS,
    Budget,
    Constraints,
    FrontierEntry,
    QualityResult,
    Recommendation,
    RejectedCandidate,
    RunState,
    SeraBackendUnavailable,
    SeraError,
    SeraModel,
    SeraResult,
    Trial,
    Workload,
)

__all__ = [
    "METRIC_LABELS",
    "REPORT_SECTIONS",
    "RUN_STATE_HEADLINES",
    "VERDICT_LABELS",
    "Backend",
    "Budget",
    "Constraints",
    "FrontierEntry",
    "InferenceConfig",
    "Measurement",
    "QualityResult",
    "Recommendation",
    "RejectedCandidate",
    "RunState",
    "SeraBackendUnavailable",
    "SeraError",
    "SeraModel",
    "SeraResult",
    "Trial",
    "Verdict",
    "Workload",
    "optimize",
    "set_backend",
]

__version__ = "0.1.0"


class Backend(Protocol):
    """What the optimization engine must provide to satisfy the public API.

    This is the single seam between the product surface and the GPU path. The
    notebook is built against a fixture-backed result first; connecting the real
    engine means registering a backend here and changing nothing else.
    """

    def run(
        self,
        *,
        models: Sequence[str],
        prompts: Sequence[str],
        evaluation: Callable[..., float] | None,
        constraints: Sequence[Constraints] | None,
        workload: Workload,
        budget: Budget,
    ) -> SeraResult: ...


_backend: Backend | None = None


def set_backend(backend: Backend | None) -> None:
    """Register the engine that `optimize` will drive.

    Called once by the backend package, or by the notebook to swap a fixture for
    the real thing.
    """
    global _backend
    _backend = backend


def optimize(
    *,
    models: Sequence[str],
    prompts: Sequence[str],
    evaluation: Callable[..., float] | None = None,
    constraints: Sequence[Constraints] | None = None,
    workload: Workload | None = None,
    budget: Budget | None = None,
    backend: Backend | None = None,
) -> SeraResult:
    """Find a fast, safe way to run these models on the available hardware.

    Quick mode is `models` plus `prompts`. Supplying `evaluation` and a quality
    floor in `constraints` promotes the run to verified mode, where the user's own
    evaluator gates every candidate.

    Raises SeraBackendUnavailable when no engine is registered — the fixture in
    `sera.fixtures` exists so the product surface can be built and demonstrated
    before that happens.
    """
    if not models:
        raise ValueError("optimize() needs at least one model identifier")
    if not prompts:
        raise ValueError("optimize() needs at least one representative prompt")
    if evaluation is not None and constraints is None:
        raise ValueError(
            "verified mode needs a quality floor: pass constraints=[sera.Constraints(...)]"
        )

    engine = backend or _backend
    if engine is None:
        raise SeraBackendUnavailable(
            "No optimization backend is registered. "
            "Call sera.set_backend(...) with an engine, or use "
            "sera.fixtures.demo_result() to work against fixed example data."
        )

    return engine.run(
        models=list(models),
        prompts=list(prompts),
        evaluation=evaluation,
        constraints=list(constraints) if constraints else None,
        workload=workload or Workload(),
        budget=budget or Budget(),
    )
