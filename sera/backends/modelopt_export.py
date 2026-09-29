"""Pinned NVIDIA ModelOpt export path; never benchmark temporary fake quantization.

Source API: NVIDIA/Model-Optimizer tag 0.46.1, examples/hf_ptq/README.md.
The resulting packed checkpoints need a compatible CUDA inference loader.
This module does not claim GPU compatibility, quality, or memory improvement.
"""
import gc
import json
import platform
import time
from copy import deepcopy
from importlib.metadata import version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..hardware import ModelDescriptor
from ..model_artifact import seal_artifact


class Calibration(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra='forbid')
    prompts: list[str] = Field(min_length=1)
    seed: int
    max_length: int = Field(ge=1)

    @model_validator(mode='after')
    def nonempty(self):
        if any(not text.strip() for text in self.prompts):
            raise ValueError('Calibration prompts must contain text')
        return self


class ModelOptRecipe(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra='forbid')
    format: Literal['bf16', 'fp8', 'nvfp4'] = 'bf16'
    calibration: Calibration | None = None

    @property
    def bits(self):
        return {'bf16':16, 'fp8':8, 'nvfp4':4}[self.format]

    @model_validator(mode='after')
    def calibration_contract(self):
        if self.format != 'bf16' and self.calibration is None:
            raise ValueError('ModelOpt quantization requires explicit calibration inputs and controls')
        if self.format == 'bf16' and self.calibration is not None:
            raise ValueError('The BF16 reference does not use calibration')
        return self


def check_cuda_runtime(torch, recipe):
    if not torch.version.cuda or torch.version.hip or not torch.cuda.is_available():
        raise RuntimeError('ModelOpt export requires a working NVIDIA CUDA PyTorch build')
    if torch.cuda.device_count() != 1 or torch.cuda.current_device() != 0:
        raise RuntimeError('Expose exactly one assigned NVIDIA device to the export worker')
    capability = torch.cuda.get_device_capability(0)
    if capability < (8, 0):
        raise RuntimeError('The BF16 reference requires CUDA compute capability 8.0 or newer')
    if recipe.format == 'fp8' and capability < (8, 9):
        raise RuntimeError('This FP8 inference path requires CUDA compute capability 8.9 or newer')
    if recipe.format == 'nvfp4' and capability < (10, 0):
        raise RuntimeError('This NVFP4 W4A4 path requires a Blackwell-class GPU')


def _runtime(recipe):
    if platform.system() != 'Linux':
        raise RuntimeError('This ModelOpt adapter requires Linux and an NVIDIA GPU')
    import torch
    check_cuda_runtime(torch, recipe)
    if version('nvidia-modelopt') != '0.46.1':
        raise RuntimeError('This export contract requires nvidia-modelopt 0.46.1')
    return torch


def check_modelopt_export(folder, recipe):
    """Reject BF16/fake-quant files mislabeled as compressed ModelOpt exports."""
    from safetensors import safe_open
    folder = Path(folder)
    model_config = json.loads((folder / 'config.json').read_text())
    metadata_path = folder / 'hf_quant_config.json'
    if recipe.format == 'bf16':
        if metadata_path.exists() or model_config.get('quantization_config') is not None:
            raise ValueError('The BF16 reference cannot contain quantization metadata')
        return
    metadata = json.loads(metadata_path.read_text())
    quant = metadata.get('quantization', {})
    if not isinstance(quant, dict) or quant.get('quant_algo') != {'fp8':'FP8', 'nvfp4':'NVFP4'}[recipe.format]:
        raise ValueError('ModelOpt checkpoint format differs from its recipe')
    if 'kv_cache_quant_algo' not in quant or quant['kv_cache_quant_algo'] is not None:
        raise ValueError('This export path preserves unquantized KV cache')
    dtypes = {}
    for shard in sorted(folder.glob('*.safetensors')):
        with safe_open(str(shard), framework='numpy') as weights:
            for name in weights.keys():  # noqa: SIM118 - safetensors reader is not a mapping
                if name in dtypes:
                    raise ValueError('Duplicate tensors across checkpoint shards')
                dtypes[name] = weights.get_slice(name).get_dtype()
    required = {'fp8': {'F8_E4M3', 'F8_E4M3FN'}, 'nvfp4': {'U8'}}[recipe.format]
    packed = [name for name, dtype in dtypes.items() if name.endswith('.weight') and dtype in required]
    if not packed:
        raise ValueError('ModelOpt export contains no real packed quantized weights')
    for name in packed:
        prefix = name[:-len('weight')]
        if prefix + 'weight_scale' not in dtypes:
            raise ValueError('Packed ModelOpt weights are missing scales')
        if recipe.format == 'nvfp4' and prefix + 'weight_scale_2' not in dtypes:
            raise ValueError('NVFP4 weights are missing their second scale')


def prepare_modelopt(*, source, destination, recipe):
    source = ModelDescriptor.model_validate(source)
    recipe = ModelOptRecipe.model_validate(recipe)
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Model export requires a new destination')
    torch = _runtime(recipe)
    from huggingface_hub import snapshot_download
    from transformers import AutoModelForCausalLM, AutoTokenizer
    started = time.perf_counter()
    snapshot = snapshot_download(repo_id=source.model_id, revision=source.revision,
        allow_patterns=['*.json', '*.safetensors', '*.txt', '*.jinja', '*.model'])
    check_modelopt_export(snapshot, ModelOptRecipe())
    model = tokenizer = None
    try:
        model = AutoModelForCausalLM.from_pretrained(snapshot, local_files_only=True,
            trust_remote_code=False, use_safetensors=True, dtype=torch.bfloat16,
            device_map={'':0}).eval()
        if any(p.device.type != 'cuda' or p.device.index != 0 or p.dtype != torch.bfloat16
               for p in model.parameters()):
            raise ValueError('The ModelOpt input must be a BF16 model entirely on the assigned GPU')
        tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
        if recipe.format == 'bf16':
            model.save_pretrained(str(destination))
        else:
            import modelopt.torch.quantization as mtq
            from modelopt.torch.export import export_hf_checkpoint
            calibration = recipe.calibration
            torch.manual_seed(calibration.seed)
            def forward_loop(calibration_model):
                with torch.inference_mode():
                    for prompt in calibration.prompts:
                        batch = tokenizer(prompt, return_tensors='pt', add_special_tokens=False,
                            truncation=True, max_length=calibration.max_length).to('cuda:0')
                        calibration_model(**batch, use_cache=False)
            config = deepcopy(mtq.FP8_DEFAULT_CFG if recipe.format == 'fp8' else mtq.NVFP4_DEFAULT_CFG)
            model = mtq.quantize(model, config, forward_loop)
            # Default unified export packs weights/scales. Never enable the
            # optional vLLM fake-quant export used for quantization research.
            with torch.inference_mode():
                export_hf_checkpoint(model, dtype=torch.bfloat16, export_dir=str(destination))
        tokenizer.save_pretrained(str(destination))
        torch.cuda.synchronize()
        check_modelopt_export(destination, recipe)
        versions = {name:version(name) for name in ('torch','transformers','nvidia-modelopt','safetensors')}
        manifest = seal_artifact(destination, backend='cuda', source=source.model_dump(),
                                 recipe=recipe.model_dump(), versions=versions)
        return {'artifact':manifest, 'preparation_seconds':time.perf_counter()-started}
    finally:
        model = tokenizer = None
        gc.collect()
        torch.cuda.empty_cache()
