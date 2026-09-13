"""Joint placement uses synthetic services here, never GPU or provider calls."""

from pathlib import Path
import time

import pytest

from sera.config import MODEL_ID, GLM_MODEL_ID, MODEL_REVISION, GLM_MODEL_REVISION, RuntimeConfig, Workload
from sera.runtime import CleanupError, SeraResponse


MIB = 1024**2


def plan_data():
    return dict(physical_gpu_bytes=1000*MIB, declared_budget_bytes=800*MIB,
        services=[dict(model_id=model, revision=revision, gpu_index=0,
            allocation_bytes=allocation*MIB,
            configuration=RuntimeConfig(gpu_memory_utilization=allocation/1000).model_dump(),
            constraints=dict(quality_floor=.99, p95_latency_ms=100.0, max_generation_errors=0))
            for model, revision, allocation in [(MODEL_ID, MODEL_REVISION, 200),
                                               (GLM_MODEL_ID, GLM_MODEL_REVISION, 500)]])


class FakeModel:
    instances = []
    wrong_model = None
    startup_failure = None
    cleanup_failure = None

    def __init__(self, *, model_id, revision, configuration, artifact_dir, placement_owner=None):
        self.model_id, self.revision = model_id, revision
        self.configuration, self.artifact_dir = configuration, Path(artifact_dir)
        self.owner = placement_owner
        self.closed = False
        self.record = dict(model_id=model_id, revision=revision,
            configuration=configuration.model_dump(), sampled_peak_memory_mib=100,
            telemetry_errors=0, gpu=dict(uuid='test-gpu', total_mib=1000), status='ready',
            versions={'vllm':'0.26.0', 'torch':'test', 'transformers':'test', 'flashinfer-python':'test'},
            memory_before_mib=0)
        self.instances.append(self)

    def start(self):
        self.artifact_dir.mkdir(parents=True)
        if self.model_id == self.startup_failure:
            raise RuntimeError('synthetic startup failure')
        return self

    def prepare(self, prompt):
        return {'prompt': prompt}, [1, 2]

    def _generate_prepared(self, payload, tokens):
        time.sleep(.001)
        text = 'wrong' if self.model_id == self.wrong_model else '4'
        return SeraResponse(text, [4], tokens, None, 'stop', 2.0,
                            dict(prompt_tokens=2, completion_tokens=1))

    def generate(self, prompt):
        if self.closed:
            raise RuntimeError('closed')
        return self._generate_prepared(*self.prepare(prompt))

    def metrics_snapshot(self):
        return dict(raw='', reduced={})

    def close(self):
        self.closed = True
        if self.model_id == self.cleanup_failure:
            self.record['cleanup_pass'] = False
            raise CleanupError('synthetic cleanup failure')
        self.record.update(cleanup_pass=True, status='closed', memory_after_mib=0)
        return self.record


class FakeOwner:
    def __init__(self, plan):
        self.plan = plan
        self.models = []
        self.record = dict(status='active', errors=[], sampled_peak_memory_mib=200,
            service_peak_memory_mib={MODEL_ID:100, GLM_MODEL_ID:100}, telemetry_errors=0,
            gpu=dict(uuid='test-gpu'))

    def acquire(self):
        return self

    def sample(self):
        return self.record

    def check(self):
        return self.sample()

    def close(self):
        errors = []
        for model in self.models:
            try:
                model.close()
            except BaseException as error:
                errors.append(error)
        self.record['cleanup_pass'] = not errors
        if errors:
            raise CleanupError('synthetic pair cleanup failure')


@pytest.fixture
def environment(monkeypatch):
    import sera.placement as placement
    FakeModel.instances = []
    FakeModel.wrong_model = FakeModel.startup_failure = FakeModel.cleanup_failure = None
    monkeypatch.setattr(placement, 'SeraModel', FakeModel)
    monkeypatch.setattr(placement, 'SharedGPUOwner', FakeOwner)
    return placement


def inputs(placement):
    workloads = {model: placement.PlacementWorkload(
        prompts=['2+2'], evaluator=lambda prompt, output: output == '4',
        evaluator_version='synthetic-arithmetic-v1', workload=Workload(concurrency=[1, 2]))
        for model in (MODEL_ID, GLM_MODEL_ID)}
    estimates = {model: placement.PlacementMemoryEstimate(weights_bytes=10*MIB,
        kv_bytes=10*MIB, workspace_bytes=10*MIB, process_overhead_bytes=10*MIB,
        fragmentation_bytes=10*MIB) for model in workloads}
    return dict(plan=plan_data(), workloads=workloads, memory_estimates=estimates)


def test_pair_returns_both_live_runners_and_saves_overlapping_gated_measurements(environment, tmp_path):
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run')
    assert result.report['decision']['outcome'] == 'safe-placement'
    assert len(result.models) == 2
    assert [model.generate('fresh').text for model in result.models] == ['4', '4']
    assert all(reference['task_quality']['passed'] for reference in result.report['isolated'].values())
    assert all(gate['passed'] for gate in result.report['joint']['gates'].values())
    assert all(window['overlap_seconds'] > 0 for window in result.report['joint']['overlap'])
    assert all(window['coverage_fraction'] > 0 for window in result.report['joint']['overlap'])
    assert (tmp_path/'run'/'result.json').is_file()
    assert 'Memory budget constrained' in (tmp_path/'run'/'report.md').read_text()
    result.close()
    assert all(model.closed for model in FakeModel.instances)
    assert result.report['returned_runner_closed'] is True


def test_isolated_quality_failure_prevents_any_joint_start(environment, tmp_path):
    FakeModel.wrong_model = MODEL_ID
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run')
    assert result.models == []
    assert result.report['decision']['outcome'] == 'not-attempted'
    assert result.report['isolated'][MODEL_ID]['task_quality']['mean'] == 0
    assert all(model.owner is None and model.closed for model in FakeModel.instances)


def test_invalid_estimated_fit_starts_no_service(environment, tmp_path):
    args = inputs(environment)
    args['memory_estimates'][MODEL_ID] = environment.PlacementMemoryEstimate(
        weights_bytes=300*MIB, kv_bytes=0, workspace_bytes=0,
        process_overhead_bytes=0, fragmentation_bytes=0)
    result = environment.place(**args, output_dir=tmp_path/'run')
    assert result.models == []
    assert result.report['decision']['reason'] == 'estimated-memory-does-not-fit'
    assert not FakeModel.instances


def test_invalid_plan_has_no_files_or_processes(environment, tmp_path):
    args = inputs(environment)
    args['plan']['services'][0]['configuration']['gpu_memory_utilization'] = .9
    with pytest.raises(ValueError):
        environment.place(**args, output_dir=tmp_path/'run')
    assert not FakeModel.instances
    assert not (tmp_path/'run').exists()


def test_both_services_are_closed_even_when_first_close_fails(environment, tmp_path):
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run')
    FakeModel.cleanup_failure = MODEL_ID
    with pytest.raises(CleanupError):
        result.close()
    assert all(model.closed for model in result.models)
    assert result.report['decision']['outcome'] == 'no-safe-placement'
    assert result.report['returned_runner_closed'] is False


def test_joint_quality_failure_rolls_back_both_services(environment, monkeypatch, tmp_path):
    original = environment.collect_joint
    def wrong_joint(*args, **kwargs):
        FakeModel.wrong_model = GLM_MODEL_ID
        return original(*args, **kwargs)
    monkeypatch.setattr(environment, 'collect_joint', wrong_joint)
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run')
    assert result.models == []
    assert result.report['decision']['outcome'] == 'no-safe-placement'
    assert all(model.closed for model in FakeModel.instances)


def test_incomplete_measurement_does_not_deadlock_peer(environment, monkeypatch, tmp_path):
    original = FakeModel.prepare
    def broken_prepare(self, prompt):
        if self.owner and self.model_id == MODEL_ID:
            raise RuntimeError('synthetic preparation failure')
        return original(self, prompt)
    monkeypatch.setattr(FakeModel, 'prepare', broken_prepare)
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run')
    assert result.models == []
    assert result.report['decision']['outcome'] == 'no-safe-placement'
    assert all(model.closed for model in FakeModel.instances)


def test_isolated_cleanup_failure_is_saved_and_cannot_continue(environment, tmp_path):
    import json
    FakeModel.cleanup_failure = MODEL_ID
    with pytest.raises(CleanupError):
        environment.place(**inputs(environment), output_dir=tmp_path/'run')
    report = json.loads((tmp_path/'run'/'result.json').read_text())
    assert report['status'] == 'cleanup-failed'
    assert report['returned_runner_closed'] is False
    assert len(FakeModel.instances) == 1


def test_second_joint_start_failure_closes_first_and_second(environment, monkeypatch, tmp_path):
    original = FakeModel.start
    def broken_start(self):
        if self.owner and self.model_id == GLM_MODEL_ID:
            self.artifact_dir.mkdir(parents=True)
            raise RuntimeError('joint startup failed')
        return original(self)
    monkeypatch.setattr(FakeModel, 'start', broken_start)
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run')
    assert len(FakeModel.instances) == 4
    assert all(model.closed for model in FakeModel.instances)
    assert result.models == []
    assert result.report['decision']['outcome'] == 'no-safe-placement'


def test_saved_plan_must_match_physical_gpu_before_joint(environment, monkeypatch, tmp_path):
    original = FakeOwner.acquire
    def changed_gpu(self):
        original(self)
        self.record['gpu'] = {'uuid':'another-gpu'}
        return self
    monkeypatch.setattr(FakeOwner, 'acquire', changed_gpu)
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run')
    assert result.models == []
    assert len(FakeModel.instances) == 2


def test_joint_wrong_measured_answers_fail_even_when_serial_quality_passes(environment, monkeypatch, tmp_path):
    original = environment.collect_joint
    def bad_measured(*args, **kwargs):
        result = original(*args, **kwargs)
        for item in result['trials'][MODEL_ID]['requests']:
            item['text'] = 'wrong'
        return result
    monkeypatch.setattr(environment, 'collect_joint', bad_measured)
    result = environment.place(**inputs(environment), output_dir=tmp_path/'run')
    gate = result.report['joint']['gates'][MODEL_ID]
    assert gate['quality_pass'] is True
    assert gate['measured_quality_pass'] is False
    assert result.models == []
