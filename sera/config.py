"""The supported single-model configuration contract."""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MODEL_ID = "Qwen/Qwen3-0.6B"
MODEL_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
LARGE_MODEL_ID = "Qwen/Qwen2.5-72B-Instruct"
LARGE_MODEL_REVISION = "495f39366efef23836d0cfae4fbe635880d2be31"
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


def validate_candidate(candidate: Candidate) -> Candidate:
    candidate = Candidate.model_validate(candidate.model_dump())
    baseline = RuntimeConfig().model_dump()
    changed = {key: value for key, value in candidate.config.model_dump().items()
               if value != baseline[key]}
    if len(changed) != 1:
        raise ValueError("The first candidate must change exactly one setting")
    lever, value = next(iter(changed.items()))
    if lever not in SUPPORTED_CHANGES or value not in SUPPORTED_CHANGES[lever]:
        raise ValueError("This milestone supports FP8 KV or a batch token limit of 2048 only")
    return candidate
