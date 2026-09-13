"""Stage ordering and hard limits inherited from completed measured stages."""

from dataclasses import dataclass
import math

from .config import Constraints


SUPPORTED_STAGES = frozenset({'latency', 'memory', 'quantization'})


@dataclass(frozen=True)
class StagePlan:
    stages: tuple[str, ...]
    k_fraction: float
    latency_regression_fraction: float


def _finite_number(value, name):
    if type(value) not in (int, float):
        raise ValueError(f'{name} must be a finite number, not a boolean or string')
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError(f'{name} must be finite') from error
    if not math.isfinite(number):
        raise ValueError(f'{name} must be finite')
    return number


def _regression_fraction(value):
    percentage = _finite_number(value, 'max_latency_regression_pct')
    if percentage < 0:
        raise ValueError('max_latency_regression_pct must be nonnegative')
    return percentage / 100


def validate_stage_options(stages, k, max_latency_regression_pct=0):
    """Validate percent inputs; retain stage order and deliberate repetitions.

    Throughput remains a standalone objective until an inherited throughput
    floor is supported. It cannot be used in this staged contract.
    """
    if not isinstance(stages, list) or not stages:
        raise ValueError('stages must be a nonempty list')
    canonical = []
    for stage in stages:
        if not isinstance(stage, str):
            raise ValueError('Each stage must be a supported stage name')
        stage = 'quantization' if stage == 'quant' else stage
        if stage not in SUPPORTED_STAGES:
            raise ValueError(f'Unsupported stage: {stage}')
        canonical.append(stage)
    percentage = _finite_number(k, 'k')
    if not 0 <= percentage < 100:
        raise ValueError('k must satisfy 0 <= k < 100 percent')
    return StagePlan(tuple(canonical), percentage / 100,
                     _regression_fraction(max_latency_regression_pct))


def inherited_constraints(original: Constraints, checkpoints: list[dict],
                          max_latency_regression_pct=0):
    """Apply completed stages' frozen measurements without relaxing any limit.

    Checkpoints use stage, status='completed', and p95_latency_ms. The measured
    value is not a previously derived ceiling: allowances must never compound.
    Memory and quantization stages freeze positive integer sampled_peak_memory_mib
    with no regression allowance. Caller checkpoints must use canonical names.
    """
    regression = _regression_fraction(max_latency_regression_pct)
    ceiling = original.p95_latency_ms
    memory_ceiling = original.max_memory_mib
    for checkpoint in checkpoints:
        if checkpoint.get('status') != 'completed':
            continue
        if checkpoint.get('stage') in ('memory', 'quantization'):
            measured_memory = checkpoint.get('sampled_peak_memory_mib')
            if type(measured_memory) is not int or measured_memory <= 0:
                raise ValueError('Completed memory stages require positive integer sampled_peak_memory_mib')
            memory_ceiling = (measured_memory if memory_ceiling is None
                              else min(memory_ceiling, measured_memory))
        if checkpoint.get('stage') != 'latency':
            continue
        measured = _finite_number(checkpoint.get('p95_latency_ms'), 'checkpoint p95_latency_ms')
        if measured <= 0:
            raise ValueError('Completed latency stages require positive measured p95_latency_ms')
        stage_ceiling = measured * (1 + regression)
        if not math.isfinite(stage_ceiling):
            raise ValueError('Inherited latency ceiling must be finite')
        ceiling = stage_ceiling if ceiling is None else min(ceiling, stage_ceiling)
    return Constraints(**{**original.model_dump(), 'p95_latency_ms': ceiling,
                          'max_memory_mib': memory_ceiling})
