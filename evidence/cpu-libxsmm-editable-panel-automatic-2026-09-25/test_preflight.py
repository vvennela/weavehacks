from pathlib import Path
import importlib.util
import pytest

spec = importlib.util.spec_from_file_location('automatic_run', Path(__file__).with_name('run.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('source,mode,valid', [
    ('Battery Power', 0, True), ('Battery Power', 1, False),
    ('AC Power', 0, False), ('Battery Power', None, False),
])
def test_only_approved_initial_energy_profile_can_run(source, mode, valid):
    observation = dict(battery=f"Now drawing from '{source}'",
        power_settings=f'Battery Power:\n powermode {mode}\nAC Power:\n powermode 0\n')
    if valid:
        module.require_automatic_battery(observation)
    else:
        with pytest.raises(RuntimeError):
            module.require_automatic_battery(observation)
