"""CUDA loader contracts; these tests do not certify NVIDIA execution."""
import os
import sys
from types import SimpleNamespace

import pytest

from sera.backends import cuda
from sera.model_artifact import seal_artifact

UUID = 'GPU-12345678-1234-1234-1234-123456789abc'


def options():
    return {'gpu_uuid': UUID, 'max_model_len': 256, 'kv_cache_memory_bytes': 1048576,
            'memory_sample_interval_seconds': 0.01}


def checkpoint(folder):
    (folder / 'config.json').write_text('{}')
    (folder / 'model.safetensors').write_bytes(b'fixture')
    return seal_artifact(folder, backend='cuda',
        source={'model_id': 'Qwen/Qwen3-0.6B', 'revision': 'a' * 40},
        recipe={'format': 'bf16', 'calibration': None}, versions={})


@pytest.mark.parametrize('change', [{'gpu_uuid': '0'}, {'kv_cache_memory_bytes': 0},
                                   {'memory_sample_interval_seconds': float('nan')}])
def test_runtime_requires_explicit_device_and_fixed_memory_budget(change):
    with pytest.raises(ValueError):
        cuda.CUDAOptions.model_validate(options() | change)
    with pytest.raises(ValueError):
        cuda.CUDAOptions.model_validate({'gpu_uuid': UUID})


def install_runtime(monkeypatch, *, in_process=True):
    calls = []
    torch = SimpleNamespace(cuda=SimpleNamespace(synchronize=lambda: None,
                                                 empty_cache=lambda: calls.append('empty')))
    class Core:
        def shutdown(self):
            calls.append('shutdown')
    class LLM:
        def __init__(self, **kwargs):
            calls.append(kwargs)
            self.llm_engine = SimpleNamespace(engine_core=Core())
        def get_tokenizer(self):
            return SimpleNamespace(encode=lambda text, **kwargs: [11, 12])
        def generate(self, prompts, params, **kwargs):
            calls.append((prompts, params))
            return [SimpleNamespace(prompt_token_ids=[11, 12], outputs=[SimpleNamespace(
                text='{"answer":1}', token_ids=[42, 99], finish_reason='stop')])]
    monkeypatch.setitem(sys.modules, 'vllm', SimpleNamespace(LLM=LLM, SamplingParams=SimpleNamespace))
    monkeypatch.setitem(sys.modules, 'vllm.sampling_params',
                        SimpleNamespace(StructuredOutputsParams=SimpleNamespace))
    monkeypatch.setitem(sys.modules, 'vllm.v1.engine.core_client',
                        SimpleNamespace(InprocClient=Core if in_process else type('Other', (), {})))
    monkeypatch.setattr(cuda, '_runtime', lambda runtime, recipe: (torch, {
        'device_name': 'NVIDIA fixture', 'memory_size': 1000, 'uuid': UUID,
        'backend': 'cuda', 'compute_capability': '9.0', 'driver': 'fixture'}))
    return calls


def test_loader_uses_fixed_cache_and_keeps_engine_in_owned_process(tmp_path, monkeypatch):
    manifest = checkpoint(tmp_path)
    calls = install_runtime(monkeypatch)
    with cuda.CUDABackend(options()).load(tmp_path, expected_id=manifest['artifact_id']) as model:
        result = model.generate('question', max_tokens=8, seed=7)
        assert result['token_ids'] == [42, 99]
        assert result['prompt_token_ids'] == [11, 12]
        assert result['finish_reason'] == 'stop'
        params = calls[-1][1]
        assert params.temperature == 0 and params.seed == 7 and params.max_tokens == 8
    settings = calls[0]
    assert settings['model'] == str(tmp_path.resolve())
    assert settings['kv_cache_memory_bytes'] == options()['kv_cache_memory_bytes']
    assert settings['quantization'] is None and settings['dtype'] == 'bfloat16'
    assert settings['cpu_offload_gb'] == 0 and settings['enable_prefix_caching'] is False
    assert settings['distributed_executor_backend'] == 'uni' and settings['max_num_seqs'] == 1
    assert settings['load_format'] == 'safetensors' and settings['trust_remote_code'] is False
    assert calls[-2:] == ['shutdown', 'empty']
    model.close()
    assert calls.count('shutdown') == 1
    with pytest.raises(RuntimeError, match='closed'):
        model.generate('question', max_tokens=8, seed=7)


def test_unexpected_engine_process_is_shutdown_and_rejected(tmp_path, monkeypatch):
    checkpoint(tmp_path)
    calls = install_runtime(monkeypatch, in_process=False)
    with pytest.raises(RuntimeError, match='process'):
        cuda.CUDABackend(options()).load(tmp_path)
    assert 'shutdown' in calls


def test_wrong_artifact_never_initializes_cuda(tmp_path, monkeypatch):
    manifest = checkpoint(tmp_path)
    monkeypatch.setattr(cuda, '_runtime', lambda *a: pytest.fail('Initialized invalid checkpoint'))
    with pytest.raises(ValueError):
        cuda.CUDABackend(options()).load(tmp_path, expected_id='b' * 64)
    assert manifest['backend'] == 'cuda'


def test_structured_generation_uses_schema_and_rejects_excess_context(tmp_path, monkeypatch):
    checkpoint(tmp_path)
    calls = install_runtime(monkeypatch)
    response_format = {'type': 'json_schema', 'json_schema': {'name': 'answer',
        'strict': True, 'schema': {'type': 'object', 'properties': {'answer': {'type': 'integer'}},
                                 'required': ['answer'], 'additionalProperties': False}}}
    with cuda.CUDABackend(options()).load(tmp_path) as model:
        result = model.generate('question', max_tokens=8, seed=0, response_format=response_format)
        assert calls[-1][1].structured_outputs.json == response_format['json_schema']['schema']
        assert result['response_format'] == response_format
        with pytest.raises(ValueError, match='context'):
            model.generate('question', max_tokens=256, seed=0)


def test_memory_sampler_includes_endpoints_and_rejects_foreign_processes(monkeypatch):
    used = iter([50, 90])
    nvml = SimpleNamespace(nvmlInit=lambda: None, nvmlShutdown=lambda: None,
        nvmlDeviceGetHandleByUUID=lambda uuid: uuid,
        nvmlDeviceGetUUID=lambda handle: UUID,
        nvmlDeviceGetMemoryInfo=lambda handle: SimpleNamespace(used=next(used)),
        nvmlDeviceGetComputeRunningProcesses=lambda handle: [SimpleNamespace(pid=os.getpid())],
        nvmlDeviceGetGraphicsRunningProcesses=lambda handle: [])
    monkeypatch.setitem(sys.modules, 'pynvml', nvml)
    with cuda.DeviceMemorySampler(UUID, interval=60) as sampler:
        pass
    result = sampler.result()
    assert result['resident_bytes'] == 50 and result['active_bytes'] == 90
    assert result['peak_bytes'] == 90 and result['sample_count'] == 2
    assert result['sample_errors'] == 0
    assert 'cache_bytes' not in result
    nvml.nvmlDeviceGetComputeRunningProcesses = lambda h: [SimpleNamespace(pid=os.getpid() + 1)]
    with cuda.DeviceMemorySampler(UUID, interval=60) as sampler:
        pass
    assert sampler.result()['sample_errors'] > 0


def test_device_assignment_preserves_inherited_visibility(monkeypatch):
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', 'GPU-ffffffff-1234-1234-1234-123456789abc')
    monkeypatch.setattr(cuda, 'discover_gpus', lambda: [{'uuid': UUID, 'name': 'fixture',
        'compute_capability': '9.0', 'total_mib': 1024, 'used_mib': 0,
        'driver': 'fixture', 'mig_mode': 'Disabled'}])
    with pytest.raises(ValueError, match='visible'):
        cuda.assign_device(UUID)
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', UUID)
    assert cuda.assign_device(UUID)['uuid'] == UUID
    assert os.environ['CUDA_VISIBLE_DEVICES'] == UUID


def test_measurement_covers_every_request_and_keeps_frozen_runtime(tmp_path, monkeypatch):
    checkpoint(tmp_path)
    calls = install_runtime(monkeypatch)
    events = []
    class Sampler:
        def __init__(self, uuid, *, interval):
            assert uuid == UUID and interval == options()['memory_sample_interval_seconds']
        def __enter__(self):
            events.append(len(calls))
            return self
        def __exit__(self, *args):
            events.append(len(calls))
        def result(self):
            return {'metric': cuda.MEMORY_METRIC, 'sample_errors': 0}
    monkeypatch.setattr(cuda, 'DeviceMemorySampler', Sampler)
    monkeypatch.setattr(cuda, 'version', lambda name: 'fixture')
    with cuda.CUDABackend(options()).load(tmp_path) as model:
        raw = model.measure(['first', 'second'], max_tokens=8, seed=0, warmup=1, repetitions=3)
    assert len(raw['requests']) == 6
    assert [(row['repetition'], row['prompt_index']) for row in raw['requests']] == [
        (r, i) for r in range(3) for i in range(2)]
    assert raw['controls']['runtime'] == options()
    assert events == [3, 9]  # two warmups precede the sampled six-request window
    assert raw['request_wall_seconds'] > 0
