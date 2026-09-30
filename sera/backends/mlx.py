"""Native Apple MLX checkpoint preparation and inference.

Exports are MLX artifacts, not PyTorch checkpoints. No provider credentials,
quality policy, or candidate-selection authority belongs in this backend.
"""

import gc
import json
import platform
import time
from importlib.metadata import version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..hardware import ModelDescriptor
from ..model_artifact import seal_artifact, verify_artifact
from ..placement_decoding import validate_formats, validate_response_format


def _json_processor(model, tokenizer, response_format):
    from outlines import from_mlxlm
    from outlines.backends import get_json_schema_logits_processor
    return get_json_schema_logits_processor('outlines_core', from_mlxlm(model, tokenizer),
        json.dumps(response_format['json_schema']['schema'], allow_nan=False))


class MLXRecipe(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra='forbid')
    bits: Literal[2, 3, 4, 8, 16] = 16
    group_size: Literal[32, 64, 128] = 64
    protected_bits: Literal[3, 4, 6, 8] | None = Field(default=None, exclude_if=lambda v: v is None)
    protection_pattern: Literal['all-v-down', 'all-except-mlp-expansion', 'mlp-and-query-output'] | None = Field(
        default=None, exclude_if=lambda value: value is None)
    attention_group_size: Literal[32, 64, 128] | None = Field(
        default=None, exclude_if=lambda value: value is None)

    @model_validator(mode='after')
    def validate_precision(self):
        if self.protection_pattern is not None and self.protected_bits is None:
            raise ValueError('A protection pattern requires protected bits')
        if (self.protection_pattern == 'mlp-and-query-output') != (self.attention_group_size is not None):
            raise ValueError('Query/output precision requires its explicit attention group size')
        if self.protected_bits is not None and self.protected_bits <= self.bits:
            raise ValueError('Protected modules require higher precision')
        return self


def mixed_quantization_predicate(recipe, num_layers):
    """Protect embeddings and selected value/down projections from low precision."""
    if recipe.protected_bits is None or type(num_layers) is not int or num_layers < 1:
        raise ValueError('Mixed quantization requires protected bits and a layer count')

    def choose(path, module):
        parts = path.split('.')
        index = next((int(part) for part in parts if part.isdigit()), None)
        sensitive = index is not None and (
            index < num_layers // 8 or index >= 7 * num_layers // 8
            or (index - num_layers // 8) % 3 == 2)
        protected = parts[-1] in {'embed_tokens', 'lm_head'} or (
            sensitive and parts[-1] in {'v_proj', 'down_proj'})
        if recipe.protection_pattern == 'all-v-down':
            protected = parts[-1] in {'embed_tokens', 'lm_head', 'v_proj', 'down_proj'}
        elif recipe.protection_pattern == 'all-except-mlp-expansion':
            protected = not ('mlp' in parts and parts[-1] in {'gate_proj', 'up_proj'})
        elif recipe.protection_pattern == 'mlp-and-query-output':
            protected = not (('mlp' in parts and parts[-1] in {'gate_proj', 'up_proj'})
                or ('self_attn' in parts and parts[-1] in {'q_proj', 'o_proj'}))
        group_size = (recipe.attention_group_size if recipe.attention_group_size is not None
            and 'self_attn' in parts and parts[-1] in {'q_proj', 'o_proj'} else recipe.group_size)
        return {'bits': recipe.protected_bits if protected else recipe.bits,
                'group_size': group_size, 'mode': 'affine'}
    return choose


def _runtime():
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise RuntimeError('This MLX adapter requires Apple silicon and macOS')
    import mlx.core as mx
    if not mx.metal.is_available():
        raise RuntimeError('MLX Metal device is unavailable')
    return mx


class MLXBackend:
    name = 'mlx'

    def capabilities(self):
        mx = _runtime()
        return {'backend': self.name, 'device': mx.device_info(),
                    'versions': {name: version(name) for name in ('mlx', 'mlx-lm', 'transformers')},
                    'weight_bits': [16, 8, 4, 3, 2], 'mixed_precision': True,
                    'memory_metric': 'mlx-active-allocator-bytes',
                    'checkpoint_format': 'mlx-safetensors', 'concurrent_requests': False}

    def prepare(self, *, source, destination, recipe):
        source = ModelDescriptor.model_validate(source)
        recipe = MLXRecipe.model_validate(recipe)
        destination = Path(destination)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError('Model export requires a new destination')
        capabilities = self.capabilities()
        from huggingface_hub import snapshot_download
        from mlx_lm import convert
        started = time.perf_counter()
        # convert loads its own model. It never mutates the source snapshot or a
        # loaded baseline. Interrupted output stays unsealed and cannot load.
        snapshot = snapshot_download(repo_id=source.model_id, revision=source.revision,
            allow_patterns=['*.json', '*.safetensors', '*.txt', '*.jinja', '*.model'])
        # MLX-LM save reopens repo IDs without their revision. A resolved local
        # snapshot keeps both the weights and copied tokenizer/config files pinned.
        options = {}
        if recipe.protected_bits is not None:
            config = json.loads((Path(snapshot) / 'config.json').read_text())
            layer_count = config.get('text_config', config).get('num_hidden_layers')
            options['quant_predicate'] = mixed_quantization_predicate(recipe, layer_count)
        convert(snapshot, mlx_path=str(destination),
                quantize=recipe.bits != 16, q_bits=recipe.bits if recipe.bits != 16 else None,
                q_group_size=recipe.group_size, q_mode='affine', dtype='bfloat16',
                trust_remote_code=False, **options)
        record = seal_artifact(destination, backend=self.name, source=source.model_dump(),
                               recipe=recipe.model_dump(), versions=capabilities['versions'])
        return {'artifact': record, 'preparation_seconds': time.perf_counter() - started}

    def load(self, folder, *, expected_id=None):
        manifest = verify_artifact(folder, expected_id=expected_id, backend=self.name)
        mx = _runtime()
        from mlx_lm import load
        model, tokenizer = load(str(Path(folder).resolve()),
                                tokenizer_config={'trust_remote_code': False})
        mx.synchronize()
        return MLXModel(model, tokenizer, manifest)


class MLXModel:
    def __init__(self, model, tokenizer, manifest):
        self.model = model
        self.tokenizer = tokenizer
        self.manifest = manifest

    def generate(self, prompt, *, max_tokens, seed, response_format=None):
        if self.model is None:
            raise RuntimeError('The model is closed')
        if type(max_tokens) is not int or max_tokens < 1 or type(seed) is not int:
            raise ValueError('Supply a positive max_tokens and integer seed')
        if not isinstance(prompt, (str, list)) or not prompt:
            raise ValueError('Supply nonempty text or chat messages')
        if response_format is not None:
            response_format = validate_response_format(response_format)
        mx = _runtime()
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler
        mx.random.seed(seed)
        text = self.tokenizer.apply_chat_template(prompt, tokenize=False,
                   add_generation_prompt=True, enable_thinking=False) if isinstance(prompt, list) else prompt
        input_ids = self.tokenizer.encode(text, add_special_tokens=False)
        mx.synchronize()
        started = time.perf_counter()
        # Grammar construction is part of request time. A fresh processor owns
        # each sequence; no completed grammar state leaks into the next request.
        processors = ([_json_processor(self.model, self.tokenizer, response_format)]
                      if response_format is not None else None)
        pieces, tokens = [], []
        finish_reason = None
        for response in stream_generate(self.model, self.tokenizer, input_ids,
                                        max_tokens=max_tokens, sampler=make_sampler(temp=0.0),
                                        logits_processors=processors):
            pieces.append(response.text)
            tokens.append(response.token)
            finish_reason = response.finish_reason
        mx.synchronize()
        return {'text': ''.join(pieces), 'token_ids': tokens, 'prompt_token_ids': input_ids,
                    'latency_ms': (time.perf_counter() - started) * 1000, 'error': None,
                    'response_format': response_format, 'finish_reason': finish_reason}

    def measure(self, prompts, *, max_tokens, seed, warmup, repetitions,
                response_formats=None, response_format_version=None):
        if (not isinstance(prompts, list) or not prompts or type(warmup) is not int
                or warmup < 0 or type(repetitions) is not int or repetitions < 1):
            raise ValueError('Supply prompts, nonnegative warmup, and positive repetitions')
        formats = validate_formats(prompts, response_formats, response_format_version, allow_unconstrained=True)
        def generate(index, prompt):
            return self.generate(prompt, max_tokens=max_tokens, seed=seed,
                                 response_format=formats[index] if formats is not None else None)
        mx = _runtime()
        for _ in range(warmup):
            for index, prompt in enumerate(prompts):
                generate(index, prompt)
        mx.synchronize()
        mx.reset_peak_memory()
        resident = mx.get_active_memory()
        rows = []
        started = time.perf_counter()
        for repetition in range(repetitions):
            for index, prompt in enumerate(prompts):
                rows.append(dict(repetition=repetition, prompt_index=index,
                                 **generate(index, prompt)))
        mx.synchronize()
        return {'artifact_id': self.manifest['artifact_id'], 'requests': rows,
                    'request_wall_seconds': time.perf_counter() - started,
                    'runtime_versions': {name: version(name) for name in
                                         ('mlx', 'mlx-lm', 'transformers', 'outlines')},
                    'controls': {'seed': seed, 'max_tokens': max_tokens, 'warmup': warmup,
                                  'repetitions': repetitions, 'sampling': 'greedy', 'concurrency': 1,
                                  'response_formats': formats,
                                  'response_format_version': response_format_version},
                    'memory': {'metric': 'mlx-active-allocator-bytes',
                                'resident_bytes': resident, 'peak_bytes': max(resident, mx.get_peak_memory()),
                                'active_bytes': mx.get_active_memory(), 'cache_bytes': mx.get_cache_memory(),
                                'scope': 'MLX allocator; not system-wide unified memory or free VRAM'},
                    'device': mx.device_info()}

    def close(self):
        self.model = self.tokenizer = None
        gc.collect()
        mx = _runtime()
        mx.synchronize()
        mx.clear_cache()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
