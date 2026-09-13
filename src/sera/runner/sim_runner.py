"""An analytic model of continuous batching, good enough to make the loop decide.

This is not a claim to predict absolute H100 latency. It is a claim that the
*mechanisms* which drive tuning decisions are represented, so the loop faces real
tradeoffs rather than a lookup table:

  - decode is memory-bandwidth bound, so quantizing weights genuinely speeds it up
  - prefill is compute bound, so a prefill-heavy workload ignores KV quantization
  - KV capacity caps concurrency, and exhausting it preempts running sequences
  - chunked prefill trades time-to-first-token against decode smoothness
  - tensor parallelism shards weights and KV but pays a per-step sync cost
  - co-tenants contend for one device's time, inflating each other's tails

Co-tenancy is not a penalty multiplier. Both tenants are scheduled against one shared
device clock, and contention falls out of that. It is the same engine for one tenant
or two, which is why a Phase 2 result is comparable to the Phase 1 rows it came from.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field

from ..config import (
    ACHIEVABLE_BW_FRACTION,
    DTYPE_BYTES,
    InferenceConfig,
    kv_cache_gb_per_token,
    weights_gb,
)
from ..ledger import Measurement, Substrate
from ..loadgen import Request, RequestResult, generate_trace, summarize
from ..spec import GpuSpec, ModelSpec
from .base import Tenant, TrialOutcome, TrialRunner

# Fraction of peak tensor-core throughput a real prefill achieves.
PREFILL_MFU = 0.45
# Fraction of peak HBM bandwidth a real decode step achieves. Defined in config.py
# so the reduction's derived-bandwidth estimate divides by the same denominator.
DECODE_BW_EFFICIENCY = ACHIEVABLE_BW_FRACTION
# Per-step all-reduce cost as a fraction of step time, per extra TP rank.
TP_SYNC_OVERHEAD = 0.06
# Compute speedup from low-precision tensor cores, by weight dtype. Weight-only
# formats (int4/awq/gptq) dequantize to bf16 for the matmul, so they buy bandwidth
# but not arithmetic.
COMPUTE_MULTIPLIER = {
    "fp32": 0.5, "bf16": 1.0, "fp16": 1.0,
    "fp8": 1.8, "int8": 1.6,
    "int4": 1.0, "awq": 1.0, "gptq": 1.0,
}
# Hard ceiling on simulated scheduler steps, so a pathological config cannot hang.
MAX_STEPS = 500_000


def _stable_seed(name: str) -> int:
    """Deterministic small integer from a model name, stable across processes."""
    return zlib.crc32(name.encode()) % 10_000


@dataclass
class _Seq:
    """One in-flight sequence inside the simulated scheduler."""

    req: Request
    prefill_remaining: int
    decode_remaining: int
    admitted_s: float
    first_token_s: float | None = None
    preempted: bool = False

    @property
    def kv_tokens(self) -> int:
        """KV currently held: prompt tokens already processed, plus tokens emitted."""
        done_prefill = self.req.input_tokens - self.prefill_remaining
        emitted = self.req.output_tokens - self.decode_remaining
        return done_prefill + emitted


@dataclass
class _TenantState:
    tenant: Tenant
    kv_capacity_tokens: int
    waiting: list[_Seq] = field(default_factory=list)
    running: list[_Seq] = field(default_factory=list)
    done: list[RequestResult] = field(default_factory=list)
    pending: list[Request] = field(default_factory=list)
    preemptions: int = 0
    kv_occupancy_samples: list[float] = field(default_factory=list)
    bw_samples: list[float] = field(default_factory=list)
    # Sequences resident per step. Sampled rather than inferred, because inference
    # from p50 latency is wrong by up to 62% under saturation.
    batch_samples: list[int] = field(default_factory=list)

    @property
    def kv_in_use(self) -> int:
        return sum(s.kv_tokens for s in self.running)


class SimRunner(TrialRunner):
    """Deterministic continuous-batching simulator. Always available."""

    substrate = Substrate.SIM

    def available(self) -> bool:
        return True

    # -- device physics ------------------------------------------------------

    def _prefill_time_s(
        self, model: ModelSpec, cfg: InferenceConfig, gpu: GpuSpec, tokens: int
    ) -> float:
        """Prefill is compute bound: 2 FLOPs per parameter per token."""
        if tokens <= 0:
            return 0.0
        flops = 2.0 * model.params_b * 1e9 * tokens
        peak = gpu.tflops_bf16 * 1e12 * COMPUTE_MULTIPLIER[cfg.weight_dtype] * PREFILL_MFU
        t = flops / peak
        # TP splits the work but adds a sync per step.
        t = t / cfg.tensor_parallel_size
        return t * (1.0 + TP_SYNC_OVERHEAD * (cfg.tensor_parallel_size - 1))

    def _decode_time_s(
        self,
        model: ModelSpec,
        cfg: InferenceConfig,
        gpu: GpuSpec,
        batch_size: int,
        kv_tokens: int,
    ) -> tuple[float, float]:
        """Decode is bandwidth bound: read all weights plus the batch's KV, per step.

        Returns (seconds, bytes_moved). Weight reads are amortized across the batch,
        which is exactly why batching helps decode and why quantization helps more
        at small batch sizes.
        """
        if batch_size <= 0:
            return 0.0, 0.0
        w_bytes = weights_gb(model, cfg) * 1e9
        kv_bytes = kv_cache_gb_per_token(model, cfg) * 1e9 * kv_tokens
        total_bytes = w_bytes + kv_bytes
        eff_bw = gpu.mem_bandwidth_gbs * 1e9 * DECODE_BW_EFFICIENCY
        t = total_bytes / eff_bw
        t = t * (1.0 + TP_SYNC_OVERHEAD * (cfg.tensor_parallel_size - 1))
        return t, total_bytes

    # -- scheduler -----------------------------------------------------------

    def _admit(self, st: _TenantState, now: float) -> None:
        """Move arrived requests into the running batch while capacity allows."""
        cfg = st.tenant.config
        while st.pending and st.pending[0].arrival_s <= now:
            st.waiting.append(
                _Seq(
                    req=st.pending.pop(0),
                    prefill_remaining=0,
                    decode_remaining=0,
                    admitted_s=now,
                )
            )

        while st.waiting and len(st.running) < cfg.max_num_seqs:
            candidate = st.waiting[0]
            needed = candidate.req.input_tokens
            if st.kv_in_use + needed > st.kv_capacity_tokens:
                # Not enough KV. vLLM preempts the most recently admitted sequence
                # and recomputes it later rather than deadlocking.
                if st.running:
                    victim = st.running.pop()
                    victim.prefill_remaining = victim.req.input_tokens
                    victim.decode_remaining = victim.req.output_tokens
                    victim.preempted = True
                    victim.first_token_s = None
                    st.waiting.insert(1, victim)
                    st.preemptions += 1
                    continue
                break
            seq = st.waiting.pop(0)
            seq.prefill_remaining = seq.req.input_tokens
            seq.decode_remaining = seq.req.output_tokens
            seq.admitted_s = now
            st.running.append(seq)

    def _step_demand(self, st: _TenantState, gpu: GpuSpec, now: float) -> tuple[float, float]:
        """Compute this tenant's work for one scheduler step.

        Returns (seconds_of_device_time, bytes_moved) without advancing state.
        """
        cfg, model = st.tenant.config, st.tenant.model
        prefilling = [s for s in st.running if s.prefill_remaining > 0]
        decoding = [s for s in st.running if s.prefill_remaining == 0 and s.decode_remaining > 0]

        prefill_tokens = 0
        if prefilling:
            if cfg.enable_chunked_prefill:
                # Prefill shares the token budget with decodes, so decode keeps
                # ticking during a long prompt. Costs TTFT, protects tail latency.
                budget = max(0, cfg.max_num_batched_tokens - len(decoding))
                for s in prefilling:
                    if budget <= 0:
                        break
                    take = min(s.prefill_remaining, budget)
                    prefill_tokens += take
                    budget -= take
            else:
                # One prompt at a time, in full. Decode stalls behind it.
                prefill_tokens = min(prefilling[0].prefill_remaining, cfg.max_num_batched_tokens)

        t_prefill = self._prefill_time_s(model, cfg, gpu, prefill_tokens)
        decode_batch = len(decoding) if (cfg.enable_chunked_prefill or not prefilling) else 0
        kv_tokens = sum(s.kv_tokens for s in decoding) if decode_batch else 0
        t_decode, bytes_moved = self._decode_time_s(model, cfg, gpu, decode_batch, kv_tokens)

        return t_prefill + t_decode, bytes_moved

    def _apply_step(self, st: _TenantState, gpu: GpuSpec, now: float, step_end: float) -> None:
        """Advance this tenant's sequences by one scheduler step."""
        cfg = st.tenant.config
        prefilling = [s for s in st.running if s.prefill_remaining > 0]
        decoding = [s for s in st.running if s.prefill_remaining == 0 and s.decode_remaining > 0]

        if prefilling:
            if cfg.enable_chunked_prefill:
                budget = max(0, cfg.max_num_batched_tokens - len(decoding))
                for s in prefilling:
                    if budget <= 0:
                        break
                    take = min(s.prefill_remaining, budget)
                    s.prefill_remaining -= take
                    budget -= take
                    if s.prefill_remaining == 0 and s.first_token_s is None:
                        s.first_token_s = step_end
            else:
                s = prefilling[0]
                take = min(s.prefill_remaining, cfg.max_num_batched_tokens)
                s.prefill_remaining -= take
                if s.prefill_remaining == 0 and s.first_token_s is None:
                    s.first_token_s = step_end

        if cfg.enable_chunked_prefill or not prefilling:
            for s in decoding:
                s.decode_remaining -= 1
                if s.first_token_s is None:
                    s.first_token_s = step_end

        finished = [s for s in st.running if s.prefill_remaining == 0 and s.decode_remaining <= 0]
        for s in finished:
            st.running.remove(s)
            st.done.append(
                RequestResult(
                    request_id=s.req.request_id,
                    arrival_s=s.req.arrival_s,
                    first_token_s=s.first_token_s or step_end,
                    completion_s=step_end,
                    output_tokens=s.req.output_tokens,
                    preempted=s.preempted,
                )
            )

        if st.kv_capacity_tokens > 0:
            st.kv_occupancy_samples.append(min(1.0, st.kv_in_use / st.kv_capacity_tokens))
        # Only steps where something was resident. Averaging in the idle tail would
        # report a batch smaller than any batch that ever ran.
        if st.running:
            st.batch_samples.append(len(st.running))

    # -- entry point ---------------------------------------------------------

    def run(self, tenants: list[Tenant], gpu: GpuSpec, seed: int = 0) -> TrialOutcome:
        if not tenants:
            return TrialOutcome({}, self.substrate, ok=False, error="no tenants")

        # Co-tenants divide the card. Each gets its share of VRAM for weights+KV,
        # which is what makes consolidation a memory question before it is a
        # bandwidth question.
        states: list[_TenantState] = []
        for t in tenants:
            share = gpu.usable_vram_gb / len(tenants)
            budget = share * t.config.gpu_memory_utilization - weights_gb(t.model, t.config)
            capacity = max(0, int(budget / kv_cache_gb_per_token(t.model, t.config)))
            if capacity <= 0:
                return TrialOutcome(
                    {}, self.substrate, ok=False,
                    error=f"{t.model.name}: weights exceed its share of {gpu.id}",
                )
            # Stable per-tenant seed. Python's hash() is salted per process, so
            # using it here would make runs irreproducible — which would quietly
            # invalidate every comparison the ledger claims to support.
            trace = generate_trace(t.workload, seed=seed + _stable_seed(t.model.name))
            states.append(
                _TenantState(tenant=t, kv_capacity_tokens=capacity, pending=list(trace))
            )

        horizon = max(t.workload.duration_s for t in tenants)
        now = 0.0
        steps = 0
        total_bytes = 0.0

        while steps < MAX_STEPS:
            steps += 1
            for st in states:
                self._admit(st, now)

            active = [st for st in states if st.running]
            if not active:
                nxt = [st.pending[0].arrival_s for st in states if st.pending]
                if not nxt:
                    break
                now = min(nxt)
                if now > horizon * 3:
                    break
                continue

            # Every active tenant's step executes on the same device, so the step
            # boundary advances by the SUM of their demands. One tenant's prefill
            # burst is therefore felt directly in the other's decode latency.
            demands = [self._step_demand(st, gpu, now) for st in active]
            step_s = sum(d[0] for d in demands)
            total_bytes += sum(d[1] for d in demands)
            if step_s <= 0:
                step_s = 1e-6
            step_end = now + step_s
            for st in active:
                self._apply_step(st, gpu, now, step_end)
            now = step_end

            if now > horizon * 5:
                break  # config cannot keep up with arrivals; report what happened

        wall = max(now, 1e-6)
        eff_bw_capacity = gpu.mem_bandwidth_gbs * 1e9 * DECODE_BW_EFFICIENCY * wall
        bw_util = min(1.0, total_bytes / eff_bw_capacity) if eff_bw_capacity > 0 else 0.0

        measurements: dict[str, Measurement] = {}
        for st in states:
            occ = (
                sum(st.kv_occupancy_samples) / len(st.kv_occupancy_samples)
                if st.kv_occupancy_samples
                else 0.0
            )
            cfg, model = st.tenant.config, st.tenant.model
            footprint = weights_gb(model, cfg) + kv_cache_gb_per_token(model, cfg) * (
                occ * st.kv_capacity_tokens
            )
            m = summarize(st.done, footprint, occ, bw_util, wall)
            m.preemptions = st.preemptions
            m.mean_batch_size = (
                sum(st.batch_samples) / len(st.batch_samples) if st.batch_samples else None
            )
            measurements[model.name] = m

        return TrialOutcome(
            measurements=measurements,
            substrate=self.substrate,
            ok=True,
            notes={
                "steps": str(steps),
                "sim_wall_s": f"{wall:.2f}",
                "tenants": ",".join(t.model.name for t in tenants),
            },
        )
