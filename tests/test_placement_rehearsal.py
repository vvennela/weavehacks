"""Rehearsal manifest checking never contacts GPU, provider, or Weave."""

import json

import pytest

from sera.placement_config import validate_placement_plan
from test_placement import environment, inputs
from test_placement_relative_latency import relative_inputs


def manifest(environment):
    args = relative_inputs(environment)
    plan = validate_placement_plan(args['plan'])
    return dict(schema_version='sera-placement-rehearsal-v1', plans=[plan.model_dump()],
                memory_estimates={plan.plan_hash:{model:value.model_dump() for model,value in args['memory_estimates'].items()}},
                concurrency=[1, 2, 4, 8])


def test_check_manifest_has_no_runtime_side_effects(environment, monkeypatch, tmp_path, capsys):
    from experiments import run_placement
    monkeypatch.setattr(run_placement, 'run_references', lambda *_:pytest.fail('no GPU'))
    monkeypatch.setattr(run_placement, 'run_search', lambda *_, **__:pytest.fail('no provider'))
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps(manifest(environment)))
    assert run_placement.main(['--manifest', str(path), '--phase', 'check']) == 0
    assert 'manifest-valid-not-live-tested' in capsys.readouterr().out


@pytest.mark.parametrize('field,value', [('quality_floor', .9), ('max_p95_slowdown_fraction', .50)])
def test_rehearsal_rejects_unapproved_task_or_latency_threshold(environment, tmp_path, field, value):
    from experiments.run_placement import load_manifest
    data = manifest(environment)
    data['plans'][0]['services'][0]['constraints'][field] = value
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='approved'):
        load_manifest(path)


def test_explicit_manifest_accounting_does_not_change_plan_or_workload(environment, tmp_path):
    from experiments.run_placement import load_manifest
    data = manifest(environment)
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps(data))
    strict = load_manifest(path)
    data['memory_accounting'] = 'total-device'
    path.write_text(json.dumps(data))
    total = load_manifest(path)
    assert strict['memory_accounting'] == 'per-service'
    assert total['memory_accounting'] == 'total-device'
    assert total['plans'] == strict['plans']
    assert {m:p.manifest() for m,p in total['workloads'].items()} == {
        m:p.manifest() for m,p in strict['workloads'].items()}
