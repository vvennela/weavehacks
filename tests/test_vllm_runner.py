"""The vLLM runner, exercised against a fake server.

Specification §22.2 asks for exactly two of these: "vLLM process manager against a
fake server" and "Metrics parser against saved vLLM output". No GPU, no weights, no
vllm install — the fake presents the same HTTP surface, so the client path under test
is the real one.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from sera.config import baseline_config
from sera.runner.base import Tenant
from sera.runner.fake_vllm import (
    FakeEngineProfile,
    FakeVllmServer,
    fake_launcher,
)
from sera.runner.vllm_runner import (
    UnsupportedConfig,
    VllmRunner,
    parse_prometheus,
    vllm_flags,
)
from sera.spec import load_spec

SPEC = "specs/molab.yaml"


@pytest.fixture(scope="module")
def spec():
    return load_spec(SPEC)


def _short(workload, seconds=2, rps=5.0):
    """Shrink a workload so a test is seconds, not minutes."""
    return replace(workload, duration_s=seconds, request_rate_rps=rps)


# ---- config -> flags. Pure; no server involved. ---------------------------


def test_flags_carry_the_real_repo_not_the_logical_name(spec):
    """InferenceConfig.model is the spec's label; --model must be the HF repo."""
    m = spec.model("qwen3_06b")
    args = vllm_flags(m, baseline_config(m), spec.gpu("gpu0"), 8000)
    assert args[:3] == ["vllm", "serve", "Qwen/Qwen3-0.6B"]
    assert "--served-model-name" in args
    assert args[args.index("--served-model-name") + 1] == "qwen3_06b"


def test_gpu_memory_utilization_is_divided_between_co_tenants(spec):
    """vLLM's flag is a fraction of the whole card. Two tenants at 0.9 would ask 180%."""
    m = spec.model("qwen3_06b")
    cfg = baseline_config(m)
    solo = vllm_flags(m, cfg, spec.gpu("gpu0"), 8000, n_tenants=1)
    pair = vllm_flags(m, cfg, spec.gpu("gpu0"), 8000, n_tenants=2)
    solo_v = float(solo[solo.index("--gpu-memory-utilization") + 1])
    pair_v = float(pair[pair.index("--gpu-memory-utilization") + 1])
    assert solo_v == pytest.approx(cfg.gpu_memory_utilization)
    assert pair_v == pytest.approx(cfg.gpu_memory_utilization / 2)


def test_dtype_and_quantization_take_different_flags(spec):
    m = spec.model("qwen3_06b")
    base = baseline_config(m)
    bf16 = vllm_flags(m, base, spec.gpu("gpu0"), 8000)
    assert "--dtype" in bf16 and bf16[bf16.index("--dtype") + 1] == "bfloat16"
    assert "--quantization" not in bf16

    fp8 = vllm_flags(m, base.with_delta({"weight_dtype": "fp8"}), spec.gpu("gpu0"), 8000)
    assert "--quantization" in fp8 and fp8[fp8.index("--quantization") + 1] == "fp8"


def test_int4_is_refused_rather_than_silently_served_as_bf16(spec):
    """The validator allows int4; vLLM cannot apply it to a bf16 repo.

    Serving bf16 while the ledger records int4 would fabricate a row, so this must
    raise rather than quietly fall back.
    """
    m = spec.model("qwen3_06b")
    for dtype in ("int4", "int8"):
        with pytest.raises(UnsupportedConfig, match="pre-quantized checkpoint"):
            vllm_flags(m, baseline_config(m).with_delta({"weight_dtype": dtype}),
                       spec.gpu("gpu0"), 8000)


def test_unsupported_config_fails_the_trial_without_starting_a_server(spec):
    m = spec.model("qwen3_06b")
    cfg = baseline_config(m).with_delta({"weight_dtype": "int4"})
    out = VllmRunner(launcher=fake_launcher).run(
        [Tenant(m, cfg, _short(spec.workload("qwen3_06b")))], spec.gpu("gpu0")
    )
    assert not out.ok
    assert "pre-quantized checkpoint" in out.error


# ---- metrics parser against real-shaped vLLM output ----------------------


SAMPLE_METRICS = """\
# HELP vllm:num_requests_running Number of requests currently running on GPU.
# TYPE vllm:num_requests_running gauge
vllm:num_requests_running{model_name="Qwen/Qwen3-0.6B"} 3.0
# HELP vllm:gpu_cache_usage_perc GPU KV-cache usage. 1 means 100 percent usage.
# TYPE vllm:gpu_cache_usage_perc gauge
vllm:gpu_cache_usage_perc{model_name="Qwen/Qwen3-0.6B"} 0.4217
# HELP vllm:num_preemptions_total Cumulative number of preemptions from the engine.
# TYPE vllm:num_preemptions_total counter
vllm:num_preemptions_total{model_name="Qwen/Qwen3-0.6B"} 17.0
"""


def test_parser_reads_labelled_metrics_and_skips_comments():
    parsed = parse_prometheus(SAMPLE_METRICS)
    assert parsed["vllm:num_requests_running"] == 3.0
    assert parsed["vllm:gpu_cache_usage_perc"] == pytest.approx(0.4217)
    assert parsed["vllm:num_preemptions_total"] == 17.0
    assert not any(k.startswith("#") for k in parsed)


def test_parser_tolerates_junk_without_raising():
    """A metrics endpoint that grows a field must not fail a trial."""
    parsed = parse_prometheus("vllm:good{a=\"b\"} 1.0\nbroken line\nvllm:bad{} notanumber\n")
    assert parsed["vllm:good"] == 1.0
    assert "vllm:bad" not in parsed


def test_fake_server_metrics_round_trip_through_the_parser():
    """The fake and the parser must agree, or tests prove nothing about real vLLM."""
    import urllib.request

    with FakeVllmServer("m", FakeEngineProfile(startup_s=0.0)) as s:
        text = urllib.request.urlopen(f"{s.base_url}/metrics", timeout=5).read().decode()
    parsed = parse_prometheus(text)
    for metric in ("vllm:num_requests_running", "vllm:gpu_cache_usage_perc",
                   "vllm:num_preemptions_total", "vllm:generation_tokens_total"):
        assert metric in parsed, f"{metric} missing from fake output"


# ---- the runner, against the fake ----------------------------------------


def test_runner_measures_a_solo_trial(spec):
    m = spec.model("qwen3_06b")
    out = VllmRunner(launcher=fake_launcher).run(
        [Tenant(m, baseline_config(m), _short(spec.workload("qwen3_06b")))],
        spec.gpu("gpu0"), seed=spec.seed,
    )
    assert out.ok, out.error
    assert out.substrate.value == "vllm"
    meas = out.measurements[m.name]
    assert meas.p95_latency_ms > 0
    assert meas.throughput_rps > 0
    assert meas.p50_latency_ms <= meas.p95_latency_ms


def test_bandwidth_is_reported_unmeasured_not_zero(spec):
    """vLLM exposes no bandwidth metric. None means unknown; 0.0 would mean idle."""
    m = spec.model("qwen3_06b")
    out = VllmRunner(launcher=fake_launcher).run(
        [Tenant(m, baseline_config(m), _short(spec.workload("qwen3_06b")))],
        spec.gpu("gpu0"), seed=spec.seed,
    )
    assert out.measurements[m.name].mem_bandwidth_util is None


def test_footprint_responds_to_quantization(spec):
    """If every config reported the same memory, the Pareto frontier would collapse."""
    m = spec.model("qwen3_06b")
    wl = _short(spec.workload("qwen3_06b"))
    runner = VllmRunner(launcher=fake_launcher)
    base = runner.run([Tenant(m, baseline_config(m), wl)], spec.gpu("gpu0"))
    fp8 = runner.run(
        [Tenant(m, baseline_config(m).with_delta({"weight_dtype": "fp8"}), wl)],
        spec.gpu("gpu0"),
    )
    assert fp8.measurements[m.name].footprint_gb < base.measurements[m.name].footprint_gb


def test_joint_trial_measures_every_tenant(spec):
    """Phase 2 indexes measurements[name] for each tenant; a missing key is a KeyError."""
    tenants = [
        Tenant(spec.model(n), baseline_config(spec.model(n)), _short(spec.workload(n)))
        for n in spec.model_names
    ]
    out = VllmRunner(launcher=fake_launcher).run(tenants, spec.gpu("gpu0"), seed=spec.seed)
    assert out.ok, out.error
    assert set(out.measurements) == set(spec.model_names)
    for m in out.measurements.values():
        assert m.throughput_rps > 0


def test_server_failure_is_a_trial_outcome_not_a_crash(spec):
    """Spec §21: startup, timeout and OOM failures must not kill the optimization run."""
    from contextlib import contextmanager

    @contextmanager
    def dead_launcher(tenant, gpu, port, n_tenants):
        raise RuntimeError("simulated CUDA OOM at startup")
        yield  # pragma: no cover

    m = spec.model("qwen3_06b")
    out = VllmRunner(launcher=dead_launcher).run(
        [Tenant(m, baseline_config(m), _short(spec.workload("qwen3_06b")))],
        spec.gpu("gpu0"),
    )
    assert not out.ok
    assert "could not start server" in out.error
    assert out.measurements == {}


def test_request_errors_are_counted_not_raised(spec):
    """Every request failing yields an empty-result measurement, never an exception."""
    from contextlib import contextmanager

    from sera.runner.vllm_runner import Endpoint

    @contextmanager
    def failing(tenant, gpu, port, n_tenants):
        s = FakeVllmServer(
            tenant.config.model, FakeEngineProfile(startup_s=0.0, fail_with=500)
        ).start()
        try:
            yield Endpoint(s.base_url, tenant.config.model)
        finally:
            s.stop()

    m = spec.model("qwen3_06b")
    out = VllmRunner(launcher=failing).run(
        [Tenant(m, baseline_config(m), _short(spec.workload("qwen3_06b")))],
        spec.gpu("gpu0"),
    )
    assert out.ok
    assert "errors=" in out.notes[m.name]
    assert out.measurements[m.name].throughput_rps == 0.0


def test_available_is_false_and_never_raises_without_a_host(monkeypatch):
    monkeypatch.delenv("SERA_VLLM_HOST", raising=False)
    monkeypatch.setenv("PATH", "/nonexistent")
    assert VllmRunner().available() is False
