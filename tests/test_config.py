import pytest
from pydantic import ValidationError

from sera.config import Candidate, RuntimeConfig, validate_candidate


def test_named_baseline_is_explicit_and_frozen():
    config = RuntimeConfig()
    assert config.kv_cache_dtype == "auto"
    assert config.max_num_batched_tokens == 4096
    assert config.dtype == "bfloat16"
    assert config.quantization is None
    assert config.gpu_memory_utilization == 0.9
    with pytest.raises(ValidationError):
        config.max_num_seqs = 16


def test_candidate_requires_a_name_reason_and_complete_config():
    candidate = Candidate(name="kv-fp8", reason="Test cache precision", config=RuntimeConfig(kv_cache_dtype="fp8"))
    assert candidate.config.kv_cache_dtype == "fp8"
    for field in ["name", "reason", "config"]:
        data = candidate.model_dump()
        del data[field]
        with pytest.raises(ValidationError):
            Candidate.model_validate(data)


@pytest.mark.parametrize("change", [
    {"max_num_seqs": 0}, {"max_num_seqs": "8"}, {"max_num_seqs": True},
    {"max_num_batched_tokens": -1}, {"max_num_batched_tokens": 65537},
    {"gpu_memory_utilization": 0.0}, {"gpu_memory_utilization": 1.1},
    {"gpu_memory_utilization": float("nan")}, {"gpu_memory_utilization": float("inf")},
    {"dtype": "float16"}, {"quantization": "fp8"}, {"kv_cache_dtype": "int4"},
    {"tensor_parallel_size": 2}, {"max_model_len": 4097},
    {"enable_prefix_caching": "false"}, {"unknown_flag": 1},
    {"tensor_parallel_size": True}, {"enable_prefix_caching": 0},
    {"enable_chunked_prefill": 1}, {"enforce_eager": 1},
])
def test_config_rejects_invalid_or_unimplemented_settings(change):
    with pytest.raises(ValidationError):
        RuntimeConfig(**change)


def test_batch_tokens_cover_at_least_one_token_per_sequence():
    with pytest.raises(ValidationError):
        RuntimeConfig(max_num_seqs=8, max_num_batched_tokens=4)
    assert RuntimeConfig(max_num_batched_tokens=2048).max_num_batched_tokens == 2048


def test_hash_is_stable_and_covers_settings():
    original = RuntimeConfig()
    assert original.config_hash == RuntimeConfig.model_validate_json(original.model_dump_json()).config_hash
    assert original.config_hash != RuntimeConfig(kv_cache_dtype="fp8").config_hash


def test_candidate_rejects_empty_text_and_extra_fields():
    with pytest.raises(ValidationError):
        Candidate(name="", reason="", config=RuntimeConfig(), approval=True)


@pytest.mark.parametrize("config", [RuntimeConfig(), RuntimeConfig(max_num_seqs=16),
    RuntimeConfig(kv_cache_dtype="fp8", max_num_batched_tokens=2048),
    RuntimeConfig(gpu_memory_utilization=0.8)])
def test_first_candidate_must_change_one_active_lever(config):
    with pytest.raises(ValueError):
        validate_candidate(Candidate(name="trial", reason="Measured hypothesis", config=config))


def test_first_candidate_accepts_cache_or_batch_change():
    for config in [RuntimeConfig(kv_cache_dtype="fp8"), RuntimeConfig(max_num_batched_tokens=2048)]:
        candidate = Candidate(name="trial", reason="Measured hypothesis", config=config)
        assert validate_candidate(candidate) == candidate
def test_batch_candidate_preserves_explicit_fp8_weight_reference():
    from sera.config import Candidate, RuntimeConfig, validate_candidate
    baseline = RuntimeConfig(quantization="fp8_per_tensor")
    candidate = Candidate(name="batch-2048", reason="Compare batching after weights fit",
                          config=RuntimeConfig(quantization="fp8_per_tensor", max_num_batched_tokens=2048))
    assert validate_candidate(candidate, baseline=baseline) == candidate
