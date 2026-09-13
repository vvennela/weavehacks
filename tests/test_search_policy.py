from copy import deepcopy

import pytest

from sera.config import InvestigationSpace, LARGE_MODEL_ID, MODEL_ID, RuntimeConfig, Workload
from sera.search_policy import propose_search_space


def baseline(length=100, **config):
    return {'runtime': {'configuration': RuntimeConfig(**config).model_dump()},
            'input_token_ids': [list(range(length))]}


def propose(record, concurrency=1, **kwargs):
    return propose_search_space(record, model_id=MODEL_ID,
                                workload=Workload(concurrency=[concurrency]), **kwargs)


def test_normal_values_follow_tokens_and_declared_load_without_combinations():
    report = propose(baseline())
    assert report['space']['supported_changes'] == {
        'max_model_len': [256], 'max_num_seqs': [1], 'max_num_batched_tokens': [256]}
    assert len(report['space']['candidate_hashes']) == 3
    assert report['evidence']['required_context_tokens'] == 164
    assert report['missing_or_invalid']
    assert all(len(row['changed']) == 1 for row in report['candidates'])


@pytest.mark.parametrize('tokens', [None, [], [[]], [[True]], [['1']], [[-1]]])
def test_missing_or_malformed_input_tokens_produce_no_guessed_space(tokens):
    record = baseline()
    record['input_token_ids'] = tokens
    assert propose(record)['space'] is None


def test_long_context_is_never_shortened_below_prompt_plus_output_allowance():
    report = propose(baseline(3000), concurrency=8)
    assert 'max_model_len' not in (report['space'] or {}).get('supported_changes', {})
    assert propose(baseline(4050))['space'] is None


def test_all_noops_return_no_candidate():
    report = propose(baseline(64, max_model_len=128, max_num_seqs=1, max_num_batched_tokens=128))
    assert report['space'] is None
    assert report['status'] == 'no-candidate'


def load_metrics(queue=10, before=0, after=0, kv=99):
    return [{'concurrency': 8, 'metrics': {
        'before-measurement': {'preemptions': before},
        'after-measurement': {'mean_queue_ms': queue, 'preemptions': after, 'kv_cache_percent': kv}}}]


def test_higher_batch_requires_demand_queue_and_zero_observed_preemptions():
    record = baseline(900)
    record['loads'] = load_metrics()
    report = propose(record, concurrency=8)
    assert report['space']['supported_changes']['max_num_batched_tokens'] == [8192]
    assert report['evidence']['loads'][0]['preemptions_delta'] == 0
    assert 'cumulative' in report['evidence']['loads'][0]['queue_scope']
    assert report['evidence']['kv_pressure_established'] is False
    record['loads'] = load_metrics(queue=0)
    assert 'max_num_batched_tokens' not in propose(record, concurrency=8)['space']['supported_changes']


@pytest.mark.parametrize('bad', [True, -1, float('nan'), float('inf'), '10', None])
def test_invalid_queue_is_not_positive_queue_evidence(bad):
    record = baseline(900)
    record['loads'] = load_metrics(queue=bad)
    report = propose(record, concurrency=8)
    assert 'max_num_batched_tokens' not in report['space']['supported_changes']


def test_preemption_delta_selects_lower_batch_and_counter_reset_does_not():
    record = baseline(900)
    record['loads'] = load_metrics(before=10, after=12)
    report = propose(record, concurrency=8)
    assert report['space']['supported_changes']['max_num_batched_tokens'] == [2048]
    record['loads'] = load_metrics(before=10, after=0)
    report = propose(record, concurrency=8)
    assert 'max_num_batched_tokens' not in report['space']['supported_changes']
    assert report['missing_or_invalid']


def test_explicit_frozen_space_is_preserved_exactly_and_not_mutated():
    supplied = InvestigationSpace(supported_changes={'max_num_batched_tokens': [2048, 1024]},
                                 candidate_hashes=[RuntimeConfig(max_num_batched_tokens=1024).config_hash])
    before = deepcopy(supplied.model_dump())
    report = propose({}, explicit_space=supplied)
    assert report['space'] == before
    assert report['status'] == 'explicit-preserved'
    report['space']['supported_changes']['max_num_batched_tokens'].append(512)
    assert supplied.model_dump() == before


def test_explicit_dictionary_is_preserved_without_inserting_optional_fields():
    supplied = {'supported_changes': {'max_num_batched_tokens': [2048]}}
    assert propose({}, explicit_space=supplied)['space'] == supplied


def test_large_fp8_never_generates_cache_precision_and_bounds_stay_small():
    record = baseline(900, quantization='fp8_per_tensor', max_num_batched_tokens=65536)
    report = propose_search_space(record, model_id=LARGE_MODEL_ID, workload=Workload(concurrency=[8]))
    assert 'kv_cache_dtype' not in report['space']['supported_changes']
    assert len(report['candidates']) <= 32
    assert all(row['configuration']['quantization'] == 'fp8_per_tensor' and
               row['configuration']['kv_cache_dtype'] == 'auto' for row in report['candidates'])


@pytest.mark.parametrize('record', [{}, {'runtime': None}, {'runtime': {'configuration': {}}},
                                  {'runtime': {'configuration': {'max_model_len': True}}}])
def test_missing_or_malformed_baseline_configuration_is_reported_not_guessed(record):
    report = propose(record)
    assert report['space'] is None
    assert 'configuration' in report['missing_or_invalid'][0]


def test_incomplete_load_coverage_never_uses_queue_to_expand_batches():
    record = baseline(900)
    record['loads'] = load_metrics()
    report = propose_search_space(record, model_id=MODEL_ID, workload=Workload(concurrency=[1, 8]))
    assert 'max_num_batched_tokens' not in report['space']['supported_changes']


def test_input_records_and_live_defaults_are_unchanged():
    from sera.config import SUPPORTED_CHANGES
    record = baseline()
    before, defaults = deepcopy(record), deepcopy(SUPPORTED_CHANGES)
    propose(record)
    assert record == before
    assert SUPPORTED_CHANGES == defaults
