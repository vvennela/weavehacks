"""The lever space, and the memory arithmetic every component agrees on.

Three specialists own three disjoint groups of levers. Disjointness is deliberate:
it lets the arbiter attribute a measured change to exactly one agent's claim.

The memory model here is shared by the validator (which rejects on paper), the
simulator (which predicts), and the fit check (which decides whether two models can
share a card). One implementation so those three can never disagree.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

from .spec import GpuSpec, ModelSpec

# Bytes per element for each supported precision.
DTYPE_BYTES: dict[str, float] = {
    "fp32": 4.0,
    "bf16": 2.0,
    "fp16": 2.0,
    "fp8": 1.0,
    "int8": 1.0,
    "int4": 0.5,
    "awq": 0.5,
    "gptq": 0.5,
}

# Quality cost we expect from each weight precision, as a fraction of the baseline
# eval score. Used only by the simulator; on real hardware the eval measures it.
# These are deliberately pessimistic for aggressive quantization — the loop should
# have to discover that int4 breaks the floor rather than being told.
DTYPE_QUALITY_PENALTY: dict[str, float] = {
    "bf16": 0.000,
    "fp16": 0.000,
    "fp8": 0.004,
    "int8": 0.012,
    "awq": 0.030,
    "gptq": 0.032,
    "int4": 0.055,
}

# Fraction of spec-sheet HBM bandwidth a real streaming decode read achieves. No
# kernel hits the number on the box; ~80% is the usual ceiling for a large sequential
# read. It lives here rather than in the simulator because two components now divide
# by it — the simulator, computing utilization from bytes it moved, and the reduction,
# deriving utilization from measured throughput. If they used different denominators
# they would report different numbers for the same physical traffic, against a
# specialist threshold that was calibrated on only one of them.
ACHIEVABLE_BW_FRACTION = 0.80

Lever = Literal["quantization", "batching", "parallelism"]


@dataclass(frozen=True)
class InferenceConfig:
    """A servable configuration. Frozen so a trial's config cannot drift after the fact."""

    model: str

    # -- quantization specialist owns these ---------------------------------
    weight_dtype: str = "bf16"
    kv_cache_dtype: str = "bf16"

    # -- batching specialist owns these -------------------------------------
    max_num_seqs: int = 256
    max_num_batched_tokens: int = 8192
    enable_chunked_prefill: bool = False

    # -- parallelism specialist owns these ----------------------------------
    tensor_parallel_size: int = 1
    pipeline_parallel_size: int = 1

    # -- placement, owned by Phase 2 not by any specialist ------------------
    gpu_memory_utilization: float = 0.90

    def with_delta(self, delta: dict[str, Any]) -> InferenceConfig:
        unknown = set(delta) - {f for f in self.__dataclass_fields__}
        if unknown:
            raise ValueError(f"unknown config fields: {sorted(unknown)}")
        return replace(self, **delta)

    def diff(self, other: InferenceConfig) -> dict[str, tuple[Any, Any]]:
        return {
            f: (getattr(self, f), getattr(other, f))
            for f in self.__dataclass_fields__
            if getattr(self, f) != getattr(other, f) and f != "model"
        }

    def levers_touched(self, baseline: InferenceConfig) -> set[Lever]:
        """Which specialists' territory this config differs from baseline in.

        The arbiter asserts this has size <= 1 for single-lever trials, which is what
        keeps attribution honest.
        """
        changed = set(baseline.diff(self))
        touched: set[Lever] = set()
        if changed & {"weight_dtype", "kv_cache_dtype"}:
            touched.add("quantization")
        if changed & {"max_num_seqs", "max_num_batched_tokens", "enable_chunked_prefill"}:
            touched.add("batching")
        if changed & {"tensor_parallel_size", "pipeline_parallel_size"}:
            touched.add("parallelism")
        return touched

    def as_dict(self) -> dict[str, Any]:
        return {f: getattr(self, f) for f in self.__dataclass_fields__}

    def label(self) -> str:
        return (
            f"{self.model}[w={self.weight_dtype},kv={self.kv_cache_dtype},"
            f"seqs={self.max_num_seqs},tok={self.max_num_batched_tokens},"
            f"cp={int(self.enable_chunked_prefill)},tp={self.tensor_parallel_size}]"
        )


# --------------------------------------------------------------------------
# Memory arithmetic — one implementation, three consumers.
# --------------------------------------------------------------------------


def weights_gb(model: ModelSpec, cfg: InferenceConfig) -> float:
    """Weight footprint after quantization, per device.

    Tensor parallelism shards weights across devices, so per-device cost divides.
    """
    bytes_per = DTYPE_BYTES[cfg.weight_dtype]
    total = model.params_b * 1e9 * bytes_per / 1e9
    return total / cfg.tensor_parallel_size


def kv_cache_gb_per_token(model: ModelSpec, cfg: InferenceConfig) -> float:
    """KV cache cost of a single token of context, per device.

    2 (K and V) x layers x kv_heads x head_dim x bytes. GQA already shows up here
    through num_kv_heads, which is why it is a spec field rather than an assumption.
    """
    bytes_per = DTYPE_BYTES[cfg.kv_cache_dtype]
    per_token = (
        2 * model.num_layers * model.num_kv_heads * model.head_dim * bytes_per
    )
    return per_token / 1e9 / cfg.tensor_parallel_size


def kv_cache_gb(model: ModelSpec, cfg: InferenceConfig, concurrent_tokens: int) -> float:
    return kv_cache_gb_per_token(model, cfg) * concurrent_tokens


def footprint_gb(
    model: ModelSpec,
    cfg: InferenceConfig,
    concurrent_tokens: int,
) -> float:
    """Total per-device footprint: weights plus the KV cache actually in use."""
    return weights_gb(model, cfg) + kv_cache_gb(model, cfg, concurrent_tokens)


def max_concurrent_tokens(
    model: ModelSpec,
    cfg: InferenceConfig,
    gpu: GpuSpec,
) -> int:
    """How many tokens of KV fit once weights are resident.

    Negative headroom means the weights alone overflow the card; callers treat a
    result of 0 as 'does not fit'.
    """
    budget = gpu.usable_vram_gb * cfg.gpu_memory_utilization - weights_gb(model, cfg)
    if budget <= 0:
        return 0
    return int(budget / kv_cache_gb_per_token(model, cfg))


def baseline_config(model: ModelSpec) -> InferenceConfig:
    """The sensible starting point every improvement is measured against.

    Deliberately unremarkable: full precision, stock batching, single device. If the
    baseline were already tuned, the loop's gains would be manufactured.
    """
    return InferenceConfig(model=model.name)
