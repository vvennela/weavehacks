"""Placement plans are arithmetic contracts, not permission to start two services."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from sera.config import GLM_MODEL_ID, GLM_MODEL_REVISION, MODEL_ID, MODEL_REVISION, RuntimeConfig


def valid_plan():
    physical = 1000  # Synthetic bytes, not suggested live allocations.
    return {'physical_gpu_bytes': physical, 'declared_budget_bytes': 800,
            'services': [
                {'model_id': model_id, 'revision': revision, 'gpu_index': 0,
                 'allocation_bytes': allocation,
                 'configuration': RuntimeConfig(gpu_memory_utilization=allocation / physical).model_dump(),
                 'constraints': {'quality_floor': .99, 'p95_latency_ms': latency,
                                 'max_generation_errors': 0}}
                for model_id, revision, allocation, latency in [
                    (MODEL_ID, MODEL_REVISION, 200, 123.0),
                    (GLM_MODEL_ID, GLM_MODEL_REVISION, 520, 456.0)]]}


def validate(value):
    from sera.placement_config import validate_placement_plan
    return validate_placement_plan(value)


def test_exact_approved_pair_and_reserve_boundary_are_valid_without_live_actions():
    plan = validate(valid_plan())
    assert {service.model_id for service in plan.services} == {MODEL_ID, GLM_MODEL_ID}
    assert sum(service.allocation_bytes for service in plan.services) == 720
    assert [service.configuration.gpu_memory_utilization for service in plan.services] == [.2, .52]
    assert [service.constraints.p95_latency_ms for service in plan.services] == [123.0, 456.0]


@pytest.mark.parametrize('field,value', [
    ('physical_gpu_bytes', 0), ('physical_gpu_bytes', -1), ('physical_gpu_bytes', True),
    ('physical_gpu_bytes', 1000.0), ('declared_budget_bytes', '800'),
    ('declared_budget_bytes', 0), ('declared_budget_bytes', False),
    ('declared_budget_bytes', 1001),
])
def test_invalid_physical_or_declared_budget_is_rejected(field, value):
    with pytest.raises(ValidationError):
        validate(valid_plan() | {field: value})


def test_shared_reserve_uses_exact_integer_arithmetic_above_float_precision():
    data = valid_plan()
    data['physical_gpu_bytes'] = 2**60
    data['declared_budget_bytes'] = 2**59
    allowed = 9 * data['declared_budget_bytes'] // 10
    data['services'][0]['allocation_bytes'] = 2**56
    data['services'][1]['allocation_bytes'] = allowed - 2**56
    for service in data['services']:
        service['configuration']['gpu_memory_utilization'] = service['allocation_bytes'] / data['physical_gpu_bytes']
    validate(data)
    data['services'][1]['allocation_bytes'] += 1
    data['services'][1]['configuration']['gpu_memory_utilization'] = (
        data['services'][1]['allocation_bytes'] / data['physical_gpu_bytes'])
    with pytest.raises(ValidationError, match='reserve'):
        validate(data)


@pytest.mark.parametrize('change', [
    {'allocation_bytes': 0}, {'allocation_bytes': -1}, {'allocation_bytes': True},
    {'allocation_bytes': 200.0}, {'gpu_index': 1}, {'gpu_index': False}, {'gpu_index': 0.0},
    {'revision': 'main'}, {'model_id': 'Qwen/Qwen2.5-72B-Instruct'},
])
def test_invalid_service_identity_assignment_or_allocation_is_rejected(change):
    data = valid_plan()
    data['services'][0].update(change)
    with pytest.raises(ValidationError):
        validate(data)


@pytest.mark.parametrize('services', ['missing', 'duplicate', 'third'])
def test_exactly_one_of_each_specified_model_is_required(services):
    data = valid_plan()
    if services == 'missing':
        data['services'].pop()
    elif services == 'duplicate':
        data['services'][1] = deepcopy(data['services'][0])
    else:
        data['services'].append(deepcopy(data['services'][0]))
    with pytest.raises(ValidationError):
        validate(data)


@pytest.mark.parametrize('change', [
    {'quality_floor': -.01}, {'quality_floor': 1.01}, {'quality_floor': True},
    {'p95_latency_ms': 0}, {'p95_latency_ms': float('inf')}, {'p95_latency_ms': float('nan')},
    {'p95_latency_ms': True}, {'p95_latency_ms': None}, {'p95_latency_ms': '100'},
    {'max_generation_errors': 1}, {'max_generation_errors': False}, {'max_generation_errors': 0.0},
])
def test_per_model_constraints_remain_hard_explicit_requirements(change):
    data = valid_plan()
    data['services'][1]['constraints'].update(change)
    with pytest.raises(ValidationError):
        validate(data)


@pytest.mark.parametrize('field', ['quality_floor', 'p95_latency_ms', 'max_generation_errors'])
def test_no_constraint_threshold_is_invented(field):
    data = valid_plan()
    del data['services'][1]['constraints'][field]
    with pytest.raises(ValidationError):
        validate(data)


def test_fraction_uses_physical_capacity_not_declared_budget():
    data = valid_plan()
    data['services'][0]['configuration']['gpu_memory_utilization'] = 200 / 800
    with pytest.raises(ValidationError, match='physical'):
        validate(data)


@pytest.mark.parametrize('change', [
    {'kv_cache_memory_bytes': 100}, {'tensor_parallel_size': 2},
    {'max_model_len': 4097}, {'max_num_batched_tokens': 7},
])
def test_existing_runtime_limits_and_no_memory_override_remain_enforced(change):
    data = valid_plan()
    data['services'][0]['configuration'].update(change)
    with pytest.raises(ValidationError):
        validate(data)


def test_plan_hash_is_order_independent_and_binds_constraints_and_configuration():
    data = valid_plan()
    before = validate(data).plan_hash
    data['services'].reverse()
    assert validate(data).plan_hash == before
    data['services'][0]['constraints']['p95_latency_ms'] += 1
    assert validate(data).plan_hash != before
    data = valid_plan()
    data['services'][0]['configuration']['max_num_seqs'] = 4
    assert validate(data).plan_hash != before


def test_nested_data_is_revalidated_and_extra_fields_fail():
    plan = validate(valid_plan())
    plan.services.append(plan.services[0])
    with pytest.raises(ValidationError):
        validate(plan)
    with pytest.raises(ValidationError):
        validate(valid_plan() | {'approved_to_start': True})


@pytest.mark.parametrize('floor', [0, .8, .99, 1])
def test_quality_floor_is_caller_supplied_not_a_global_pilot_default(floor):
    data = valid_plan()
    data['services'][0]['constraints']['quality_floor'] = floor
    assert validate(data).services[0].constraints.quality_floor == floor


@pytest.mark.parametrize('index,quantization,kv_dtype', [
    (1, None, 'fp8'), (1, 'fp8_per_tensor', 'fp8'), (0, 'fp8_per_tensor', 'fp8'),
])
def test_unverified_precision_combinations_remain_disabled(index, quantization, kv_dtype):
    data = valid_plan()
    data['services'][index]['configuration'].update(quantization=quantization, kv_cache_dtype=kv_dtype)
    with pytest.raises(ValidationError, match='unverified'):
        validate(data)


@pytest.mark.parametrize('index,quantization,kv_dtype', [
    (0, None, 'fp8'), (0, 'fp8_per_tensor', 'auto'), (1, 'fp8_per_tensor', 'auto'),
])
def test_supported_precision_types_are_only_structurally_valid_not_quality_approved(index, quantization, kv_dtype):
    data = valid_plan()
    data['services'][index]['configuration'].update(quantization=quantization, kv_cache_dtype=kv_dtype)
    assert validate(data).services[index].configuration.kv_cache_dtype == kv_dtype


def test_unconstrained_physical_budget_still_keeps_shared_reserve():
    data = valid_plan()
    data['declared_budget_bytes'] = data['physical_gpu_bytes']
    assert validate(data).declared_budget_bytes == 1000


def test_prebuilt_nested_models_cannot_bypass_revalidation():
    from sera.placement_config import PlacementService
    data = valid_plan()
    data['services'][0]['configuration'] = RuntimeConfig(
        gpu_memory_utilization=.2).model_copy(update={'max_model_len': 5000})
    with pytest.raises(ValidationError):
        validate(data)
    data = valid_plan()
    data['services'][0] = PlacementService(**data['services'][0]).model_copy(update={'gpu_index': 1})
    with pytest.raises(ValidationError):
        validate(data)
