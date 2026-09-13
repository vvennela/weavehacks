"""Structural contracts for the specified two-model plan; no live placement support.

Byte budgets and each model's quality and latency limits are required inputs.
Validation checks settings and reserved allocations only. It does not establish
estimated or observed fit, compatible checkpoints, passing isolated task evidence,
joint latency, or permission to launch a shared runtime.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import GLM_MODEL_ID, GLM_MODEL_REVISION, MODEL_ID, MODEL_REVISION, RuntimeConfig
from .storage import content_hash


PINNED_PLACEMENT_MODELS = {MODEL_ID: MODEL_REVISION, GLM_MODEL_ID: GLM_MODEL_REVISION}


class _PlacementRecord(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra='forbid', allow_inf_nan=False,
                              revalidate_instances='always')


class PlacementConstraints(_PlacementRecord):
    """Required per-model gates; do not infer limits from calibration results."""

    quality_floor: float = Field(ge=0, le=1)
    p95_latency_ms: float | None = Field(default=None, gt=0)
    max_p95_slowdown_fraction: float | None = Field(default=None, ge=0)
    max_generation_errors: int = Field(ge=0, le=0)

    @model_validator(mode='after')
    def require_latency_contract(self):
        if self.p95_latency_ms is None and self.max_p95_slowdown_fraction is None:
            raise ValueError('Each model requires an absolute or relative p95 latency limit')
        return self


class PlacementService(_PlacementRecord):
    model_id: Literal[MODEL_ID, GLM_MODEL_ID]
    revision: str
    gpu_index: int = Field(ge=0, le=0)
    allocation_bytes: int = Field(gt=0)
    configuration: RuntimeConfig
    constraints: PlacementConstraints

    @field_validator('configuration', mode='before')
    @classmethod
    def revalidate_configuration(cls, value):
        return value.model_dump() if isinstance(value, RuntimeConfig) else value

    @model_validator(mode='after')
    def validate_pinned_configuration(self):
        if self.revision != PINNED_PLACEMENT_MODELS[self.model_id]:
            raise ValueError('Placement requires the approved pinned model revision')
        if self.configuration.kv_cache_dtype == 'fp8' and (
                self.model_id == GLM_MODEL_ID or self.configuration.quantization is not None):
            raise ValueError('GLM FP8 KV and combined FP8 weights/KV remain unverified and disabled')
        return self


class PlacementPlan(_PlacementRecord):
    physical_gpu_bytes: int = Field(gt=0)
    declared_budget_bytes: int = Field(gt=0)
    services: list[PlacementService] = Field(min_length=2, max_length=2)

    @model_validator(mode='after')
    def validate_shared_budget(self):
        if {service.model_id for service in self.services} != set(PINNED_PLACEMENT_MODELS):
            raise ValueError('Placement requires exactly one configuration of each specified model')
        if self.declared_budget_bytes > self.physical_gpu_bytes:
            raise ValueError('Declared budget exceeds physical GPU capacity')
        # Keep the ten-percent reserve exact even above floating-point integer precision.
        allocated = sum(service.allocation_bytes for service in self.services)
        if 10 * allocated > 9 * self.declared_budget_bytes:
            raise ValueError('Service allocations must leave ten percent of the declared budget as reserve')
        for service in self.services:
            if service.configuration.tensor_parallel_size != 1:
                raise ValueError('Shared single-GPU placement requires tensor_parallel_size=1')
            fraction = service.allocation_bytes / self.physical_gpu_bytes
            if service.configuration.gpu_memory_utilization > fraction:
                raise ValueError('Server memory fraction must not exceed allocated bytes / physical GPU bytes')
        return self

    @property
    def plan_hash(self) -> str:
        checked = validate_placement_plan(self).model_dump()
        # Keep hashes stable for the original absolute-only contract.
        for service in checked['services']:
            if service['constraints']['max_p95_slowdown_fraction'] is None:
                service['constraints'].pop('max_p95_slowdown_fraction')
        checked['services'].sort(key=lambda service: service['model_id'])
        return content_hash({'schema_version': 'sera-placement-plan-v1', 'plan': checked})


def validate_placement_plan(value) -> PlacementPlan:
    """Revalidate nested mutable data; do not treat this result as a deployment gate."""
    if isinstance(value, PlacementPlan):
        value = value.model_dump()
    return PlacementPlan.model_validate(value)
