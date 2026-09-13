import json
from itertools import combinations

import pytest

from benchmarks.grade import grade_case, load_cases, score_responses


def test_frozen_case_set_has_valid_reference_answers():
    cases = load_cases()
    assert len(cases) == 24
    assert len({case['id'] for case in cases}) == 24
    assert {case['difficulty'] for case in cases} == {'easy', 'moderate', 'harder'}
    assert sum(case['category'] == 'coding' for case in cases) == 12
    for case in cases:
        assert case['max_tokens'] == 128
        assert case['prompt'] and case['rationale']
        result = grade_case(case, json.dumps({'answer': case['expected']}))
        assert result['passed']
        assert result['format_valid']


@pytest.mark.parametrize('output', [
    '', '1', '{"answer": 1, "extra": 0}', '{"answer": 0, "answer": 1}',
    '```json\n{"answer": 1}\n```', 'Answer: {"answer": 1}',
    '{"answer": NaN}', '{"answer": Infinity}', '{"answer": 1} trailing',
    '__import__("os").system("echo unsafe")', '[' * 2000,
])
def test_invalid_format_fails_without_execution(output):
    result = grade_case({'expected': 1}, output)
    assert not result['passed']
    assert not result['format_valid']


@pytest.mark.parametrize('value', [True, '1', 1.0, [1], None, 0])
def test_types_and_values_are_not_coerced(value):
    result = grade_case({'expected': 1}, json.dumps({'answer': value}))
    assert result['format_valid']
    assert not result['passed']


def test_json_key_order_and_whitespace_do_not_change_score():
    case = {'expected': {'ids': [3, 1], 'ok': True}}
    assert grade_case(case, ' {"answer": {"ok": true, "ids": [3,1]}}\n')['passed']
    assert not grade_case(case, '{"answer":{"ok":true,"ids":[1,3]}}')['passed']


def test_missing_outputs_count_as_failures_and_extra_ids_are_rejected():
    cases = load_cases()
    responses = {cases[0]['id']: json.dumps({'answer': cases[0]['expected']})}
    report = score_responses(cases, responses)
    assert report['passed'] == 1
    assert report['total'] == 24
    assert report['accuracy'] == 1 / 24
    assert len(report['per_case']) == 24
    assert report['per_case'][1]['reason'] == 'missing_output'
    with pytest.raises(ValueError, match='Unknown case'):
        score_responses(cases, {'not-a-case': '{}'})


def test_all_reference_responses_score_one_and_no_partial_credit():
    cases = load_cases()
    responses = {c['id']: json.dumps({'answer': c['expected']}) for c in cases}
    assert score_responses(cases, responses)['accuracy'] == 1
    assert not grade_case({'expected': [1, 2]}, '{"answer": [1, 3]}')['passed']


def test_answer_keys_against_independent_trusted_calculations():
    # These are fixed, reviewed test computations, never model output or eval().
    answers = {}
    answers['code-01-slice'] = [8, 3, 9, 2, 7][1:4]
    counts = {'red': 2, 'blue': 5}
    answers['code-02-default'] = counts.get('green', 0) + counts['red']
    answers['code-03-filter'] = [x * 2 for x in [1, 4, 3, 6] if x % 2 == 0]
    answers['code-04-inclusive-repair'] = 'B'
    assert [sum(range(1, n + 1)) for n in range(10)] == [
        n * (n + 1) // 2 for n in range(10)
    ]
    rows = [('m', 2), ('a', 1), ('z', 2), ('b', 1)]
    answers['code-05-stable-sort'] = [name for name, _ in sorted(rows, key=lambda x: x[1])]
    first = [1, 2]
    alias = first
    copied = first[:]
    alias.append(3)
    copied[0] = 9
    answers['code-06-alias'] = [first, copied]
    answers['code-07-run-count'] = [
        sum(i == 0 or x != xs[i - 1] for i, x in enumerate(xs))
        for xs in ([], [2, 2, 5, 5, 2])
    ]
    answers['code-08-fallback-repair'] = 'A'
    assert [10 if x is None else x for x in [None, 0, -3, 7]] == [10, 0, -3, 7]
    answers['code-09-negative-divmod'] = [-7 // 3, -7 % 3, 7 // -3, 7 % -3]

    def add(value, bucket=[]):
        bucket.append(value)
        return len(bucket)

    answers['code-10-default-list'] = [add('a'), add('b'), add('c', []), add('d')]
    answers['code-11-bisect-repair'] = 'C'
    for values in ([], [1], [1, 1, 3, 7]):
        for target in range(-1, 10):
            lo, hi = 0, len(values)
            while lo < hi:
                mid = (lo + hi) // 2
                if values[mid] < target:
                    lo = mid + 1
                else:
                    hi = mid
            assert lo == next((i for i, value in enumerate(values) if value >= target), len(values))
    answers['code-12-overlap-repair'] = 'D'
    for a, b in combinations(range(-2, 4), 2):
        for c, d in combinations(range(-2, 4), 2):
            assert (max(a, c) < min(b, d)) == bool(set(range(a, b)) & set(range(c, d)))

    answers['reason-01-remainder'] = 47 % 6
    answers['reason-02-unit-conversion'] = 2 * 1000 + 350
    answers['reason-03-inclusion'] = 30 - (18 + 14 - 7)
    answers['reason-04-critical-path'] = max(3, 5) + 4 + 2
    answers['reason-05-modular'] = next(n for n in range(1, 100) if n % 5 == 2 and n % 7 == 3)
    valid_paths = 0
    for up_steps in combinations(range(5), 2):
        x = y = 0
        blocked = False
        for step in range(5):
            if step in up_steps:
                y += 1
            else:
                x += 1
            blocked |= (x, y) == (1, 1)
        valid_paths += not blocked
    answers['reason-06-path-count'] = valid_paths

    record = {'job_id': 'task-27', 'owner': 'Mina', 'retries': 2, 'status': 'queued'}
    answers['extract-01-record'] = {key: record[key] for key in ('job_id', 'retries')}
    answers['extract-02-status-filter'] = [key for key, status in [('r1', 'ok'), ('r2', 'error'), ('r3', 'ok')] if status == 'ok']
    events = [('A', 4, 'queued'), ('B', 3, 'running'), ('A', 9, 'done'), ('B', 2, 'queued')]
    latest = {}
    for name, seq, state in sorted(events, key=lambda event: event[1]):
        latest[name] = state
    answers['extract-03-latest-event'] = latest
    counts = {'p': 0, 'q': None, 's': 3}
    answers['extract-04-null-zero'] = {
        key: counts[key] if counts.get(key) is not None else 10 for key in ['p', 'q', 'r', 's']
    }
    transactions = [('t1', 'A', 5), ('t2', 'B', 7), ('t1', 'A', 5), ('t3', 'A', -2), ('t4', 'B', -3)]
    seen = set()
    balances = {'A': 0, 'B': 0}
    for transaction, account, amount in transactions:
        if transaction not in seen:
            seen.add(transaction)
            balances[account] += amount
    answers['extract-05-ledger'] = balances
    records = [('oak', 1, True), ('elm', 3, False), ('oak', 4, True), ('elm', 2, True), ('ash', 5, False)]
    versions = {}
    for name, version, valid in records:
        if valid:
            versions[name] = max(version, versions.get(name, version))
    answers['extract-06-latest-valid'] = [[name, version] for name, version in sorted(versions.items())]
    assert answers == {case['id']: case['expected'] for case in load_cases()}
