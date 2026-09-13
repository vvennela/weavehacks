"""Optional recording hooks. Core inference has no dependency on a trace service."""

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import inspect


_event_sink = ContextVar('sera_event_sink', default=None)


class InspectionReadError(RuntimeError):
    """A read failure with a fixed, secret-free explanation."""

    messages = {
        'missing-trace-id': 'A current trace ID is required.',
        'unsupported-query': 'The inspection query is not supported.',
        'invalid-scope': 'A complete bounded trial scope is required.',
        'duplicate-scope': 'The trial scope contains duplicate identities.',
        'query-failed': 'The persisted trace query failed.',
        'call-limit': 'The trace query reached the bounded call limit.',
        'incomplete-metrics': 'The persisted trial metrics are missing or duplicated.',
        'incomplete-requests': 'The persisted request counts do not match the saved trial metrics.',
        'incomplete-diagnosis': 'The required persisted trial diagnosis is missing or duplicated.',
        'task-binding-mismatch': 'Saved request does not match the fixed task answer key.',
    }

    def __init__(self, reason_code):
        if reason_code not in self.messages:
            raise ValueError('Unsupported inspection error code')
        self.reason_code = reason_code
        self.safe_message = self.messages[reason_code]
        super().__init__(self.safe_message)


class TraceSinkError(RuntimeError):
    """An enabled sink failed; its arbitrary exception text is not exported."""

    def __init__(self, event_name, error_type):
        self.event_name = event_name
        self.error_type = error_type
        super().__init__(f'Trace sink failed for {event_name}: {error_type}')


@contextmanager
def use_event_sink(sink):
    """Enable sink(event_name, payload) in this context; None disables it."""
    if sink is not None and not callable(sink):
        raise TypeError('The event sink must be callable or None')
    if inspect.iscoroutinefunction(sink):
        raise TypeError('The event sink must be synchronous')
    token = _event_sink.set(sink)
    try:
        yield
    finally:
        _event_sink.reset(token)


def event_sink_enabled():
    return _event_sink.get() is not None


def emit_event(event_name, payload):
    """Publish a copy of an already-safe record, never a model or client object."""
    sink = _event_sink.get()
    if sink is None:
        return False
    try:
        result = sink(event_name, deepcopy(payload))
        if inspect.isawaitable(result):
            if inspect.iscoroutine(result):
                result.close()
            raise TypeError('The event sink must finish synchronously')
    except Exception as error:
        raise TraceSinkError(event_name, type(error).__name__) from None
    return True


def recorded_model_request(*, trial_id, model_id, revision, config_hash, phase,
                           concurrency, prompt_index, prompt, response):
    """Export selected fields from a saved response; do not perform inference."""
    usage = response.get('usage') or {}
    error = response.get('error')
    safe_prompt = (prompt if isinstance(prompt, str) else
                   [{'role': message['role'], 'content': message['content']} for message in prompt])
    return emit_event('recorded_model_request', {
        'trial_id': trial_id, 'model_id': model_id, 'revision': revision,
        'config_hash': config_hash, 'phase': phase, 'concurrency': concurrency,
        'prompt_index': prompt_index, 'input': safe_prompt, 'output': response.get('text'),
        'error': error.split(':', 1)[0] if error else None,
        'usage': {key: usage.get(key) for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
        'prompt_token_ids': response.get('prompt_token_ids'), 'token_ids': response.get('token_ids'),
        'finish_reason': response.get('finish_reason'), 'latency_ms': response.get('latency_ms'),
        'timing_scope': 'Span duration is logging time, not inference; latency_ms is the recorded request latency.',
    })
