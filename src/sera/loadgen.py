"""Turn a declared traffic shape into a concrete request trace, and measurements back out.

The same trace generator feeds the simulator and the real vLLM client, so a config
compared across substrates at least saw the same arrival pattern and the same
prompt-length distribution.

Traces are seeded and deterministic: rerunning a spec reproduces the run exactly,
which is what makes a ledger worth keeping.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .ledger import Measurement
from .spec import Workload


@dataclass(frozen=True)
class Request:
    arrival_s: float
    input_tokens: int
    output_tokens: int
    request_id: int


def generate_trace(workload: Workload, seed: int = 0) -> list[Request]:
    """Build the arrival trace for one workload.

    Arrivals are Poisson when burstiness == 1. Above that, inter-arrival gaps are
    drawn from a Gamma with shape 1/burstiness, which clusters requests into bursts
    at the same mean rate. Bursts matter: a co-tenant's prefill burst is what breaks
    the other model's p95, and averaged-out traffic would hide exactly that.
    """
    rng = np.random.default_rng(seed)
    requests: list[Request] = []

    mean_gap = 1.0 / workload.request_rate_rps
    shape = 1.0 / max(workload.burstiness, 1e-6)
    scale = mean_gap / shape

    t = 0.0
    rid = 0
    while t < workload.duration_s:
        gap = float(rng.gamma(shape, scale)) if workload.burstiness != 1.0 else float(
            rng.exponential(mean_gap)
        )
        t += gap
        if t >= workload.duration_s:
            break
        inp = max(8, int(rng.normal(workload.input_len_mean, workload.input_len_stdev)))
        out = max(1, int(rng.normal(workload.output_len_mean, workload.output_len_stdev)))
        requests.append(Request(arrival_s=t, input_tokens=inp, output_tokens=out, request_id=rid))
        rid += 1

    return requests


@dataclass
class RequestResult:
    """What one request experienced end to end."""

    request_id: int
    arrival_s: float
    first_token_s: float
    completion_s: float
    output_tokens: int
    preempted: bool = False

    @property
    def latency_ms(self) -> float:
        return (self.completion_s - self.arrival_s) * 1000.0

    @property
    def ttft_ms(self) -> float:
        return (self.first_token_s - self.arrival_s) * 1000.0


def summarize(
    results: list[RequestResult],
    footprint_gb: float,
    kv_occupancy: float,
    mem_bandwidth_util: float,
    wall_time_s: float,
) -> Measurement:
    """Collapse a trace of completed requests into the numbers the gates read."""
    if not results:
        return Measurement(
            p50_latency_ms=float("inf"),
            p95_latency_ms=float("inf"),
            throughput_rps=0.0,
            footprint_gb=footprint_gb,
            kv_occupancy=kv_occupancy,
            preemptions=0,
            mem_bandwidth_util=mem_bandwidth_util,
        )

    latencies = np.array([r.latency_ms for r in results])
    return Measurement(
        p50_latency_ms=float(np.percentile(latencies, 50)),
        p95_latency_ms=float(np.percentile(latencies, 95)),
        throughput_rps=len(results) / wall_time_s if wall_time_s > 0 else 0.0,
        footprint_gb=footprint_gb,
        kv_occupancy=kv_occupancy,
        preemptions=sum(1 for r in results if r.preempted),
        mem_bandwidth_util=mem_bandwidth_util,
    )
