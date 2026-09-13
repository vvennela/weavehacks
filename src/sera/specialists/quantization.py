"""Precision. Owns weight_dtype and kv_cache_dtype.

Decode reads every weight once per step, so at low batch sizes decode speed is very
nearly a bandwidth-over-weight-bytes calculation. That makes this the strongest lever
on a bandwidth-bound workload and a near-irrelevance on a compute-bound one — which
is exactly the distinction the specialist has to make rather than assume.

It is also the only lever that can fail the quality gate, so it predicts latency wins
knowing the eval may take them back.
"""

from __future__ import annotations

from ..ledger import Prediction
from .base import Context, Dead, Proposal, Specialist, Verdict

# Descending precision. Each step buys bandwidth and costs accuracy.
WEIGHT_LADDER = ["bf16", "fp8", "int8", "int4"]
KV_LADDER = ["bf16", "fp8"]

# Below this bandwidth utilization, shrinking weights does not buy meaningful latency.
BANDWIDTH_LIVE_THRESHOLD = 0.35
# Above this KV occupancy, the cache itself is worth shrinking.
KV_PRESSURE_THRESHOLD = 0.50
# Above this prefill share the workload is arithmetic bound, not bandwidth bound.
COMPUTE_BOUND_PREFILL_SHARE = 0.60
# Precisions with native tensor-core support, which speed up prefill as well as decode.
TENSOR_CORE_FORMATS = {"fp8", "int8"}


class QuantizationSpecialist(Specialist):
    name = "quantization"
    lever = "quantization"

    def propose(self, ctx: Context) -> list[Verdict]:
        d = ctx.digest
        cfg = ctx.config

        idx_now = (
            WEIGHT_LADDER.index(cfg.weight_dtype) if cfg.weight_dtype in WEIGHT_LADDER else 0
        )
        next_dtype = (
            WEIGHT_LADDER[idx_now + 1] if idx_now + 1 < len(WEIGHT_LADDER) else None
        )

        # None means neither the substrate nor the roofline derivation could produce a
        # number. Comparing None-as-zero against the threshold would silently conclude
        # "not bandwidth bound" from an absence of evidence, so the bandwidth argument
        # is simply unavailable and the specialist has to make its case on prefill share
        # or cache pressure.
        #
        # A derived figure is real evidence but weaker evidence: it is a roofline
        # computed from measured throughput, accurate to within about 25% of the
        # simulator's physical accounting. Weaker evidence gets a discounted
        # confidence, and a dead reason that says "not established" rather than
        # "ruled out" — a number carrying that much error cannot refute a bottleneck,
        # only fail to demonstrate one.
        bw = d.mem_bandwidth_util
        bandwidth_known = bw is not None
        bandwidth_derived = d.mem_bandwidth_source == "derived"
        bandwidth_bound = bandwidth_known and bw >= BANDWIDTH_LIVE_THRESHOLD
        kv_pressured = d.kv_occupancy >= KV_PRESSURE_THRESHOLD

        # Precision is not only a bandwidth lever. On prefill-dominated traffic the
        # bottleneck is arithmetic, and fp8/int8 execute on native tensor cores at
        # materially higher throughput. Formats that dequantize to bf16 before the
        # matmul (int4, awq, gptq) buy bytes but no arithmetic, so they do not
        # qualify — a distinction worth making, because getting it wrong means
        # proposing int4 for a compute-bound model and watching nothing happen.
        compute_bound = d.prefill_token_share >= COMPUTE_BOUND_PREFILL_SHARE
        tensor_core_gain = next_dtype in TENSOR_CORE_FORMATS
        compute_live = compute_bound and tensor_core_gain and d.p95_slo_ratio > 1.0

        if not bandwidth_bound and not kv_pressured and not compute_live:
            if bandwidth_known and bandwidth_derived:
                why = (
                    f"derived bandwidth utilization {bw:.1%} is below "
                    f"{BANDWIDTH_LIVE_THRESHOLD:.0%} — derived rather than measured, so "
                    "this fails to establish bandwidth pressure rather than ruling it out"
                )
            elif bandwidth_known:
                why = (
                    f"measured bandwidth utilization {bw:.1%} is below "
                    f"{BANDWIDTH_LIVE_THRESHOLD:.0%}"
                )
            else:
                why = (
                    "bandwidth utilization was neither measurable nor derivable, so it "
                    "cannot support a case"
                )
            why += f" and KV occupancy {d.kv_occupancy:.1%} is low"
            if compute_bound and not tensor_core_gain:
                why += (
                    f"; prefill dominates at {d.prefill_token_share:.0%} but the next step "
                    f"({next_dtype}) dequantizes to bf16 for the matmul, so it would buy "
                    "bytes and no arithmetic"
                )
            elif compute_bound and d.p95_slo_ratio <= 1.0:
                why += "; prefill dominates but latency is already inside SLO"
            return [Dead(self.name, self.lever, why + " — shrinking tensors buys little here")]

        out: list[Verdict] = []

        # Cache precision and weight precision are separate bets with separate risks,
        # so when both are live they are offered as two candidates rather than one
        # merged config. The arbiter decides which is worth a slot.
        # Offered whenever the lever is live at all, not only under cache pressure.
        # Halving KV element size is cheap, independent of what the weights are doing,
        # and carries a different quality risk — it degrades attention history rather
        # than the parameters. Withholding it until the cache is nearly full meant this
        # specialist only ever had one thing to say, which left the arbiter nothing to
        # rank and nothing to explore.
        if cfg.kv_cache_dtype in KV_LADDER[:-1]:
            nxt = KV_LADDER[KV_LADDER.index(cfg.kv_cache_dtype) + 1]
            delta = {"kv_cache_dtype": nxt}
            if not ctx.already_tried(delta):
                out.append(Proposal(
                    specialist=self.name,
                    lever=self.lever,
                    delta=delta,
                    prediction=Prediction(
                        metric="footprint_gb",
                        direction="decrease",
                        magnitude_pct=40.0,
                        confidence=0.7,
                        rationale=f"KV at {d.kv_occupancy:.0%}; halving cache element size",
                    ),
                    rationale=(
                        f"KV occupancy is {d.kv_occupancy:.1%}. Moving the cache to {nxt} "
                        "halves per-token cost and raises the concurrency ceiling without "
                        "touching the weights, so it is a separate bet from weight "
                        "precision and carries a different quality risk — degraded "
                        "attention history rather than degraded parameters."
                    ),
                ))

        idx = idx_now
        if idx >= len(WEIGHT_LADDER) - 1:
            if out:
                return out
            return [Dead(
                self.name,
                self.lever,
                f"already at {cfg.weight_dtype}, the most aggressive supported precision",
            )]

        nxt = WEIGHT_LADDER[idx + 1]
        delta = {"weight_dtype": nxt}
        if ctx.already_tried(delta):
            # Skip ahead rather than repeat a spent trial.
            if idx + 2 < len(WEIGHT_LADDER):
                nxt = WEIGHT_LADDER[idx + 2]
                delta = {"weight_dtype": nxt}
                if ctx.already_tried(delta):
                    return out or [Dead(
                        self.name, self.lever, "every precision step has been tried"
                    )]
            else:
                return out or [Dead(
                    self.name, self.lever, "every precision step has been tried"
                )]

        # The argument differs by which bottleneck is actually live, and so does the
        # size of the claim. Saying "45% off" when the mechanism does not apply is how
        # a specialist loses calibration and, with it, its share of the budget.
        if bandwidth_bound:
            mechanism = (
                f"Bandwidth utilization is {bw:.1%} ({d.mem_bandwidth_source}) and weights "
                f"are {d.weights_share_of_footprint:.0%} of the footprint at "
                f"{d.weight_bytes_per_param:.0f} bytes/param. Every decode step re-reads the "
                f"full weight tensor, so {cfg.weight_dtype} to {nxt} cuts the bytes that "
                "step must move."
            )
            # The size of the win does not depend on how we learned we are in this
            # regime — halving weight bytes halves the bytes a decode step moves either
            # way, and the derivation understates traffic, so if anything it understates
            # the win. What the weaker evidence buys is less certainty that we are in
            # the regime at all, which is what confidence means. Discounting magnitude
            # instead would corrupt the calibration signal: the ledger would score the
            # specialist as over-delivering and reward a claim it hedged.
            expected = 45.0
            confidence = 0.6 if bandwidth_derived else 0.75
            if bandwidth_derived:
                mechanism += (
                    " That utilization was not read from a counter — no serving engine "
                    "exposes one — but derived from measured throughput against the "
                    "declared weight and cache shapes, so it is a floor on the real "
                    "figure. Confidence is discounted accordingly; the expected "
                    "magnitude is not, because the mechanism is unchanged."
                )
        else:
            mechanism = (
                f"Prefill is {d.prefill_token_share:.0%} of tokens and p95 is "
                f"{d.p95_slo_ratio:.2f}x SLO, so this is compute bound rather than "
                + (
                    f"bandwidth bound — {d.mem_bandwidth_source} utilization is only "
                    f"{bw:.1%}. "
                    if bandwidth_known
                    else "bandwidth bound, and bandwidth was neither measurable nor "
                    "derivable here. "
                )
                + f"{nxt} runs on native tensor cores at materially higher throughput, so "
                "the win here is arithmetic, not bytes."
            )
            expected, confidence = 40.0, 0.6

        out.append(Proposal(
            specialist=self.name,
            lever=self.lever,
            delta=delta,
            prediction=Prediction(
                metric="p95_latency_ms",
                direction="decrease",
                magnitude_pct=expected,
                confidence=confidence,
                rationale=(
                    f"{'bandwidth' if bandwidth_bound else 'tensor-core throughput'} "
                    f"at {nxt}"
                ),
            ),
            rationale=(
                mechanism
                + f" Expect roughly {expected:.0f}% off p95, and expect the eval to decide "
                "whether it is keepable."
            ),
        ))
        return out
