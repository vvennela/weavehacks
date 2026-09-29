"""Load sealed ModelOpt checkpoints with vLLM 0.30.0 on one NVIDIA GPU.

Pinned API: https://github.com/vllm-project/vllm/tree/v0.30.0/vllm
Contract tests do not establish device compatibility or performance.
"""
import gc
import math
import os
import platform
import sys
import threading
import time
from importlib.metadata import version
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..hardware import HardwareAssignment, discover_gpus, preflight_hardware
from ..model_artifact import verify_artifact
from ..placement_decoding import validate_formats, validate_response_format
from .modelopt_export import ModelOptRecipe, check_cuda_runtime, check_modelopt_export

VERSIONS = ('torch', 'transformers', 'vllm', 'nvidia-ml-py')
MEMORY_METRIC = 'nvml-sampled-device-used-bytes'
MEMORY_SCOPE = 'Sampled NVIDIA device memory including runtime and KV cache; not an exact high-water mark'


class CUDAOptions(BaseModel):
    """Operator-supplied controls, identical for baseline and candidate loads."""
    model_config = ConfigDict(strict=True, frozen=True, extra='forbid', allow_inf_nan=False)
    gpu_uuid: str
    max_model_len: int = Field(gt=0)
    kv_cache_memory_bytes: int = Field(gt=0)
    memory_sample_interval_seconds: float = Field(gt=0)

    @field_validator('gpu_uuid')
    @classmethod
    def physical_device(cls, value):
        HardwareAssignment(gpu_uuids=[value])
        return value


def assign_device(gpu_uuid):
    """Validate the inherited visibility restriction before narrowing it."""
    assignment = HardwareAssignment(gpu_uuids=[gpu_uuid])
    device = preflight_hardware(assignment, discover_gpus(),
                               visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'))[0]
    os.environ['CUDA_VISIBLE_DEVICES'] = gpu_uuid
    return device


def _runtime(options, recipe):
    if platform.system() != 'Linux':
        raise RuntimeError('The CUDA adapter requires Linux and an assigned NVIDIA GPU')
    if version('vllm') != '0.30.0':
        raise RuntimeError('This CUDA loader requires vLLM 0.30.0')
    # Direct ManagedResult.load() calls need the same installed compiler helpers
    # as disposable workers, even when Python was invoked by an absolute path.
    os.environ['PATH'] = os.pathsep.join((str(Path(sys.executable).parent),
                                         os.environ.get('PATH', os.defpath)))
    import torch
    if torch.cuda.is_initialized():
        raise RuntimeError('Load CUDA checkpoints in a fresh process before CUDA initialization')
    device = assign_device(options.gpu_uuid)
    # vLLM defaults to a separate engine process. Keep all device work inside
    # the native worker's owned process so deadline and cancellation apply.
    os.environ['VLLM_ENABLE_V1_MULTIPROCESSING'] = '0'
    check_cuda_runtime(torch, recipe)
    properties = torch.cuda.get_device_properties(0)
    actual_uuid = str(properties.uuid)
    if actual_uuid.removeprefix('GPU-').lower() != options.gpu_uuid.removeprefix('GPU-').lower():
        raise RuntimeError('CUDA device identity differs from the assigned GPU')
    return torch, {'device_name': device['name'], 'memory_size': properties.total_memory,
                   'uuid': options.gpu_uuid, 'backend': 'cuda',
                   'compute_capability': device['compute_capability'], 'driver': device['driver']}


def _shutdown(engine, torch):
    try:
        engine.llm_engine.engine_core.shutdown()
    finally:
        gc.collect()
        torch.cuda.empty_cache()


class CUDABackend:
    name = 'cuda'

    def __init__(self, runtime):
        self.runtime = CUDAOptions.model_validate(runtime)

    def load(self, folder, *, expected_id=None):
        manifest = verify_artifact(folder, expected_id=expected_id, backend=self.name)
        recipe = ModelOptRecipe.model_validate(manifest['recipe'])
        check_modelopt_export(folder, recipe)
        torch, device = _runtime(self.runtime, recipe)
        from vllm import LLM
        from vllm.v1.engine.core_client import InprocClient
        engine = None
        try:
            engine = LLM(model=str(Path(folder).resolve()), dtype='bfloat16',
                quantization={'bf16': None, 'fp8': 'modelopt', 'nvfp4': 'modelopt_fp4'}[recipe.format],
                load_format='safetensors', trust_remote_code=False, tensor_parallel_size=1,
                distributed_executor_backend='uni', enforce_eager=True, max_num_seqs=1,
                max_model_len=self.runtime.max_model_len,
                max_num_batched_tokens=self.runtime.max_model_len,
                kv_cache_memory_bytes=self.runtime.kv_cache_memory_bytes,
                kv_cache_dtype='auto', cpu_offload_gb=0, enable_prefix_caching=False,
                generation_config='vllm')
            if not isinstance(engine.llm_engine.engine_core, InprocClient):
                raise RuntimeError('vLLM must execute in the owned native worker process')  # noqa: TRY004
            tokenizer = engine.get_tokenizer()
            return CUDAModel(engine, tokenizer, manifest, torch, device, self.runtime)
        except BaseException:
            if engine is not None:
                _shutdown(engine, torch)
            raise


class DeviceMemorySampler:
    """Sample the assigned physical device, including both window endpoints."""
    def __init__(self, gpu_uuid, *, interval):
        self.gpu_uuid, self.interval = gpu_uuid, interval
        self.count = self.errors = self.peak = 0
        self.first = self.last = None
        self.previous_time = None
        self.max_gap = 0.0
        self.stop = threading.Event()
        self.thread = None

    def _sample(self):
        now = time.monotonic()
        if self.previous_time is not None:
            self.max_gap = max(self.max_gap, now - self.previous_time)
        self.previous_time = now
        try:
            nvml = self.nvml
            processes = (nvml.nvmlDeviceGetComputeRunningProcesses(self.handle)
                         + nvml.nvmlDeviceGetGraphicsRunningProcesses(self.handle))
            if any(process.pid != os.getpid() for process in processes):
                raise RuntimeError('A foreign process is using the assigned device')
            used = nvml.nvmlDeviceGetMemoryInfo(self.handle).used
            if type(used) is not int or used < 0:
                raise ValueError('Invalid device memory reading')
            if self.first is None:
                self.first = used
            self.last = used
            self.peak = max(self.peak, used)
            self.count += 1
        except Exception:  # noqa: BLE001 -- every sampler failure invalidates the memory result
            self.errors += 1

    def _run(self):
        while not self.stop.wait(self.interval):
            self._sample()

    def __enter__(self):
        import pynvml
        self.nvml = pynvml
        pynvml.nvmlInit()
        try:
            self.handle = pynvml.nvmlDeviceGetHandleByUUID(self.gpu_uuid)
            actual = pynvml.nvmlDeviceGetUUID(self.handle)
            actual = actual.decode() if isinstance(actual, bytes) else actual
            if actual.lower() != self.gpu_uuid.lower():
                raise RuntimeError('NVML device identity differs from the assigned GPU')
            self._sample()
            self.thread = threading.Thread(target=self._run, name='sera-cuda-memory', daemon=True)
            self.thread.start()
            return self
        except BaseException:
            pynvml.nvmlShutdown()
            raise

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join()
        try:
            self._sample()
        finally:
            self.nvml.nvmlShutdown()

    def result(self):
        return {'metric': MEMORY_METRIC, 'scope': MEMORY_SCOPE,
                'resident_bytes': self.first, 'active_bytes': self.last, 'peak_bytes': self.peak,
                'sample_count': self.count, 'sample_errors': self.errors,
                'sample_interval_seconds': self.interval, 'max_sample_gap_seconds': self.max_gap}


class CUDAModel:
    def __init__(self, engine, tokenizer, manifest, torch, device, runtime):
        self.engine, self.tokenizer, self.manifest = engine, tokenizer, manifest
        self.torch, self.device, self.runtime = torch, device, runtime

    def generate(self, prompt, *, max_tokens, seed, response_format=None):
        if self.engine is None:
            raise RuntimeError('The model is closed')
        if type(max_tokens) is not int or max_tokens < 1 or type(seed) is not int:
            raise ValueError('Supply a positive max_tokens and integer seed')
        if not isinstance(prompt, (str, list)) or not prompt:
            raise ValueError('Supply nonempty text or chat messages')
        if response_format is not None:
            response_format = validate_response_format(response_format)
        from vllm import SamplingParams
        from vllm.sampling_params import StructuredOutputsParams
        text = self.tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True,
                   enable_thinking=False) if isinstance(prompt, list) else prompt
        input_ids = self.tokenizer.encode(text, add_special_tokens=False)
        if not input_ids or len(input_ids) + max_tokens > self.runtime.max_model_len:
            raise ValueError('Request exceeds the fixed context limit or has no input tokens')
        structured = (StructuredOutputsParams(json=response_format['json_schema']['schema'])
                      if response_format is not None else None)
        parameters = SamplingParams(temperature=0, max_tokens=max_tokens, seed=seed,
                                    structured_outputs=structured)
        self.torch.cuda.synchronize()
        started = time.perf_counter()
        output = self.engine.generate([{'prompt_token_ids': input_ids}], parameters, use_tqdm=False)
        self.torch.cuda.synchronize()
        elapsed = (time.perf_counter() - started) * 1000
        if len(output) != 1 or len(output[0].outputs) != 1 or output[0].prompt_token_ids != input_ids:
            raise RuntimeError('Inference output does not match the single input request')
        completion = output[0].outputs[0]
        return {'text': completion.text, 'token_ids': list(completion.token_ids),
                'prompt_token_ids': input_ids, 'latency_ms': elapsed, 'error': None,
                'response_format': response_format, 'finish_reason': completion.finish_reason}

    def measure(self, prompts, *, max_tokens, seed, warmup, repetitions,
                response_formats=None, response_format_version=None):
        if (not isinstance(prompts, list) or not prompts or type(warmup) is not int
                or warmup < 0 or type(repetitions) is not int or repetitions < 1):
            raise ValueError('Supply prompts, nonnegative warmup, and positive repetitions')
        formats = validate_formats(prompts, response_formats, response_format_version)
        def generate(index, prompt):
            return self.generate(prompt, max_tokens=max_tokens, seed=seed,
                                 response_format=formats[index] if formats is not None else None)
        for _ in range(warmup):
            for index, prompt in enumerate(prompts):
                generate(index, prompt)
        self.torch.cuda.synchronize()
        rows = []
        with DeviceMemorySampler(self.runtime.gpu_uuid,
                interval=self.runtime.memory_sample_interval_seconds) as sampler:
            started = time.perf_counter()
            for repetition in range(repetitions):
                for index, prompt in enumerate(prompts):
                    rows.append(dict(repetition=repetition, prompt_index=index, **generate(index, prompt)))
            self.torch.cuda.synchronize()
            elapsed = time.perf_counter() - started
        if not math.isfinite(elapsed) or elapsed <= 0:
            raise RuntimeError('Invalid request measurement window')
        return {'artifact_id': self.manifest['artifact_id'], 'requests': rows,
                'request_wall_seconds': elapsed, 'device': self.device,
                'runtime_versions': {name: version(name) for name in VERSIONS},
                'controls': {'seed': seed, 'max_tokens': max_tokens, 'warmup': warmup,
                             'repetitions': repetitions, 'sampling': 'greedy', 'concurrency': 1,
                             'response_formats': formats, 'response_format_version': response_format_version,
                             'runtime': self.runtime.model_dump()},
                'memory': sampler.result()}

    def close(self):
        if self.engine is not None:
            engine, self.engine = self.engine, None
            self.tokenizer = None
            _shutdown(engine, self.torch)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
