"""Configured swarm entry point; explicit low-level calls keep their contract."""

import inspect
import os

from . import pipeline
from .config import Budget, LARGE_MODEL_ID, MODEL_ID, Workload


_LEGACY_OPTIONS = {'candidate', 'agent', 'budget', 'investigation_space',
                   'automatic_space', 'swarm', 'trace_reader', 'baseline_configuration'}


def _required_environment(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise ValueError(f'{name} must be set for the configured swarm')
    return value


def _configured_agent():
    provider = _required_environment('SERA_AGENT_PROVIDER')
    if provider not in ('wandb', 'codex-relay'):
        raise ValueError('SERA_AGENT_PROVIDER must be wandb or codex-relay')
    model = _required_environment('SERA_AGENT_MODEL')
    project = _required_environment('SERA_PROJECT')
    if provider == 'codex-relay':
        from .relay import RelayAgent
        return RelayAgent(project=project, model=model,
                          relay_dir=_required_environment('SERA_RELAY_DIR'))
    if os.environ.get('SERA_RELAY_DIR'):
        raise ValueError('SERA_RELAY_DIR is only valid with codex-relay')
    from .agent import WandbAgent
    return WandbAgent(project=project, model=model)


def optimize(*, models, prompts, mode='auto', **options):
    """Run the full configured swarm and return a caller-owned live result.

    With no explicit low-level search options, ``auto`` selects a Weave-backed
    swarm, automatic candidates, concurrency 1/2/4/8, and plateau-plus-confirmation
    stopping without a total trial cap. Configure provider/model/project and a
    passing certificate through SERA_* environment variables first.

    Explicit agent, candidate, budget, space, swarm, automatic_space, reader, or reference
    options preserve the previous low-level API. Use mode='swarm' to combine
    those explicit options with configured setup, or mode='fixed' for the
    original no-agent comparison. A fixed space never expands automatically.

    Quick mode checks token agreement, not task correctness. Fit-first Qwen72B
    still requires evaluation, evaluation_version, and Constraints. Always close
    the returned result, preferably with ``with sera.optimize(...) as result``.
    """
    if mode not in ('auto', 'swarm', 'fixed'):
        raise ValueError('mode must be auto, swarm, or fixed')
    arguments = dict(models=models, prompts=prompts, **options)
    inspect.signature(pipeline.optimize).bind(**arguments)
    if mode == 'fixed':
        if any(options.get(name) is not None for name in
               ('agent', 'budget', 'investigation_space', 'trace_reader', 'provider_check')) or any(
                   options.get(name, False) is not False for name in ('swarm', 'automatic_space')):
            raise ValueError('mode=fixed cannot include agent investigation options')
        return pipeline.optimize(**arguments)
    if mode == 'auto' and _LEGACY_OPTIONS.intersection(options):
        return pipeline.optimize(**arguments)
    if options.get('candidate') is not None or options.get('swarm', True) is not True:
        raise ValueError('Configured swarm requires swarm=True and no fixed candidate')
    if options.get('trace_reader') is not None and not callable(options['trace_reader']):
        raise ValueError('trace_reader must be callable')
    if models not in ([MODEL_ID], [LARGE_MODEL_ID]):
        raise ValueError('Supply one supported pinned Qwen model')
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 32:
        raise ValueError('Supply 1 to 32 prompts; inputs are never silently dropped')
    if models == [LARGE_MODEL_ID] and (options.get('evaluation') is None or options.get('constraints') is None):
        raise ValueError('Fit-first loading requires a versioned task evaluator and explicit quality floor')
    arguments.setdefault('budget', Budget(max_candidate_trials=None))
    arguments.setdefault('workload', Workload(concurrency=[1, 2, 4, 8]))
    arguments.setdefault('automatic_space', options.get('investigation_space') is None)
    arguments['swarm'] = True
    if type(arguments['automatic_space']) is not bool:
        raise ValueError('automatic_space must be a boolean')
    if arguments['automatic_space'] and options.get('investigation_space') is not None:
        raise ValueError('Automatic space cannot expand an explicit investigation space')
    if arguments['budget'] is None:
        raise ValueError('Configured swarm requires a budget; use Budget(max_candidate_trials=None) for no cap')
    arguments['budget'] = Budget.model_validate(arguments['budget'])
    arguments['workload'] = Workload.model_validate(arguments['workload'])
    agent = options.get('agent')
    if agent is None:
        agent = _configured_agent()
    if not callable(getattr(agent, 'fork', None)):
        raise ValueError('Configured swarm requires a forkable agent')
    _required_environment('WANDB_API_KEY')
    certificate = options.get('provider_check') or _required_environment('SERA_PROVIDER_CHECK')
    from .provider_check import require_provider_check
    require_provider_check(certificate, agent)
    arguments.update(agent=agent, provider_check=certificate)
    return _run_traced(arguments)


def _run_traced(arguments):
    try:
        import weave
    except ImportError:
        raise ImportError('Install sera-inference[swarm] to run the configured swarm') from None
    from .tracing import use_event_sink
    from .weave_evidence import WeaveEvidenceReader
    from .weave_integration import (TracedInvestigationAgent, traced_evidence_reader,
                                    trial_trace_failures, weave_event_sink)

    agent = TracedInvestigationAgent(arguments['agent'], weave)
    client = weave.init(agent.project)
    result = None

    def run():
        nonlocal result
        call = weave.get_current_call()
        if call is None:
            raise RuntimeError('Weave did not create the required investigation trace')
        reader = arguments.get('trace_reader')
        if reader is None:
            reader = WeaveEvidenceReader(client, call.trace_id)
        result = pipeline.optimize(**(arguments | dict(agent=agent,
            trace_reader=traced_evidence_reader(weave, reader))))
        failures = trial_trace_failures(result.report) + agent.trace_failures
        result.report.update(weave_url=call.ui_url, trace_status='failed' if failures else 'enabled',
                             trace_export_failures=failures, public_api_mode='configured-swarm')
        result._save()
        return result.report  # Never serialize the live runner or client as an op output.

    try:
        try:
            with use_event_sink(weave_event_sink(weave)):
                weave.op(name='sera_optimize')(run)()
        finally:
            try:
                client.flush()
            except Exception as error:
                if result is not None:
                    result.report.update(trace_status='failed', trace_flush_error=type(error).__name__)
                    result._save()
    except BaseException as error:
        if result is not None:
            try:
                result.close()
            except Exception as cleanup_error:
                error.add_note(f'Returned-runner cleanup also failed: {type(cleanup_error).__name__}')
        raise
    return result
