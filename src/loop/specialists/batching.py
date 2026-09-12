"""Scheduling. Owns max_num_seqs, max_num_batched_tokens, enable_chunked_prefill.

The interesting judgement here is knowing when to say nothing. If concurrency never
approaches the sequence cap and no request is being preempted, the batch size is not
what is slowing anything down, and spending a trial slot to prove that is waste.

Where this lever does earn its slot is prefill blocking: without chunked prefill a
long prompt monopolizes a scheduler step and every decoding sequence stalls behind it.
That shows up as tail latency, not mean latency, which is why it hides from averages.
"""

from __future__ import annotations

from ..ledger import Prediction
from .base import Context, Dead, Proposal, Specialist, Verdict

# Concurrency below this fraction of the cap means the cap is not binding.
SLOT_PRESSURE_THRESHOLD = 0.80
# Any meaningful preemption rate means the scheduler is thrashing.
PREEMPTION_THRESHOLD = 0.02
# Prefill share above this makes prefill blocking the plausible tail-latency cause.
PREFILL_HEAVY_THRESHOLD = 0.55


class BatchingSpecialist(Specialist):
    name = "batching"
    lever = "batching"

    def propose(self, ctx: Context) -> Verdict:
        d = ctx.digest
        cfg = ctx.config

        # Thrashing first: preemption means the admission policy is over-committing.
        if d.preemption_rate > PREEMPTION_THRESHOLD:
            new_seqs = max(8, cfg.max_num_seqs // 2)
            delta = {"max_num_seqs": new_seqs}
            if not ctx.already_tried(delta):
                return Proposal(
                    specialist=self.name,
                    lever=self.lever,
                    delta=delta,
                    prediction=Prediction(
                        metric="p99_latency_ms",
                        direction="decrease",
                        magnitude_pct=20.0,
                        confidence=0.7,
                        rationale=f"{d.preemption_rate:.3f} preemptions/request indicates over-admission",
                    ),
                    rationale=(
                        f"The scheduler is preempting {d.preemption_rate:.3f} times per request, "
                        f"so it is admitting more sequences than KV can hold and paying to "
                        f"recompute them. Cutting max_num_seqs to {new_seqs} trades peak "
                        "concurrency for work that does not get thrown away."
                    ),
                )

        # Prefill blocking: the classic cause of a bad tail with a fine median.
        prefill_heavy = d.prefill_token_share >= PREFILL_HEAVY_THRESHOLD
        breaching = d.p99_slo_ratio > 1.0
        if prefill_heavy and breaching and not cfg.enable_chunked_prefill:
            token_budget = max(512, ctx.model.max_model_len // 4)
            delta = {
                "enable_chunked_prefill": True,
                "max_num_batched_tokens": token_budget,
            }
            if not ctx.already_tried(delta):
                return Proposal(
                    specialist=self.name,
                    lever=self.lever,
                    delta=delta,
                    prediction=Prediction(
                        metric="p99_latency_ms",
                        direction="decrease",
                        magnitude_pct=35.0,
                        confidence=0.65,
                        rationale="chunked prefill stops long prompts from monopolizing steps",
                    ),
                    rationale=(
                        f"Prefill is {d.prefill_token_share:.0%} of tokens and p99 is "
                        f"{d.p99_slo_ratio:.2f}x SLO while the median is healthier — the "
                        "signature of decode stalling behind whole-prompt prefill steps. "
                        f"Chunking at {token_budget} tokens interleaves the two so decoding "
                        "sequences keep progressing. It costs time-to-first-token."
                    ),
                )

        # Genuine headroom pressure: the cap itself is the limit.
        if d.seq_slot_utilization >= SLOT_PRESSURE_THRESHOLD:
            new_seqs = cfg.max_num_seqs * 2
            delta = {"max_num_seqs": new_seqs}
            if not ctx.already_tried(delta):
                return Proposal(
                    specialist=self.name,
                    lever=self.lever,
                    delta=delta,
                    prediction=Prediction(
                        metric="throughput_rps",
                        direction="increase",
                        magnitude_pct=15.0,
                        confidence=0.6,
                        rationale=f"slot utilization {d.seq_slot_utilization:.0%} is at the cap",
                    ),
                    rationale=(
                        f"In-flight concurrency is {d.seq_slot_utilization:.0%} of max_num_seqs, "
                        f"so the cap is throttling admission. Raising it to {new_seqs} lets the "
                        "batch grow, which also amortizes the weight read across more tokens."
                    ),
                )

        return Dead(
            self.name,
            self.lever,
            f"sequence slots are {d.seq_slot_utilization:.0%} utilized with "
            f"{d.preemption_rate:.3f} preemptions/request"
            + (
                ""
                if not cfg.enable_chunked_prefill
                else " and chunked prefill is already on"
            )
            + " — the batch is not the constraint here",
        )
