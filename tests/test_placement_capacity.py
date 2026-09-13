"""Capacity claims distinguish estimated BF16 failure from measured FP8 success."""

from copy import deepcopy

import pytest

from sera.placement_capacity import capacity_evidence
from sera.placement_config import validate_placement_plan
from test_placement import plan_data, MODEL_ID, GLM_MODEL_ID


def example():
    baseline = validate_placement_plan(plan_data())
    data = baseline.model_dump()
    data['services'][1]['configuration']['quantization'] = 'fp8_per_tensor'
    quantized = validate_placement_plan(data)
    rejected = [dict(plan_id=baseline.plan_hash, reason='estimated-memory-does-not-fit',
                     fit_check={GLM_MODEL_ID:dict(required_bytes=600*1024**2, allocation_bytes=500*1024**2, fits=False)})]
    report = dict(decision=dict(outcome='safe-placement'),
                  shared_runtime=dict(sampled_peak_memory_mib=200, errors=[]),
                  joint=dict(gates={model:dict(passed=True) for model in (MODEL_ID, GLM_MODEL_ID)}))
    return baseline, quantized, rejected, report


@pytest.mark.parametrize('change', ['allocation', 'server_fraction', 'batching', 'quality', 'no_quantization'])
def test_other_changes_cannot_be_labeled_a_quantization_only_capacity_comparison(change):
    baseline, quantized, rejected, report = example()
    data = quantized.model_dump()
    service = data['services'][1]
    if change == 'allocation':
        service['allocation_bytes'] += 1024**2
    elif change == 'server_fraction':
        service['configuration']['gpu_memory_utilization'] -= .01
    elif change == 'batching':
        service['configuration']['max_num_batched_tokens'] = 2048
    elif change == 'quality':
        service['constraints']['quality_floor'] = .5
    else:
        service['configuration']['quantization'] = None
    selected = validate_placement_plan(data)
    proof = capacity_evidence(selected, rejected, {baseline.plan_hash:baseline}, report)
    assert proof['established'] is False


def test_passing_decision_cannot_hide_failed_joint_quality():
    baseline, quantized, rejected, report = example()
    report['joint']['gates'][MODEL_ID]['passed'] = False
    proof = capacity_evidence(quantized, rejected, {baseline.plan_hash:baseline}, report)
    assert proof['established'] is False


def test_matching_comparison_keeps_unmeasured_memory_savings_unavailable():
    baseline, quantized, rejected, report = example()
    proof = capacity_evidence(quantized, rejected, {baseline.plan_hash:baseline}, report)
    assert proof['established'] is True
    assert proof['measured_memory_savings_bytes'] is None
    assert proof['unquantized_failure_basis'] == 'deterministic-estimate-not-measured'
