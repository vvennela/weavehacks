"""ROCm adapter contracts; these tests do not certify execution on AMD hardware."""
import json
from types import SimpleNamespace

import pytest

from sera.backends import rocm
from sera.hardware import ModelDescriptor
from sera.model_artifact import seal_artifact


def torch_fixture(*, hip='7.0', available=True, devices=1):
    return SimpleNamespace(version=SimpleNamespace(hip=hip, cuda=None),
        bfloat16='bf16', uint8='uint8',
        cuda=SimpleNamespace(is_available=lambda: available, device_count=lambda: devices,
            is_bf16_supported=lambda: True, current_device=lambda: 0,
            get_device_properties=lambda i: SimpleNamespace(name='AMD fixture', total_memory=1000,
                gcnArchName='gfx942', uuid='GPU-fixture'), synchronize=lambda: None))


@pytest.mark.parametrize('options', [{'hip': None}, {'available': False}, {'devices': 2}])
def test_rocm_preflight_rejects_cpu_cuda_or_ambiguous_devices(options):
    with pytest.raises(RuntimeError):
        rocm._check_runtime(torch_fixture(**options))


def test_rocm_recipe_rejects_unsupported_or_mislabeled_quantization():
    with pytest.raises(ValueError):
        rocm.ROCmRecipe(bits=8)
    with pytest.raises(ValueError):
        rocm.ROCmRecipe(bits=4, quant_type='fp4')


def test_nf4_requires_real_packed_gpu_weights():
    class Linear4bit:
        pass
    layer = Linear4bit()
    weight = SimpleNamespace(device=SimpleNamespace(type='cuda', index=0), dtype='uint8',
        bnb_quantized=True, quant_state=SimpleNamespace(shape=(16,16), quant_type='nf4'),
        numel=lambda:128)
    layer.weight = weight
    model = SimpleNamespace(parameters=lambda: iter([weight]), modules=lambda:iter([layer]))
    rocm._check_weights(model, rocm.ROCmRecipe(bits=4), torch_fixture(), Linear4bit)
    weight.dtype = 'bf16'
    with pytest.raises(ValueError, match='packed'):
        rocm._check_weights(model, rocm.ROCmRecipe(bits=4), torch_fixture(), Linear4bit)
    weight.dtype = 'uint8'
    weight.device.type = 'cpu'
    with pytest.raises(ValueError, match='device'):
        rocm._check_weights(model, rocm.ROCmRecipe(bits=4), torch_fixture(), Linear4bit)


def test_baseline_cannot_silently_use_quantized_or_float32_parameters():
    parameter = SimpleNamespace(device=SimpleNamespace(type='cuda', index=0), dtype='fp32')
    model = SimpleNamespace(parameters=lambda:iter([parameter]), modules=lambda:iter([]))
    with pytest.raises(ValueError, match='BF16'):
        rocm._check_weights(model, rocm.ROCmRecipe(), torch_fixture(), type('Linear4bit',(),{}))


def test_reload_rejects_artifact_backend_before_initializing_gpu(tmp_path, monkeypatch):
    (tmp_path/'config.json').write_text('{}')
    (tmp_path/'model.safetensors').write_bytes(b'fixture')
    seal_artifact(tmp_path, backend='mlx', source={'model_id':'Qwen/Qwen3-0.6B','revision':'a'*40},
                  recipe={'bits':4}, versions={})
    monkeypatch.setattr(rocm, '_runtime', lambda:pytest.fail('Runtime initialized for wrong backend'))
    with pytest.raises(ValueError, match='backend'):
        rocm.ROCmBackend().load(tmp_path)


def test_reload_metadata_must_match_the_sealed_recipe(tmp_path):
    config = {'quantization_config': {'quant_method':'bitsandbytes','load_in_4bit':True,
                                     'bnb_4bit_quant_type':'nf4','bnb_4bit_use_double_quant':True,
                                     'bnb_4bit_compute_dtype':'bfloat16', 'bnb_4bit_quant_storage':'uint8'}}
    (tmp_path/'config.json').write_text(json.dumps(config))
    rocm._check_config(tmp_path, rocm.ROCmRecipe(bits=4))
    with pytest.raises(ValueError, match='baseline'):
        rocm._check_config(tmp_path, rocm.ROCmRecipe(bits=16))
    config['quantization_config']['bnb_4bit_use_double_quant'] = False
    (tmp_path/'config.json').write_text(json.dumps(config))
    with pytest.raises(ValueError, match='recipe'):
        rocm._check_config(tmp_path, rocm.ROCmRecipe(bits=4))


def test_prepare_checks_hardware_before_download_or_export(tmp_path, monkeypatch):
    def unavailable():
        raise RuntimeError('No AMD GPU')
    monkeypatch.setattr(rocm, '_runtime', unavailable)
    with pytest.raises(RuntimeError, match='No AMD'):
        rocm.ROCmBackend().prepare(source=ModelDescriptor(model_id='Qwen/Qwen3-0.6B', revision='a'*40),
                                   destination=tmp_path/'output', recipe={'bits':4})
    assert not (tmp_path/'output').exists()


def test_generation_uses_greedy_decode_and_returns_only_generated_tokens(monkeypatch):
    import sys
    from contextlib import nullcontext

    import numpy as np

    from sera.backends.rocm import ROCmModel
    torch = torch_fixture()
    torch.manual_seed = lambda seed: None
    torch.inference_mode = nullcontext
    class Inputs(dict):
        def to(self, device):
            assert device == 'cuda:0'
            return self
    class Tokenizer:
        pad_token_id, eos_token_id = 0, 99
        def __call__(self, text, **kwargs):
            return Inputs(input_ids=np.array([[11,12]]))
        def decode(self, tokens, **kwargs):
            assert tokens == [42,99]
            return '{"answer":1}'
    class Model:
        generation_config = SimpleNamespace(eos_token_id=[98,99])
        def generate(self, **kwargs):
            generation = kwargs['generation_config']
            assert generation.do_sample is False and generation.num_beams == 1
            assert generation.pad_token_id == 0
            assert generation.max_new_tokens == 8
            return np.array([[11,12,42,99]])
    monkeypatch.setitem(sys.modules, 'transformers', SimpleNamespace(GenerationConfig=SimpleNamespace))
    model = ROCmModel(Model(), Tokenizer(), {'artifact_id':'a'*64}, torch)
    result = model.generate('question', seed=0, max_tokens=8)
    assert result['prompt_token_ids'] == [11,12]
    assert result['token_ids'] == [42,99]
    assert result['finish_reason'] == 'stop'


def test_loading_saved_nf4_never_requests_requantization(monkeypatch):
    import sys
    class Linear4bit:
        def __init__(self):
            self.weight = SimpleNamespace(device=SimpleNamespace(type='cuda',index=0),
                dtype='uint8', bnb_quantized=True,
                quant_state=SimpleNamespace(shape=(16,16),quant_type='nf4'), numel=lambda:128)
    layer = Linear4bit()
    class Model:
        def eval(self):
            return self
        def parameters(self):
            return iter([layer.weight])
        def modules(self):
            return iter([layer])
    calls = []
    def load(path, **kwargs):
        calls.append(kwargs)
        assert kwargs['device_map'] == {'':0}
        assert kwargs['local_files_only'] and kwargs['use_safetensors']
        assert kwargs['trust_remote_code'] is False
        return Model()
    monkeypatch.setitem(sys.modules, 'bitsandbytes.nn', SimpleNamespace(Linear4bit=Linear4bit))
    monkeypatch.setitem(sys.modules, 'transformers', SimpleNamespace(
        AutoModelForCausalLM=SimpleNamespace(from_pretrained=load),
        AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a,**kw:object()),
        BitsAndBytesConfig=lambda **kwargs:kwargs))
    recipe = rocm.ROCmRecipe(bits=4)
    rocm._load_model('/sealed-checkpoint', recipe, torch_fixture())
    assert 'quantization_config' not in calls[-1]
    rocm._load_model('/pinned-bf16-snapshot', recipe, torch_fixture(), quantize=True)
    assert calls[-1]['quantization_config']['bnb_4bit_compute_dtype'] == 'bf16'
    layer.weight.dtype = 'bf16'
    with pytest.raises(ValueError, match='packed'):
        rocm._load_model('/invalid-export', recipe, torch_fixture())
