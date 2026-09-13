"""A stage baseline is a configuration to remeasure, never a reused verdict."""

import json

import pytest

from sera import pipeline
from sera.config import Budget, Constraints, LARGE_MODEL_ID, LARGE_MODEL_REVISION, MODEL_ID, MODEL_REVISION, RuntimeConfig, Workload
from test_investigation import install_fakes


@pytest.mark.parametrize('model_id,revision,precision', [
    (MODEL_ID, MODEL_REVISION, None),
    (LARGE_MODEL_ID, LARGE_MODEL_REVISION, 'fp8_per_tensor'),
])
@pytest.mark.parametrize('batch', [1024, 2048])
def test_stage_winner_controls_are_remeasured_under_fresh_requirements(tmp_path, monkeypatch, model_id, revision, precision, batch):
    runners, _, agent = install_fakes(monkeypatch, abstain=True)
    configuration = RuntimeConfig(quantization=precision, max_num_batched_tokens=batch,
        enable_prefix_caching=True, gpu_memory_utilization=.8)
    scored = []
    def evaluate(prompt, output):
        scored.append((prompt, output))
        return output == 'correct'
    with pipeline.optimize(models=[model_id], prompts=['question'], output_dir=tmp_path/'stage',
            baseline_configuration=configuration, evaluation=evaluate, evaluation_version='stage-quality-v2',
            constraints=Constraints(quality_floor=.99), workload=Workload(concurrency=[1, 2, 4, 8]),
            agent=agent, provider_check='fixture', budget=Budget(max_candidate_trials=1)) as result:
        baseline = result.report['baseline']
        assert baseline['config_hash'] == configuration.config_hash
        assert baseline['runtime']['configuration'] == configuration.model_dump()
        assert baseline['runtime']['model_id'] == model_id
        assert baseline['runtime']['revision'] == revision
        assert baseline['task_quality']['version'] == 'stage-quality-v2'
        assert baseline['task_quality']['passed'] is True
        assert scored
        assert len(runners) == 1 and runners[0].ready
        assert runners[0].artifact_dir == tmp_path/'stage'/'baseline'
        assert result.models[0].configuration == configuration
        assert result.report['baseline_name'] == 'sera-explicit-runtime-reference-v1'
        saved = json.loads((tmp_path/'stage'/'result.json').read_text())
        assert saved['baseline_configuration'] == configuration.model_dump()
    assert not runners[0].ready


def test_previous_configuration_does_not_inherit_a_passing_quality_verdict(tmp_path, monkeypatch):
    runners, _, agent = install_fakes(monkeypatch, abstain=True, baseline_wrong=True)
    with pipeline.optimize(models=[MODEL_ID], prompts=['question'], output_dir=tmp_path/'stage',
            baseline_configuration=RuntimeConfig(max_num_batched_tokens=2048, enable_prefix_caching=True),
            evaluation=lambda prompt, output: output == 'correct', evaluation_version='fresh-v1',
            constraints=Constraints(quality_floor=.99), agent=agent, provider_check='fixture',
            budget=Budget(max_candidate_trials=1)) as result:
        assert result.report['baseline']['task_quality']['passed'] is False
        assert result.models == []
        assert result.report['decision']['selected'] is None
    assert not any(runner.ready for runner in runners)


@pytest.mark.parametrize('model_id,configuration,overrides', [
    (MODEL_ID, RuntimeConfig(quantization='fp8_per_tensor'), {}),
    (LARGE_MODEL_ID, RuntimeConfig(), {}),
    (LARGE_MODEL_ID, RuntimeConfig(quantization='fp8_per_tensor', kv_cache_dtype='fp8'), {}),
    (MODEL_ID, RuntimeConfig(tensor_parallel_size=2), {}),
    (LARGE_MODEL_ID, RuntimeConfig(quantization='fp8_per_tensor', tensor_parallel_size=2), {}),
    (MODEL_ID, RuntimeConfig(max_num_seqs=2), {'workload': Workload(concurrency=[4])}),
    (MODEL_ID, RuntimeConfig(), {'evaluation': None}),
    (MODEL_ID, RuntimeConfig(), {'evaluation_version': ''}),
    (MODEL_ID, RuntimeConfig(), {'constraints': None}),
    (MODEL_ID, RuntimeConfig.model_construct(max_model_len=9000), {}),
])
def test_invalid_stage_baselines_fail_before_runtime_or_output_creation(tmp_path, monkeypatch, model_id, configuration, overrides):
    monkeypatch.setattr(pipeline, 'SeraModel', lambda **kwargs: pytest.fail('runtime constructed'))
    arguments = dict(models=[model_id], prompts=['question'], output_dir=tmp_path/'bad',
        baseline_configuration=configuration, evaluation=lambda prompt, output: True,
        evaluation_version='requirements-v1', constraints=Constraints(quality_floor=.99))
    arguments.update(overrides)
    with pytest.raises(ValueError):
        pipeline.optimize(**arguments)
    assert not (tmp_path/'bad').exists()


def test_existing_small_fp8_kv_control_can_be_remeasured_without_enabling_fp8_weights(tmp_path, monkeypatch):
    runners, _, agent = install_fakes(monkeypatch, abstain=True)
    configuration = RuntimeConfig(kv_cache_dtype='fp8', max_num_batched_tokens=2048)
    with pipeline.optimize(models=[MODEL_ID], prompts=['question'], output_dir=tmp_path/'cache',
            baseline_configuration=configuration, evaluation=lambda prompt, output: True,
            evaluation_version='fp8-cache-v1', constraints=Constraints(quality_floor=.99),
            agent=agent, provider_check='fixture', budget=Budget(max_candidate_trials=1)) as result:
        assert result.report['baseline']['config_hash'] == configuration.config_hash
        assert result.models[0].configuration.quantization is None
    assert not any(runner.ready for runner in runners)


@pytest.mark.parametrize('fit_first', [False, True])
@pytest.mark.parametrize('controls', [[], ['max_num_batched_tokens', 'max_num_batched_tokens']])
def test_stage_control_filter_reaches_direct_and_fit_investigation(tmp_path, monkeypatch, fit_first, controls):
    if fit_first:
        from test_fit_investigation import boundaries
        runners, _, agent = boundaries(monkeypatch)
    else:
        runners, _, agent = install_fakes(monkeypatch, abstain=True)
    captured = []
    def investigate(**arguments):
        captured.append(arguments['investigation_controls'])
        result = arguments['result']
        result.models = [arguments['active']]
        result.report['decision'] = dict(selected='baseline', outcome='baseline', reason='test-handoff')
        return result
    monkeypatch.setattr('sera.investigation.investigate', investigate)
    expected = tuple(dict.fromkeys(controls))
    with pipeline.optimize(models=[LARGE_MODEL_ID if fit_first else MODEL_ID], prompts=['question'],
            output_dir=tmp_path/'filtered', evaluation=lambda prompt, output: True,
            evaluation_version='stage-controls-v1', constraints=Constraints(quality_floor=.99),
            agent=agent, provider_check='fixture', budget=Budget(max_candidate_trials=2),
            investigation_controls=controls) as result:
        assert captured == [expected]
        assert result.report['investigation_controls'] == list(expected)
        assert result.models[0].ready
    assert not any(runner.ready for runner in runners)


@pytest.mark.parametrize('controls', [['unknown'], 'kv_cache_dtype', {'kv_cache_dtype'}])
def test_invalid_stage_control_filter_fails_before_runtime(tmp_path, monkeypatch, controls):
    _, _, agent = install_fakes(monkeypatch)
    monkeypatch.setattr(pipeline, 'SeraModel', lambda **kwargs: pytest.fail('runtime constructed'))
    with pytest.raises(ValueError, match='investigation_controls'):
        pipeline.optimize(models=[MODEL_ID], prompts=['question'], output_dir=tmp_path/'bad-filter',
            agent=agent, provider_check='fixture', budget=Budget(max_candidate_trials=1),
            investigation_controls=controls)
    assert not (tmp_path/'bad-filter').exists()


def test_stage_control_filter_without_investigation_cannot_be_silently_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, 'SeraModel', lambda **kwargs: pytest.fail('runtime constructed'))
    with pytest.raises(ValueError, match='investigation'):
        pipeline.optimize(models=[MODEL_ID], prompts=['question'], output_dir=tmp_path/'unused-filter',
                          investigation_controls=[])
    assert not (tmp_path/'unused-filter').exists()


def test_fit_first_quantization_stage_does_not_invent_another_precision_trial(tmp_path, monkeypatch):
    from test_fit_investigation import boundaries
    runners, calls, agent = boundaries(monkeypatch)
    with pipeline.optimize(models=[LARGE_MODEL_ID], prompts=['question'], output_dir=tmp_path/'fit-quant',
            evaluation=lambda prompt, output: True, evaluation_version='fit-quant-v1',
            constraints=Constraints(quality_floor=.99), agent=agent, provider_check='fixture',
            budget=Budget(max_candidate_trials=2), automatic_space=True,
            investigation_controls=['kv_cache_dtype']) as result:
        assert result.report['deployment']['candidate_trial']['task_quality']['passed'] is True
        assert result.models[0].configuration.quantization == 'fp8_per_tensor'
        assert result.models[0].configuration.kv_cache_dtype == 'auto'
        assert result.report['search_trials'] == []
        assert result.report['search']['trials_used'] == 1
        assert len(runners) == 1
        assert len(calls) == 2  # One fit recommendation and its independent arbiter.
    assert not runners[0].ready
