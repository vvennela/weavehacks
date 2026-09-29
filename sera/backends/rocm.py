"""AMD ROCm BF16/NF4 checkpoints using native Transformers and bitsandbytes.

Contract-tested without an AMD device. A successful export is not a quality or
performance certificate. GPU allocator metrics exclude non-PyTorch allocations.
API references: https://huggingface.co/docs/bitsandbytes/v0.50.2/installation
https://huggingface.co/docs/transformers/v5.17.0/quantization/bitsandbytes
"""
import gc
import json
import math
import platform
import time
from importlib.metadata import version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..hardware import ModelDescriptor
from ..model_artifact import seal_artifact, verify_artifact
from ..placement_decoding import validate_formats, validate_response_format

VERSIONS = ('torch', 'transformers', 'bitsandbytes', 'accelerate', 'outlines')
MEMORY_SCOPE = 'PyTorch ROCm allocator; not total device memory or free VRAM'


class ROCmRecipe(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra='forbid')
    bits: Literal[4, 16] = 16
    quant_type: Literal['nf4'] = 'nf4'
    double_quant: bool = True


def _check_runtime(torch):
    if not torch.version.hip or torch.version.cuda or not torch.cuda.is_available():
        raise RuntimeError('This adapter requires a working ROCm build of PyTorch and an AMD GPU')
    if torch.cuda.device_count() != 1 or torch.cuda.current_device() != 0:
        raise RuntimeError('Expose exactly one assigned AMD device to this worker')
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError('The ROCm reference requires native BF16 support')
    props = torch.cuda.get_device_properties(0)
    return {'device_name': props.name, 'memory_size': props.total_memory,
            'architecture': props.gcnArchName, 'uuid': str(getattr(props, 'uuid', 'unavailable')),
            'backend': 'rocm', 'hip_version': torch.version.hip}


def _runtime():
    if platform.system() != 'Linux':
        raise RuntimeError('This ROCm adapter requires Linux with an AMD GPU')
    import torch
    _check_runtime(torch)
    return torch


def _probe_nf4(torch):
    from bitsandbytes.functional import dequantize_4bit, quantize_4bit
    tensor = torch.arange(128, device='cuda:0', dtype=torch.bfloat16).reshape(16, 8)
    packed, state = quantize_4bit(tensor, quant_type='nf4', compress_statistics=True)
    restored = dequantize_4bit(packed, state)
    torch.cuda.synchronize()
    if packed.dtype != torch.uint8 or packed.numel() != 64 or not torch.isfinite(restored).all().item():
        raise RuntimeError('The installed ROCm NF4 kernels did not pass their runtime probe')


def _check_config(folder, recipe):
    metadata = json.loads((Path(folder) / 'config.json').read_text())
    quant = metadata.get('quantization_config')
    if recipe.bits == 16:
        if quant is not None:
            raise ValueError('The BF16 baseline cannot load prequantized weights')
    elif (not isinstance(quant, dict) or quant.get('quant_method') != 'bitsandbytes'
          or quant.get('load_in_4bit', quant.get('_load_in_4bit')) is not True
          or quant.get('load_in_8bit', quant.get('_load_in_8bit', False)) is not False
          or quant.get('bnb_4bit_compute_dtype') != 'bfloat16'
          or quant.get('bnb_4bit_quant_storage') != 'uint8'
          or quant.get('bnb_4bit_quant_type') != recipe.quant_type
          or quant.get('bnb_4bit_use_double_quant') is not recipe.double_quant):
        raise ValueError('Checkpoint quantization metadata differs from its recipe')


def _check_weights(model, recipe, torch, linear4bit):
    parameters = list(model.parameters())
    if not parameters or any(p.device.type != 'cuda' or p.device.index != 0 for p in parameters):
        raise ValueError('All parameters must remain on the assigned ROCm device; offload is disabled')
    quantized = [module for module in model.modules() if isinstance(module, linear4bit)]
    if recipe.bits == 16:
        if quantized or any(p.dtype != torch.bfloat16 for p in parameters):
            raise ValueError('The reference must contain only BF16 parameters')
        return
    if not quantized:
        raise ValueError('No real packed NF4 modules were loaded')
    for module in quantized:
        weight = module.weight
        state = getattr(weight, 'quant_state', None)
        if (weight.dtype != torch.uint8 or not getattr(weight, 'bnb_quantized', False)
                or state is None or state.quant_type != 'nf4'
                or weight.numel() != (math.prod(state.shape) + 1) // 2):
            raise ValueError('NF4 requires packed uint8 weights with their quantization state')


def _load_model(folder, recipe, torch, *, quantize=False):
    from bitsandbytes.nn import Linear4bit
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    options = {'local_files_only': True, 'trust_remote_code': False,
               'dtype': torch.bfloat16, 'device_map': {'': 0}, 'use_safetensors': True}
    if quantize and recipe.bits == 4:
        options['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True,
            bnb_4bit_quant_type=recipe.quant_type, bnb_4bit_use_double_quant=recipe.double_quant,
            bnb_4bit_compute_dtype=torch.bfloat16)
    # On reload, Transformers reads the saved quantization config and tensors;
    # it must not re-quantize a fresh BF16 model under a new request recipe.
    model = AutoModelForCausalLM.from_pretrained(str(folder), **options).eval()
    tokenizer = AutoTokenizer.from_pretrained(str(folder), local_files_only=True, trust_remote_code=False)
    _check_weights(model, recipe, torch, Linear4bit)
    torch.cuda.synchronize()
    return model, tokenizer


class ROCmBackend:
    name = 'rocm'

    def capabilities(self):
        torch = _runtime()
        return {'backend': self.name, 'device': _check_runtime(torch),
                'versions': {name: version(name) for name in VERSIONS},
                'weight_bits': [16, 4], 'checkpoint_format': 'transformers-bitsandbytes-safetensors',
                'memory_metric': 'torch-rocm-allocated-bytes', 'concurrent_requests': False,
                'release_validation': 'requires-AMD-device-validation'}

    def prepare(self, *, source, destination, recipe):
        source = ModelDescriptor.model_validate(source)
        recipe = ROCmRecipe.model_validate(recipe)
        destination = Path(destination)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError('Model export requires a new destination')
        torch = _runtime()
        if recipe.bits == 4:
            _probe_nf4(torch)
        capabilities = self.capabilities()
        from huggingface_hub import snapshot_download
        started = time.perf_counter()
        snapshot = snapshot_download(repo_id=source.model_id, revision=source.revision,
            allow_patterns=['*.json', '*.safetensors', '*.txt', '*.jinja', '*.model'])
        _check_config(snapshot, ROCmRecipe())
        model = tokenizer = None
        try:
            model, tokenizer = _load_model(snapshot, recipe, torch, quantize=True)
            model.save_pretrained(str(destination))
            tokenizer.save_pretrained(str(destination))
            _check_config(destination, recipe)
            manifest = seal_artifact(destination, backend=self.name, source=source.model_dump(),
                                     recipe=recipe.model_dump(), versions=capabilities['versions'])
            return {'artifact': manifest, 'preparation_seconds': time.perf_counter() - started}
        finally:
            del model, tokenizer
            gc.collect()
            torch.cuda.empty_cache()

    def load(self, folder, *, expected_id=None):
        manifest = verify_artifact(folder, expected_id=expected_id, backend=self.name)
        recipe = ROCmRecipe.model_validate(manifest['recipe'])
        _check_config(folder, recipe)
        torch = _runtime()
        model, tokenizer = _load_model(Path(folder).resolve(), recipe, torch)
        return ROCmModel(model, tokenizer, manifest, torch)


class ROCmModel:
    def __init__(self, model, tokenizer, manifest, torch):
        self.model, self.tokenizer, self.manifest, self.torch = model, tokenizer, manifest, torch

    def generate(self, prompt, *, max_tokens, seed, response_format=None):
        if self.model is None:
            raise RuntimeError('The model is closed')
        if type(max_tokens) is not int or max_tokens < 1 or type(seed) is not int:
            raise ValueError('Supply a positive max_tokens and integer seed')
        if not isinstance(prompt, (str, list)) or not prompt:
            raise ValueError('Supply nonempty text or chat messages')
        if response_format is not None:
            response_format = validate_response_format(response_format)
        torch = self.torch
        torch.manual_seed(seed)
        text = self.tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True,
                   enable_thinking=False) if isinstance(prompt, list) else prompt
        inputs = self.tokenizer(text, return_tensors='pt', add_special_tokens=False).to('cuda:0')
        input_ids = inputs['input_ids'][0].tolist()
        torch.cuda.synchronize()
        started = time.perf_counter()
        processors = []
        if response_format is not None:
            from outlines import from_transformers
            from outlines.backends import get_json_schema_logits_processor
            processors.append(get_json_schema_logits_processor('outlines_core',
                from_transformers(self.model, self.tokenizer),
                json.dumps(response_format['json_schema']['schema'], allow_nan=False)))
        from transformers import GenerationConfig
        generation = GenerationConfig(do_sample=False, num_beams=1, max_new_tokens=max_tokens,
            eos_token_id=self.model.generation_config.eos_token_id,
            pad_token_id=(self.tokenizer.pad_token_id if self.tokenizer.pad_token_id is not None
                          else self.tokenizer.eos_token_id),
            use_cache=True)
        with torch.inference_mode():
            output = self.model.generate(**inputs, generation_config=generation, logits_processor=processors)
        torch.cuda.synchronize()
        elapsed = (time.perf_counter() - started) * 1000
        tokens = output[0, len(input_ids):].tolist()
        eos = generation.eos_token_id
        stops = eos if isinstance(eos, list) else [eos]
        return {'text': self.tokenizer.decode(tokens, skip_special_tokens=True),
                'token_ids': tokens, 'prompt_token_ids': input_ids, 'latency_ms': elapsed, 'error': None,
                'response_format': response_format,
                'finish_reason': 'stop' if tokens and tokens[-1] in stops else 'length'}

    def measure(self, prompts, *, max_tokens, seed, warmup, repetitions,
                response_formats=None, response_format_version=None):
        if (not isinstance(prompts, list) or not prompts or type(warmup) is not int
                or warmup < 0 or type(repetitions) is not int or repetitions < 1):
            raise ValueError('Supply prompts, nonnegative warmup, and positive repetitions')
        formats = validate_formats(prompts, response_formats, response_format_version)
        def generate(index, prompt):
            return self.generate(prompt, max_tokens=max_tokens, seed=seed,
                                 response_format=formats[index] if formats is not None else None)
        torch = self.torch
        for _ in range(warmup):
            for index, prompt in enumerate(prompts):
                generate(index, prompt)
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats(0)
        resident = torch.cuda.memory_allocated(0)
        rows = []
        started = time.perf_counter()
        for repetition in range(repetitions):
            for index, prompt in enumerate(prompts):
                rows.append(dict(repetition=repetition, prompt_index=index, **generate(index, prompt)))
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - started
        active = torch.cuda.memory_allocated(0)
        reserved = torch.cuda.memory_reserved(0)
        return {'artifact_id': self.manifest['artifact_id'], 'requests': rows,
                'request_wall_seconds': elapsed, 'runtime_versions': {name: version(name) for name in VERSIONS},
                'device': _check_runtime(torch),
                'controls': {'seed': seed, 'max_tokens': max_tokens, 'warmup': warmup,
                             'repetitions': repetitions, 'sampling': 'greedy', 'concurrency': 1,
                             'response_formats': formats, 'response_format_version': response_format_version},
                'memory': {'metric': 'torch-rocm-allocated-bytes', 'scope': MEMORY_SCOPE,
                           'resident_bytes': resident, 'peak_bytes': torch.cuda.max_memory_allocated(0),
                           'active_bytes': active, 'cache_bytes': reserved - active,
                           'reserved_bytes': reserved, 'peak_reserved_bytes': torch.cuda.max_memory_reserved(0)}}

    def close(self):
        self.model = self.tokenizer = None
        gc.collect()
        self.torch.cuda.synchronize()
        self.torch.cuda.empty_cache()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
