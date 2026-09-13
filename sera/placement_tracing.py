"""Optional Weave export for explicit placement; never serialize live owners."""

from .tracing import use_event_sink
from .weave_evidence import RECORDED_OPS
from .diagnosis import runtime_failure_evidence


def _summary(result):
    report = result.report
    shared = report.get('shared_runtime') or {}
    return dict(plan_hash=report['plan_hash'], workload_hash=report['workload_hash'],
        status=report['status'], decision=report['decision'],
        error_type=report.get('error_type'), cleanup_error=report.get('cleanup_error'),
        isolated_gates=report['isolated_gates'], joint_gates=report.get('joint', {}).get('gates'),
        overlap=report.get('joint', {}).get('overlap'),
        isolated_comparison=report.get('joint', {}).get('isolated_comparison'),
        memory=dict(device_peak_mib=shared.get('sampled_peak_memory_mib'),
                    service_peak_mib=shared.get('service_peak_memory_mib'),
                    telemetry_errors=shared.get('telemetry_errors'), errors=shared.get('errors')),
        returned_runner_count=len(result.models), returned_runner_closed=report['returned_runner_closed'],
        weave_url=report.get('weave_url'), trace_status=report.get('trace_status'),
        quantization_enabled_placement=report['quantization_enabled_placement'])


def _trial_failures(result):
    trials = list(result.report['isolated'].values()) + list(result.report.get('joint', {}).get('trials', {}).values())
    return [dict(trial_id=trial['trial_id'], model_id=trial['runtime']['model_id'],
                 event=export.get('failed_event'), error_type=export.get('error_type'))
            for trial in trials for export in [trial.get('trace_export', {})]
            if export.get('status') == 'failed']


def placement_event_sink(weave):
    """Shared event vocabulary for explicit trials and the placement search."""
    def operation(name):
        def record(payload):
            return payload
        return weave.op(name=name)(record)

    operations = {name:operation(name) for name in (*RECORDED_OPS,
        'placement_quality_gate', 'placement_decision', 'placement_cleanup', 'placement_runtime_failure')}

    def sink(name, payload):
        operations[name](payload)
    return sink


def run_traced_placement(execute, arguments, project):
    try:
        import weave
    except ImportError:
        raise ImportError('Install sera-inference[swarm] for optional placement tracing') from None
    client = weave.init(project)
    result = None
    sink = placement_event_sink(weave)

    def flush():
        try:
            client.flush()
        except Exception as error:
            if result is not None:
                result.report.update(trace_status='failed', trace_flush_error=type(error).__name__)
                result._save()

    def cleanup_trace(completed):
        # The optimization root has ended after return. This event carries its URL
        # and plan hash; it does not pretend later caller activity happened inside it.
        with use_event_sink(sink):
            completed._event('placement_cleanup', _summary(completed))
        flush()

    def run():
        call = weave.get_current_call()
        if call is None:
            raise RuntimeError('Weave did not create the placement trace')

        def observe(created):
            nonlocal result
            result = created
            result.report.update(weave_url=call.ui_url, trace_status='enabled', trace_export_failures=[])
            result._trace_on_close = cleanup_trace

        try:
            execute(**arguments, _result_observer=observe)
        finally:
            if result is not None:
                result.report['trace_export_failures'].extend(_trial_failures(result))
                if result.report['trace_export_failures']:
                    result.report['trace_status'] = 'failed'
                runtimes = result.report['isolated_runtimes'] + (
                    [model.record for model in result.owner.models] if result.owner is not None else [])
                for runtime in runtimes:
                    if runtime.get('startup_failure'):
                        result._event('placement_runtime_failure', dict(
                            plan_hash=result.report['plan_hash'], model_id=runtime['model_id'],
                            revision=runtime['revision'], config_hash=runtime.get('config_hash'),
                            startup_failure=runtime_failure_evidence(runtime['startup_failure'])))
                result._event('placement_decision', _summary(result))
                result._save()
        return _summary(result)

    try:
        try:
            with use_event_sink(sink):
                weave.op(name='sera_place')(run)()
        finally:
            flush()
    except BaseException as error:
        if result is not None and result.owner is not None:
            try:
                result.close()
            except BaseException as cleanup_error:
                error.add_note('Placement cleanup or trace persistence also failed: ' + type(cleanup_error).__name__)
        raise
    return result
