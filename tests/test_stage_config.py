from dataclasses import FrozenInstanceError

import pytest

from sera.config import Constraints
from sera.stage_config import inherited_constraints, validate_stage_options


def test_stage_order_aliases_repeats_and_percentage_units():
    stages = ['latency', 'quant', 'memory', 'latency']
    plan = validate_stage_options(stages, 3.0, 10)
    assert plan.stages == ('latency', 'quantization', 'memory', 'latency')
    assert plan.k_fraction == 0.03
    assert plan.latency_regression_fraction == 0.1
    assert stages[1] == 'quant'
    with pytest.raises(FrozenInstanceError):
        plan.k_fraction = 0.5


@pytest.mark.parametrize('stages', [None, [], 'latency', ('latency',),
                                   ['Latency'], ['unknown'], ['throughput'], [True], [[]]])
def test_invalid_stage_lists_fail(stages):
    with pytest.raises(ValueError):
        validate_stage_options(stages, 3, 0)


@pytest.mark.parametrize('value', [True, False, None, '3', -1, 100, float('nan'),
                                  float('inf'), float('-inf')])
def test_invalid_improvement_percentage_fails(value):
    with pytest.raises(ValueError):
        validate_stage_options(['latency'], value, 0)


@pytest.mark.parametrize('value', [True, False, None, '3', -1, float('nan'),
                                  float('inf'), float('-inf')])
def test_invalid_regression_percentage_fails(value):
    with pytest.raises(ValueError):
        validate_stage_options(['latency'], 3, value)
    with pytest.raises(ValueError):
        inherited_constraints(Constraints(quality_floor=0.99), [], value)


def test_percentage_boundaries():
    assert validate_stage_options(['quantization'], 0, 0).k_fraction == 0
    assert validate_stage_options(['memory'], 99.999, 200).latency_regression_fraction == 2


def test_default_allows_no_latency_regression():
    assert validate_stage_options(['latency'], 3).latency_regression_fraction == 0
    result = inherited_constraints(Constraints(quality_floor=0.99),
                                   [dict(stage='latency', status='completed', p95_latency_ms=100)])
    assert result.p95_latency_ms == 100


def test_no_completed_latency_stage_preserves_all_original_constraints():
    original = Constraints(quality_floor=0.99, max_memory_mib=24576, p95_latency_ms=100)
    checkpoints = [dict(stage='latency', status='failed'),
                   dict(stage='latency', status='running', p95_latency_ms=1),
                   dict(stage='memory', status='failed', p95_latency_ms=1),
                   dict(stage='throughput', status='completed', p95_latency_ms=1)]
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
    assert result.max_memory_mib == 20000
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
                              [dict(stage='latency', status='completed', p95_latency_ms=1e308)],
                              1e308)


@pytest.mark.parametrize('stage', ['memory', 'quantization'])
@pytest.mark.parametrize('original_cap,expected', [(None, 18000), (24576, 18000), (17000, 17000)])
def test_memory_checkpoints_preserve_tightest_cap_without_regression(stage, original_cap, expected):
    original = Constraints(quality_floor=0.99, max_memory_mib=original_cap, p95_latency_ms=100)
    checkpoints = [dict(stage=stage, status='completed', sampled_peak_memory_mib=20000),
                   dict(stage=stage, status='completed', sampled_peak_memory_mib=18000)]
    result = inherited_constraints(original, checkpoints, 10)
    assert result.max_memory_mib == expected
    assert result.p95_latency_ms == 100
    assert result.quality_floor == 0.99


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
