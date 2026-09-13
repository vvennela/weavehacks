"""The supported single-model configuration contract."""

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator


MODEL_ID = "Qwen/Qwen3-0.6B"
MODEL_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
LARGE_MODEL_ID = "Qwen/Qwen2.5-72B-Instruct"
LARGE_MODEL_REVISION = "495f39366efef23836d0cfae4fbe635880d2be31"
GLM_MODEL_ID = "zai-org/glm-4-9b-chat-hf"
GLM_MODEL_REVISION = "8599336fc6c125203efb2360bfaf4c80eef1d1bf"
BASELINE_NAME = "sera-baseline-v1"


class Objective(BaseModel):
    """User priority; quality remains a hard gate, not part of the score."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", allow_inf_nan=False)

    priority: Literal["latency", "throughput", "memory"] = "latency"
    min_improvement_fraction: float = Field(default=0.05, ge=0, lt=1)


class Constraints(BaseModel):
    """Hard limits for the measured single-model workload."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", allow_inf_nan=False)

    quality_floor: float = Field(ge=0, le=1)
    p95_latency_ms: float | None = Field(default=None, gt=0)
    max_memory_mib: int | None = Field(default=None, gt=0)


class Workload(BaseModel):
    """Declared closed-loop client loads; quality is always checked serially."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    concurrency: list[int] = Field(default_factory=lambda: [1], min_length=1, max_length=4)

    @field_validator("concurrency")
    @classmethod
    def validate_loads(cls, values):
        if any(type(value) is not int or value not in {1, 2, 4, 8} for value in values):
            raise ValueError("Supported concurrency levels are 1, 2, 4, and 8")
        if values != sorted(set(values)):
            raise ValueError("Concurrency levels must be unique and increasing")
        return values


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", allow_inf_nan=False)

    dtype: Literal["bfloat16"] = "bfloat16"
    quantization: Literal["fp8_per_tensor"] | None = None
    kv_cache_dtype: Literal["auto", "fp8"] = "auto"
    tensor_parallel_size: Literal[1] = 1
    max_model_len: int = Field(default=4096, ge=65, le=4096)
    max_num_seqs: int = Field(default=8, ge=1, le=256)
    max_num_batched_tokens: int = Field(default=4096, ge=1, le=65536)
    gpu_memory_utilization: float = Field(default=0.9, gt=0, le=0.9)
    enable_prefix_caching: Literal[False] = False
    enable_chunked_prefill: Literal[True] = True
    enforce_eager: Literal[True] = True

    @field_validator("tensor_parallel_size", mode="before")
    @classmethod
    def strict_parallel_type(cls, value):
        if type(value) is not int:
            raise ValueError("tensor_parallel_size must be an integer")
        return value

    @field_validator("enable_prefix_caching", "enable_chunked_prefill", "enforce_eager", mode="before")
    @classmethod
    def strict_boolean_type(cls, value):
        if type(value) is not bool:
            raise ValueError("Flags must be booleans")
        return value

    @model_validator(mode="after")
    def validate_batch(self):
        if self.max_num_batched_tokens < self.max_num_seqs:
            raise ValueError("Batch token limit must cover at least one token per sequence")
        return self

    @property
    def config_hash(self) -> str:
        encoded = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()


class Candidate(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    config: RuntimeConfig


# The two changes already named in the milestone plan. This is not full search.
SUPPORTED_CHANGES = {"kv_cache_dtype": ["fp8"], "max_num_batched_tokens": [2048]}


CONTROL_ROLES = {
    "kv_cache_dtype": "quantization", "max_num_batched_tokens": "batching",
    "max_num_seqs": "batching", "max_model_len": "batching",
}
CONTROL_VALUE_ADAPTERS = {
    lever: TypeAdapter(RuntimeConfig.model_fields[lever].rebuild_annotation(),
                       config=ConfigDict(strict=True))
    for lever in CONTROL_ROLES if lever != "kv_cache_dtype"
}


def validate_control_value(lever, value):
    """Legal capability only. This does not activate a setting for a live run."""
    if lever not in CONTROL_ROLES:
        raise ValueError("Unsupported proposal control")
    if lever == "kv_cache_dtype":
        if type(value) is not str or value != "fp8":
            raise ValueError("The cache proposal control supports FP8 only")
        return value
    return CONTROL_VALUE_ADAPTERS[lever].validate_python(value)


def validate_supported_changes(supported_changes):
    """Validate the explicit per-run value set without extending live defaults."""
    if not isinstance(supported_changes, dict):
        raise ValueError("supported_changes must map legal controls to value lists")
    for lever, values in supported_changes.items():
        if lever not in CONTROL_ROLES or not isinstance(values, list):
            raise ValueError("supported_changes must map legal controls to value lists")
        for value in values:
            validate_control_value(lever, value)
    return supported_changes


def validate_control_candidate(candidate: Candidate, *, baseline=None) -> Candidate:
    """Check one bounded control change against the actual parent configuration."""
    candidate = Candidate.model_validate(candidate.model_dump())
    baseline = (RuntimeConfig() if baseline is None else RuntimeConfig.model_validate(baseline)).model_dump()
    changed = {key: value for key, value in candidate.config.model_dump().items()
               if value != baseline[key]}
    if len(changed) != 1:
        raise ValueError("A candidate must change exactly one setting from its actual parent")
    lever, value = next(iter(changed.items()))
    validate_control_value(lever, value)
    return candidate


def validate_candidate(candidate: Candidate, *, baseline=None, supported_changes=None,
                       frozen_candidate_hashes=None) -> Candidate:
    """Apply active values and an optional frozen universe after capability validation."""
    baseline = RuntimeConfig() if baseline is None else RuntimeConfig.model_validate(baseline)
    candidate = validate_control_candidate(candidate, baseline=baseline)
    supported_changes = validate_supported_changes(
        SUPPORTED_CHANGES if supported_changes is None else supported_changes)
    changed = {key: value for key, value in candidate.config.model_dump().items()
               if value != baseline.model_dump()[key]}
    lever, value = next(iter(changed.items()))
    if not any(type(allowed) is type(value) and allowed == value
               for allowed in supported_changes.get(lever, [])):
        raise ValueError("Proposed setting is not active in this run")
    if frozen_candidate_hashes is not None:
        if (not isinstance(frozen_candidate_hashes, list)
                or any(not isinstance(key, str) or re.fullmatch('[0-9a-f]{64}', key) is None
                       for key in frozen_candidate_hashes)
                or candidate.config.config_hash not in frozen_candidate_hashes):
            raise ValueError("Candidate is outside the frozen configuration universe")
    return candidate
