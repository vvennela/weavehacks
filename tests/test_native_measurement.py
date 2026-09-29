"""Native results must prove complete, comparable measurements before selection."""

from copy import deepcopy

import pytest

from sera.config import Constraints, Objective
from sera.measurement import select_candidate
from sera.native_measurement import native_trial


def measurement():
    return {'artifact_id': 'a' * 64, 'device': {'device_name': 'fixture', 'memory_size': 1000},
            'runtime_versions': {name: 'fixture' for name in ('mlx', 'mlx-lm', 'transformers', 'outlines')},
            'controls': {'seed': 0, 'max_tokens': 64, 'warmup': 1, 'repetitions': 3,
                         'sampling': 'greedy', 'concurrency': 1,
                         'response_formats': None, 'response_format_version': None},
            'request_wall_seconds': 0.1,
            'memory': {'metric': 'mlx-active-allocator-bytes', 'resident_bytes': 50,
                       'peak_bytes': 100, 'active_bytes': 50, 'cache_bytes': 10,
                       'scope': 'MLX allocator; not system-wide unified memory or free VRAM'},
            'requests': [{'repetition': r, 'prompt_index': i, 'text': 'correct',
                          'error': None, 'latency_ms': 10.0, 'token_ids': [3],
                          'prompt_token_ids': [i + 1], 'response_format': None,
                          'finish_reason': 'stop'} for r in range(3) for i in range(2)]}


def trial(raw):
    return native_trial(raw, prompts=['first', 'second'], evaluator=lambda p, t: t == 'correct',
                        evaluation_version='fixture-v1', floor=0.99,
                        artifact_id='a' * 64, controls=measurement()['controls'], trial_id='test')


def test_valid_native_result_uses_all_requests_and_real_window():
    result = trial(measurement())
    assert result['status'] == 'collected'
    assert result['task_quality']['mean'] == 1
    assert len(result['task_quality']['per_prompt']) == 6
    assert result['reduced']['output_tokens_per_second'] == 60
    assert result['input_token_ids'] == [[1], [2]]
    assert result['runtime']['memory']['metric'] == 'mlx-active-allocator-bytes'


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'empty', 'nan', 'error',
                                    'artifact', 'tokens', 'format', 'controls', 'finish', 'window',
                                    'device', 'versions'])
def test_invalid_measurements_cannot_pass_existing_selection_gates(mutation):
    raw = measurement()
    if mutation == 'missing': raw['requests'].pop()
    if mutation == 'duplicate': raw['requests'][-1] = deepcopy(raw['requests'][0])
    if mutation == 'empty': raw['requests'][-1]['text'] = ''
    if mutation == 'nan': raw['requests'][-1]['latency_ms'] = float('nan')
    if mutation == 'error': raw['requests'][-1]['error'] = 'failed'
    if mutation == 'artifact': raw['artifact_id'] = 'b' * 64
    if mutation == 'tokens': raw['requests'][-1]['prompt_token_ids'] = [999]
    if mutation == 'format': raw['requests'][-1]['response_format'] = {}
    if mutation == 'controls': raw['controls']['seed'] = 42
    if mutation == 'finish': raw['requests'][-1]['finish_reason'] = 'error'
    if mutation == 'window': raw['request_wall_seconds'] = 0
    if mutation == 'device': raw.pop('device')
    if mutation == 'versions': raw.pop('runtime_versions')
    raw['memory']['peak_bytes'] = 70
    candidate = trial(raw)
    decision = select_candidate(trial(measurement()), candidate,
        objective=Objective(priority='memory'), constraints=Constraints(quality_floor=0.99))
    assert candidate['status'] != 'collected'
    assert decision['selected'] == 'baseline'


def test_later_quality_failure_is_not_hidden_by_first_repetition():
    raw = measurement()
    raw['requests'][-1]['text'] = 'wrong'
    result = trial(raw)
    assert result['task_quality']['mean'] == pytest.approx(5/6)
    assert result['task_quality']['passed'] is False


@pytest.mark.parametrize('mutation', ['missing', 'negative', 'incoherent', 'boolean', 'scope'])
def test_invalid_memory_remains_unavailable(mutation):
    raw = measurement()
    if mutation == 'missing': raw['memory'].pop('cache_bytes')
    if mutation == 'negative': raw['memory']['resident_bytes'] = -1
    if mutation == 'incoherent': raw['memory']['peak_bytes'] = 1
    if mutation == 'boolean': raw['memory']['peak_bytes'] = True
    if mutation == 'scope': raw['memory']['metric'] = 'unknown'
    result = trial(raw)
    assert result['runtime']['telemetry_errors'] != 0
    assert result['runtime']['sampled_peak_memory_mib'] is None


def test_rocm_measurements_keep_their_allocator_scope_and_runtime_identity():
    raw = measurement()
    raw['runtime_versions'] = {name:'fixture' for name in
                               ('torch','transformers','bitsandbytes','accelerate','outlines')}
    raw['device'].update(backend='rocm', hip_version='7.0', architecture='gfx942')
    raw['memory'].update(metric='torch-rocm-allocated-bytes',
                        scope='PyTorch ROCm allocator; not total device memory or free VRAM',
                        reserved_bytes=60, peak_reserved_bytes=100)
    def collect():
        return native_trial(raw, prompts=['first','second'], evaluator=lambda p,t:True,
            evaluation_version='fixture-v1', floor=0.99, artifact_id='a'*64,
            controls=measurement()['controls'], trial_id='rocm', backend='rocm')
    result = collect()
    assert result['status'] == 'collected'
    assert result['runtime']['telemetry_errors'] == 0
    raw['memory']['reserved_bytes'] = 1
    assert collect()['runtime']['sampled_peak_memory_mib'] is None
    raw['device']['backend'] = 'cuda'
    assert collect()['status'] != 'collected'


@pytest.mark.parametrize('mutation', [None, 'errors', 'few-samples', 'interval', 'uuid', 'gap', 'metric'])
def test_cuda_device_samples_are_validated_without_allocator_claims(mutation):
    from test_cuda_backend import UUID, options

    from sera.backends.cuda import MEMORY_METRIC, MEMORY_SCOPE, VERSIONS
    raw = measurement()
    raw['runtime_versions'] = {name: 'fixture' for name in VERSIONS}
    raw['device'].update(backend='cuda', uuid=UUID, compute_capability='9.0', driver='fixture')
    raw['controls']['runtime'] = options()
    raw['memory'] = {'metric': MEMORY_METRIC, 'scope': MEMORY_SCOPE, 'resident_bytes': 50,
                     'active_bytes': 50, 'peak_bytes': 100, 'sample_count': 5, 'sample_errors': 0,
                     'sample_interval_seconds': 0.01, 'max_sample_gap_seconds': 0.012}
    if mutation == 'errors': raw['memory']['sample_errors'] = 1
    if mutation == 'few-samples': raw['memory']['sample_count'] = 1
    if mutation == 'interval': raw['memory']['sample_interval_seconds'] = 1
    if mutation == 'uuid': raw['device']['uuid'] = 'wrong'
    if mutation == 'gap': raw['memory']['max_sample_gap_seconds'] = float('nan')
    if mutation == 'metric': raw['memory']['metric'] = 'torch-allocated-bytes'
    result = native_trial(raw, prompts=['first', 'second'], evaluator=lambda p, t: True,
        evaluation_version='fixture-v1', floor=0.99, artifact_id='a'*64,
        controls=raw['controls'], trial_id='cuda', backend='cuda')
    assert result['runtime']['memory_measurement_method'] == 'sampled-device-memory'
    if mutation == 'uuid':
        assert result['status'] != 'collected'
    elif mutation is not None:
        assert result['runtime']['sampled_peak_memory_mib'] is None
    else:
        assert result['status'] == 'collected'
        assert result['runtime']['telemetry_errors'] == 0
