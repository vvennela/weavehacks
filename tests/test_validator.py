"""Paper rejections must catch what would otherwise waste a trial slot."""

from __future__ import annotations

from loop.config import InferenceConfig
from loop.spec import GpuSpec, ModelSpec
from loop.validator import fits_together, validate

MODEL = ModelSpec(
    name="m", hf_id="x/m", params_b=1.5, num_layers=28, hidden_size=1536,
    num_attn_heads=12, num_kv_heads=2, max_model_len=4096,
)
GPU = GpuSpec(id="g0", name="A10G", vram_gb=24.0, mem_bandwidth_gbs=600.0)


def test_tp_must_divide_kv_heads():
    """2 kv heads cannot shard 4 ways. Discovering this on deploy costs a slot."""
    bad = InferenceConfig(model="m", tensor_parallel_size=4)
    res = validate(bad, MODEL, GPU, available_gpus=8)
    assert not res.ok
    assert "num_kv_heads" in res.reason


def test_tp_must_divide_attention_heads():
    model = ModelSpec(
        name="m", hf_id="x/m", params_b=1.5, num_layers=28, hidden_size=1536,
        num_attn_heads=12, num_kv_heads=12, max_model_len=4096,
    )
    res = validate(InferenceConfig(model="m", tensor_parallel_size=8), model, GPU,
                   available_gpus=8)
    assert not res.ok
    assert "num_attn_heads" in res.reason


def test_tp_cannot_exceed_available_devices():
    res = validate(InferenceConfig(model="m", tensor_parallel_size=2), MODEL, GPU,
                   available_gpus=1)
    assert not res.ok
    assert "available GPUs" in res.reason


def test_weights_that_overflow_vram_are_rejected():
    big = ModelSpec(
        name="big", hf_id="x/big", params_b=70.0, num_layers=80, hidden_size=8192,
        num_attn_heads=64, num_kv_heads=8, max_model_len=4096,
    )
    res = validate(InferenceConfig(model="big"), big, GPU, available_gpus=1)
    assert not res.ok
    assert "do not fit" in res.reason


def test_config_leaving_no_room_for_kv_is_rejected():
    """Fitting the weights is not enough if nothing is left to cache with."""
    # 16GB of weights into a 17.01GB budget: they fit, but the 1.01GB left over
    # holds barely 1200 tokens of a cache this wide.
    model = ModelSpec(
        name="tight", hf_id="x/t", params_b=8.0, num_layers=40, hidden_size=5120,
        num_attn_heads=40, num_kv_heads=40, max_model_len=4096,
    )
    small = GpuSpec(id="g", name="small", vram_gb=21.0, mem_bandwidth_gbs=600.0)
    res = validate(InferenceConfig(model="tight"), model, small, available_gpus=1)
    assert not res.ok
    assert "KV cache" in res.reason


def test_chunked_prefill_required_for_small_token_budget():
    """A real vLLM constraint: a whole prompt must fit one batch without chunking."""
    cfg = InferenceConfig(model="m", max_num_batched_tokens=512,
                          enable_chunked_prefill=False)
    res = validate(cfg, MODEL, GPU, available_gpus=1)
    assert not res.ok
    assert "enable_chunked_prefill" in res.reason

    ok = validate(cfg.with_delta({"enable_chunked_prefill": True}), MODEL, GPU,
                  available_gpus=1)
    assert ok.ok


def test_weight_only_formats_rejected_as_kv_dtype():
    res = validate(InferenceConfig(model="m", kv_cache_dtype="int4"), MODEL, GPU)
    assert not res.ok
    assert "weight-only" in res.reason


def test_baseline_is_legal():
    assert validate(InferenceConfig(model="m"), MODEL, GPU, available_gpus=2).ok


def test_reserved_memory_shrinks_the_budget():
    """Phase 2's fit check reuses this path with a co-tenant's footprint reserved."""
    cfg = InferenceConfig(model="m")
    assert validate(cfg, MODEL, GPU, available_gpus=1, reserved_gb=0.0).ok
    assert not validate(cfg, MODEL, GPU, available_gpus=1, reserved_gb=21.0).ok


def test_fits_together_accounts_for_both_tenants():
    a = InferenceConfig(model="a")
    b = InferenceConfig(model="b")
    models = {"a": MODEL, "b": MODEL}
    ok = fits_together({"a": a, "b": b}, models, GPU, {"a": 8192, "b": 8192})
    assert ok.ok
    assert ok.detail["total_gb"] < ok.detail["capacity_gb"]

    tiny = GpuSpec(id="t", name="tiny", vram_gb=4.0, mem_bandwidth_gbs=600.0)
    assert not fits_together({"a": a, "b": b}, models, tiny, {"a": 8192, "b": 8192}).ok
