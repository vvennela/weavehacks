import pytest

from examples.optimize_cpu_kernel import require_ac


def test_battery_measurement_is_refused():
    with pytest.raises(RuntimeError,match='AC power'):
        require_ac({'battery':"Now drawing from 'Battery Power'"})


def test_ac_measurement_can_proceed():
    require_ac({'battery':"Now drawing from 'AC Power'\n -InternalBattery-0: charging"})


@pytest.mark.parametrize('source', ['AC Power', 'Battery Power'])
def test_current_power_mode_can_establish_a_baseline(source):
    from examples.optimize_cpu_kernel import check_power
    initial = dict(battery=f"Now drawing from '{source}'", power_settings='fixed')
    check_power(initial, initial)


@pytest.mark.parametrize('changed', [
    dict(battery="Now drawing from 'AC Power'", power_settings='fixed'),
    dict(battery="Now drawing from 'Battery Power'", power_settings='changed'),
    dict(battery='Unavailable', power_settings='fixed'),
])
def test_power_change_or_unknown_source_rejects_measurement(changed):
    from examples.optimize_cpu_kernel import check_power
    initial = dict(battery="Now drawing from 'Battery Power'", power_settings='fixed')
    with pytest.raises(RuntimeError):
        check_power(changed, initial)
