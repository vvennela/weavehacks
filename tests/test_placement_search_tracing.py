"""The automatic placement loop keeps joint iterations under one trace."""

from test_placement import environment
from test_placement_search import search_inputs
from test_placement_tracing import weave


def test_search_trace_contains_agent_choices_and_unique_joint_trials(search_inputs, weave):
    search, args = search_inputs
    result = search.optimize_placement(**args, weave_project='test/project')
    assert result.report['trace_status'] == 'enabled'
    assert result.report['weave_url'] == 'test-url'
    events = weave['events']
    assert len([event for event in events if event['name'] == 'arbiter']) == 3
    requests = [event for event in events if event['name'] == 'recorded_model_request']
    assert {event['output']['trial_id'] for event in requests} == {
        'trial-001/joint', 'trial-002/joint', 'trial-003/joint', 'return-validation/joint'}
    assert all(event['parent'] is not None for event in requests)
    root = next(event for event in events if event['name'] == 'sera_optimize_placement')
    assert root['output']['stop_reason'] == 'objective-plateau-confirmed'
    assert root['output']['selected_plan_id']
    assert 'models' not in root['output']
    result.close()
    assert any(event['name'] == 'placement_search_cleanup' for event in events)
    assert weave['flushed'] == 2


def test_joint_trace_export_failure_is_reported_without_changing_gate(search_inputs, weave):
    search, args = search_inputs
    weave['fail_event'] = 'recorded_model_request'
    result = search.optimize_placement(**args, weave_project='test/project')
    assert result.report['trace_status'] == 'failed'
    assert result.report['trace_export_failures']
    assert len(result.models) == 2
    result.close()
