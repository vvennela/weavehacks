import importlib.util
from pathlib import Path
import json
from copy import deepcopy
import pytest

FOLDER = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('next_checkpoint', FOLDER/'checkpoint.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def saved():
    prior = FOLDER.parent/'cpu-libxsmm-next-2026-09-25'
    return json.loads((prior/'agent/state.json').read_text())


def test_original_plan_retains_spent_budget_and_queue():
    state = saved()
    module.validate_plan(state)
    assert state['calls'] == 32
    assert state['implementations'] == 1
    assert state['pending'] == ['scratch_lifetime', 'sme_fp32_schedule']


@pytest.mark.parametrize('change', ['budget', 'queue', 'board', 'ballot', 'attempt'])
def test_changed_plan_is_refused(change):
    state = deepcopy(saved())
    if change == 'budget': state['calls'] = 0
    if change == 'queue': state['pending'].reverse()
    if change == 'board': state['rounds'][0]['board'][0]['recommendation'] += 'changed'
    if change == 'ballot': state['rounds'][0]['ballots'].pop()
    if change == 'attempt': state['rounds'][0]['implementations'][0]['status'] = 'proposed'
    with pytest.raises(ValueError):
        module.validate_plan(state)
