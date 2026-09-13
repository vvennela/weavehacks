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
    ACHIEVABLE_BW_FRACTION,
    DTYPE_BYTES,
    InferenceConfig,
    kv_cache_gb_per_token,
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
    mem_bandwidth_util: float | None  # 0-1 fraction of HBM bandwidth, or None if unknown
    mem_bandwidth_source: str         # "measured" | "derived" | "unavailable"
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
            (
                f"Memory bandwidth utilization is {self.mem_bandwidth_util:.1%} "
                f"({self.mem_bandwidth_source})."
                if self.mem_bandwidth_util is not None
                else "Memory bandwidth utilization was not measurable on this "
                "substrate and could not be derived — treat it as unknown, not as idle."
            ),
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


def derive_bandwidth_util(
    measurement: Measurement,
    cfg: InferenceConfig,
    model: ModelSpec,
    gpu: GpuSpec,
    workload: Workload,
) -> float | None:
    """Estimate HBM utilization from measured throughput and declared shapes.

    vLLM exposes no bandwidth counter and NVML's memory-controller utilization is
    unavailable in most containers, so on real hardware `Measurement.mem_bandwidth_util`
    is almost always None. That absence has a measured cost: with no bandwidth evidence
    the quantization specialist cannot make its case, and a decode-bound model gets zero
    proposals and never improves. That happened in the fake-vLLM run, to glm4_9b.

    Spec 10.4 forbids replacing a missing measurement with an *agent estimate*. This is
    not one. Every input is either measured by the trial (throughput, p50) or declared
    in the spec (parameter count, layer shape, device bandwidth), and the arithmetic is
    the same roofline every serving engineer does by hand:

        per decode step, one device reads its whole weight shard once, plus the KV
        history of every sequence in the batch.

        steps/s        = generated tokens/s / mean resident batch
        weight traffic = weight bytes (per device) x steps/s
        KV traffic     = KV bytes/token (per device) x mean context x generated tokens/s
        utilization    = (weight + KV traffic) / device achievable bandwidth

    The error is two-sided, and it was tempting to claim otherwise. Excluding prefill
    traffic biases the estimate low. But batch size comes from Little's law using p50
    latency, and on a right-skewed latency distribution p50 understates mean residency,
    which understates the batch, which overstates steps/s and so overstates traffic.
    Those two pull opposite ways and neither dominates by construction.

    So the honest claim is an empirical one, and `test_bandwidth_derivation.py` pins it:
    swept across the whole lever space against the simulator — which models bandwidth
    physically and therefore serves as ground truth — the derived figure lands within
    25% of the simulated one, and on the larger, decode-dominated model within 10%. One
    config in that sweep overshoots by 16%.

    An overshoot can make the quantization specialist argue bandwidth pressure that is
    not there. That is a tolerable failure and not a silent one: the cost is a single
    trial slot, the prediction is recorded as MISSED, and the specialist's calibration
    drops, which is exactly the mechanism that is supposed to handle a specialist whose
    evidence is shakier than it thinks. Pretending to a guarantee the arithmetic does
    not support would be the worse trade.

    Callers must record the result as derived, never as measured — the two are
    different grades of evidence and the specialists price them differently.

    Returns None when the trial produced nothing to reason from.
    """
    if measurement.throughput_rps <= 0 or measurement.p50_latency_ms <= 0:
        return None
    if gpu.mem_bandwidth_gbs <= 0 or workload.output_len_mean <= 0:
        return None

    gen_tokens_per_s = measurement.throughput_rps * workload.output_len_mean

    # Prefer the batch the substrate actually observed. vLLM publishes
    # `vllm:num_requests_running` and the simulator counts its own resident sequences,
    # so on both substrates this is a sampled quantity rather than an inferred one.
    #
    # The fallback is Little's law on the served stream, and it is a poor one: p50
    # understates mean residency whenever the latency distribution is right-skewed,
    # which understates the batch, which overstates steps/s and therefore traffic.
    # Measured against the simulator that error reached 62% on a saturated workload —
    # which is why the sampled figure exists at all, and why a substrate that cannot
    # sample it gets a visibly worse estimate rather than a silently worse one.
    if measurement.mean_batch_size is not None and measurement.mean_batch_size > 0:
        batch = measurement.mean_batch_size
    else:
        residency_s = measurement.p50_latency_ms / 1000.0
        batch = measurement.throughput_rps * residency_s
    # A batch larger than the configured ceiling is not something the engine can run.
    batch = min(max(batch, 1.0), float(cfg.max_num_seqs))

    decode_steps_per_s = gen_tokens_per_s / batch

    # Both of these are already per-device: they divide by tensor_parallel_size.
    weight_bytes = weights_gb(model, cfg) * 1e9
    kv_bytes_per_token = kv_cache_gb_per_token(model, cfg) * 1e9

    # A sequence mid-flight has its prompt plus, on average, half its output decoded.
    mean_context_tokens = workload.input_len_mean + workload.output_len_mean / 2.0

    weight_traffic = weight_bytes * decode_steps_per_s
    kv_traffic = kv_bytes_per_token * mean_context_tokens * gen_tokens_per_s

    # Against ACHIEVABLE bandwidth, not the spec sheet — the same denominator the
    # simulator divides by. Utilization is only comparable across substrates if the
    # thing it is a fraction OF is the same thing.
    achievable_bytes_per_s = gpu.mem_bandwidth_gbs * 1e9 * ACHIEVABLE_BW_FRACTION
    # Clamped at 1.0: past saturation the roofline stops being informative, and the
    # honest reading of ">100%" is "saturated", not "180% utilized".
    return min(1.0, (weight_traffic + kv_traffic) / achievable_bytes_per_s)


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

    # Prefer what the substrate measured; fall back to the roofline derivation rather
    # than leaving the strongest specialist with nothing to argue from. Which one was
    # used travels with the digest, so a derived number is never mistaken for a probe.
    bw = measurement.mem_bandwidth_util
    bw_source = "measured"
    if bw is None:
        bw = derive_bandwidth_util(measurement, cfg, model, gpu, workload)
        bw_source = "derived" if bw is not None else "unavailable"

    cur_bytes = DTYPE_BYTES[cfg.weight_dtype]
    min_bytes = min(DTYPE_BYTES[d] for d in ("int4", "fp8", "int8", "bf16"))
    quant_headroom = max(0.0, 1.0 - (min_bytes / cur_bytes))

    w_gb = weights_gb(model, cfg)
    kv_gb = max(measurement.footprint_gb - w_gb, 0.0)
    weights_share = w_gb / max(w_gb + kv_gb, 1e-9)

    return Digest(
        model=model.name,
        kv_occupancy=measurement.kv_occupancy,
        mem_bandwidth_util=bw,
        mem_bandwidth_source=bw_source,
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
