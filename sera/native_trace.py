"""Mandatory operator-side Weave tracing for native worker experiments."""

import os


def trace_native_job(*, project, run):
    """Return a measured record only after its completed trace is visible remotely.

    ``run`` returns JSON evidence, never a model, client, or credential. Failed
    workers retain their local job files even when exporting the trace fails.
    """
    if not os.environ.get('WANDB_API_KEY', '').strip():
        raise ValueError('The operator must configure WANDB_API_KEY')
    if not isinstance(project, str) or len(project.split('/')) != 2 or any(
        not part.strip() for part in project.split('/')
    ):
        raise ValueError('Supply the operator entity/project')
    import weave

    client = weave.init(project)
    reference = {}

    @weave.op(name='sera_native_checkpoint_experiment')
    def experiment():
        call = weave.get_current_call()
        if call is None:
            raise RuntimeError('Weave did not create the required native experiment trace')
        reference.update(call_id=call.id, trace_id=call.trace_id, url=call.ui_url)
        return run()

    try:
        result = experiment()
    except BaseException as error:
        try:
            client.flush()
        except Exception as trace_error:  # noqa: BLE001 - preserve the original worker failure
            error.add_note(f'Trace flush also failed: {type(trace_error).__name__}')
        raise
    client.flush()
    calls = client.get_calls(filter={'trace_ids': [reference['trace_id']]}, limit=10)
    if not any(call.id == reference['call_id'] and call.ended_at is not None
               and call.exception is None for call in calls):
        raise RuntimeError('Required completed native trace is not visible remotely')
    reference['remote_verified'] = True
    return {'result': result, 'trace': reference}
