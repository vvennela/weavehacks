"""Serving measurements in, a dozen named numbers out. No LLM anywhere in this file.

Every specialist argues from this same digest. That matters more than it sounds: if
each agent computed its own view of the evidence, disagreements between them would be
disagreements about arithmetic rather than about strategy, and the arbiter would have
no basis for choosing. One reduction, one shared set of facts, three interpretations.

Each scalar is named for what it tells you, and `interpret()` turns the numbers into
short factual statements so an LLM-backed specialist reasons over evidence rather than
re-deriving ratios and getting them wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from .config import (
    DTYPE_BYTES,
    InferenceConfig,
    kv_cache_gb_per_token,
    max_concurrent_tokens,
    weights_gb,
)
from .ledger import Measurement
from .spec import GpuSpec, ModelSpec, Slo, Workload


@dataclass
class Digest:
    """Derived scalars describing where a configuration is actually spending itself."""

    model: str

    # Where is the pressure?
    kv_occupancy: float               # 0-1, fraction of KV cache in use
    mem_bandwidth_util: float         # 0-1, fraction of HBM bandwidth consumed
    preemption_rate: float            # preemptions per completed request
    seq_slot_utilization: float       # 0-1, concurrency vs max_num_seqs

    # How far from the requirements?
    p95_slo_ratio: float              # measured p95 / SLO. >1 means breaching.
    throughput_deficit_rps: float     # demanded rps minus served rps. >0 means falling behind.

    # What shape is the work?
    prefill_token_share: float        # 0-1, prefill tokens / all tokens in the workload
    decode_steps_per_request: float

    # What room is left in each lever?
    weight_bytes_per_param: float     # current precision, in bytes
    quantization_headroom: float      # 1 - (min possible bytes / current bytes)
    weights_share_of_footprint: float # 0-1, weights vs weights+KV
    tp_headroom: int                  # additional devices this model could shard across

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def interpret(self) -> list[str]:
        """Plain statements of fact for the specialists to reason over.

        Deliberately does not recommend anything — naming the bottleneck is the
        specialists' job, and pre-chewing it would collapse three perspectives into one.
        """
        out = [
            f"KV cache occupancy is {self.kv_occupancy:.1%}.",
            f"Memory bandwidth utilization is {self.mem_bandwidth_util:.1%}.",
            f"Sequence slot utilization is {self.seq_slot_utilization:.1%} of max_num_seqs.",
            f"Preemptions per request: {self.preemption_rate:.3f}.",
            f"Measured p95 is {self.p95_slo_ratio:.2f}x the SLO"
            + (" (BREACHING)." if self.p95_slo_ratio > 1.0 else " (within budget)."),
            f"Prefill accounts for {self.prefill_token_share:.1%} of tokens processed; "
            f"each request decodes {self.decode_steps_per_request:.0f} steps.",
            f"Weights are {self.weights_share_of_footprint:.1%} of the memory footprint "
            f"at {self.weight_bytes_per_param:.1f} bytes/param.",
        ]
        if self.throughput_deficit_rps > 0.05:
            out.append(
                f"Serving is {self.throughput_deficit_rps:.2f} rps behind offered load — "
                "the queue is growing."
            )
        if self.tp_headroom > 0:
            out.append(f"{self.tp_headroom} additional device(s) are free for sharding.")
        else:
            out.append("No spare devices; tensor parallelism cannot grow.")
        return out


def reduce_metrics(
    measurement: Measurement,
    cfg: InferenceConfig,
    model: ModelSpec,
    gpu: GpuSpec,
    workload: Workload,
    slo: Slo,
    available_gpus: int = 1,
) -> Digest:
    """Compute the shared digest. Pure function of its inputs."""
    completed = max(measurement.throughput_rps * workload.duration_s, 1.0)

    # Workload shape. Prefill share is a property of the traffic, not the config —
    # it is why a prompt-heavy tenant ignores KV quantization advice.
    total_prefill = workload.input_len_mean
    total_decode = workload.output_len_mean
    prefill_share = total_prefill / max(total_prefill + total_decode, 1)

    # Concurrency the workload actually demands, by Little's law: in-flight requests
    # equal arrival rate times mean residency.
    mean_latency_s = measurement.p50_latency_ms / 1000.0
    demanded_concurrency = workload.request_rate_rps * mean_latency_s
    seq_slot_util = min(1.0, demanded_concurrency / max(cfg.max_num_seqs, 1))

    cur_bytes = DTYPE_BYTES[cfg.weight_dtype]
    min_bytes = min(DTYPE_BYTES[d] for d in ("int4", "fp8", "int8", "bf16"))
    quant_headroom = max(0.0, 1.0 - (min_bytes / cur_bytes))

    w_gb = weights_gb(model, cfg)
    kv_gb = max(measurement.footprint_gb - w_gb, 0.0)
    weights_share = w_gb / max(w_gb + kv_gb, 1e-9)

    return Digest(
        model=model.name,
        kv_occupancy=measurement.kv_occupancy,
        mem_bandwidth_util=measurement.mem_bandwidth_util,
        preemption_rate=measurement.preemptions / completed,
        seq_slot_utilization=seq_slot_util,
        p95_slo_ratio=measurement.p95_latency_ms / max(slo.p95_latency_ms, 1e-9),
        throughput_deficit_rps=max(
            0.0, workload.request_rate_rps - measurement.throughput_rps
        ),
        prefill_token_share=prefill_share,
        decode_steps_per_request=float(workload.output_len_mean),
        weight_bytes_per_param=cur_bytes,
        quantization_headroom=quant_headroom,
        weights_share_of_footprint=weights_share,
        tp_headroom=max(0, available_gpus - cfg.tensor_parallel_size),
    )
