"""CUDA research integration with synthetic results, not hardware validation."""
import json
from pathlib import Path

import pytest
from test_cuda_backend import UUID, options
from test_native_optimizer import Agent, profile

from sera import native_optimizer as native
from sera.backends.cuda import MEMORY_METRIC, MEMORY_SCOPE, VERSIONS
from sera.managed_service import _result
from sera.model_artifact import seal_artifact, verify_artifact


def cuda_profile():
    return profile() | {'backend': 'cuda', 'runtime': options(), 'recipes': {
        'fp8': {'format': 'fp8', 'calibration': {'prompts': ['Calibrate.'], 'seed': 0, 'max_length': 32}}}}


def test_cuda_profile_requires_runtime_and_freezes_prepare_measure_controls():
    contract = native.validate_native_profile(cuda_profile())
    assert contract.baseline_recipe().format == 'bf16'
    assert contract.prepare_job('/destination', contract.baseline_recipe())['gpu_uuid'] == UUID
    assert contract.measure_job('/artifact', 'a'*64)['runtime'] == options()
    invalid = cuda_profile()
    invalid.pop('runtime')
    with pytest.raises(ValueError):
        native.validate_native_profile(invalid)


@pytest.mark.parametrize('sample_errors', [0, 1])
def test_cuda_research_confirms_checkpoint_or_rejects_invalid_memory(tmp_path, monkeypatch, sample_errors):
    jobs = []
    def worker(job, **kwargs):
        jobs.append(job)
        if job['operation'] == 'prepare':
            assert job['gpu_uuid'] == UUID
            folder = Path(job['destination'])
            folder.mkdir(parents=True)
            (folder / 'config.json').write_text('{}')
            (folder / 'model.safetensors').write_bytes(b'fixture')
            return {'artifact': seal_artifact(folder, backend='cuda', source=job['source'],
                recipe=job['recipe'], versions={}), 'preparation_seconds': 0.01}
        assert job['runtime'] == options()
        manifest = verify_artifact(job['artifact'])
        baseline = manifest['recipe']['format'] == 'bf16'
        controls = {key: job[key] for key in ('seed', 'max_tokens', 'warmup', 'repetitions',
            'response_formats', 'response_format_version', 'runtime')}
        controls.update(sampling='greedy', concurrency=1)
        return {'artifact_id': manifest['artifact_id'], 'controls': controls,
            'device': {'device_name': 'fixture', 'memory_size': 1000, 'backend': 'cuda',
                       'uuid': UUID, 'compute_capability': '9.0', 'driver': 'fixture'},
            'runtime_versions': {name: 'fixture' for name in VERSIONS}, 'request_wall_seconds': 0.1,
            'memory': {'metric': MEMORY_METRIC, 'scope': MEMORY_SCOPE,
                'resident_bytes': 20, 'active_bytes': 20, 'peak_bytes': 100 if baseline else 60,
                'sample_count': 5, 'sample_errors': 0 if baseline else sample_errors,
                'sample_interval_seconds': 0.01, 'max_sample_gap_seconds': 0.012},
            'requests': [{'repetition': r, 'prompt_index': 0, 'text': json.dumps({'answer': 1}),
                'token_ids': [1], 'prompt_token_ids': [2], 'latency_ms': 10., 'error': None,
                'finish_reason': 'stop', 'response_format': None} for r in range(job['repetitions'])]}
    monkeypatch.setattr(native, 'run_native_job', worker)
    monkeypatch.setattr(native, 'trace_native_job', lambda project, run:
        {'result': run(), 'trace': {'remote_verified': True, 'url': 'fixture-trace'}})
    report = native.optimize_native(profile=cuda_profile(), output_dir=tmp_path/'run',
                                    project='fixture/project', agent=Agent(('fp8',)))
    assert report['status'] == 'completed'
    assert report['selected_recipe_id'] == ('fp8' if sample_errors == 0 else 'baseline')
    if sample_errors == 0:
        assert len([job for job in jobs if job['operation'] == 'measure']) == 4
        assert report['trials'][0]['repeated_decision']['selected'] == 'candidate'
    public = _result(report)
    assert public['backend'] == 'cuda' and public['runtime'] == options()
    assert public['measurements']['scope'] == MEMORY_SCOPE
