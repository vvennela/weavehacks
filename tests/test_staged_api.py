"""Ordered stages use fake service boundaries; these are not GPU measurements."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

import sera
from sera.config import MODEL_ID, MODEL_REVISION


def trial(config, *, name='baseline', latency=100.0, memory=1000):
    return {'trial_id': name, 'status': 'collected', 'config_hash': config.config_hash,
        'input_token_ids': [[1, 2]],
        'task_quality': {'valid_outputs': True, 'mean': 1.0, 'passed': True},
        'reduced': {'p95_latency_ms': latency, 'output_tokens_per_second': 10.0, 'generation_errors': 0},
        'runtime': {'configuration': config.model_dump(), 'model_id': MODEL_ID,
            'revision': MODEL_REVISION, 'gpu': {'uuid': 'fixture-gpu'}, 'versions': {'vllm': 'fixture'},
            'telemetry_errors': 0,
            'sampled_peak_memory_mib': memory}}


class FakeResult:
    def __init__(self, folder, baseline_config, selected, events):
        self.output_dir = folder
        self.events = events
        self.report = {'status': 'ready', 'task_quality_verified': True,
            'decision': {'selected': selected['trial_id'], 'outcome': 'improved'},
            'baseline_configuration': baseline_config.model_dump()}
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
    return {'models': [MODEL_ID], 'prompts': ['question'], 'stages': ['latency', 'quant'], 'k': 3.0,
        'evaluation': lambda prompt, output: True,
        'evaluation_version': 'fixture-v1', 'constraints': sera.Constraints(quality_floor=.99),
        'output_dir': tmp_path / 'staged'}


def test_stages_rebase_freeze_limits_and_return_only_final_runner(tmp_path, stage_runner):
    calls, children, events = stage_runner
    result = sera.optimize(**options(tmp_path))
    assert [call['objective'].priority for call in calls] == ['latency', 'memory']
    assert all(call['objective'].min_improvement_fraction == 0.0 for call in calls)
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
    _, children, _ = stage_runner
    args = options(tmp_path)
    args['k'] = 0.0
    with pytest.raises(RuntimeError, match='constraint'):
        sera.optimize(**args)
    assert all(result.closed for result in children)
    report = json.loads((tmp_path / 'staged/result.json').read_text())
    assert report['status'] == 'failed'
    assert (tmp_path / 'staged/checkpoints/001.json').exists()
    assert not (tmp_path / 'staged/checkpoints/002.json').exists()


@pytest.mark.parametrize('extra', [{'evaluation': None}, {'evaluation_version': ''},
    {'constraints': None}, {'mode': 'fixed'}, {'objective': sera.Objective()},
    {'automatic_space': False}, {'stages': []}, {'k': True}, {'k': 100.0},
    {'stages': ['throughput']}, {'trace_reader': lambda *args: None}])
def test_bad_stage_contract_fails_before_provider_or_gpu(tmp_path, monkeypatch, extra):
    monkeypatch.setattr('sera.api._configured_agent', lambda: pytest.fail('No provider setup'))
    args = options(tmp_path) | extra
    with pytest.raises((ValueError, TypeError)):
        sera.optimize(**args)
    assert not (tmp_path / 'staged').exists()


def test_standalone_minimum_gain_sets_existing_objective_threshold(monkeypatch):
    calls = []
    monkeypatch.setattr('sera.pipeline.optimize', lambda **args: calls.append(args) or 'result')
    assert sera.optimize(models=[MODEL_ID], prompts=['q'], mode='fixed', min_improvement_pct=3.0,
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


def test_stage_start_failure_keeps_checkpoint_and_no_live_previous_runner(tmp_path, stage_runner, monkeypatch):
    from sera import api
    calls, children, _ = stage_runner
    original = api._run_traced

    def fail_second(arguments):
        if calls:
            raise RuntimeError('fixture startup failed')
        return original(arguments)

    monkeypatch.setattr(api, '_run_traced', fail_second)
    with pytest.raises(RuntimeError, match='startup failed'):
        sera.optimize(**options(tmp_path))
    assert children[0].closed
    report = json.loads((tmp_path / 'staged/result.json').read_text())
    assert report['returned_runner_closed'] and report['status'] == 'failed'
    assert len(report['checkpoints']) == 1


def test_cleanup_failure_prevents_next_stage_and_keeps_completed_checkpoint(tmp_path, stage_runner, monkeypatch):
    from sera import api
    calls, _, _ = stage_runner
    original = api._run_traced

    def dirty_runner(arguments):
        result = original(arguments)
        result.close = lambda: (_ for _ in ()).throw(RuntimeError('fixture cleanup failed'))
        return result

    monkeypatch.setattr(api, '_run_traced', dirty_runner)
    with pytest.raises(RuntimeError, match='cleanup failed'):
        sera.optimize(**options(tmp_path))
    assert len(calls) == 1
    report = json.loads((tmp_path / 'staged/result.json').read_text())
    assert not report['returned_runner_closed']
    assert report['stages'][0]['status'] == 'completed'


@pytest.mark.parametrize(('candidate_latency', 'selected'), [(98.0, 'baseline'), (97.0, 'candidate')])
def test_k_uses_measured_improvement_boundary(candidate_latency, selected):
    from sera.measurement import select_candidate
    config = sera.RuntimeConfig()
    baseline = trial(config)
    candidate = trial(config, name='candidate', latency=candidate_latency)
    result = select_candidate(baseline, candidate,
        objective=sera.Objective(min_improvement_fraction=.03),
        constraints=sera.Constraints(quality_floor=.99))
    assert result['selected'] == selected


def test_checkpoint_keeps_exact_source_snapshot_when_cleanup_mutates_runtime(tmp_path, stage_runner, monkeypatch):
    from sera import api
    from sera.storage import content_hash
    original = api._run_traced

    def mutable_runtime(arguments):
        result = original(arguments)
        close = result.close

        def close_and_record():
            result.trials[0]['runtime'].update(status='closed', memory_after_mib=0)
            close()

        result.close = close_and_record
        return result

    monkeypatch.setattr(api, '_run_traced', mutable_runtime)
    with sera.optimize(**options(tmp_path)):
        pass
    checkpoint = json.loads((tmp_path / 'staged/checkpoints/001.json').read_text())
    source = json.loads((tmp_path / 'staged' / checkpoint['source_trial_snapshot_path']).read_text())
    assert content_hash(source) == checkpoint['source_trial_hash']
    assert 'memory_after_mib' not in source['runtime']


@pytest.mark.parametrize('telemetry_errors', [None, 1, True])
def test_checkpoint_rejects_unverified_memory_samples(tmp_path, stage_runner, monkeypatch, telemetry_errors):
    from sera import api
    original = api._run_traced

    def bad_telemetry(arguments):
        result = original(arguments)
        result.trials[0]['runtime']['telemetry_errors'] = telemetry_errors
        return result

    monkeypatch.setattr(api, '_run_traced', bad_telemetry)
    with pytest.raises(RuntimeError, match='telemetry'):
        sera.optimize(**options(tmp_path))
    assert stage_runner[1][0].closed
    assert not (tmp_path / 'staged/checkpoints/001.json').exists()


def test_checkpoint_hash_and_snapshot_use_one_copy_despite_later_sampling(tmp_path, stage_runner, monkeypatch):
    from sera import stages
    from sera.storage import content_hash
    original = stages._checkpoint

    def sample_after_checkpoint(current, *args):
        result = original(current, *args)
        current.trials[0]['runtime']['sampled_peak_memory_mib'] += 1
        return result

    monkeypatch.setattr(stages, '_checkpoint', sample_after_checkpoint)
    with sera.optimize(**options(tmp_path)):
        pass
    checkpoint = json.loads((tmp_path / 'staged/checkpoints/001.json').read_text())
    source = json.loads((tmp_path / 'staged' / checkpoint['source_trial_snapshot_path']).read_text())
    assert content_hash(source) == checkpoint['source_trial_hash']
