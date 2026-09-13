"""Live entrypoint contract tests. Boundaries are fake; no network or GPU use."""

import importlib
import json
import sys
from types import SimpleNamespace

import pytest

from benchmarks.grade import SYSTEM_PROMPT, dataset_hash, load_cases
from sera.config import LARGE_MODEL_ID, MODEL_ID, RuntimeConfig


@pytest.fixture
def cli(monkeypatch):
    monkeypatch.setenv('WANDB_API_KEY', 'fixture-not-a-real-key')
    return importlib.import_module('experiments.run_investigation')


def arguments(tmp_path, model=MODEL_ID):
    return ['--model', model, '--budget', '2', '--batching-values', '2048', '1024',
            '--project', 'test/project', '--provider-check', str(tmp_path/'provider.json'),
            '--output-dir', str(tmp_path/'run')]


def install_boundaries(cli, monkeypatch, tmp_path, *, no_runner=False, probe_error=False,
                       close_error=False, invalid_probe=False):
    observed = {'calls': [], 'flushed': False, 'closed': False}

    def provider_check(path, agent):
        observed['calls'].append('provider-check')
        assert agent.project == 'test/project'
        return {'path': str(path), 'fixture': True}

    def init(project):
        observed['calls'].append('weave-init')
        return SimpleNamespace(flush=lambda: observed.update(flushed=True))

    monkeypatch.setitem(sys.modules, 'weave', SimpleNamespace(
        init=init, op=lambda fn=None, **_: fn if fn is not None else lambda actual: actual,
        get_current_call=lambda: SimpleNamespace(ui_url='https://wandb.ai/fixture/call')))

    class Runner:
        def __init__(self):
            self.model_id = observed['kwargs']['models'][0]
            self.revision = 'fixture-pinned-revision'
            self.configuration = observed['kwargs']['baseline_configuration'] or RuntimeConfig()

        def generate(self, prompt):
            observed['probe_prompt'] = prompt
            if probe_error:
                raise RuntimeError('fixture generation failure')
            text = '{"answer": 999}' if invalid_probe else '{"answer": 5}'
            return SimpleNamespace(text=text, to_dict=lambda: {'text': text, 'latency_ms': 10})

    class Result:
        def __init__(self):
            self.models = [] if no_runner else [Runner()]
            self.report = {'status': 'no-safe-configuration' if no_runner else 'ready',
                           'task_quality_verified': not no_runner,
                           'search': {'trials_used': 2, 'stop_reason': 'budget-exhausted'}}
            self.output_dir = tmp_path/'run'
            self.output_dir.mkdir()

        def _save(self):
            (self.output_dir/'result.json').write_text(json.dumps(self.report))

        def close(self):
            observed['closed'] = True
            if close_error:
                raise RuntimeError('fixture cleanup failure')
            self.report['returned_runner_closed'] = True
            self._save()

        def print_summary(self):
            pass

    def optimize(**kwargs):
        observed['calls'].append('optimize')
        observed['kwargs'] = kwargs
        observed['result'] = Result()
        return observed['result']

    monkeypatch.setattr(cli, 'require_provider_check', provider_check)
    monkeypatch.setattr(cli.sera, 'optimize', optimize)
    return observed


@pytest.mark.parametrize('model', [MODEL_ID, LARGE_MODEL_ID])
def test_declared_profile_reaches_optimizer_and_saves_fresh_probe(cli, monkeypatch, tmp_path, model):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    assert cli.main(arguments(tmp_path, model)) == 0
    kwargs = observed['kwargs']
    assert kwargs['models'] == [model]
    assert kwargs['automatic_space'] is False
    assert kwargs['budget'].max_candidate_trials == 2
    assert kwargs['investigation_space'].supported_changes == {'max_num_batched_tokens': [2048, 1024]}
    assert kwargs['constraints'].quality_floor == .99
    assert kwargs['evaluation_version'] == 'sera-easy-strict-json-v1'
    assert kwargs['workload'].concurrency == [1]
    assert kwargs['objective'].min_improvement_fraction == .05
    assert kwargs['baseline_configuration'] == (
        RuntimeConfig(quantization='fp8_per_tensor') if model == LARGE_MODEL_ID else None)
    cases = load_cases(cli.CASES_PATH)
    assert len(kwargs['prompts']) == len(cases) == 8
    assert all(prompt[0] == {'role': 'system', 'content': SYSTEM_PROMPT} for prompt in kwargs['prompts'])
    assert kwargs['evaluation'](kwargs['prompts'][0], '{"answer": 5}') is True
    assert kwargs['evaluation'](kwargs['prompts'][0], '```json\n{"answer": 5}\n```') is False
    assert observed['calls'] == ['provider-check', 'weave-init', 'optimize']
    report = json.loads((tmp_path/'run'/'result.json').read_text())
    assert report['evaluation_cases_sha256'] == dataset_hash(cases)
    assert report['weave_url'] == 'https://wandb.ai/fixture/call'
    assert report['post_return_probe']['latency_ms'] == 10
    assert report['post_return_task_passed'] is True
    assert observed['closed'] and observed['flushed']


@pytest.mark.parametrize('extra', [
    ['--budget', '0'], ['--budget', '9'], ['--batching-values', '4096'],
    ['--batching-values', '2048', '2048'], ['--batching-values', '1'],
    ['--concurrency', '3'], ['--concurrency', '8', '1'],
])
def test_invalid_profile_stops_before_provider_or_gpu(cli, monkeypatch, tmp_path, extra):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as error:
        cli.main(arguments(tmp_path) + extra)
    assert error.value.code == 2
    assert observed['calls'] == []
    assert not (tmp_path/'run').exists()


def test_old_provider_certificate_stops_before_trace_or_gpu(cli, monkeypatch, tmp_path):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    from sera.provider_check import require_provider_check
    monkeypatch.setattr(cli, 'require_provider_check', require_provider_check)
    args = arguments(tmp_path)
    args[args.index('--provider-check') + 1] = str(cli.CASES_PATH.parents[1]/'evidence/provider-v4/result.json')
    with pytest.raises(SystemExit) as error:
        cli.main(args)
    assert error.value.code == 2
    assert observed['calls'] == []
    assert not (tmp_path/'run').exists()


def test_explicit_workload_and_priority_are_not_replaced(cli, monkeypatch, tmp_path):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    assert cli.main(arguments(tmp_path) + ['--concurrency', '1', '2', '4', '8',
                                         '--priority', 'throughput']) == 0
    assert observed['kwargs']['workload'].concurrency == [1, 2, 4, 8]
    assert observed['kwargs']['objective'].priority == 'throughput'


@pytest.mark.parametrize('failure', ['no_runner', 'probe_error', 'invalid_probe', 'close_error'])
def test_failed_return_cannot_report_success_and_always_closes(cli, monkeypatch, tmp_path, failure):
    observed = install_boundaries(cli, monkeypatch, tmp_path, **{failure: True})
    assert cli.main(arguments(tmp_path)) == 1
    assert observed['closed'] and observed['flushed']
    wrapper = json.loads((tmp_path/'run'/'invocation.json').read_text())
    assert wrapper['passed'] is False


def test_no_weave_is_explicit_and_keeps_local_evidence(cli, monkeypatch, tmp_path):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    assert cli.main(arguments(tmp_path) + ['--no-weave']) == 0
    assert observed['calls'] == ['provider-check', 'optimize']
    assert observed['closed'] and not observed['flushed']
    report = json.loads((tmp_path/'run'/'result.json').read_text())
    assert report['weave_url'] is None
    assert report['trace_status'] == 'disabled-explicitly'
    assert type(observed['kwargs']['agent']) is cli.sera.WandbAgent


def test_existing_output_is_not_overwritten(cli, monkeypatch, tmp_path):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    folder = tmp_path/'run'
    folder.mkdir()
    saved = folder/'keep.txt'
    saved.write_text('existing evidence')
    with pytest.raises(SystemExit) as error:
        cli.main(arguments(tmp_path))
    assert error.value.code == 2
    assert saved.read_text() == 'existing evidence'
    assert observed['calls'] == []


def test_optimizer_failure_keeps_failed_evidence_and_flushes_trace(cli, monkeypatch, tmp_path):
    observed = install_boundaries(cli, monkeypatch, tmp_path)

    def fail_optimizer(**kwargs):
        folder = kwargs['output_dir']
        folder.mkdir()
        (folder/'result.json').write_text('{"status": "failed", "error": "RuntimeError"}')
        raise RuntimeError('fixture optimizer failure')

    monkeypatch.setattr(cli.sera, 'optimize', fail_optimizer)
    assert cli.main(arguments(tmp_path)) == 1
    assert observed['flushed']
    report = json.loads((tmp_path/'run'/'result.json').read_text())
    assert report == {'status': 'failed', 'error': 'RuntimeError'}
    wrapper = json.loads((tmp_path/'run'/'invocation.json').read_text())
    assert wrapper['passed'] is False
    assert wrapper['error'] == 'RuntimeError'
    assert wrapper['weave_url'] == 'https://wandb.ai/fixture/call'


def test_import_has_no_execution_side_effects(cli, monkeypatch):
    def unexpected(**kwargs):
        raise AssertionError('Import must not execute inference')

    monkeypatch.setattr(cli.sera, 'optimize', unexpected)
    importlib.reload(cli)


def arguments_without_batching(tmp_path, model=MODEL_ID):
    args = arguments(tmp_path, model)
    start = args.index('--batching-values')
    del args[start:start + 3]
    return args


def test_small_model_explicit_multi_specialist_scope_reaches_optimizer(cli, monkeypatch, tmp_path):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    assert cli.main(arguments(tmp_path) + ['--sequence-values', '4', '--context-values', '2048',
                                         '--fp8-kv']) == 0
    expected = {'max_num_batched_tokens': [2048, 1024], 'max_num_seqs': [4],
                'max_model_len': [2048], 'kv_cache_dtype': ['fp8']}
    kwargs = observed['kwargs']
    assert kwargs['investigation_space'].supported_changes == expected
    assert kwargs['baseline_configuration'] is None
    assert kwargs['budget'].max_candidate_trials == 2
    assert kwargs['constraints'].quality_floor == .99
    invocation = json.loads((tmp_path/'run'/'invocation.json').read_text())
    assert {key: set(values) for key, values in invocation['investigation_space']['supported_changes'].items()} == {
        key: set(values) for key, values in expected.items()}
    assert len(invocation['investigation_space']['candidate_hashes']) == 5


@pytest.mark.parametrize('flags,expected', [
    (['--sequence-values', '4'], {'max_num_seqs': [4]}),
    (['--context-values', '2048'], {'max_model_len': [2048]}),
    (['--fp8-kv'], {'kv_cache_dtype': ['fp8']}),
])
def test_batching_values_are_not_invented_for_other_explicit_controls(cli, monkeypatch, tmp_path, flags, expected):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    assert cli.main(arguments_without_batching(tmp_path) + flags) == 0
    assert observed['kwargs']['investigation_space'].supported_changes == expected


@pytest.mark.parametrize('flags', [
    ['--sequence-values', '0'], ['--sequence-values', '257'], ['--sequence-values', '8'],
    ['--sequence-values', '4', '4'], ['--sequence-values', '2', '--concurrency', '4'],
    ['--context-values', '64'], ['--context-values', '4097'], ['--context-values', '4096'],
    ['--context-values', '2048', '2048'],
])
def test_invalid_new_control_values_stop_before_provider_trace_or_artifacts(cli, monkeypatch, tmp_path, flags):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as error:
        cli.main(arguments(tmp_path) + flags)
    assert error.value.code == 2
    assert observed['calls'] == []
    assert not (tmp_path/'run').exists()


def test_no_explicit_controls_stop_before_provider_trace_or_artifacts(cli, monkeypatch, tmp_path):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as error:
        cli.main(arguments_without_batching(tmp_path))
    assert error.value.code == 2
    assert observed['calls'] == []
    assert not (tmp_path/'run').exists()


def test_large_model_fp8_kv_is_rejected_before_starting_anything(cli, monkeypatch, tmp_path):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as error:
        cli.main(arguments(tmp_path, LARGE_MODEL_ID) + ['--fp8-kv'])
    assert error.value.code == 2
    assert observed['calls'] == []
    assert not (tmp_path/'run').exists()


def test_large_model_can_use_explicit_batch_sequence_and_context_controls(cli, monkeypatch, tmp_path):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    assert cli.main(arguments(tmp_path, LARGE_MODEL_ID) + ['--sequence-values', '4',
                                                        '--context-values', '2048']) == 0
    assert observed['kwargs']['investigation_space'].supported_changes == {
        'max_num_batched_tokens': [2048, 1024], 'max_num_seqs': [4], 'max_model_len': [2048]}
    assert observed['kwargs']['baseline_configuration'] == RuntimeConfig(quantization='fp8_per_tensor')


def test_fit_first_is_explicit_and_freezes_followup_controls_against_fp8_reference(cli, monkeypatch, tmp_path):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    assert cli.main(arguments(tmp_path, LARGE_MODEL_ID) + ['--fit-first']) == 0
    kwargs = observed['kwargs']
    assert kwargs['baseline_configuration'] is None
    assert kwargs['budget'].max_candidate_trials == 2  # Includes the deployment trial; never add a trial.
    invocation = json.loads((tmp_path/'run'/'invocation.json').read_text())
    assert invocation['fit_first'] is True
    assert set(invocation['investigation_space']['candidate_hashes']) == {
        RuntimeConfig(quantization='fp8_per_tensor', max_num_batched_tokens=value).config_hash
        for value in (2048, 1024)}


@pytest.mark.parametrize('model,extra', [(MODEL_ID, []), (LARGE_MODEL_ID, ['--fp8-kv'])])
def test_unsupported_fit_first_profile_stops_before_provider_trace_or_gpu(cli, monkeypatch, tmp_path, model, extra):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as error:
        cli.main(arguments(tmp_path, model) + ['--fit-first', *extra])
    assert error.value.code == 2
    assert observed['calls'] == []
    assert not (tmp_path/'run').exists()


def recording_weave():
    from functools import wraps
    calls = []
    active = []

    def op(fn=None, *, name=None):
        def decorate(function):
            @wraps(function)
            def wrapped(*args, **kwargs):
                call = {'name': name or function.__name__, 'parent': active[-1]['name'] if active else None,
                        'args': args, 'kwargs': kwargs}
                calls.append(call)
                active.append(call)
                try:
                    call['output'] = function(*args, **kwargs)
                    return call['output']
                except Exception as error:
                    call['error_type'] = type(error).__name__
                    raise
                finally:
                    active.pop()
            return wrapped
        return decorate(fn) if fn is not None else decorate

    return SimpleNamespace(op=op, calls=calls)


def test_child_trace_names_and_history_preserve_single_provider_invocations(cli):
    calls = []

    class Agent:
        model = 'fixture-model'
        project = 'test/project'
        history = []

        def request(self, role, evidence, instruction):
            entry = {'role': role, 'evidence': evidence, 'instruction': instruction}
            self.history.append(entry)
            calls.append(entry)
            return entry

        def review(self, evidence):
            return self.request('frontier', evidence, 'unchanged review instruction')

    agent = Agent()
    weave = recording_weave()
    traced = cli.TracedInvestigationAgent(agent, weave)
    assert traced.history is agent.history
    assert (traced.model, traced.project) == (agent.model, agent.project)

    @weave.op
    def experiment():
        traced.request('arbiter', {'fit_plan': {}, 'specialist_role': 'quantization'}, 'fit advice')
        traced.request('proposal', {'specialist_role': 'quantization'}, 'cache advice')
        traced.request('proposal', {'specialist_role': 'batching'}, 'batch advice')
        traced.request('arbiter', {'legal_proposal_ids': ['p1']}, 'rank')
        return traced.review({'eligible_trial_ids': ['baseline']})

    assert experiment() is agent.history[-1]
    assert len(calls) == len(agent.history) == 5
    children = weave.calls[1:]
    assert [call['name'] for call in children] == [
        'fit_quantization_advisor', 'quantization_specialist', 'batching_specialist', 'arbiter', 'frontier_reviewer']
    assert all(call['parent'] == 'experiment' for call in children)
    assert [call['output'] for call in children] == calls
    assert 'fixture-not-a-real-key' not in repr(weave.calls)


@pytest.mark.parametrize('method', ['request', 'review'])
def test_child_trace_preserves_agent_failure_without_retry_or_history_repair(cli, method):
    class Agent:
        model = 'fixture-model'
        project = 'test/project'
        history = []

        def request(self, role, evidence, instruction):
            self.history.append({'role': role, 'raw_failure': True})
            raise RuntimeError('fixture provider failure')

        def review(self, evidence):
            return self.request('frontier', evidence, 'review')

    base = Agent()
    weave = recording_weave()
    traced = cli.TracedInvestigationAgent(base, weave)
    with pytest.raises(RuntimeError, match='fixture provider failure'):
        if method == 'request':
            traced.request('arbiter', {}, 'rank')
        else:
            traced.review({})
    assert len(base.history) == len(weave.calls) == 1
    assert weave.calls[0]['error_type'] == 'RuntimeError'
    assert traced.history is base.history


def test_tracing_cli_uses_local_agent_adapter(cli, monkeypatch, tmp_path):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    assert cli.main(arguments(tmp_path)) == 0
    assert isinstance(observed['kwargs']['agent'], cli.TracedInvestigationAgent)


def test_child_trace_setup_failure_does_not_start_optimizer_and_flushes_client(cli, monkeypatch, tmp_path):
    observed = install_boundaries(cli, monkeypatch, tmp_path)

    def fail_trace(*args, **kwargs):
        raise RuntimeError('fixture trace setup failure')

    sys.modules['weave'].op = fail_trace
    assert cli.main(arguments(tmp_path)) == 1
    assert observed['calls'] == ['provider-check', 'weave-init']
    assert observed['flushed']
    assert not (tmp_path/'run').exists()


@pytest.mark.parametrize('method', ['request', 'review'])
def test_provider_returned_reasoning_and_failed_attempts_are_exported_exactly_once(cli, method):
    class Agent:
        model = 'fixture-model'
        project = 'test/project'

        def __init__(self):
            self.history = [{'role': 'old-call', 'attempts': []}]

        def request(self, role, evidence, instruction):
            self.history.append({'role': role, 'model': self.model, 'headers': {'secret': 'never-log'},
                'attempts': [
                    {'attempt': 1, 'schema_valid': False, 'latency_ms': 12.0,
                     'raw_response': {'headers': {'secret': 'never-log'}, 'choices': [{
                         'finish_reason': 'length', 'message': {'content': '{"partial":',
                         'reasoning': 'Exact provider reasoning on failed attempt.', 'api_key': 'never-log'}}]}},
                    {'attempt': 2, 'schema_valid': True, 'latency_ms': 15.0,
                     'raw_response': {'choices': [{'finish_reason': 'stop', 'message': {
                         'content': '{"reason":"Measured evidence"}',
                         'reasoning': 'Exact provider reasoning on valid attempt.'}}]}}]})
            return {'accepted': True}

        def review(self, evidence):
            return self.request('frontier', evidence, 'review instruction')

    base = Agent()
    weave = recording_weave()
    traced = cli.TracedInvestigationAgent(base, weave)
    if method == 'request':
        response = traced.request('arbiter', {}, 'rank')
    else:
        response = traced.review({})
    assert response == {'accepted': True}
    assert len(base.history) == 2
    exported = [call for call in weave.calls if call['name'] == 'record_agent_response']
    assert len(exported) == 2
    first, second = [call['args'][0] for call in exported]
    assert first['content'] == '{"partial":'
    assert first['reasoning'] == 'Exact provider reasoning on failed attempt.'
    assert first['finish_reason'] == 'length' and first['schema_valid'] is False
    assert second['reasoning'] == 'Exact provider reasoning on valid attempt.'
    assert second['reasoning_source'] == 'provider-returned reasoning'
    assert second['attempt'] == 2 and second['latency_ms'] == 15.0
    assert 'never-log' not in repr(exported)
    assert all(call['parent'] in {'arbiter', 'frontier_reviewer'} for call in exported)


def test_absent_provider_reasoning_is_not_invented(cli):
    agent = SimpleNamespace(model='fixture-model', project='test/project', history=[])

    def request(*args):
        agent.history.append({'role': 'arbiter', 'attempts': [
            {'attempt': 1, 'schema_valid': False, 'latency_ms': 1.0}]})
        return None

    agent.request = request
    agent.review = lambda evidence: request()
    weave = recording_weave()
    traced = cli.TracedInvestigationAgent(agent, weave)
    assert traced.request('arbiter', {}, 'rank') is None
    exported = next(call for call in weave.calls if call['name'] == 'record_agent_response')['args'][0]
    assert 'reasoning' not in exported
    assert exported['reasoning_source'] == 'not returned'


@pytest.mark.parametrize('raw_response', [
    {'choices': [{'message': 'malformed'}]},
    {'choices': [{'message': ['malformed']}]},
    {'choices': ['malformed']},
    {'choices': 'malformed'},
    'malformed',
])
def test_malformed_attempt_trace_cannot_replace_later_valid_recommendation(cli, raw_response):
    agent = SimpleNamespace(model='fixture-model', project='test/project', history=[])
    valid = {'accepted': True}

    def request(*args):
        agent.history.append({'role': 'arbiter', 'attempts': [
            {'attempt': 1, 'schema_valid': False, 'raw_response': raw_response},
            {'attempt': 2, 'schema_valid': True, 'raw_response': {'choices': [{
                'message': {'content': '{"accepted":true}', 'reasoning': 'Actual provider explanation.'}}]}}]})
        return valid

    agent.request = request
    agent.review = lambda evidence: request()
    weave = recording_weave()
    traced = cli.TracedInvestigationAgent(agent, weave)
    assert traced.request('arbiter', {}, 'rank') is valid
    assert agent.history[0]['attempts'][0]['raw_response'] is raw_response
    exported = [call['args'][0] for call in weave.calls if call['name'] == 'record_agent_response']
    assert len(exported) == 2
    assert exported[0]['response_payload_malformed'] is True
    assert exported[0]['content'] is None and 'reasoning' not in exported[0]
    assert exported[0]['schema_valid'] is False
    assert exported[1]['content'] == '{"accepted":true}'
    assert exported[1]['reasoning'] == 'Actual provider explanation.'


@pytest.mark.parametrize('model,extra', [(MODEL_ID, []), (LARGE_MODEL_ID, ['--fit-first'])])
def test_automatic_space_is_explicit_without_a_guessed_premeasurement_pool(cli, monkeypatch, tmp_path, model, extra):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    assert cli.main(arguments_without_batching(tmp_path, model) + ['--auto-space', *extra]) == 0
    assert observed['kwargs']['automatic_space'] is True
    assert observed['kwargs']['investigation_space'] is None
    invocation = json.loads((tmp_path/'run'/'invocation.json').read_text())
    assert invocation['automatic_space'] is True
    assert invocation['investigation_space'] is None  # The fake optimizer has no measured policy output.


@pytest.mark.parametrize('flags', [
    ['--batching-values', '2048'], ['--sequence-values', '4'],
    ['--context-values', '2048'], ['--fp8-kv'],
])
def test_auto_space_conflicts_with_every_explicit_control_before_external_work(cli, monkeypatch, tmp_path, flags):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as error:
        cli.main(arguments_without_batching(tmp_path) + ['--auto-space', *flags])
    assert error.value.code == 2
    assert observed['calls'] == []
    assert not (tmp_path/'run').exists()


def test_measured_events_and_returned_probe_use_named_child_export_ops(cli, monkeypatch, tmp_path):
    from sera.tracing import emit_event, event_sink_enabled
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    weave = recording_weave()
    sys.modules['weave'].op = weave.op
    original = cli.sera.optimize

    def optimize(**kwargs):
        result = original(**kwargs)
        emit_event('recorded_model_request', {'output': 'saved measured output', 'latency_ms': 23.0,
                                            'timing_scope': 'logging only'})
        emit_event('recorded_trial_metrics', {'trial_id': 'trial-1', 'status': 'collected'})
        return result

    monkeypatch.setattr(cli.sera, 'optimize', optimize)
    assert cli.main(arguments(tmp_path)) == 0
    requests = [call for call in weave.calls if call['name'] == 'recorded_model_request']
    assert len(requests) == 2
    assert requests[0]['args'][0]['output'] == 'saved measured output'
    returned = requests[1]['args'][0]
    assert returned['phase'] == 'post-return-probe'
    assert returned['output'] == '{"answer": 5}' and returned['latency_ms'] == 10
    assert 'logging time' in returned['timing_scope']
    assert all(call['parent'] == 'run_investigation' for call in requests)
    assert any(call['name'] == 'recorded_trial_metrics' for call in weave.calls)
    assert not event_sink_enabled()
    assert observed['closed']


def test_no_weave_disables_even_an_inherited_event_sink(cli, monkeypatch, tmp_path):
    from sera.tracing import emit_event, event_sink_enabled, use_event_sink
    install_boundaries(cli, monkeypatch, tmp_path)
    original = cli.sera.optimize
    inherited = []

    def optimize(**kwargs):
        assert not event_sink_enabled()
        assert emit_event('recorded_model_request', {'output': 'not exported'}) is False
        return original(**kwargs)

    monkeypatch.setattr(cli.sera, 'optimize', optimize)
    with use_event_sink(lambda *event: inherited.append(event)):
        assert cli.main(arguments(tmp_path) + ['--no-weave']) == 0
        assert event_sink_enabled()
    assert inherited == []


@pytest.mark.parametrize('location', ['baseline', 'candidate_trial', 'search_trials', 'deployment'])
def test_saved_measurement_trace_failure_is_explicit_without_rewriting_quality(cli, monkeypatch, tmp_path, location):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    original = cli.sera.optimize

    def optimize(**kwargs):
        result = original(**kwargs)
        trial = {'trial_id': 'saved-trial', 'trace_export': {'status': 'failed', 'emitted_events': 2,
                 'failed_event': 'recorded_model_request', 'error_type': 'RuntimeError'}}
        result.report[location] = ([trial] if location == 'search_trials' else
                                   {'candidate_trial': trial} if location == 'deployment' else trial)
        return result

    monkeypatch.setattr(cli.sera, 'optimize', optimize)
    assert cli.main(arguments(tmp_path)) == 1
    invocation = json.loads((tmp_path/'run'/'invocation.json').read_text())
    assert invocation['trace_export_failures'][0]['event'] == 'recorded_model_request'
    assert invocation['passed'] is False
    assert observed['result'].report['task_quality_verified'] is True
    assert observed['result'].report['trace_status'] == 'failed'
    assert observed['closed'] and observed['flushed']


def test_post_return_export_failure_keeps_saved_output_and_closes_runner(cli, monkeypatch, tmp_path):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    weave = recording_weave()

    def op(fn=None, *, name=None):
        def decorate(function):
            if name == 'recorded_model_request':
                def fail(*args, **kwargs):
                    raise RuntimeError('fixture trace export failed')
                return fail
            return weave.op(function, name=name)
        return decorate(fn) if fn is not None else decorate

    sys.modules['weave'].op = op
    assert cli.main(arguments(tmp_path)) == 1
    report = json.loads((tmp_path/'run'/'result.json').read_text())
    assert report['post_return_probe']['text'] == '{"answer": 5}'
    assert report['task_quality_verified'] is True
    assert observed['closed'] and observed['flushed']


def test_provider_export_failure_preserves_recommendation_but_fails_invocation(cli, monkeypatch, tmp_path):
    observed = install_boundaries(cli, monkeypatch, tmp_path)
    original = cli.sera.optimize

    class Agent:
        model = 'fixture-model'

        def __init__(self, project):
            self.project = project
            self.history = []

        def request(self, *args):
            self.history.append({'role': 'arbiter', 'attempts': [{'attempt': 1, 'schema_valid': True}]})
            return {'accepted': True}

        def review(self, evidence):
            return self.request()

    def op(fn=None, *, name=None):
        def decorate(function):
            if function.__name__ == 'record_agent_response':
                def fail(*args):
                    raise RuntimeError('fixture export failure')
                return fail
            return function
        return decorate(fn) if fn is not None else decorate

    def optimize(**kwargs):
        agent = kwargs['agent']
        assert agent.request('arbiter', {}, 'rank') == {'accepted': True}
        assert agent.history[0]['attempts'][0]['schema_valid'] is True
        return original(**kwargs)

    monkeypatch.setattr(cli.sera, 'WandbAgent', Agent)
    monkeypatch.setattr(cli.sera, 'optimize', optimize)
    sys.modules['weave'].op = op
    assert cli.main(arguments(tmp_path)) == 1
    invocation = json.loads((tmp_path/'run'/'invocation.json').read_text())
    assert invocation['trace_export_failures'] == [
        {'event': 'record_agent_response', 'error_type': 'RuntimeError'}]
    assert observed['result'].report['task_quality_verified'] is True
    assert observed['closed'] and observed['flushed']


def test_automatic_space_saves_actual_measured_policy_audit(cli, monkeypatch, tmp_path):
    install_boundaries(cli, monkeypatch, tmp_path)
    original = cli.sera.optimize
    resolved = {'max_num_batched_tokens': [2048]}
    policy = {'fixture': 'measured baseline policy audit'}

    def optimize(**kwargs):
        result = original(**kwargs)
        result.report.update(investigation_space=resolved, candidate_policy=policy)
        return result

    monkeypatch.setattr(cli.sera, 'optimize', optimize)
    assert cli.main(arguments_without_batching(tmp_path) + ['--auto-space']) == 0
    invocation = json.loads((tmp_path/'run'/'invocation.json').read_text())
    assert invocation['investigation_space'] == resolved
    assert invocation['candidate_policy'] == policy
