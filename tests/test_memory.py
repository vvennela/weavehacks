import pytest

from sera.memory import estimate_memory, fits_memory, combined_allocations_fit


def test_weight_and_kv_units():
    estimate = estimate_memory(parameter_count=100, weight_bytes=2, layers=2, kv_heads=4,
                               head_dim=8, tokens=10, sequences=3, kv_bytes=2, workspace_bytes=50)
    assert estimate["weights_bytes"] == 200
    assert estimate["kv_bytes"] == 2 * 2 * 4 * 8 * 10 * 3 * 2
    assert estimate["total_bytes"] == 200 + 7680 + 50


def test_fp8_halves_only_kv_component():
    settings = dict(parameter_count=100, weight_bytes=2, layers=2, kv_heads=4,
                    head_dim=8, tokens=10, sequences=3, workspace_bytes=50)
    bf16 = estimate_memory(**settings, kv_bytes=2)
    fp8 = estimate_memory(**settings, kv_bytes=1)
    assert fp8["kv_bytes"] * 2 == bf16["kv_bytes"]
    assert fp8["weights_bytes"] == bf16["weights_bytes"]


def test_fit_boundary_keeps_explicit_reserve():
    assert fits_memory(required_bytes=900, budget_bytes=1000, reserve_bytes=100)
    assert not fits_memory(required_bytes=901, budget_bytes=1000, reserve_bytes=100)
    assert not fits_memory(required_bytes=1, budget_bytes=100, reserve_bytes=100)


def test_joint_budget_checks_declared_and_physical_capacity():
    assert combined_allocations_fit([400, 500], declared_bytes=1000, physical_bytes=2000, reserve_bytes=100)
    assert not combined_allocations_fit([400, 501], declared_bytes=1000, physical_bytes=2000, reserve_bytes=100)
    assert not combined_allocations_fit([400, 500], declared_bytes=2000, physical_bytes=899, reserve_bytes=0)


@pytest.mark.parametrize("value", [-1, True, 1.5, float("nan")])
def test_invalid_byte_amounts_rejected(value):
    with pytest.raises(ValueError):
        fits_memory(required_bytes=value, budget_bytes=1000, reserve_bytes=100)
