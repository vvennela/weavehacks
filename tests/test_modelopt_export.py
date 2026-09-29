"""ModelOpt export contracts. No CUDA execution or accuracy is certified here."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from sera.backends import modelopt_export as export

save_file = pytest.importorskip("safetensors.numpy").save_file


def recipe(format='fp8'):
    return export.ModelOptRecipe(format=format, calibration={
        'prompts':['Calibration input.'], 'seed':0, 'max_length':32})


def write_checkpoint(folder, *, algo='NVFP4', dtype=np.uint8):
    (folder/'config.json').write_text('{}')
    (folder/'hf_quant_config.json').write_text(json.dumps({'quantization':{
        'quant_algo':algo,'kv_cache_quant_algo':None,'group_size':16,'exclude_modules':[]}}))
    save_file({'model.layers.0.mlp.up_proj.weight':np.zeros((8,4),dtype=dtype),
               'model.layers.0.mlp.up_proj.weight_scale':np.ones((8,1),dtype=np.float32),
               'model.layers.0.mlp.up_proj.weight_scale_2':np.ones((1,),dtype=np.float32)},
              str(folder/'model.safetensors'))


def test_quantization_requires_explicit_calibration_controls():
    with pytest.raises(ValueError,match='calibration'):
        export.ModelOptRecipe(format='fp8')
    with pytest.raises(ValueError):
        export.ModelOptRecipe(format='nvfp4', calibration={'prompts':['x']})
    assert export.ModelOptRecipe().bits == 16
    assert recipe('nvfp4').bits == 4


def test_nvfp4_export_requires_packed_weights_and_scale_metadata(tmp_path):
    write_checkpoint(tmp_path)
    export.check_modelopt_export(tmp_path, recipe('nvfp4'))
    write_checkpoint(tmp_path, dtype=np.float32)
    with pytest.raises(ValueError,match='packed'):
        export.check_modelopt_export(tmp_path, recipe('nvfp4'))


def test_checkpoint_format_must_match_selected_recipe(tmp_path):
    write_checkpoint(tmp_path)
    with pytest.raises(ValueError,match='recipe'):
        export.check_modelopt_export(tmp_path, recipe('fp8'))
    with pytest.raises(ValueError,match='BF16'):
        export.check_modelopt_export(tmp_path, export.ModelOptRecipe())


def test_quantized_kv_cache_is_not_silently_added(tmp_path):
    write_checkpoint(tmp_path)
    metadata=json.loads((tmp_path/'hf_quant_config.json').read_text())
    metadata['quantization']['kv_cache_quant_algo']='FP8'
    (tmp_path/'hf_quant_config.json').write_text(json.dumps(metadata))
    with pytest.raises(ValueError,match='KV'):
        export.check_modelopt_export(tmp_path, recipe('nvfp4'))


def test_cuda_runtime_rejects_wrong_gpu_before_download():
    torch=SimpleNamespace(version=SimpleNamespace(cuda='12.8',hip=None),
        cuda=SimpleNamespace(is_available=lambda:True,device_count=lambda:1,
            current_device=lambda:0,get_device_capability=lambda i:(8,0)))
    with pytest.raises(RuntimeError,match='8.9'):
        export.check_cuda_runtime(torch,recipe('fp8'))
    with pytest.raises(RuntimeError,match='Blackwell'):
        export.check_cuda_runtime(torch,recipe('nvfp4'))
    torch.version.hip='7.0'
    with pytest.raises(RuntimeError,match='NVIDIA'):
        export.check_cuda_runtime(torch,export.ModelOptRecipe())


def test_fp8_safetensors_storage_is_recognized_without_loading_to_gpu(tmp_path):
    import struct
    write_checkpoint(tmp_path, algo='FP8')
    metadata = {'model.layers.0.mlp.up_proj.weight':
                {'dtype':'F8_E4M3','shape':[8,8],'data_offsets':[0,64]},
                'model.layers.0.mlp.up_proj.weight_scale':
                {'dtype':'F32','shape':[1],'data_offsets':[64,68]}}
    header = json.dumps(metadata).encode()
    header += b' ' * (-len(header) % 8)
    (tmp_path/'model.safetensors').write_bytes(struct.pack('<Q',len(header)) + header + bytes(64) + struct.pack('<f',1))
    export.check_modelopt_export(tmp_path, recipe('fp8'))


def test_modelopt_export_pins_source_calibrates_and_seals_packed_files(tmp_path, monkeypatch):
    import sys
    from contextlib import nullcontext
    from pathlib import Path
    from types import ModuleType
    source = {'model_id':'Qwen/Qwen3-0.6B','revision':'a'*40}
    snapshot = tmp_path/'snapshot'
    snapshot.mkdir()
    (snapshot/'config.json').write_text('{}')
    calls = []
    torch = SimpleNamespace(bfloat16='bf16', manual_seed=lambda seed:calls.append(('seed',seed)),
        inference_mode=nullcontext, cuda=SimpleNamespace(synchronize=lambda:None,empty_cache=lambda:None))
    class Batch(dict):
        def to(self, device):
            assert device == 'cuda:0'
            return self
    class Tokenizer:
        def __call__(self, prompt, **kwargs):
            calls.append(('calibrate',prompt,kwargs))
            return Batch(input_ids='fixture')
        def save_pretrained(self, folder):
            (Path(folder)/'tokenizer.json').write_text('{}')
    class Model:
        def eval(self):
            return self
        def parameters(self):
            return iter([SimpleNamespace(device=SimpleNamespace(type='cuda',index=0),dtype='bf16')])
        def __call__(self, **kwargs):
            assert kwargs == {'input_ids':'fixture','use_cache':False}
    def download(**kwargs):
        assert kwargs['repo_id']==source['model_id'] and kwargs['revision']==source['revision']
        return str(snapshot)
    def load(path,**kwargs):
        assert path==str(snapshot) and kwargs['local_files_only']
        assert kwargs['trust_remote_code'] is False and kwargs['use_safetensors'] is True
        assert kwargs['device_map']=={'':0}
        return Model()
    def quantize(model,config,forward_loop):
        assert config == {'name':'nvfp4-fixture'}
        forward_loop(model)
        return model
    def save(model, dtype=None, export_dir=None, **kwargs):
        # Match ModelOpt 0.46.1: the second positional argument is dtype,
        # not the destination. Preserve BF16 for all unquantized parameters.
        assert dtype == torch.bfloat16
        assert export_dir == str(tmp_path/'export')
        Path(export_dir).mkdir()
        write_checkpoint(Path(export_dir))
    modules={name:ModuleType(name) for name in ('modelopt','modelopt.torch','modelopt.torch.quantization','modelopt.torch.export')}
    modules['modelopt'].torch=modules['modelopt.torch']
    modules['modelopt.torch'].quantization=modules['modelopt.torch.quantization']
    modules['modelopt.torch.quantization'].NVFP4_DEFAULT_CFG={'name':'nvfp4-fixture'}
    modules['modelopt.torch.quantization'].quantize=quantize
    modules['modelopt.torch.export'].export_hf_checkpoint=save
    for name,module in modules.items():
        monkeypatch.setitem(sys.modules,name,module)
    monkeypatch.setitem(sys.modules,'huggingface_hub',SimpleNamespace(snapshot_download=download))
    monkeypatch.setitem(sys.modules,'transformers',SimpleNamespace(
        AutoModelForCausalLM=SimpleNamespace(from_pretrained=load),
        AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a,**k:Tokenizer())))
    monkeypatch.setattr(export,'_runtime',lambda recipe:torch)
    monkeypatch.setattr(export,'version',lambda name:'fixture')
    result=export.prepare_modelopt(source=source,destination=tmp_path/'export',recipe=recipe('nvfp4'))
    assert result['artifact']['backend']=='cuda'
    assert result['artifact']['source']==source
    assert calls[0]==('seed',0)
    assert calls[1][1]=='Calibration input.'
    assert calls[1][2]['max_length']==32
    assert calls[1][2]['add_special_tokens'] is False


def test_bf16_reference_preserves_source_weights_without_gpu_round_trip(tmp_path, monkeypatch):
    import struct
    import sys
    source = {'model_id': 'fixture/bf16', 'revision': 'a' * 40}
    snapshot = tmp_path / 'snapshot'
    snapshot.mkdir()
    (snapshot / 'config.json').write_text('{"dtype":"bfloat16"}')
    (snapshot / 'tokenizer.json').write_text('{}')
    (snapshot / 'remote_code.py').write_text('must not be copied')
    header = json.dumps({'weight': {'dtype': 'BF16', 'shape': [2], 'data_offsets': [0, 4]}}).encode()
    header += b' ' * (-len(header) % 8)
    weights = struct.pack('<Q', len(header)) + header + bytes(4)
    (snapshot / 'model.safetensors').write_bytes(weights)
    def unexpected_load(*args, **kwargs):
        pytest.fail('An already BF16 reference must not load on the GPU to be copied')
    monkeypatch.setattr(export, '_runtime', lambda recipe: SimpleNamespace(
        bfloat16='bf16', cuda=SimpleNamespace(empty_cache=lambda: None)))
    monkeypatch.setattr(export, 'version', lambda name: 'fixture')
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(snapshot_download=lambda **kwargs: str(snapshot)))
    monkeypatch.setitem(sys.modules, 'transformers', SimpleNamespace(
        AutoModelForCausalLM=SimpleNamespace(from_pretrained=unexpected_load),
        AutoTokenizer=SimpleNamespace(from_pretrained=unexpected_load)))
    destination = tmp_path / 'export'
    result = export.prepare_modelopt(source=source, destination=destination, recipe=export.ModelOptRecipe())
    assert (destination / 'model.safetensors').read_bytes() == weights
    assert (destination / 'model.safetensors').stat().st_ino != (snapshot / 'model.safetensors').stat().st_ino
    assert not (destination / 'remote_code.py').exists()
    assert result['artifact']['source'] == source
    from sera.model_artifact import verify_artifact
    verify_artifact(destination, expected_id=result['artifact']['artifact_id'], backend='cuda')


@pytest.mark.parametrize('dtype', [np.float16, np.float32, np.uint8])
def test_reference_copy_does_not_mislabel_other_weight_types_as_bf16(tmp_path, dtype):
    snapshot = tmp_path / 'snapshot'
    snapshot.mkdir()
    save_file({'weight': np.zeros((2,), dtype=dtype)}, str(snapshot / 'model.safetensors'))
    destination = tmp_path / 'export'
    assert export._copy_bf16_reference(snapshot, destination) is False
    assert not destination.exists()
