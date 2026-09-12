"""Placement. Owns tensor_parallel_size and pipeline_parallel_size.

Sharding a model across devices divides both the weight bytes each device must read
per decode step and the KV cache each device holds, so it attacks the same bottleneck
quantization does — but it pays in devices rather than in accuracy.

That distinction is the whole reason this specialist exists separately, and it is why
its proposals become inconvenient in Phase 2: a config that needs two cards cannot be
the answer to "can these two models share one card?"
"""

from __future__ import annotations

from ..ledger import Prediction
from .base import Context, Dead, Proposal, Specialist, Verdict

TP_SYNC_COST_PER_RANK = 0.06


class ParallelismSpecialist(Specialist):
    name = "parallelism"
    lever = "parallelism"

    def propose(self, ctx: Context) -> Verdict:
        d = ctx.digest
        cfg = ctx.config
        model = ctx.model

        if d.tp_headroom < 1:
            return Dead(
                self.name,
                self.lever,
                f"tp={cfg.tensor_parallel_size} already uses every available device; "
                "no spare hardware to shard onto",
            )

        target = cfg.tensor_parallel_size * 2
        # Legality is cheap to check and expensive to discover on deployment.
        if model.num_kv_heads % target != 0:
            return Dead(
                self.name,
                self.lever,
                f"tp={target} does not divide num_kv_heads={model.num_kv_heads}; "
                "the next legal degree needs more devices than are free",
            )
        if model.num_attn_heads % target != 0:
            return Dead(
                self.name,
                self.lever,
                f"tp={target} does not divide num_attn_heads={model.num_attn_heads}",
            )
        if target > ctx.available_gpus:
            return Dead(
                self.name,
                self.lever,
                f"tp={target} needs {target} devices, {ctx.available_gpus} available",
            )

        delta = {"tensor_parallel_size": target}
        if ctx.already_tried(delta):
            return Dead(self.name, self.lever, f"tp={target} has already been trialled")

        # The win is a bandwidth division; the cost is a synchronization per step.
        gross = 50.0
        net = gross - (TP_SYNC_COST_PER_RANK * 100 * (target - 1))

        return Proposal(
            specialist=self.name,
            lever=self.lever,
            delta=delta,
            prediction=Prediction(
                metric="p99_latency_ms",
                direction="decrease",
                magnitude_pct=net,
                confidence=0.7,
                rationale=f"tp={target} halves per-device weight and KV bytes per step",
            ),
            rationale=(
                f"Bandwidth utilization is {d.mem_bandwidth_util:.1%} with weights at "
                f"{d.weights_share_of_footprint:.0%} of footprint. Sharding to tp={target} "
                f"divides both the weight read and the KV cache across {target} devices, "
                f"costing roughly {TP_SYNC_COST_PER_RANK:.0%} per extra rank in all-reduce. "
                "Unlike quantization this keeps the numerics intact — but it consumes "
                f"{target} devices, which constrains anything we do about co-tenancy later."
            ),
        )
