"""Strict JSON grading for sera-task-v1; never execute model output."""

import hashlib
import json
from collections import Counter
from pathlib import Path


BENCHMARK_VERSION = 'sera-task-v1'
SYSTEM_PROMPT = (
    'Solve the task. Return only one JSON object with exactly one key, "answer". '
    'Use the JSON type required by the question. Do not include explanation, '
    'Markdown, or code fences. Use JSON true, false, and null, not Python literals.'
)


def load_cases(path=None):
    case_path = Path(path) if path else Path(__file__).with_name('cases.json')
    cases = json.loads(case_path.read_text())
    if not cases or len({case['id'] for case in cases}) != len(cases):
        raise ValueError('Cases must be nonempty and have unique IDs')
    return cases


def dataset_hash(cases):
    canonical = json.dumps(cases, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f'Non-JSON numeric constant: {value}')


def _same_value(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _same_value(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _same_value(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def grade_case(case, raw_output):
    if not isinstance(raw_output, str) or not raw_output.strip():
        return {'passed': False, 'format_valid': False, 'reason': 'empty_output'}
    if len(raw_output) > 16384:
        return {'passed': False, 'format_valid': False, 'reason': 'output_too_large'}
    try:
        parsed = json.loads(
            raw_output, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        if not isinstance(parsed, dict) or set(parsed) != {'answer'}:
            raise ValueError('Expected exactly one answer field')
        passed = _same_value(parsed['answer'], case['expected'])
    except (ValueError, RecursionError):
        return {'passed': False, 'format_valid': False, 'reason': 'invalid_json_format'}
    return {
        'passed': passed,
        'format_valid': True,
        'reason': 'correct' if passed else 'wrong_answer',
    }


def score_responses(cases, responses):
    case_ids = {case['id'] for case in cases}
    unknown = set(responses) - case_ids
    if unknown:
        raise ValueError(f'Unknown case IDs: {sorted(unknown)}')
    if not cases or len(case_ids) != len(cases):
        raise ValueError('Cases must be nonempty and have unique IDs')
    results = []
    for case in cases:
        result = grade_case(case, responses.get(case['id']))
        if case['id'] not in responses:
            result['reason'] = 'missing_output'
        results.append({
            'id': case['id'], 'category': case['category'],
            'difficulty': case['difficulty'], **result,
        })
    passed = sum(result['passed'] for result in results)
    groups = {}
    for field in ('category', 'difficulty'):
        groups[field] = {}
        for value in sorted({result[field] for result in results}):
            subset = [result for result in results if result[field] == value]
            successes = sum(result['passed'] for result in subset)
            groups[field][value] = {
                'passed': successes, 'total': len(subset),
                'accuracy': successes / len(subset),
            }
    return {
        'benchmark': BENCHMARK_VERSION, 'dataset_sha256': dataset_hash(cases),
        'passed': passed, 'total': len(cases), 'accuracy': passed / len(cases),
        'format_valid': sum(result['format_valid'] for result in results),
        'failure_counts': dict(Counter(
            result['reason'] for result in results if not result['passed']
        )),
        'by_category': groups['category'], 'by_difficulty': groups['difficulty'],
        'per_case': results,
    }
