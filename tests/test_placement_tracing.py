"""Fake Weave boundaries; no trace service, model provider, or GPU calls."""

from contextvars import ContextVar
from types import SimpleNamespace
import sys
import json

import pytest

from test_placement import environment, inputs, FakeModel, MODEL_ID, GLM_MODEL_ID
from sera.runtime import CleanupError


@pytest.fixture
def weave(monkeypatch):
    events = []
    current = ContextVar('placement_test_call', default=None)
    state = dict(events=events, flushed=0, fail_event=None, flush_error=False, fail_after_root=False)
    def op(fn=None, *, name=None):
        def decorate(function):
            def run(*args, **kwargs):
                operation = name or function.__name__
                if operation == state['fail_event']:
                    raise RuntimeError('secret provider diagnostic')
                parent = current.get()
                token = current.set(SimpleNamespace(trace_id='test-trace', ui_url='test-url'))
                try:
                    output = function(*args, **kwargs)
                    events.append(dict(name=operation, parent=parent, args=args, output=output))
                    if operation == 'sera_place' and state['fail_after_root']:
                        raise OSError('synthetic root serialization failure')
                    return output
                finally:
                    current.reset(token)
            return run
        return decorate(fn) if fn else decorate
    def flush():
        state['flushed'] += 1
        if state['flush_error']:
            raise OSError('secret flush diagnostic')
    def initialize(project):
        state['project'] = project
        return SimpleNamespace(flush=flush)
    monkeypatch.setitem(sys.modules, 'weave', SimpleNamespace(
        init=initialize, op=op, get_current_call=current.get))
    return state


def test_trace_includes_joint_outputs_scores_failure_reasons_and_root(environment, weave, tmp_path):
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run', weave_project='test/project')
    assert result.report['trace_status'] == 'enabled'
    assert result.report['weave_url'] == 'test-url'
    events = weave['events']
    requests = [event for event in events if event['name'] == 'recorded_model_request']
    assert {event['output']['model_id'] for event in requests} == {MODEL_ID, GLM_MODEL_ID}
    assert {event['output']['trial_id'] for event in requests} == {'isolated', 'joint'}
    assert all(event['parent'] is not None for event in requests)
    assert all(event['output']['output'] == '4' for event in requests)
    gates = [event['output'] for event in events if event['name'] == 'placement_quality_gate']
    assert len(gates) == 4
    assert all(gate['task_quality']['passed'] for gate in gates)
    root = next(event for event in events if event['name'] == 'sera_place')
    assert root['output']['decision']['outcome'] == 'safe-placement'
    assert 'models' not in root['output']
    assert weave['flushed'] == 1
    result.close()
    assert any(event['name'] == 'placement_cleanup' for event in events)
    assert weave['flushed'] == 2


def test_failed_quality_outputs_and_gate_are_visible(environment, weave, tmp_path):
    FakeModel.wrong_model = MODEL_ID
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run', weave_project='test/project')
    assert result.models == []
    gates = [event['output'] for event in weave['events'] if event['name'] == 'placement_quality_gate']
    assert gates[0]['task_quality']['mean'] == 0
    assert gates[0]['gate']['passed'] is False
    decision = next(event['output'] for event in weave['events'] if event['name'] == 'placement_decision')
    assert decision['decision']['reason'] == 'isolated-requirements-failed'


def test_trace_failure_does_not_rewrite_measured_quality_or_leak_exception(environment, weave, tmp_path):
    weave['fail_event'] = 'placement_quality_gate'
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run', weave_project='test/project')
    assert len(result.models) == 2
    assert result.report['decision']['outcome'] == 'safe-placement'
    assert result.report['trace_status'] == 'failed'
    assert result.report['trace_export_failures']
    assert 'secret' not in json.dumps(result.report)
    result.close()


def test_flush_failure_is_saved_and_does_not_leak_or_close_accessible_runner(environment, weave, tmp_path):
    weave['flush_error'] = True
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run', weave_project='test/project')
    assert len(result.models) == 2
    assert result.report['trace_status'] == 'failed'
    assert result.report['trace_flush_error'] == 'OSError'
    assert 'secret' not in json.dumps(result.report)
    result.close()


def test_failed_root_setup_starts_no_gpu(environment, weave, tmp_path):
    weave['fail_event'] = 'sera_place'
    with pytest.raises(RuntimeError):
        environment.place(**inputs(environment), output_dir=tmp_path/'run', weave_project='test/project')
    assert not FakeModel.instances


def test_untraced_call_does_not_initialize_weave(environment, weave, tmp_path):
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run')
    assert 'project' not in weave
    assert not weave['events']
    result.close()


def test_failed_isolated_cleanup_stays_failed_under_trace_wrapper(environment, weave, tmp_path):
    FakeModel.cleanup_failure = MODEL_ID
    with pytest.raises(CleanupError):
        environment.place(**inputs(environment), output_dir=tmp_path/'run', weave_project='test/project')
    report = json.loads((tmp_path/'run'/'result.json').read_text())
    assert report['status'] == 'cleanup-failed'
    assert report['returned_runner_closed'] is False


def test_request_export_failure_marks_trace_failed_not_quality(environment, weave, tmp_path):
    weave['fail_event'] = 'recorded_model_request'
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run', weave_project='test/project')
    assert result.report['trace_status'] == 'failed'
    assert result.report['decision']['outcome'] == 'safe-placement'
    assert len(result.report['trace_export_failures']) == 4
    result.close()


def test_runtime_failure_trace_excludes_arbitrary_server_error_text(environment, weave, monkeypatch, tmp_path):
    def fail_start(self):
        self.artifact_dir.mkdir(parents=True)
        self.record.update(startup_failure=dict(category='unclassified', known_message='secret server text'),
                           error='secret server text')
        raise RuntimeError('secret server text')
    monkeypatch.setattr(FakeModel, 'start', fail_start)
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run', weave_project='test/project')
    event = next(event for event in weave['events'] if event['name'] == 'placement_runtime_failure')
    assert event['output']['startup_failure']['category'] == 'unclassified'
    assert 'secret server text' not in str(weave['events'])
    assert result.models == []


def test_root_export_failure_after_execution_closes_both_returned_runners(environment, weave, tmp_path):
    weave['fail_after_root'] = True
    with pytest.raises(OSError, match='serialization'):
        environment.place(**inputs(environment), output_dir=tmp_path/'run', weave_project='test/project')
    assert len(FakeModel.instances) == 4
    assert all(model.closed for model in FakeModel.instances)


def test_failed_flush_persistence_still_closes_both_runners(environment, weave, monkeypatch, tmp_path):
    original = environment.PlacementResult._save
    def fail_save(self):
        if self.report.get('trace_flush_error'):
            raise OSError('synthetic trace persistence failure')
        return original(self)
    monkeypatch.setattr(environment.PlacementResult, '_save', fail_save)
    weave['flush_error'] = True
    with pytest.raises(OSError, match='persistence'):
        environment.place(**inputs(environment), output_dir=tmp_path/'run', weave_project='test/project')
    assert len(FakeModel.instances) == 4
    assert all(model.closed for model in FakeModel.instances)
