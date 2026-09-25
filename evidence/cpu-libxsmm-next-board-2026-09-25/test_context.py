import importlib.util
import json
from pathlib import Path

import pytest


def module():
    spec = importlib.util.spec_from_file_location('next_board', Path(__file__).with_name('run.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_history_retains_attempts_and_both_mode_measurements(tmp_path):
    for phase, mode in [('low', 'Low Power'), ('automatic', 'Automatic')]:
        folder = tmp_path / phase
        (folder / 'agent').mkdir(parents=True)
        (folder / 'search').mkdir()
        (folder / 'controls.json').write_text(json.dumps({'profile': {'energy_mode': mode}}))
        (folder / 'agent/state.json').write_text(json.dumps({'calls': 2, 'implementations': 1,
            'rounds': [{'implementations': [{'status': 'failed', 'error': 'TimeoutExpired: detail'}]}]}))
        (folder / 'search/result.json').write_text(json.dumps({'status': 'completed', 'trials': [
            {'name': 'baseline', 'source_hash': 'same', 'scores': [1 if phase=='low' else 2],
             'control_scores': [], 'promoted': False}]}))
    result = module().load_prior(tmp_path, ('low', 'automatic'))
    assert [x['profile']['energy_mode'] for x in result] == ['Low Power', 'Automatic']
    assert [x['trials'][0]['scores'] for x in result] == [[1], [2]]
    assert all(x['attempts'][0]['error_type'] == 'TimeoutExpired' for x in result)


def test_missing_phase_fails_instead_of_silent_history_loss(tmp_path):
    driver = module()
    with pytest.raises(FileNotFoundError):
        driver.load_prior(tmp_path, ('missing',))
