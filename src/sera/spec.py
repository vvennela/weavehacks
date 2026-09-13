"""Declared inputs to the optimization run.

The spec is the contract every other component reads: which models, what hardware,
what traffic each workload sees, how fast it must answer, how good the answers must
be, and how many trials we are allowed to spend finding out.

Nothing here is inferred. If a number matters to a decision, it is declared.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class SpecError(ValueError):
    """The spec is missing something a downstream component needs."""


@dataclass(frozen=True)
class ModelSpec:
    """Architecture facts needed for memory arithmetic and parallelism legality.

    These are read off the model config, not guessed. The validator uses them to
    reject impossible configurations on paper before they cost a trial slot.
    """

    name: str
    hf_id: str
    params_b: float
    num_layers: int
    hidden_size: int
    num_attn_heads: int
    num_kv_heads: int
    max_model_len: int
    base_dtype: str = "bf16"
    revision: str = "main"
    # Read from config.json, never inferred. Qwen3-0.6B declares head_dim 128 with
    # hidden_size 1024 over 16 heads, so hidden_size // num_attn_heads would give 64
    # and halve every KV-cache number downstream. Left as None only for older
    # architectures whose config omits it, where the quotient is correct.
    head_dim_override: int | None = None

    @property
    def head_dim(self) -> int:
        if self.head_dim_override is not None:
            return self.head_dim_override
        return self.hidden_size // self.num_attn_heads

    def __post_init__(self) -> None:
        if self.num_attn_heads % self.num_kv_heads != 0:
            raise SpecError(
                f"{self.name}: num_attn_heads ({self.num_attn_heads}) must be divisible "
                f"by num_kv_heads ({self.num_kv_heads})"
            )
        if self.head_dim_override is None and self.hidden_size % self.num_attn_heads != 0:
            raise SpecError(
                f"{self.name}: hidden_size ({self.hidden_size}) is not divisible by "
                f"num_attn_heads ({self.num_attn_heads}) and no head_dim_override was given"
            )


@dataclass(frozen=True)
class GpuSpec:
    """One device we are allowed to place work on."""

    id: str
    name: str
    vram_gb: float
    mem_bandwidth_gbs: float
    # Dense bf16 tensor-core throughput. Prefill is compute bound, decode is
    # bandwidth bound, so the simulator needs both numbers to model either.
    tflops_bf16: float = 165.0
    # Fraction of VRAM the serving runtime reserves for itself (activations,
    # fragmentation, CUDA context). Memory arithmetic must respect it.
    overhead_frac: float = 0.10

    @property
    def usable_vram_gb(self) -> float:
        return self.vram_gb * (1.0 - self.overhead_frac)


@dataclass(frozen=True)
class Workload:
    """The traffic shape a model actually sees.

    Load generation replays this shape. A config tuned against the wrong shape is
    tuned against nothing.
    """

    model: str
    request_rate_rps: float
    input_len_mean: int
    input_len_stdev: int
    output_len_mean: int
    output_len_stdev: int
    duration_s: int = 60
    # Bursty traffic is what breaks a co-tenant's tail latency. Declaring it lets
    # the joint trial reproduce the contention rather than average it away.
    burstiness: float = 1.0

    def __post_init__(self) -> None:
        if self.request_rate_rps <= 0:
            raise SpecError(f"{self.model}: request_rate_rps must be positive")


@dataclass(frozen=True)
class Slo:
    """What 'fast enough' means for one model.

    p95 end-to-end latency is the primary requirement, matching the Sera spec.
    Only the fields that are set are gated; `p50_latency_ms` is advisory and is
    reported rather than enforced.
    """

    model: str
    p95_latency_ms: float
    p50_latency_ms: float | None = None
    min_throughput_rps: float | None = None
    max_error_rate: float = 0.0


@dataclass(frozen=True)
class QualityFloor:
    """What 'good enough' means for one model.

    Held separately from the SLO because a config can be fast and wrong, and that is
    the failure mode a latency-only tuner never catches.
    """

    model: str
    min_score: float
    eval_name: str = "smoke_eval"
    smoke_min_score: float = 0.5


@dataclass(frozen=True)
class Budget:
    """Bounded search. The arbiter spends against this and Phase 2 must be left some."""

    phase1_trials: int
    phase2_trials: int
    concurrent_slots: int = 3
    max_rounds: int = 4

    def __post_init__(self) -> None:
        if self.concurrent_slots < 1:
            raise SpecError("concurrent_slots must be at least 1")


@dataclass(frozen=True)
class Spec:
    models: list[ModelSpec]
    gpus: list[GpuSpec]
    workloads: list[Workload]
    slos: list[Slo]
    quality_floors: list[QualityFloor]
    budget: Budget
    seed: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    def model(self, name: str) -> ModelSpec:
        return _one(self.models, name, "model")

    def workload(self, name: str) -> Workload:
        return _one(self.workloads, name, "workload", key="model")

    def slo(self, name: str) -> Slo:
        return _one(self.slos, name, "SLO", key="model")

    def quality_floor(self, name: str) -> QualityFloor:
        return _one(self.quality_floors, name, "quality floor", key="model")

    def gpu(self, gpu_id: str) -> GpuSpec:
        return _one(self.gpus, gpu_id, "gpu", key="id")

    @property
    def model_names(self) -> list[str]:
        return [m.name for m in self.models]

    def __post_init__(self) -> None:
        # Every model needs a full set of declarations. A missing SLO or floor means
        # a gate would silently pass, which is worse than a crash.
        for m in self.models:
            for label, lookup in (
                ("workload", self.workload),
                ("SLO", self.slo),
                ("quality floor", self.quality_floor),
            ):
                try:
                    lookup(m.name)
                except SpecError as exc:
                    raise SpecError(f"model '{m.name}' has no {label} declared") from exc
        if not self.gpus:
            raise SpecError("at least one GPU must be declared")

        # An unsatisfiable requirement is worse than a strict one: every trial
        # reverts, the loop reports no viable config, and nothing in the output
        # says the target was impossible. Throughput cannot exceed offered load,
        # so catch that here rather than letting it look like a tuning failure.
        for m in self.models:
            slo, wl = self.slo(m.name), self.workload(m.name)
            if slo.min_throughput_rps is not None:
                if slo.min_throughput_rps > wl.request_rate_rps:
                    raise SpecError(
                        f"{m.name}: min_throughput_rps ({slo.min_throughput_rps}) exceeds "
                        f"offered load request_rate_rps ({wl.request_rate_rps}) — no "
                        "configuration can serve more traffic than arrives, so this SLO "
                        "is unsatisfiable by construction"
                    )
            if slo.p95_latency_ms <= 0:
                raise SpecError(f"{m.name}: p95_latency_ms must be positive")


def _one(items: list, needle: str, label: str, key: str = "name"):
    for it in items:
        if getattr(it, key) == needle:
            return it
    known = ", ".join(getattr(i, key) for i in items) or "none"
    raise SpecError(f"no {label} declared for '{needle}' (declared: {known})")


def load_spec(path: str | Path) -> Spec:
    """Read a spec YAML. Raises SpecError with a pointed message on anything missing."""
    path = Path(path)
    if not path.exists():
        raise SpecError(f"spec not found: {path}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise SpecError(f"spec must be a YAML mapping, got {type(raw).__name__}")

    try:
        return Spec(
            models=[ModelSpec(**m) for m in raw["models"]],
            gpus=[GpuSpec(**g) for g in raw["gpus"]],
            workloads=[Workload(**w) for w in raw["workloads"]],
            slos=[Slo(**s) for s in raw["slos"]],
            quality_floors=[QualityFloor(**q) for q in raw["quality_floors"]],
            budget=Budget(**raw["budget"]),
            seed=raw.get("seed", 0),
            meta=raw.get("meta", {}),
        )
    except KeyError as exc:
        raise SpecError(f"spec is missing required section: {exc}") from exc
    except TypeError as exc:
        raise SpecError(f"spec section has wrong or unexpected fields: {exc}") from exc
