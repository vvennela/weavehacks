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
