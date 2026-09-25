import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('measure_prepared', Path(__file__).with_name('run.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_saved_candidate_replays_and_keeps_the_remaining_swarm_order():
    checkpoint = module.read_checkpoint()
    candidate = module.validate_checkpoint(**checkpoint)
    assert candidate.name == 'libxsmm-k-loop-software-pipeline'
    assert checkpoint['state']['pending'] == ['address_generation', 'sme_fp32_tiles']
    assert checkpoint['state']['calls'] == 33


@pytest.mark.parametrize('part', ['source', 'response', 'state', 'correctness'])
def test_altered_checkpoint_is_rejected(part):
    checkpoint = module.read_checkpoint()
    if part == 'source':
        checkpoint['source'] += '\n/* changed */\n'
    elif part == 'response':
        checkpoint['response']['edits'][0]['new'] += '\n'
    elif part == 'state':
        checkpoint['state']['pending'].reverse()
    else:
        checkpoint['correctness']['source_hash'] = 'wrong'
    with pytest.raises(ValueError):
        module.validate_checkpoint(**checkpoint)


def test_battery_preflight_prevents_model_and_evaluator_setup(monkeypatch):
    monkeypatch.setattr(module, 'host_observation', lambda: {'battery': "Now drawing from 'Battery Power'"})
    monkeypatch.setattr(module, 'KernelAdvisoryTeam', lambda **kwargs: pytest.fail('Model setup on battery'))
    monkeypatch.setattr(module, 'HillsKernelEvaluator', lambda **kwargs: pytest.fail('Evaluator setup on battery'))
    with pytest.raises(RuntimeError, match='AC power'):
        module.main([])
