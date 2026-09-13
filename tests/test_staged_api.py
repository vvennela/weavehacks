"""Ordered stages use fake service boundaries; these are not GPU measurements."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

import sera
from sera.config import MODEL_ID, MODEL_REVISION


def trial(config, *, name='baseline', latency=100.0, memory=1000):
    return dict(trial_id=name, status='collected', config_hash=config.config_hash,
        input_token_ids=[[1, 2]],
        task_quality=dict(valid_outputs=True, mean=1.0, passed=True),
        reduced=dict(p95_latency_ms=latency, output_tokens_per_second=10.0, generation_errors=0),
        runtime=dict(configuration=config.model_dump(), model_id=MODEL_ID,
            revision=MODEL_REVISION, gpu={'uuid': 'fixture-gpu'}, versions={'vllm': 'fixture'},
            sampled_peak_memory_mib=memory))


class FakeResult:
    def __init__(self, folder, baseline_config, selected, events):
        self.output_dir = folder
        self.events = events
        self.report = dict(status='ready', task_quality_verified=True,
            decision={'selected': selected['trial_id'], 'outcome': 'improved'},
            baseline_configuration=baseline_config.model_dump())
        self.trials = [selected]
        self.models = [SimpleNamespace(configuration=sera.RuntimeConfig(**selected['runtime']['configuration']))]
        self.weave_url = 'https://example.invalid/fixture-trace'
        self.closed = False

    def close(self):
        self.closed = True
        self.events.append('close')


@pytest.fixture
def stage_runner(monkeypatch):
    from sera import api
    events, calls, results = [], [], []

    def run(arguments):
        events.append('start')
        assert all(result.closed for result in results), 'Two stage runners must not overlap'
        calls.append(arguments)
        baseline = arguments.get('baseline_configuration') or sera.RuntimeConfig()
        config = sera.RuntimeConfig(**(baseline.model_dump() | (
            {'enable_prefix_caching': True} if len(calls) == 1 else {'kv_cache_dtype': 'fp8'})))
        selected = trial(config, name='trial-1', latency=100.0 if len(calls) == 1 else 102.0,
                         memory=1000 if len(calls) == 1 else 800)
        result = FakeResult(arguments['output_dir'], baseline, selected, events)
        results.append(result)
        return result

    monkeypatch.setattr(api, '_run_traced', run)
    monkeypatch.setattr(api, '_configured_agent', lambda: SimpleNamespace(fork=lambda: None))
    monkeypatch.setattr('sera.provider_check.require_provider_check', lambda *args: {})
    monkeypatch.setenv('WANDB_API_KEY', 'fixture')
    monkeypatch.setenv('SERA_PROVIDER_CHECK', '/fixture/certificate')
    return calls, results, events


def options(tmp_path):
    return dict(models=[MODEL_ID], prompts=['question'], stages=['latency', 'quant'], k=3.0,
        max_latency_regression_pct=3.0, evaluation=lambda prompt, output: True,
        evaluation_version='fixture-v1', constraints=sera.Constraints(quality_floor=.99),
        output_dir=tmp_path / 'staged')


def test_stages_rebase_freeze_limits_and_return_only_final_runner(tmp_path, stage_runner):
    calls, children, events = stage_runner
    result = sera.optimize(**options(tmp_path))
    assert [call['objective'].priority for call in calls] == ['latency', 'memory']
    assert all(call['objective'].min_improvement_fraction == .03 for call in calls)
    assert calls[1]['baseline_configuration'] == children[0].models[0].configuration
    assert calls[1]['constraints'].p95_latency_ms == 103.0
    assert calls[1]['constraints'].quality_floor == .99
    assert calls[1]['investigation_controls'] == ['kv_cache_dtype']
    assert calls[0]['budget'].max_candidate_trials is None
    assert events == ['start', 'close', 'start']
    assert result.models == children[1].models and not children[1].closed
    saved = json.loads((tmp_path / 'staged/checkpoints/001.json').read_text())
    assert saved['configuration']['enable_prefix_caching'] is True
    assert saved['configuration']['kv_cache_dtype'] == 'auto'
    assert saved['p95_latency_ms'] == 100.0
    result.close()
    assert children[1].closed
    report = json.loads((tmp_path / 'staged/result.json').read_text())
    assert report['status'] == 'closed' and report['returned_runner_closed']
    assert len(report['stages']) == 2


def test_stage_guard_rejects_a_returned_runner_that_breaks_prior_limit(tmp_path, stage_runner):
    calls, children, _ = stage_runner
    args = options(tmp_path)
    args['max_latency_regression_pct'] = 0.0
    with pytest.raises(RuntimeError, match='constraint'):
        sera.optimize(**args)
    assert all(result.closed for result in children)
    report = json.loads((tmp_path / 'staged/result.json').read_text())
    assert report['status'] == 'failed'
    assert (tmp_path / 'staged/checkpoints/001.json').exists()
    assert not (tmp_path / 'staged/checkpoints/002.json').exists()


@pytest.mark.parametrize('extra', [dict(evaluation=None), dict(evaluation_version=''),
    dict(constraints=None), dict(mode='fixed'), dict(objective=sera.Objective()),
    dict(automatic_space=False), dict(stages=[]), dict(k=True), dict(k=100.0),
    dict(stages=['throughput']), dict(trace_reader=lambda *args: None)])
def test_bad_stage_contract_fails_before_provider_or_gpu(tmp_path, monkeypatch, extra):
    monkeypatch.setattr('sera.api._configured_agent', lambda: pytest.fail('No provider setup'))
    args = options(tmp_path) | extra
    with pytest.raises((ValueError, TypeError)):
        sera.optimize(**args)
    assert not (tmp_path / 'staged').exists()


def test_standalone_k_sets_existing_objective_threshold(monkeypatch):
    calls = []
    monkeypatch.setattr('sera.pipeline.optimize', lambda **args: calls.append(args) or 'result')
    assert sera.optimize(models=[MODEL_ID], prompts=['q'], mode='fixed', k=3.0,
        objective=sera.Objective(priority='memory')) == 'result'
    assert calls[0]['objective'] == sera.Objective(priority='memory', min_improvement_fraction=.03)


def test_stage_inputs_are_not_modified(tmp_path, stage_runner):
    args = options(tmp_path)
    original_stages = deepcopy(args['stages'])
    original_constraints = args['constraints'].model_dump()
    with sera.optimize(**args):
        pass
    assert args['stages'] == original_stages
    assert args['constraints'].model_dump() == original_constraints
