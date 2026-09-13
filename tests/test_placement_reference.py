"""Saved references must match actual raw requests, plan, and task contract."""

import json

import pytest

from test_placement import environment, inputs, FakeModel, MODEL_ID


def reference(environment, tmp_path):
    return environment.measure_placement_references(**inputs(environment), output_dir=tmp_path/'references')


def test_reference_stage_stops_after_two_closed_isolated_models(environment, tmp_path):
    result = reference(environment, tmp_path)
    assert result.report['status'] == 'references-ready'
    assert result.report['decision']['outcome'] == 'references-ready'
    assert result.models == []
    assert len(FakeModel.instances) == 2
    assert all(model.closed and model.owner is None for model in FakeModel.instances)


def test_bound_reference_skips_new_isolated_starts(environment, tmp_path):
    reference(environment, tmp_path)
    result = environment.place(**inputs(environment), output_dir=tmp_path/'joint',
                               isolated_reference=tmp_path/'references'/'result.json')
    assert result.report['decision']['outcome'] == 'safe-placement'
    assert len(FakeModel.instances) == 4
    assert len(result.models) == 2
    assert result.report['isolated_reference']['sha256']
    result.close()


@pytest.mark.parametrize('change', ['quality', 'latency', 'tokens', 'workload', 'plan', 'cleanup'])
def test_tampered_or_mismatched_references_never_start_a_joint_service(environment, tmp_path, change):
    reference(environment, tmp_path)
    path = tmp_path/'references'/'result.json'
    record = json.loads(path.read_text())
    trial = record['isolated'][MODEL_ID]
    if change == 'quality':
        trial['quality'][0]['text'] = 'wrong'
        trial['task_quality']['passed'] = True
    elif change == 'latency':
        trial['reduced']['p95_latency_ms'] = .001
    elif change == 'tokens':
        trial['requests'][0]['prompt_token_ids'] = [999]
    elif change == 'workload':
        record['workloads'][MODEL_ID]['evaluator_version'] = 'other-version'
    elif change == 'plan':
        record['plan']['declared_budget_bytes'] -= 1
    elif change == 'cleanup':
        trial['runtime']['cleanup_pass'] = False
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        environment.place(**inputs(environment), output_dir=tmp_path/'joint', isolated_reference=path)
    assert len(FakeModel.instances) == 2
