"""Does the derived bandwidth figure agree with a substrate that models bandwidth?

vLLM exposes no bandwidth counter, so on real hardware `Measurement.mem_bandwidth_util`
is None and the quantization specialist — the strongest lever in the system — has
nothing to argue from. `derive_bandwidth_util` fills that gap with a roofline computed
from measured throughput and declared shapes.

A derivation nobody checks is just an assumption with arithmetic on it. The simulator
accumulates bytes moved per step and divides by achievable bandwidth, so it can be
checked against.

Be clear about what that check is worth. The simulator and the derivation share
`config.py`'s weight and KV arithmetic, and the simulator's per-step accumulation is the
same roofline the derivation evaluates in aggregate. So agreement here says the
aggregation is right — that steps/s, mean context and the batch are being combined
correctly — and says nothing about whether a roofline describes a real GPU. This is a
consistency check, not a validation against hardware.

It still earns its place: it caught a 62% error. The batch was originally inferred from
p50 latency via Little's law, which collapses under saturation; sampling the resident
batch from the substrate instead took the worst case from 62% to 2.3%. That bug was
invisible to every other test in the suite.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from sera.config import ACHIEVABLE_BW_FRACTION, InferenceConfig, baseline_config
from sera.ledger import Measurement
from sera.reduction import derive_bandwidth_util, reduce_metrics
from sera.runner.base import Tenant
from sera.runner.sim_runner import SimRunner
from sera.spec import GpuSpec, ModelSpec, Slo, Workload

GPU = GpuSpec(
    id="gpu0",
    name="RTX PRO 6000 Blackwell",
    vram_gb=96.0,
    mem_bandwidth_gbs=1792.0,
    tflops_bf16=503.0,
)

SMALL = ModelSpec(
    name="small",
    hf_id="fake/small",
    params_b=0.6,
    num_layers=28,
    hidden_size=1024,
    num_attn_heads=16,
    num_kv_heads=8,
    max_model_len=4096,
    head_dim_override=128,
)

LARGE = ModelSpec(
    name="large",
    hf_id="fake/large",
    params_b=9.4,
    num_layers=40,
    hidden_size=4096,
    num_attn_heads=32,
    num_kv_heads=2,
    max_model_len=4096,
)


def _workload(model: str) -> Workload:
    return Workload(
        model=model,
        request_rate_rps=4.0,
        input_len_mean=256,
        input_len_stdev=32,
        output_len_mean=256,
        output_len_stdev=32,
        duration_s=20,
    )


def _variants(model: ModelSpec) -> dict[str, InferenceConfig]:
    """One config per lever position, so the sweep covers the space the loop moves in."""
    base = baseline_config(model)
    return {
        "baseline": base,
        "fp8_weights": replace(base, weight_dtype="fp8"),
        "int8_weights": replace(base, weight_dtype="int8"),
        "int4_weights": replace(base, weight_dtype="int4"),
        "fp8_kv": replace(base, kv_cache_dtype="fp8"),
        "seqs_16": replace(base, max_num_seqs=16),
        "seqs_1024": replace(base, max_num_seqs=1024),
        "chunked_prefill": replace(base, enable_chunked_prefill=True),
    }


def _sweep(model: ModelSpec) -> list[tuple[str, float, float]]:
    runner = SimRunner()
    wl = _workload(model.name)
    out = []
    for label, cfg in _variants(model).items():
        result = runner.run([Tenant(model, cfg, wl)], GPU, seed=7)
        m = result.measurements[model.name]
        simulated = m.mem_bandwidth_util
        derived = derive_bandwidth_util(m, cfg, model, GPU, wl)
        assert simulated is not None and derived is not None
        out.append((label, simulated, derived))
    return out


@pytest.mark.parametrize("model,tolerance", [(SMALL, 0.05), (LARGE, 0.02)])
def test_derivation_tracks_the_simulated_bandwidth(model: ModelSpec, tolerance: float) -> None:
    """Within 5% on the small model, 2% on the decode-dominated one.

    Measured worst cases are 2.3% and 0.6%; the tolerances leave roughly 2x headroom
    for seed and platform drift. They are deliberately tight — loose ones would have
    passed the Little's-law version that was 62% wrong.

    The small model gets the looser bound honestly: at 0.6B parameters the weight term
    is small enough that residual error in mean context length still moves the answer.
    On the 9.4B model weights dominate and everything else is rounding.
    """
    for label, simulated, derived in _sweep(model):
        rel = abs(derived - simulated) / max(simulated, 1e-9)
        assert rel <= tolerance, (
            f"{model.name}/{label}: derived {derived:.3f} vs simulated {simulated:.3f} "
            f"({rel:.1%} off, tolerance {tolerance:.0%})"
        )


def test_derivation_ranks_configs_the_same_way_the_simulator_does() -> None:
    """Agreement on the ordering matters more than agreement on the value.

    The specialist reads the figure against a threshold, so what has to survive is
    the relative picture: a config the simulator says moves more bytes must not come
    back from the derivation as the quieter one.
    """
    rows = _sweep(LARGE)
    by_sim = [label for label, sim, _ in sorted(rows, key=lambda r: r[1])]
    by_derived = [label for label, _, der in sorted(rows, key=lambda r: r[2])]
    # Compare the extremes rather than the whole permutation: configs that sit within
    # noise of each other may legitimately swap, but the busiest and quietest must not.
    assert by_sim[0] == by_derived[0], f"quietest config disagrees: {by_sim} vs {by_derived}"
    assert by_sim[-1] == by_derived[-1], f"busiest config disagrees: {by_sim} vs {by_derived}"


def test_quantizing_weights_lowers_the_derived_figure_at_fixed_throughput() -> None:
    """The mechanism the specialist argues from, isolated.

    Holding the measurement fixed and only halving weight precision must lower derived
    traffic. If this ever inverts, the specialist is arguing from a number that moves
    the wrong way and every proposal it makes is backwards.
    """
    wl = _workload(LARGE.name)
    m = Measurement(
        p50_latency_ms=400.0,
        p95_latency_ms=800.0,
        throughput_rps=3.5,
        footprint_gb=18.8,
        kv_occupancy=0.2,
        mean_batch_size=8.0,
    )
    base = baseline_config(LARGE)
    bf16 = derive_bandwidth_util(m, base, LARGE, GPU, wl)
    fp8 = derive_bandwidth_util(m, replace(base, weight_dtype="fp8"), LARGE, GPU, wl)
    assert bf16 is not None and fp8 is not None
    assert fp8 < bf16


def test_unmeasurable_inputs_yield_none_not_zero() -> None:
    """No traffic served means no basis for an estimate.

    Returning 0.0 here would read to the specialist as "bandwidth is idle", which is
    the precise confusion the None-valued field exists to prevent — reintroducing it
    inside the fallback would defeat the point of having the fallback.
    """
    wl = _workload(LARGE.name)
    cfg = baseline_config(LARGE)
    dead = Measurement(
        p50_latency_ms=float("inf"),
        p95_latency_ms=float("inf"),
        throughput_rps=0.0,
        footprint_gb=18.8,
    )
    assert derive_bandwidth_util(dead, cfg, LARGE, GPU, wl) is None


def test_digest_labels_where_the_number_came_from() -> None:
    """A measured figure and a derived one must never be indistinguishable downstream."""
    wl = _workload(LARGE.name)
    slo = Slo(model=LARGE.name, p95_latency_ms=450.0, min_throughput_rps=3.0)
    cfg = baseline_config(LARGE)
    common = dict(p50_latency_ms=400.0, p95_latency_ms=800.0, throughput_rps=3.5,
                  footprint_gb=18.8, kv_occupancy=0.2)

    measured = reduce_metrics(
        Measurement(**common, mem_bandwidth_util=0.42), cfg, LARGE, GPU, wl, slo
    )
    assert measured.mem_bandwidth_source == "measured"
    assert measured.mem_bandwidth_util == 0.42
    assert "measured" in " ".join(measured.interpret())

    fallback = reduce_metrics(
        Measurement(**common, mem_bandwidth_util=None), cfg, LARGE, GPU, wl, slo
    )
    assert fallback.mem_bandwidth_source == "derived"
    assert fallback.mem_bandwidth_util is not None
    assert "derived" in " ".join(fallback.interpret())


def test_nothing_to_derive_from_reports_unavailable() -> None:
    wl = _workload(LARGE.name)
    slo = Slo(model=LARGE.name, p95_latency_ms=450.0, min_throughput_rps=3.0)
    cfg = baseline_config(LARGE)
    d = reduce_metrics(
        Measurement(p50_latency_ms=0.0, p95_latency_ms=0.0, throughput_rps=0.0,
                    footprint_gb=18.8, mem_bandwidth_util=None),
        cfg, LARGE, GPU, wl, slo,
    )
    assert d.mem_bandwidth_source == "unavailable"
    assert d.mem_bandwidth_util is None
    assert "could not be derived" in " ".join(d.interpret())


def test_both_substrates_divide_by_the_same_denominator() -> None:
    """The simulator and the reduction must mean the same thing by '80% utilized'.

    They used to differ: the simulator divided by achievable bandwidth, the derivation
    by the spec sheet, a silent 20% disagreement feeding one shared threshold.
    """
    from sera.runner import sim_runner

    assert sim_runner.DECODE_BW_EFFICIENCY == ACHIEVABLE_BW_FRACTION
