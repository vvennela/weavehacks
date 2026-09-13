"""One Weave root for measured placement selection and its joint trials."""

from .placement_tracing import placement_event_sink
from .tracing import use_event_sink
from .weave_integration import TracedInvestigationAgent


def _summary(result):
    report = result.report
    return {key:report.get(key) for key in ('schema_version', 'status', 'objective', 'budget',
        'plan_ids', 'workload_hash', 'rejected', 'references', 'rounds', 'selected_plan_id',
        'stop_reason', 'returned_runner_closed', 'weave_url', 'trace_status', 'error_type',
        'capacity_evidence', 'quantization_enabled_placement', 'memory_accounting')}


def traced_placement_search(execute, arguments, project):
    if arguments['agent'].project != project:
        raise ValueError('Placement tracing project must match the selected agent project')
    try:
        import weave
    except ImportError:
        raise ImportError('Install sera-inference[swarm] for placement search tracing') from None
    client = weave.init(project)
    agent = TracedInvestigationAgent(arguments['agent'], weave)
    result = None

    def flush():
        try:
            client.flush()
        except Exception as error:
            if result is not None:
                result.report.update(trace_status='failed', trace_flush_error=type(error).__name__)
                result._save()

    def close_trace(completed):
        def record_cleanup():
            return _summary(completed)
        try:
            weave.op(name='placement_search_cleanup')(record_cleanup)()
        except Exception as error:
            completed.report.update(trace_status='failed', trace_cleanup_error=type(error).__name__)
        flush()

    def run():
        call = weave.get_current_call()
        if call is None:
            raise RuntimeError('Weave did not create a placement search root')
        def observe(created):
            nonlocal result
            result = created
            result.report.update(weave_url=call.ui_url, trace_status='enabled')
            result._trace_on_close = close_trace
        try:
            execute(**(arguments | dict(agent=agent)), _observe=observe)
        finally:
            if result is not None:
                failures = agent.trace_failures[:]
                records = [trial.get('report', {}) for trial in result.report['trials']]
                if result.report.get('restoration'):
                    records.append(result.report['restoration'])
                for record in records:
                    failures.extend(record.get('trace_export_failures', []))
                    for trial in record.get('joint', {}).get('trials', {}).values():
                        export = trial.get('trace_export', {})
                        if export.get('status') == 'failed':
                            failures.append(dict(event=export.get('failed_event'), error_type=export.get('error_type')))
                result.report['trace_export_failures'] = failures
                if failures:
                    result.report['trace_status'] = 'failed'
                result._save()
        return _summary(result)

    try:
        try:
            with use_event_sink(placement_event_sink(weave)):
                weave.op(name='sera_optimize_placement')(run)()
        finally:
            flush()
    except BaseException as error:
        if result is not None and result.placement is not None:
            try:
                result.close()
            except BaseException as cleanup_error:
                error.add_note('Placement search cleanup also failed: ' + type(cleanup_error).__name__)
        raise
    return result
