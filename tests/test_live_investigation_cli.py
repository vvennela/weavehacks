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
        init=init, op=lambda fn: fn,
        get_current_call=lambda: SimpleNamespace(ui_url='https://wandb.ai/fixture/call')))

    class Runner:
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
