"""Opt-in event sinks are context-local and cannot mutate measurement records."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from sera.tracing import TraceSinkError, emit_event, recorded_model_request, use_event_sink


def test_default_sink_is_noop_and_nested_context_restores_parent():
    outer, inner = [], []
    assert emit_event('fixture', {'value': 0}) is False
    with use_event_sink(lambda name, payload: outer.append((name, payload))):
        assert emit_event('fixture', {'value': 1}) is True
        with use_event_sink(lambda name, payload: inner.append((name, payload))):
            emit_event('fixture', {'value': 2})
        with use_event_sink(None):
            assert emit_event('fixture', {'value': 3}) is False
        emit_event('fixture', {'value': 4})
    assert [payload['value'] for _, payload in outer] == [1, 4]
    assert [payload['value'] for _, payload in inner] == [2]
    assert emit_event('fixture', {'value': 5}) is False


def test_sink_is_not_implicitly_shared_with_request_worker_threads():
    events = []
    with use_event_sink(lambda *event: events.append(event)):
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(emit_event, 'worker', {'value': 1}).result() is False
        emit_event('parent', {'value': 2})
    assert [name for name, _ in events] == ['parent']


def test_sink_failure_is_explicit_without_exposing_exception_body():
    def fail(name, payload):
        raise RuntimeError('fixture secret must not appear in trace errors')

    with use_event_sink(fail), pytest.raises(TraceSinkError) as failure:
        emit_event('recorded_model_request', {'value': 1})
    assert failure.value.event_name == 'recorded_model_request'
    assert failure.value.error_type == 'RuntimeError'
    assert 'fixture secret' not in str(failure.value)


def test_async_sink_is_rejected_instead_of_silently_dropping_events():
    async def async_sink(name, payload):
        return None

    with pytest.raises(TypeError, match='synchronous'):
        with use_event_sink(async_sink):
            emit_event('fixture', {})


def test_recorded_request_allowlists_response_fields_and_copies_input():
    events = []
    prompt = [{'role': 'user', 'content': 'question'}]
    response = {'text': 'answer', 'token_ids': [3], 'prompt_token_ids': [2],
                'latency_ms': 12.0, 'finish_reason': 'stop',
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'headers': 'secret'},
                'headers': {'Authorization': 'secret'}, 'api_key': 'secret',
                'error': 'RuntimeError: secret'}

    def sink(name, payload):
        events.append((name, payload))
        payload['input'][0]['content'] = 'mutated event'

    with use_event_sink(sink):
        recorded_model_request(trial_id='returned', model_id='fixture', revision='pin',
            config_hash='hash', phase='post-return', concurrency=1, prompt_index=0,
            prompt=prompt, response=response)
    name, event = events[0]
    assert name == 'recorded_model_request'
    assert event['output'] == 'answer'
    assert event['latency_ms'] == 12.0
    assert event['error'] == 'RuntimeError'
    assert event['usage'] == {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': None}
    assert event['token_ids'] == [3]
    assert event['prompt_token_ids'] == [2]
    assert 'logging time' in event['timing_scope']
    assert 'secret' not in repr(event)
    assert prompt[0]['content'] == 'question'
    assert response['text'] == 'answer'
