"""Paper-only feasibility. No GPU, no deployment, no trial slot spent.

A rejection here costs microseconds. The same rejection discovered by deploying the
config costs a slot out of a bounded budget, plus the minutes to find out. So every
check that can be arithmetic is arithmetic.

Each rejection carries the numbers that produced it, because the reason is fed back
to the proposing specialist — "tp=3 does not divide 8 kv heads" is actionable in a way
that "invalid config" is not.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import (
    DTYPE_BYTES,
    InferenceConfig,
    kv_cache_gb_per_token,
    max_concurrent_tokens,
    weights_gb,
)
from .spec import GpuSpec, ModelSpec

# A config that cannot hold at least this many tokens of KV cannot serve the
# workload at any useful concurrency; treat it as not fitting.
MIN_VIABLE_KV_TOKENS = 4096


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""
    detail: dict[str, float] | None = None

    def __bool__(self) -> bool:
        return self.ok


def validate(
    cfg: InferenceConfig,
    model: ModelSpec,
    gpu: GpuSpec,
    available_gpus: int = 1,
    reserved_gb: float = 0.0,
) -> ValidationResult:
    """Check one candidate against arithmetic and backend legality.

    `reserved_gb` is VRAM already committed to a co-tenant. Phase 1 passes 0;
    Phase 2's fit check passes the other model's footprint, which is how the same
    function serves both callers.
    """
    tp = cfg.tensor_parallel_size
    pp = cfg.pipeline_parallel_size

    # -- precision legality -------------------------------------------------
    for field, dtype in (("weight_dtype", cfg.weight_dtype), ("kv_cache_dtype", cfg.kv_cache_dtype)):
        if dtype not in DTYPE_BYTES:
            return ValidationResult(
                False, f"unsupported {field}: {dtype!r} (known: {sorted(DTYPE_BYTES)})"
            )
    # Weight-only quantization formats are not valid KV cache dtypes.
    if cfg.kv_cache_dtype in {"awq", "gptq", "int4"}:
        return ValidationResult(
            False,
            f"kv_cache_dtype={cfg.kv_cache_dtype} is a weight-only format; "
            "KV cache supports fp8/fp16/bf16",
        )

    # -- parallelism legality ----------------------------------------------
    if tp < 1 or pp < 1:
        return ValidationResult(False, f"parallel sizes must be >= 1 (tp={tp}, pp={pp})")

    if tp * pp > available_gpus:
        return ValidationResult(
            False,
            f"tp*pp={tp * pp} exceeds available GPUs ({available_gpus})",
            {"tp": tp, "pp": pp, "available": available_gpus},
        )

    # vLLM shards attention heads across TP ranks; both counts must divide evenly.
    if model.num_attn_heads % tp != 0:
        return ValidationResult(
            False,
            f"tp={tp} does not divide num_attn_heads={model.num_attn_heads}",
            {"tp": tp, "num_attn_heads": model.num_attn_heads},
        )
    if model.num_kv_heads % tp != 0:
        return ValidationResult(
            False,
            f"tp={tp} does not divide num_kv_heads={model.num_kv_heads}",
            {"tp": tp, "num_kv_heads": model.num_kv_heads},
        )
    if pp > 1 and model.num_layers % pp != 0:
        return ValidationResult(
            False,
            f"pp={pp} does not divide num_layers={model.num_layers}",
            {"pp": pp, "num_layers": model.num_layers},
        )

    # -- batching legality --------------------------------------------------
    if cfg.max_num_seqs < 1:
        return ValidationResult(False, f"max_num_seqs must be >= 1 (got {cfg.max_num_seqs})")
    # Without chunked prefill a single request's prefill must fit in one batch,
    # so the token budget has to cover the longest supported prompt.
    if not cfg.enable_chunked_prefill and cfg.max_num_batched_tokens < model.max_model_len:
        return ValidationResult(
            False,
            f"max_num_batched_tokens={cfg.max_num_batched_tokens} < max_model_len="
            f"{model.max_model_len} requires enable_chunked_prefill=True",
            {
                "max_num_batched_tokens": cfg.max_num_batched_tokens,
                "max_model_len": model.max_model_len,
            },
        )

    if not 0.0 < cfg.gpu_memory_utilization <= 1.0:
        return ValidationResult(
            False, f"gpu_memory_utilization must be in (0,1] (got {cfg.gpu_memory_utilization})"
        )

    # -- memory arithmetic --------------------------------------------------
    w_gb = weights_gb(model, cfg)
    budget_gb = gpu.usable_vram_gb * cfg.gpu_memory_utilization - reserved_gb

    if w_gb >= budget_gb:
        return ValidationResult(
            False,
            f"weights {w_gb:.2f}GB do not fit in {budget_gb:.2f}GB available "
            f"(vram {gpu.vram_gb}GB, reserved {reserved_gb:.2f}GB)",
            {"weights_gb": w_gb, "budget_gb": budget_gb, "reserved_gb": reserved_gb},
        )

    kv_tokens = int((budget_gb - w_gb) / kv_cache_gb_per_token(model, cfg))
    if kv_tokens < MIN_VIABLE_KV_TOKENS:
        return ValidationResult(
            False,
            f"only {kv_tokens} tokens of KV cache fit after weights "
            f"(need >= {MIN_VIABLE_KV_TOKENS})",
            {"kv_tokens": float(kv_tokens), "weights_gb": w_gb, "budget_gb": budget_gb},
        )

    return ValidationResult(
        True,
        "",
        {
            "weights_gb": w_gb,
            "kv_tokens": float(kv_tokens),
            "headroom_gb": budget_gb - w_gb,
        },
    )


def fits_together(
    configs: dict[str, InferenceConfig],
    models: dict[str, ModelSpec],
    gpu: GpuSpec,
    concurrent_tokens: dict[str, int],
) -> ValidationResult:
    """Phase 2 fit check: do these models share this card on arithmetic alone?

    Deliberately separate from the joint trial. Fitting is necessary and nowhere near
    sufficient — two models can fit comfortably and still destroy each other's tail
    latency through bandwidth contention. This answers only the cheap question.
    """
    total = 0.0
    breakdown: dict[str, float] = {}
    for name, cfg in configs.items():
        model = models[name]
        w = weights_gb(model, cfg)
        kv = kv_cache_gb_per_token(model, cfg) * concurrent_tokens.get(name, 0)
        breakdown[f"{name}_weights_gb"] = w
        breakdown[f"{name}_kv_gb"] = kv
        total += w + kv

    capacity = gpu.usable_vram_gb
    breakdown["total_gb"] = total
    breakdown["capacity_gb"] = capacity
    breakdown["headroom_gb"] = capacity - total

    if total > capacity:
        return ValidationResult(
            False,
            f"co-tenancy needs {total:.2f}GB but {gpu.id} offers {capacity:.2f}GB usable",
            breakdown,
        )
    return ValidationResult(True, "", breakdown)
