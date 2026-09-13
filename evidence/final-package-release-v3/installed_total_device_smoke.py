"""Wheel-only accounting API checks. No process, GPU, or provider is started."""

import inspect
import json
from pathlib import Path
from unittest.mock import patch

import sera
from sera.config import MODEL_ID, MODEL_REVISION, GLM_MODEL_ID, GLM_MODEL_REVISION
from sera.placement_config import validate_memory_accounting
from sera.placement_runtime import SharedGPUOwner


def main():
    assert 'site-packages' in str(Path(sera.__file__))
    assert validate_memory_accounting('total-device') == 'total-device'
    for function in (sera.place, sera.optimize_placement):
        assert inspect.signature(function).parameters['memory_accounting'].default == 'per-service'
    plan = dict(physical_gpu_bytes=1000, declared_budget_bytes=800, services=[
        dict(model_id=model, revision=revision, gpu_index=0, allocation_bytes=allocation,
             configuration=sera.RuntimeConfig(gpu_memory_utilization=allocation / 1000).model_dump(),
             constraints=dict(quality_floor=.99, p95_latency_ms=100.0, max_generation_errors=0))
        for model, revision, allocation in ((MODEL_ID, MODEL_REVISION, 200),
                                            (GLM_MODEL_ID, GLM_MODEL_REVISION, 520))])
    with patch('subprocess.run', side_effect=AssertionError('No external process in installed smoke')):
        owner = SharedGPUOwner(plan, memory_accounting='total-device')
        assert owner.record['status'] == 'not-started'
        assert owner.record['per_service_memory_verified'] is False
        assert owner.record['service_allocation_semantics'] == 'configured-vllm-budget-not-verified-process-cap'
        assert set(owner.record['service_peak_memory_mib'].values()) == {None}
        assert SharedGPUOwner(plan).memory_accounting == 'per-service'
        with patch('sera.placement._run_placement', side_effect=lambda arguments, project: arguments):
            forwarded = sera.place(plan=plan, workloads={}, memory_estimates={}, output_dir='not-created',
                                   memory_accounting='total-device')
            assert forwarded['memory_accounting'] == 'total-device'
        with patch('sera.placement_search._optimize_placement', side_effect=lambda **arguments: arguments):
            forwarded = sera.optimize_placement(plans=[plan], workloads={}, memory_estimates={},
                isolated_references={}, agent=None, provider_check=None, output_dir='not-created',
                memory_accounting='total-device')
            assert forwarded['memory_accounting'] == 'total-device'
        try:
            sera.place(plan=plan, workloads={}, memory_estimates={}, output_dir='not-created',
                       memory_accounting='auto')
        except ValueError as error:
            assert 'memory_accounting' in str(error)
        else:
            raise AssertionError('Unknown accounting mode was accepted')
    print(json.dumps(dict(status='passed', package_path=sera.__file__,
        accounting_mode='explicit-total-device', default_mode='per-service',
        per_service_memory_verified=False, checks=['installed public signatures',
            'explicit mode forwarded through place and optimize_placement',
            'constructor marks service memory unknown', 'unknown mode rejected before execution'],
        gpu_calls=0, provider_calls=0, runtime_boundaries='stubbed')))


if __name__ == '__main__':
    main()
