"""The adapter smoke constrains requested JSON types without answer leakage."""

from copy import deepcopy

import pytest

from benchmarks.grade import load_cases
from scripts.check_native_checkpoint import requested_formats


def test_json_decoding_does_not_depend_on_expected_answers():
    cases = load_cases('benchmarks/easy_cases.json')
    changed = deepcopy(cases)
    for case in changed:
        case['expected'] = {'unrelated': ['secret-answer']}
        case['rationale'] = 'secret rationale'
    assert requested_formats(changed) == requested_formats(cases)
    assert 'secret' not in str(requested_formats(changed))


def test_unknown_tasks_cannot_silently_inherit_a_format():
    cases = load_cases('benchmarks/easy_cases.json')
    cases[0]['id'] = 'new-task'
    with pytest.raises(ValueError, match='unchanged eight'):
        requested_formats(cases)
