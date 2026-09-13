from dataclasses import FrozenInstanceError

import pytest

from sera.config import Constraints
from sera.measurement import constraint_failures
from sera.stage_config import inherited_constraints, validate_stage_options


def test_stage_order_aliases_repeats_and_percentage_units():
    stages = ['latency', 'quant', 'memory', 'throughput', 'throughput', 'latency']
    plan = validate_stage_options(stages, 3.0, 10)
    assert plan.stages == ('latency', 'quantization', 'memory', 'throughput', 'throughput', 'latency')
    assert plan.regression_fraction == 0.03
    assert plan.min_improvement_fraction == 0.1
    assert stages[1] == 'quant'
    with pytest.raises(FrozenInstanceError):
        plan.regression_fraction = 0.5


@pytest.mark.parametrize('stages', [None, [], 'latency', ('latency',),
                                   ['Latency'], ['unknown'], [True], [[]]])
def test_invalid_stage_lists_fail(stages):
    with pytest.raises(ValueError):
        validate_stage_options(stages, 3, 0)


@pytest.mark.parametrize('value', [True, False, None, '3', -1, 100, float('nan'),
                                  float('inf'), float('-inf')])
def test_invalid_regression_percentage_fails(value):
    with pytest.raises(ValueError):
        validate_stage_options(['latency'], value, 0)
    with pytest.raises(ValueError):
        inherited_constraints(Constraints(quality_floor=0.99), [], k=value)


@pytest.mark.parametrize('value', [True, False, None, '3', -1, 100, float('nan'),
                                  float('inf'), float('-inf')])
def test_invalid_improvement_percentage_fails(value):
    with pytest.raises(ValueError):
        validate_stage_options(['latency'], 3, value)


def test_percentage_boundaries():
    assert validate_stage_options(['quantization'], 0, 0).regression_fraction == 0
    assert validate_stage_options(['memory'], 99.999, 99.999).min_improvement_fraction == pytest.approx(0.99999)


def test_default_improvement_is_zero_and_unprovided_inherited_regression_is_zero():
    plan = validate_stage_options(['latency'], 3)
    assert plan.regression_fraction == 0.03
    assert plan.min_improvement_fraction == 0
    result = inherited_constraints(Constraints(quality_floor=0.99),
                                   [dict(stage='latency', status='completed', p95_latency_ms=100)])
    assert result.p95_latency_ms == 100


def test_no_completed_latency_stage_preserves_all_original_constraints():
    original = Constraints(quality_floor=0.99, max_memory_mib=24576, p95_latency_ms=100)
    checkpoints = [dict(stage='latency', status='failed'),
                   dict(stage='latency', status='running', p95_latency_ms=1),
                   dict(stage='memory', status='failed', p95_latency_ms=1),
                   dict(stage='throughput', status='failed', p95_latency_ms=1)]
    assert inherited_constraints(original, checkpoints, 10) == original


def test_completed_latency_caps_preserve_stricter_original_limits():
    original = Constraints(quality_floor=0.99, max_memory_mib=24576, p95_latency_ms=105)
    checkpoints = [dict(stage='latency', status='completed', p95_latency_ms=100)]
    result = inherited_constraints(original, checkpoints, 10)
    assert result == original
    assert result is not original


def test_repeated_latency_stages_use_frozen_measurements_without_compounding():
    original = Constraints(quality_floor=0.99, max_memory_mib=24576)
    checkpoints = [dict(stage='latency', status='completed', p95_latency_ms=100),
                   dict(stage='quantization', status='completed', p95_latency_ms=109,
                        sampled_peak_memory_mib=20000),
                   dict(stage='latency', status='completed', p95_latency_ms=95)]
    result = inherited_constraints(original, checkpoints, 10)
    assert result.p95_latency_ms == pytest.approx(104.5)
    assert result.quality_floor == 0.99
    assert result.max_memory_mib == 22000
    assert inherited_constraints(original, checkpoints, 10) == result
    assert checkpoints[0]['p95_latency_ms'] == 100
    assert original.p95_latency_ms is None


@pytest.mark.parametrize('value', [None, True, '100', 0, -1, float('nan'), float('inf')])
def test_completed_latency_without_valid_measured_p95_fails_closed(value):
    checkpoints = [dict(stage='latency', status='completed', p95_latency_ms=value)]
    with pytest.raises(ValueError):
        inherited_constraints(Constraints(quality_floor=0.99), checkpoints, 0)


def test_missing_completed_latency_measurement_fails_closed():
    with pytest.raises(ValueError):
        inherited_constraints(Constraints(quality_floor=0.99),
                              [dict(stage='latency', status='completed')], 0)


def test_overflowing_latency_cap_fails_closed():
    with pytest.raises(ValueError):
        inherited_constraints(Constraints(quality_floor=0.99),
                              [dict(stage='latency', status='completed', p95_latency_ms=1.7e308)],
                              99)


@pytest.mark.parametrize('stage', ['memory', 'quantization'])
@pytest.mark.parametrize('original_cap,expected', [(None, 19800), (24576, 19800), (17000, 17000)])
def test_memory_checkpoints_preserve_tightest_cap_with_regression(stage, original_cap, expected):
    original = Constraints(quality_floor=0.99, max_memory_mib=original_cap, p95_latency_ms=100)
    checkpoints = [dict(stage=stage, status='completed', sampled_peak_memory_mib=20000),
                   dict(stage=stage, status='completed', sampled_peak_memory_mib=18000)]
    result = inherited_constraints(original, checkpoints, 10)
    assert result.max_memory_mib == expected
    assert result.p95_latency_ms == 100
    assert result.quality_floor == 0.99


@pytest.mark.parametrize('measured,k,expected', [(101, 3, 104), (1000, 2.9, 1029),
                                               (101, 0, 101), (101, 0.01, 101)])
def test_memory_ceiling_is_exact_integer_floor(measured, k, expected):
    result = inherited_constraints(Constraints(quality_floor=0.99),
                                   [dict(stage='memory', status='completed',
                                         sampled_peak_memory_mib=measured)], k=k)
    assert result.max_memory_mib == expected


def test_repeated_memory_stages_do_not_compound_allowance():
    checkpoints = [dict(stage='memory', status='completed', sampled_peak_memory_mib=1000),
                   dict(stage='quantization', status='completed', sampled_peak_memory_mib=1020)]
    result = inherited_constraints(Constraints(quality_floor=0.99), checkpoints, k=3)
    assert result.max_memory_mib == 1030


@pytest.mark.parametrize('latency,quality,failures', [
    (101, 1.0, []),
    (104, 1.0, ['latency-requirement-failed']),
    (101, 0.98, ['task-quality-failed']),
])
def test_two_percent_memory_gain_keeps_three_percent_latency_and_quality_gates(latency, quality, failures):
    plan = validate_stage_options(['latency', 'quantization'], k=3)
    assert 0.02 > plan.min_improvement_fraction
    constraints = inherited_constraints(Constraints(quality_floor=0.99),
                                        [dict(stage='latency', status='completed', p95_latency_ms=100)],
                                        k=3)
    candidate = dict(status='collected', task_quality=dict(valid_outputs=True, mean=quality),
                     reduced=dict(p95_latency_ms=latency), runtime=dict(sampled_peak_memory_mib=980))
    assert constraint_failures(candidate, constraints) == failures


@pytest.mark.parametrize('stage', ['memory', 'quantization'])
@pytest.mark.parametrize('value', [None, True, '100', 100.0, 0, -1, float('nan'), float('inf')])
def test_completed_memory_without_positive_integer_measurement_fails(stage, value):
    with pytest.raises(ValueError):
        inherited_constraints(Constraints(quality_floor=0.99),
                              [dict(stage=stage, status='completed', sampled_peak_memory_mib=value)], 0)


def test_missing_completed_memory_measurement_fails_closed():
    with pytest.raises(ValueError):
        inherited_constraints(Constraints(quality_floor=0.99),
                              [dict(stage='memory', status='completed')], 0)


@pytest.mark.parametrize('original_floor,expected', [(None, 108), (100, 108), (115, 115)])
def test_throughput_floor_uses_tightest_frozen_measurement(original_floor, expected):
    original = Constraints(quality_floor=.99, p95_latency_ms=100, max_memory_mib=2000,
                           min_output_tokens_per_second=original_floor)
    checkpoints = [{'stage': 'throughput', 'status': 'completed', 'output_tokens_per_second': 120},
                   {'stage': 'latency', 'status': 'completed', 'p95_latency_ms': 95},
                   {'stage': 'throughput', 'status': 'completed', 'output_tokens_per_second': 110}]
    result = inherited_constraints(original, checkpoints, k=10)
    assert result.min_output_tokens_per_second == expected
    assert result.p95_latency_ms == 100
    assert result.max_memory_mib == 2000
    assert result.quality_floor == .99
    assert inherited_constraints(original, checkpoints, k=10) == result


@pytest.mark.parametrize('value', [None, True, '100', 0, -1, float('nan'), float('inf')])
def test_throughput_checkpoint_requires_positive_finite_measurement(value):
    with pytest.raises(ValueError):
        inherited_constraints(Constraints(quality_floor=.99),
            [{'stage': 'throughput', 'status': 'completed', 'output_tokens_per_second': value}])


@pytest.mark.parametrize('value', [True, '100', 0, -1, float('nan'), float('inf')])
def test_throughput_constraint_requires_positive_finite_number(value):
    with pytest.raises(ValueError):
        Constraints(quality_floor=.99, min_output_tokens_per_second=value)


@pytest.mark.parametrize('value,expected', [(100, []), (101, []),
    (99, ['throughput-requirement-failed']), (None, ['throughput-requirement-failed']),
    (float('nan'), ['throughput-requirement-failed']), (0, ['throughput-requirement-failed'])])
def test_throughput_floor_is_a_hard_gate(value, expected):
    candidate = {'status': 'collected', 'task_quality': {'valid_outputs': True, 'mean': 1.0},
                 'reduced': {'output_tokens_per_second': value}}
    assert constraint_failures(candidate,
        Constraints(quality_floor=.99, min_output_tokens_per_second=100)) == expected
