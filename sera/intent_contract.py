"""Turn interpreted intent into enforceable, non-weakened experiment limits."""
import re
from typing import Literal

from pydantic import BaseModel, Field

Precision = Literal['int2', 'int3', 'int4', 'int8', 'fp8', 'nvfp4', 'nf4']


class IntentRequirements(BaseModel):
    required_precision: Precision | None = None
    quality_retention: float | None = Field(default=None, gt=0, le=1)
    throughput_retention: float | None = Field(default=None, gt=0, le=1)
    max_memory_mib: float | None = Field(default=None, gt=0)
    p95_latency_ms: float | None = Field(default=None, gt=0)


def recipe_precision(backend, recipe):
    if backend == 'cuda':
        return recipe.format
    if backend == 'rocm' and recipe.bits == 4:
        return 'nf4'
    if getattr(recipe, 'protected_bits', None) and recipe.protected_bits != recipe.bits:
        return f'mixed-int{recipe.bits}-int{recipe.protected_bits}'
    return f'int{recipe.bits}' if recipe.bits != 16 else 'bf16'


def recipe_catalog(profile):
    return [{'recipe_id': key, 'precision': recipe_precision(profile.backend, recipe)}
            for key, recipe in profile.recipes.items()]


def apply_requirements(profile, plan):
    from .native_optimizer import validate_native_profile
    from .rag_intake import IntakeNeedsInput
    value = profile.model_dump()
    if plan.required_precision:
        selected = {key: recipe.model_dump() for key, recipe in profile.recipes.items()
                    if recipe_precision(profile.backend, recipe) == plan.required_precision}
        if not selected:
            raise IntakeNeedsInput([(f'The registered {profile.backend} recipes do not provide {plan.required_precision}. '
                                    'Register a compatible runtime and recipe, or choose another precision.')])
        value['recipes'] = selected
        value['required_precision'] = plan.required_precision
    if plan.quality_retention is not None or plan.throughput_retention is not None:
        prior = profile.retention
        value['retention'] = {
            'quality': max(prior.quality if prior else profile.constraints.quality_floor, plan.quality_retention or 0),
            'throughput': max((prior.throughput or 0) if prior else 0, plan.throughput_retention or 0) or None}
    for field in ('max_memory_mib', 'p95_latency_ms'):
        requested = getattr(plan, field)
        if requested is not None:
            previous = value['constraints'].get(field)
            value['constraints'][field] = min(previous, requested) if previous is not None else requested
    return validate_native_profile(value)


INTENT_RULES = (
    'Distinguish a required numeric format from a memory optimization goal. '
    'For a required format, set required_precision to its exact supported format and restrict experiments '
    'to that format. FP4/NVFP4, NF4 and integer INT4 are different; never substitute one for another. '
    'For lowest-memory searches without a required format, leave required_precision null so the swarm '
    'can compare the available recipes. Encode explicit requested quality/throughput retention fractions, '
    'memory limits in MiB, and p95 latency limits in milliseconds in their respective fields; otherwise '
    'leave them null. The harness can tighten operator gates but cannot weaken them. If a requested '
    'tradeoff is ambiguous and changes acceptance, ask a short clarification question. '
)


def verify_explicit_precision(intent, plan):
    """Catch omitted direct format commands; Astra handles the wider intent."""
    from .rag_intake import IntakeNeedsInput
    formats = r'(nvfp4|fp4|nf4|fp8|int[2348])'
    for clause in re.split(r'[.;!?\n]|\b(?:but|and)\b', intent.lower()):
        # Negation and comparisons need semantic interpretation, not keyword rules.
        if re.search(r"\b(not|never|avoid|without|compare|versus)\b|don['’]t", clause):
            continue
        match = re.search(r'\b(?:run(?:ning)?\s+at|quantiz(?:e|ation)\b.{0,60}?\bto|(?:must\s+)?use|keep\b.{0,40}?\b(?:at|in))\s+' + formats + r'\b', clause)
        if match:
            required = 'nvfp4' if match[1] == 'fp4' else match[1]
            if plan.required_precision != required:
                raise IntakeNeedsInput([f'Confirm the required precision: {required}. The interpreted plan did not preserve it.'])
