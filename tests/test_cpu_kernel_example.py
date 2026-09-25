import pytest

from examples.optimize_cpu_kernel import require_ac


def test_battery_measurement_is_refused():
    with pytest.raises(RuntimeError,match='AC power'):
        require_ac({'battery':"Now drawing from 'Battery Power'"})


def test_ac_measurement_can_proceed():
    require_ac({'battery':"Now drawing from 'AC Power'\n -InternalBattery-0: charging"})
