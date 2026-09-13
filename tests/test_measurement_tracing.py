"""Trace saved outputs only after all timed request windows finish."""

import json
from types import SimpleNamespace

from sera import measurement
from sera.config import RuntimeConfig, Workload
from sera.tracing import use_event_sink


class Model:
    configuration = RuntimeConfig()

    def __init__(self, folder, *, fail_request=False):
        self.artifact_dir = folder
        self.record = {'model_id': 'fixture', 'revision': 'pin', 'env': {'API_KEY': 'secret'}}
        self.calls = 0
        self.fail_request = fail_request

    def prepare(self, prompt):
        return {}, [2]

    def _generate_prepared(self, payload, tokens):
        self.calls += 1
        if self.fail_request:
            raise RuntimeError('secret request detail')
        return SimpleNamespace(to_dict=lambda: {
            'text': 'answer', 'token_ids': [3], 'prompt_token_ids': [2],
            'latency_ms': 10.0, 'finish_reason': 'stop',
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1}})

    def metrics_snapshot(self):
        return {'raw': '', 'reduced': {}}


def test_saved_requests_are_traced_after_every_measurement_window(tmp_path, monkeypatch):
    model = Model(tmp_path)
    clock_values = iter([100.0, 102.0, 200.0, 203.0])
    clock_calls = []

    def clock():
        clock_calls.append(True)
        return next(clock_values)

    monkeypatch.setattr(measurement.time, 'perf_counter', clock)
    events = []

    def sink(name, payload):
        assert len(clock_calls) == 4
        assert model.calls == 10
        saved = json.loads((tmp_path/'trial.json').read_text())
        assert saved['status'] == 'collected'
        assert len(saved['requests']) == 6
        events.append((name, payload))

    with use_event_sink(sink):
        result = measurement.collect_trial(model, ['question'], 'baseline', baseline=True,
                                            workload=Workload(concurrency=[1, 2]))
    requests = [payload for name, payload in events if name == 'recorded_model_request']
    assert len(requests) == 10
    assert [row['phase'] for row in requests] == ['warmup'] + ['measured']*3 + ['warmup'] + ['measured']*3 + ['quality', 'self_check']
    assert [row['concurrency'] for row in requests] == [1]*4 + [2]*4 + [1, 1]
    assert all(row['input'] == 'question' and row['output'] == 'answer' for row in requests)
    assert all(row['latency_ms'] == 10.0 for row in requests)
    assert 'secret' not in repr(events)
    assert events[-1][0] == 'recorded_trial_metrics'
    assert result['reduced']['request_wall_seconds'] == 5.0
    assert result['reduced']['output_tokens_per_second'] == 6/5
    assert result['trace_export']['status'] == 'complete'
    assert result['trace_export']['emitted_events'] == 11


def test_trace_sink_failure_is_saved_without_changing_measured_verdict(tmp_path):
    model = Model(tmp_path)

    def fail(name, payload):
        raise RuntimeError('secret sink error detail')

    with use_event_sink(fail):
        result = measurement.collect_trial(model, ['question'], 'candidate')
    assert result['status'] == 'collected'
    assert model.calls == 5
    assert result['reduced']['request_count'] == 3
    assert result['trace_export'] == {
        'status': 'failed', 'emitted_events': 0, 'error_type': 'RuntimeError',
        'failed_event': 'recorded_model_request',
        'timing_scope': 'Events are exported after measurement; span durations measure logging time.'}
    assert json.loads((tmp_path/'trial.json').read_text())['trace_export'] == result['trace_export']


def test_failed_requests_are_traced_without_secret_exception_messages(tmp_path):
    model = Model(tmp_path, fail_request=True)
    events = []
    with use_event_sink(lambda name, payload: events.append((name, payload))):
        result = measurement.collect_trial(model, ['question'], 'candidate')
    assert result['status'] == 'request-errors'
    requests = [payload for name, payload in events if name == 'recorded_model_request']
    assert len(requests) == 5
    assert all(row['error'] == 'RuntimeError' and row['output'] == '' for row in requests)
    assert all(row['latency_ms'] is None for row in requests)
    assert 'secret' not in repr(events)


def test_default_collection_does_not_require_or_enable_tracing(tmp_path):
    result = measurement.collect_trial(Model(tmp_path), ['question'], 'candidate')
    assert result['status'] == 'collected'
    assert 'trace_export' not in result
