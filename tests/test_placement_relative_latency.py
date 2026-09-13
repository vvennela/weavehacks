"""The 10% slowdown allowance is frozen before measuring either workload."""

import json

import pytest

from test_placement import environment, inputs, FakeOwner, MODEL_ID, GLM_MODEL_ID


def relative_inputs(environment):
    args = inputs(environment)
    for service in args['plan']['services']:
        service['constraints'].pop('p95_latency_ms')
        service['constraints']['max_p95_slowdown_fraction'] = .10
    return args


def test_relative_ceiling_is_saved_from_isolated_latency_before_joint_start(environment, monkeypatch, tmp_path):
    original = FakeOwner.acquire
    def acquire(self):
        report = json.loads((tmp_path/'run'/'result.json').read_text())
        limits = report['derived_joint_latency_limits']
        for model in (MODEL_ID, GLM_MODEL_ID):
            assert limits[model]['isolated_p95_ms'] == 2.
            assert limits[model]['max_p95_slowdown_fraction'] == .10
            assert limits[model]['p95_latency_limit_ms'] == pytest.approx(2.2)
            assert limits[model]['isolated_trial_sha256']
        return original(self)
    monkeypatch.setattr(FakeOwner, 'acquire', acquire)
    result = environment.place(**relative_inputs(environment), output_dir=tmp_path/'run')
    assert len(result.models) == 2
    result.close()


@pytest.mark.parametrize('latency,passed', [(2.2, True), (2.20001, False)])
def test_joint_gate_enforces_the_frozen_ratio_without_changing_task_gate(environment, monkeypatch, tmp_path, latency, passed):
    original = environment.collect_joint
    def measured(*args, **kwargs):
        result = original(*args, **kwargs)
        result['trials'][MODEL_ID]['reduced']['p95_latency_ms'] = latency
        return result
    monkeypatch.setattr(environment, 'collect_joint', measured)
    result = environment.place(**relative_inputs(environment), output_dir=tmp_path/'run')
    gate = result.report['joint']['gates'][MODEL_ID]
    assert gate['latency_pass'] is passed
    assert gate['quality_pass'] is True
    assert gate['latency_limit_ms'] == pytest.approx(2.2)
    assert gate['max_p95_slowdown_fraction'] == .10
    assert bool(result.models) is passed
    result.close()
