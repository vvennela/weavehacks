import importlib.util
from pathlib import Path
import sys

import pytest

folder = Path(__file__).resolve().parent
sys.path.insert(0,str(folder))
spec = importlib.util.spec_from_file_location('strassen_driver',folder/'run.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('stress_passed',[True,False])
def test_driver_keeps_gates_and_requires_both_correctness_suites(monkeypatch,tmp_path,stress_passed):
    calls = []
    saved = {}
    class Team:
        def __init__(self,**kwargs):
            calls.append(kwargs)
    monkeypatch.setattr(module,'KernelAdvisoryTeam',Team)
    monkeypatch.setattr(module,'save_json',lambda path,value:saved.update({str(path):value}))
    monkeypatch.setattr(module,'host_observation',lambda:dict(battery="Now drawing from 'Battery Power'",power_settings='unchanged'))
    monkeypatch.setattr(module,'validate_cpu_kernel',lambda *args,**kwargs:dict(passed=True,source_hash='test',stage='correctness'))
    monkeypatch.setattr(module.numerics,'validate',lambda *args,**kwargs:dict(passed=stress_passed,error='stress failure'))
    def optimize(**kwargs):
        assert isinstance(kwargs['propose'],Team)
        assert kwargs['repeats'] == 10
        assert kwargs['min_improvement'] == .05
        assert kwargs['max_candidates'] == 6
        assert kwargs['max_seconds'] == 1800
        result = kwargs['validate'](folder/'baseline/kernel.c',tmp_path/'correctness.json',timeout=120)
        assert result['passed'] is stress_passed
        assert result['numerical_stress']['passed'] is stress_passed
        if not stress_passed:
            assert result['stage'] == 'numerical-correctness'
        return dict(status='offline-test')
    monkeypatch.setattr(module,'optimize_kernel',optimize)
    module.main()
    assert calls[0]['max_calls'] == 108 and calls[0]['timeout'] == 180
    assert calls[0]['max_rounds'] == 6 and calls[0]['batch_size'] == 3
    assert 'strassen_one_level' in calls[0]['task']
    controls = saved[str(folder/'controls.json')]
    assert controls['approved_one_level_strassen']
    assert not controls['prior_scores_imported']
    assert controls['historical_battery_automatic_peak_gflops'] == 1668.5964359101147
    assert controls['prior_ac_initial_baseline_peak_gflops'] == 1685.6230608449698
    assert controls['prior_ac_control_peak_gflops'] == 1687.3925479742732
