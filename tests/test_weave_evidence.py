"""Persisted trace queries use fake boundaries: no Weave service or model calls."""

from copy import deepcopy
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

import pytest

from experiments.weave_evidence import WeaveEvidenceReader, WeaveEvidenceError


IDENTITY = dict(trial_id='candidate', model_id='fixture-model', revision='pinned', config_hash='config-1')


def evidence():
    return {'trace_scope': [IDENTITY | {'task_quality': {'version': 'fixed-v1', 'per_prompt': [
        {'prompt_index': 0, 'score': 0, 'error': None}, {'prompt_index': 1, 'score': 1, 'error': None}]}}]}


def call(name, identifier, payload, **changes):
    return SimpleNamespace(id=identifier, trace_id='this-run',
        op_name=f'weave:///entity/project/op/{name}:version', ended_at='complete', exception=None,
        output=IDENTITY | payload, **changes)


def calls():
    result = []
    for phase in ('measured', 'quality', 'self_check'):
        for index in range(2):
            result.append(call('recorded_model_request', f'{phase}-{index}', dict(
                phase=phase, prompt_index=index, concurrency=1, input='question', output=f'answer-{index}',
                latency_ms=10 + index, usage={'completion_tokens': 3}, secret='must-not-leak')))
    result.append(call('recorded_trial_metrics', 'metrics', dict(status='collected',
        reduced={'request_count': 2}, quality_requests=2, self_check_requests=2,
        loads=[{'concurrency': 1, 'reduced': {'request_count': 2, 'p95_latency_ms': 11}}])))
    return result


class Client:
    entity = 'entity'
    project = 'project'

    def __init__(self, records=None):
        self.records = calls() if records is None else records
        self.events = []

    def flush(self):
        self.events.append('flush')

    def get_calls(self, **kwargs):
        self.events.append(kwargs)
        return iter(self.records)


def test_remote_reads_are_filtered_cited_bounded_and_cache_is_detached():
    client = Client()
    reader = WeaveEvidenceReader(client, 'this-run')
    quality = reader('quality_outputs', evidence())
    assert client.events[0] == 'flush'
    query = client.events[1]
    assert query['filter'] == {'trace_ids': ['this-run'], 'op_names': [
        'weave:///entity/project/op/recorded_model_request:*',
        'weave:///entity/project/op/recorded_trial_metrics:*']}
    assert query['limit'] == 6001 and 'inputs' not in query['columns']
    assert all(key in repr(query['query']) for key in IDENTITY.values())
    assert quality['source'] == 'weave' and quality['trace_id'] == 'this-run'
    assert quality['records'][0]['call_id'] == 'quality-0'
    assert quality['records'][0]['task_score'] == 0
    assert quality['records'][0]['evaluator_source'] == 'fixed local evaluator'
    assert quality['records'][0]['evaluator_version'] == 'fixed-v1'
    assert len(quality['records'][0]['output_sha256']) == 64
    assert 'must-not-leak' not in repr(quality)
    quality['records'][0]['output'] = 'changed by caller'
    repeated = reader('quality_outputs', evidence())
    assert repeated['cache_status'] == 'hit' and repeated['records'][0]['output'] == 'answer-0'
    assert len(client.events) == 2
    slow = reader('latency_outliers', evidence())
    assert [item['call_id'] for item in slow['records']] == ['measured-1', 'measured-0']
    loads = reader('load_metrics', evidence())
    assert loads['records'][0]['call_id'] == 'metrics'
    assert loads['records'][0]['reduced']['p95_latency_ms'] == 11


@pytest.mark.parametrize('field,value', [('trace_id', 'wrong-run'), ('ended_at', None),
                                        ('exception', 'failed')])
def test_nonmatching_calls_are_never_evidence(field, value):
    unwanted = deepcopy(calls()[0])
    setattr(unwanted, field, value)
    unwanted.id = 'unwanted'
    result = WeaveEvidenceReader(Client(calls() + [unwanted]), 'this-run')('latency_outliers', evidence())
    assert all(item['call_id'] != 'unwanted' for item in result['records'])


@pytest.mark.parametrize('field', list(IDENTITY))
def test_each_identity_field_must_match_even_if_server_filter_leaks(field):
    unwanted = deepcopy(calls()[0])
    unwanted.id = 'unwanted'
    unwanted.output[field] = 'wrong'
    result = WeaveEvidenceReader(Client(calls() + [unwanted]), 'this-run')('latency_outliers', evidence())
    assert all(item['call_id'] != 'unwanted' for item in result['records'])


@pytest.mark.parametrize('records', [[], calls()[:-1], calls()[1:]])
def test_missing_or_partial_persisted_data_fails_without_local_fallback(records):
    with pytest.raises(WeaveEvidenceError, match='incomplete'):
        WeaveEvidenceReader(Client(records), 'this-run')('quality_outputs', evidence())


def test_failed_query_is_explicit_and_not_cached():
    client = Client()
    def fail(**kwargs):
        raise RuntimeError('secret server body')
    client.get_calls = fail
    reader = WeaveEvidenceReader(client, 'this-run')
    with pytest.raises(WeaveEvidenceError) as error:
        reader('quality_outputs', evidence())
    assert 'RuntimeError' in str(error.value) and 'secret' not in str(error.value)
    client.get_calls = lambda **kwargs: iter(calls())
    assert reader('quality_outputs', evidence())['cache_status'] == 'miss'


def test_query_limit_is_detected_not_silently_treated_as_complete():
    with pytest.raises(WeaveEvidenceError, match='limit'):
        WeaveEvidenceReader(Client([calls()[0]] * 6001), 'this-run')('quality_outputs', evidence())


def test_new_scope_or_score_snapshot_invalidates_cache_and_threads_share_only_fetch():
    client = Client()
    reader = WeaveEvidenceReader(client, 'this-run')
    with ThreadPoolExecutor(max_workers=3) as workers:
        results = list(workers.map(lambda _: reader('quality_outputs', evidence()), range(3)))
    assert sum(result['cache_status'] == 'miss' for result in results) == 1
    assert len(client.events) == 2
    changed = evidence()
    changed['trace_scope'][0]['task_quality']['per_prompt'][0]['score'] = 1
    assert reader('quality_outputs', changed)['cache_status'] == 'miss'
    changed['trace_scope'][0]['config_hash'] = 'new-config'
    with pytest.raises(WeaveEvidenceError):
        reader('quality_outputs', changed)
    assert len(client.events) == 6


@pytest.mark.parametrize('query,scope', [('invented', evidence()), ('quality_outputs', {}),
                                     ('quality_outputs', {'trace_scope': [{}]})])
def test_invalid_requests_fail_before_query(query, scope):
    client = Client()
    with pytest.raises(WeaveEvidenceError):
        WeaveEvidenceReader(client, 'this-run')(query, scope)
    assert client.events == []


def test_output_examples_remain_bounded_and_original_saved_values_are_not_repaired():
    records = calls()
    records[2].output.update(input='i' * 3000, output='```bad answer' + 'x' * 3000)
    result = WeaveEvidenceReader(Client(records), 'this-run')('quality_outputs', evidence())
    selected = result['records'][0]
    assert len(selected['input']) == len(selected['output']) == 1000
    assert selected['output'].startswith('```bad answer')
    assert selected['input_truncated'] and selected['output_truncated']
    assert len(records[2].output['output']) > 3000


def test_new_trial_invalidates_cache_and_scores_join_on_configuration_and_prompt_index():
    client = Client()
    reader = WeaveEvidenceReader(client, 'this-run')
    reader('quality_outputs', evidence())
    later = deepcopy(calls())
    for record in later:
        record.id = 'later-' + record.id
        record.output.update(trial_id='trial-2', config_hash='config-2')
    client.records.extend(later)
    scope = evidence()
    scope['trace_scope'].append(dict(IDENTITY, trial_id='trial-2', config_hash='config-2',
        task_quality={'version': 'same-evaluator', 'per_prompt': [{'prompt_index': 1, 'score': 0}]}))
    result = reader('quality_outputs', scope)
    assert result['cache_status'] == 'miss' and len(client.events) == 4
    by_call = {item['call_id']: item for item in result['records']}
    assert by_call['quality-1']['task_score'] == 1
    assert by_call['later-quality-1']['task_score'] == 0
    assert result['records'][1]['call_id'] == 'later-quality-1'


def test_example_and_load_counts_remain_bounded_at_larger_declared_scope():
    client = Client([])
    scope = []
    for trial_index in range(9):
        identity = dict(IDENTITY, trial_id=f'trial-{trial_index}', config_hash=f'config-{trial_index}')
        scope.append(identity)
        for record in calls():
            record.id = f'{trial_index}-{record.id}'
            record.output.update(identity)
            if record.op_name.endswith('/recorded_trial_metrics:version'):
                record.output['loads'] *= 4
            client.records.append(record)
    reader = WeaveEvidenceReader(client, 'this-run')
    quality = reader('quality_outputs', {'trace_scope': scope})
    assert len(quality['records']) == 4 and quality['omitted_record_count'] == 14
    slow = reader('latency_outliers', {'trace_scope': scope})
    assert len(slow['records']) == 2 and slow['omitted_record_count'] == 16
    loads = reader('load_metrics', {'trace_scope': scope})
    assert len(loads['records']) == 12 and loads['omitted_record_count'] == 24


def test_weave_boxed_numbers_and_nonsliceable_lists_are_normalized_before_validation():
    class BoxedInt(int):
        pass

    class BoxedFloat(float):
        pass

    class WeaveList(list):
        def __getitem__(self, index):
            if isinstance(index, slice):
                raise TypeError('Slices not yet supported')
            return super().__getitem__(index)

    records = calls()
    records[0].output['latency_ms'] = BoxedFloat(999)
    records[0].output['input'] = WeaveList([{'role': 'user', 'content': 'question'}])
    records[-1].output['reduced']['request_count'] = BoxedInt(2)
    records[-1].output['quality_requests'] = BoxedInt(2)
    records[-1].output['self_check_requests'] = BoxedInt(2)
    records[-1].output['loads'] = WeaveList(records[-1].output['loads'])
    result = WeaveEvidenceReader(Client(records), 'this-run')('latency_outliers', evidence())
    assert result['records'][0]['call_id'] == 'measured-0'
    assert type(result['records'][0]['latency_ms']) is float
    assert result['records'][0]['input'] == [{'role': 'user', 'content': 'question'}]
    assert isinstance(records[0].output['input'], WeaveList)
