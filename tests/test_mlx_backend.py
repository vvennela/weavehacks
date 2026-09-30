"""Validate MLX requests before model loading or file mutation."""

from pathlib import Path

import pytest

from sera.backends.mlx import MLXBackend, MLXRecipe


@pytest.mark.parametrize('recipe', [{'bits': 1}, {'bits': True}, {'group_size': 7}, {'unknown': 1}])
def test_invalid_recipe_is_rejected(recipe):
    with pytest.raises(ValueError):
        MLXRecipe.model_validate(recipe)


def test_export_rejects_existing_destination_before_loading(tmp_path):
    with pytest.raises(FileExistsError):
        MLXBackend().prepare(source={'model_id': 'Qwen/Qwen3-0.6B', 'revision': 'a' * 40},
                             destination=tmp_path, recipe={'bits': 4})


def test_loading_requires_a_verified_artifact_before_importing_mlx(tmp_path, monkeypatch):
    import builtins
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name.startswith('mlx'):
            pytest.fail('Unsealed checkpoints must not reach MLX')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    with pytest.raises(FileNotFoundError):
        MLXBackend().load(tmp_path)


def test_no_runtime_or_model_dependencies_on_import():
    import subprocess
    import sys
    result = subprocess.run([sys.executable, '-c',
        ('import sys; from sera.backends.mlx import MLXBackend; '
        'assert "mlx.core" not in sys.modules; assert "mlx_lm" not in sys.modules')],
        capture_output=True, text=True, check=True)
    assert not result.stdout


def test_conversion_uses_the_pinned_local_snapshot_for_all_export_files(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    source = {'model_id': 'Qwen/Qwen3-0.6B', 'revision': 'a' * 40}
    snapshot = tmp_path / 'snapshot'
    snapshot.mkdir()
    seen = []
    def download(**kwargs):
        assert kwargs['repo_id'] == source['model_id']
        assert kwargs['revision'] == source['revision']
        return str(snapshot)
    def convert(path, **kwargs):
        assert path == str(snapshot), 'Saving from a repo ID can reopen the unpinned main snapshot'
        seen.append(kwargs)
        destination = Path(kwargs['mlx_path'])
        destination.mkdir()
        (destination / 'config.json').write_text('{}')
        (destination / 'model.safetensors').write_bytes(b'fixture')
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(snapshot_download=download))
    monkeypatch.setitem(sys.modules, 'mlx_lm', SimpleNamespace(convert=convert))
    monkeypatch.setattr(MLXBackend, 'capabilities', lambda self: {'versions': {'mlx': 'fixture'}})
    result = MLXBackend().prepare(source=source, destination=tmp_path / 'export', recipe={'bits': 4})
    assert seen[0]['trust_remote_code'] is False
    assert seen[0]['quantize'] is True
    assert result['artifact']['source'] == source


def test_structured_generation_records_exact_format_and_uses_fresh_processor(monkeypatch):
    import sys
    from types import SimpleNamespace

    from sera.backends import mlx
    processors = []
    def build(model, tokenizer, response_format):
        processor = object()
        processors.append(processor)
        return processor
    def stream(model, tokenizer, tokens, **kwargs):
        assert kwargs['logits_processors'] == [processors[-1]]
        yield SimpleNamespace(text='{"answer": 17}', token=9, finish_reason='stop')
    monkeypatch.setattr(mlx, '_json_processor', build)
    monkeypatch.setattr(mlx, '_runtime', lambda: SimpleNamespace(
        synchronize=lambda: None, random=SimpleNamespace(seed=lambda seed: None)))
    monkeypatch.setitem(sys.modules, 'mlx_lm', SimpleNamespace(stream_generate=stream))
    monkeypatch.setitem(sys.modules, 'mlx_lm.sample_utils', SimpleNamespace(make_sampler=lambda **kw: None))
    model = mlx.MLXModel(object(), SimpleNamespace(encode=lambda *a, **kw: [1, 2]), {})
    schema = {'type': 'json_schema', 'json_schema': {'name': 'integer_answer', 'schema': {
        'type': 'object', 'properties': {'answer': {'type': 'integer'}},
        'required': ['answer'], 'additionalProperties': False}}}
    for _ in range(2):
        result = model.generate('Question', max_tokens=64, seed=0, response_format=schema)
        assert result['text'] == '{"answer": 17}'
        assert result['response_format'] == schema
        assert result['token_ids'] == [9]
    assert processors[0] is not processors[1]


def test_structured_measurement_rejects_unversioned_formats_before_runtime(monkeypatch):
    from sera.backends import mlx
    monkeypatch.setattr(mlx, '_runtime', lambda: pytest.fail('Invalid contracts must fail before runtime'))
    model = mlx.MLXModel(object(), object(), {})
    with pytest.raises(ValueError, match='version'):
        model.measure(['Question'], max_tokens=64, seed=0, warmup=1, repetitions=3,
                      response_formats=[{}])


@pytest.mark.parametrize('bits', [2, 3])
def test_lower_precision_recipe_is_supported(bits):
    assert MLXRecipe(bits=bits).bits == bits


def test_mixed_recipe_preserves_sensitive_modules_and_serializes_identity():
    from sera.backends.mlx import mixed_quantization_predicate
    recipe = MLXRecipe(bits=2, group_size=128, protected_bits=4)
    choose = mixed_quantization_predicate(recipe, 32)
    assert choose('model.embed_tokens', object())['bits'] == 4
    assert choose('lm_head', object())['bits'] == 4
    assert choose('model.layers.0.mlp.down_proj', object())['bits'] == 4
    assert choose('model.layers.10.self_attn.q_proj', object())['bits'] == 2
    assert choose('model.layers.9.mlp.down_proj', object())['bits'] == 4
    assert choose('model.layers.10.mlp.down_proj', object())['bits'] == 2
    assert recipe.model_dump()['protected_bits'] == 4
    assert MLXRecipe(bits=4).model_dump() == {'bits': 4, 'group_size': 64}


def test_mixed_recipe_rejects_non_increasing_precision():
    with pytest.raises(ValueError):
        MLXRecipe(bits=4, protected_bits=3)


def test_expansion_only_low_precision_preserves_attention_and_output():
    from sera.backends.mlx import mixed_quantization_predicate
    recipe = MLXRecipe(bits=3, protected_bits=4, group_size=128,
                       protection_pattern='all-except-mlp-expansion')
    choose = mixed_quantization_predicate(recipe, 36)
    for name in ('gate_proj', 'up_proj'):
        assert choose('model.layers.10.mlp.' + name, None)['bits'] == 3
    for name in ('q_proj', 'k_proj', 'v_proj', 'o_proj', 'down_proj', 'embed_tokens', 'lm_head'):
        assert choose('model.layers.10.' + name, None)['bits'] == 4


def test_all_value_and_down_projections_are_protected():
    from sera.backends.mlx import mixed_quantization_predicate
    choose = mixed_quantization_predicate(MLXRecipe(bits=3, protected_bits=4,
        protection_pattern='all-v-down'), 36)
    for index in range(36):
        assert choose(f'model.layers.{index}.mlp.down_proj', None)['bits'] == 4
        assert choose(f'model.layers.{index}.self_attn.v_proj', None)['bits'] == 4
        assert choose(f'model.layers.{index}.self_attn.q_proj', None)['bits'] == 3


def test_protection_pattern_requires_higher_precision():
    with pytest.raises(ValueError):
        MLXRecipe(bits=3, protection_pattern='all-v-down')
