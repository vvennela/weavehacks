"""Fixed example results, so the product surface can be built before the GPU is.

`demo_result()` is the agreed shape of a finished run. The notebook renders from
it, and the backend targets it: if a real run produces a SeraResult that renders
correctly here, the integration is done.

The numbers are plausible but invented. Nothing in this module measures anything,
and `SeraModel.generate` returns canned text — a fixture-backed model raises
rather than pretending to serve. Do not import this from the GPU path.
"""

from __future__ import annotations

from .config import InferenceConfig
from .ledger import Measurement, Verdict
from .types import (
    FrontierEntry,
    QualityResult,
    Recommendation,
    RejectedCandidate,
    RunState,
    SeraModel,
    SeraResult,
    Trial,
)

MODEL_A = "Qwen/Qwen3-0.6B"
MODEL_B = "zai-org/glm-4-9b-chat-hf"


def _quality(score: float, *, verified: bool = False, floor: float = 0.99) -> QualityResult:
    return QualityResult(
        score=score,
        floor=floor,
        passed=score >= floor,
        verified=verified,
        method="User evaluation" if verified else "Behavior-preservation proxy",
    )


def demo_result() -> SeraResult:
    """One model, quick mode, a real improvement found in six trials.

    This is the happy path the demo tells: baseline is unremarkable, the batching
    specialist's proposal wins, one quantization candidate is rolled back on
    quality, and two candidates never run because they cannot fit.
    """
    baseline_cfg = InferenceConfig(model=MODEL_A)
    winner_cfg = baseline_cfg.with_delta(
        {"max_num_seqs": 512, "max_num_batched_tokens": 16384, "enable_chunked_prefill": True}
    )

    baseline_m = Measurement(
        p50_latency_ms=182.0,
        p95_latency_ms=412.0,
        throughput_rps=22.4,
        footprint_gb=6.8,
        kv_occupancy=0.31,
    )
    winner_m = Measurement(
        p50_latency_ms=121.0,
        p95_latency_ms=268.0,
        throughput_rps=38.9,
        footprint_gb=7.1,
        kv_occupancy=0.62,
    )
    fp8_m = Measurement(
        p50_latency_ms=104.0,
        p95_latency_ms=231.0,
        throughput_rps=44.2,
        footprint_gb=4.3,
        kv_occupancy=0.48,
    )

    quality_pass = _quality(0.997)
    quality_fail = _quality(0.961)

    trials = [
        Trial(
            trial_id="t0",
            phase=1,
            model_id=MODEL_A,
            configuration=baseline_cfg,
            verdict=Verdict.ACCEPTED,
            specialist=None,
            lever=None,
            measurement=baseline_m,
            quality=_quality(1.0),
            note="Baseline.",
        ),
        Trial(
            trial_id="t1",
            phase=1,
            model_id=MODEL_A,
            configuration=winner_cfg,
            verdict=Verdict.ACCEPTED,
            specialist="batching",
            lever="batching",
            measurement=winner_m,
            quality=quality_pass,
            note="Larger batches with chunked prefill cut p95 by 35%.",
        ),
        Trial(
            trial_id="t2",
            phase=1,
            model_id=MODEL_A,
            configuration=baseline_cfg.with_delta({"weight_dtype": "fp8", "kv_cache_dtype": "fp8"}),
            verdict=Verdict.REVERTED_QUALITY,
            specialist="quantization",
            lever="quantization",
            measurement=fp8_m,
            quality=quality_fail,
            note="Fastest candidate measured, but behavior drifted below the floor. Rolled back.",
        ),
        Trial(
            trial_id="t3",
            phase=1,
            model_id=MODEL_A,
            configuration=baseline_cfg.with_delta({"max_num_seqs": 1024}),
            verdict=Verdict.REVERTED_SLO,
            specialist="batching",
            lever="batching",
            measurement=Measurement(
                p50_latency_ms=142.0,
                p95_latency_ms=498.0,
                throughput_rps=41.1,
                footprint_gb=7.9,
                preemptions=37,
            ),
            quality=_quality(0.996),
            note="Throughput rose but tail latency regressed past the baseline.",
        ),
        Trial(
            trial_id="t4",
            phase=1,
            model_id=MODEL_A,
            configuration=baseline_cfg.with_delta({"tensor_parallel_size": 2}),
            verdict=Verdict.FAILED,
            specialist="parallelism",
            lever="parallelism",
            measurement=None,
            quality=None,
            note="Engine failed to start: only one device visible.",
        ),
    ]

    rejected = [
        RejectedCandidate(
            model_id=MODEL_A,
            configuration=baseline_cfg.with_delta({"weight_dtype": "int4"}),
            reason="int4 weights are not supported for this architecture on the installed vLLM build.",
            specialist="quantization",
        ),
        RejectedCandidate(
            model_id=MODEL_A,
            configuration=baseline_cfg.with_delta({"tensor_parallel_size": 4}),
            reason="Tensor parallelism of 4 needs 4 devices; 1 is available.",
            specialist="parallelism",
        ),
    ]

    recommended = Recommendation(
        model_id=MODEL_A,
        configuration=winner_cfg,
        baseline=baseline_m,
        optimized=winner_m,
        quality=quality_pass,
        trials_used=5,
        rationale=(
            "Largest verified latency win. The faster fp8 candidate was rejected "
            "because it failed the quality gate."
        ),
    )

    frontier = [
        FrontierEntry(
            model_id=MODEL_A,
            configuration=winner_cfg,
            measurement=winner_m,
            quality=quality_pass,
            label="Lowest verified latency",
        ),
        FrontierEntry(
            model_id=MODEL_A,
            configuration=baseline_cfg,
            measurement=baseline_m,
            quality=_quality(1.0),
            label="Smallest memory footprint",
        ),
    ]

    models = [
        SeraModel(
            model_id=MODEL_A,
            revision="c1899de289a04d12100db370d81485cdf75e298f",
            configuration=winner_cfg,
            metrics_snapshot=winner_m,
            _generate=lambda prompt: (
                "Paged attention stores the KV cache in fixed-size blocks, so the "
                "engine can serve many requests without reserving contiguous memory "
                "for each one."
            ),
        )
    ]

    return SeraResult(
        state=RunState.IMPROVED,
        models=models,
        recommended=recommended,
        frontier=frontier,
        baselines={MODEL_A: baseline_m},
        trials=trials,
        rejected=rejected,
        report={
            "GPU": "1x NVIDIA L40S (48 GB)",
            "Trial budget": "8 candidates, 5 used",
            "Concurrency sweep": "1, 2, 4, 8",
            "Quality tolerance": "0.99 of baseline",
        },
        weave_url="https://wandb.ai/sera/sera-demo/r/call/0193f2a1-demo",
        mode="quick",
    )


def no_safe_improvement_result() -> SeraResult:
    """The honest-negative path: Sera looked and found nothing safe.

    The product principles commit to reporting this rather than shipping a
    marginal or quality-damaging win, so the notebook has to render it as a
    legitimate outcome and not as a failure.
    """
    baseline_cfg = InferenceConfig(model=MODEL_B)
    baseline_m = Measurement(
        p50_latency_ms=340.0,
        p95_latency_ms=705.0,
        throughput_rps=9.1,
        footprint_gb=19.4,
        kv_occupancy=0.72,
    )

    trials = [
        Trial(
            trial_id="t0",
            phase=1,
            model_id=MODEL_B,
            configuration=baseline_cfg,
            verdict=Verdict.ACCEPTED,
            measurement=baseline_m,
            quality=_quality(1.0),
            note="Baseline.",
        ),
        Trial(
            trial_id="t1",
            phase=1,
            model_id=MODEL_B,
            configuration=baseline_cfg.with_delta({"weight_dtype": "awq"}),
            verdict=Verdict.REVERTED_QUALITY,
            specialist="quantization",
            lever="quantization",
            measurement=Measurement(
                p50_latency_ms=214.0,
                p95_latency_ms=441.0,
                throughput_rps=14.8,
                footprint_gb=11.2,
            ),
            quality=_quality(0.948),
            note="Much faster, but answer quality fell below the floor. Rolled back.",
        ),
        Trial(
            trial_id="t2",
            phase=1,
            model_id=MODEL_B,
            configuration=baseline_cfg.with_delta({"max_num_seqs": 512}),
            verdict=Verdict.REVERTED_SLO,
            specialist="batching",
            lever="batching",
            measurement=Measurement(
                p50_latency_ms=366.0,
                p95_latency_ms=812.0,
                throughput_rps=10.2,
                footprint_gb=20.1,
                preemptions=54,
            ),
            quality=_quality(0.999),
            note="Preemption under load pushed the tail past baseline.",
        ),
    ]

    return SeraResult(
        state=RunState.NO_SAFE_IMPROVEMENT,
        models=[
            SeraModel(
                model_id=MODEL_B,
                revision="8b7d2f1a0c4e5b9d3a6f8c2e1b4d7a9c0e3f5b8d",
                configuration=baseline_cfg,
                metrics_snapshot=baseline_m,
                _generate=lambda prompt: "(baseline configuration, unchanged)",
            )
        ],
        recommended=None,
        frontier=[],
        baselines={MODEL_B: baseline_m},
        trials=trials,
        rejected=[
            RejectedCandidate(
                model_id=MODEL_B,
                configuration=baseline_cfg.with_delta({"tensor_parallel_size": 2}),
                reason="Tensor parallelism of 2 needs 2 devices; 1 is available.",
                specialist="parallelism",
            )
        ],
        report={
            "GPU": "1x NVIDIA L40S (48 GB)",
            "Trial budget": "8 candidates, 3 used",
            "Why no recommendation": "Every faster candidate failed the quality floor or the latency requirement.",
        },
        weave_url="https://wandb.ai/sera/sera-demo/r/call/0193f2a1-negative",
        mode="quick",
    )
