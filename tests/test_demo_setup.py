"""The short demo must prepare real, checked inputs without launching a GPU trial."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from sera.demo import demo_tasks, prepare_demo


def test_packaged_demo_uses_unchanged_eight_tasks_and_strict_answers():
    from benchmarks.grade import SYSTEM_PROMPT, grade_case, load_cases
    cases = load_cases(Path(__file__).resolve().parents[1] / 'benchmarks/easy_cases.json')
    prompts, evaluate = demo_tasks()
    assert len(prompts) == 8
    for prompt, case in zip(prompts, cases):
        assert prompt == [{'role': 'system', 'content': SYSTEM_PROMPT},
                          {'role': 'user', 'content': case['prompt']}]
        for output in [json.dumps({'answer': case['expected']}), '{}', 'null',
                       '{"answer":true}', '{"answer":5.0}', '{"answer":5,"answer":5}',
                       '{"answer":NaN}', '```json\n{"answer":5}\n```', '', None]:
            assert evaluate(prompt, output) == grade_case(case, output)['passed']


@pytest.fixture
def prepared(monkeypatch, tmp_path):
    from sera import demo
    monkeypatch.setenv('WANDB_API_KEY', 'weave-test-secret')
    monkeypatch.setenv('OPENAI_API_KEY', 'openai-test-secret')
    monkeypatch.delenv('SERA_PROVIDER_CHECK', raising=False)
    monkeypatch.setattr(demo, '_check_gpu', lambda: {'used_mib': 0})
    events = []
    monkeypatch.setattr(demo, 'require_provider_check', lambda path, agent: events.append('certificate'))
    monkeypatch.setattr(demo, 'check_provider', lambda **kw: events.append('provider') or {'passed': True})
    monkeypatch.setattr(demo, 'LiteLLMAgent', lambda **kw: SimpleNamespace(
        model=kw['model'], provider='litellm-openai', project=kw['project']))
    return demo, events, tmp_path


def test_setup_reuses_explicit_certificate_without_gpu_trials(prepared):
    _demo, events, folder = prepared
    args = prepare_demo(project='test/project', certificate=folder/'certificate.json')
    assert events == ['certificate']
    assert args['models'] == ['Qwen/Qwen2.5-72B-Instruct']
    assert args['baseline_configuration'].quantization == 'fp8_per_tensor'
    assert args['constraints'].quality_floor == .99
    assert args['workload'].concurrency == [1, 2, 4, 8]
    assert args['mode'] == 'swarm' and len(args['prompts']) == 8
    assert 'stages' not in args and 'objective' not in args
    assert 'output_dir' not in args  # Each optimize call gets its own unique folder.
    assert 'secret' not in repr(args)


def test_setup_checks_new_provider_and_stops_if_it_fails(prepared, monkeypatch):
    demo, events, folder = prepared
    monkeypatch.setattr(demo, 'check_provider', lambda **kw: events.append('provider') or {'passed': False})
    with pytest.raises(RuntimeError, match='Provider check failed'):
        prepare_demo(project='test/project', evidence_root=folder)
    assert events == ['provider']


def test_missing_key_stops_before_paid_calls(prepared, monkeypatch):
    _demo, events, folder = prepared
    monkeypatch.delenv('OPENAI_API_KEY')
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        prepare_demo(project='test/project', evidence_root=folder)
    assert not events


def test_busy_gpu_stops_before_provider_calls(prepared, monkeypatch):
    demo, events, folder = prepared
    monkeypatch.setattr(demo, '_check_gpu', lambda: {'used_mib': 100})
    with pytest.raises(RuntimeError, match='GPU is in use'):
        prepare_demo(project='test/project', evidence_root=folder)
    assert not events


def test_missing_gpu_has_clear_instruction(monkeypatch):
    from sera import runtime
    from sera.demo import _check_gpu
    monkeypatch.setattr(runtime, 'gpu_snapshot', lambda: (_ for _ in ()).throw(FileNotFoundError()))
    with pytest.raises(RuntimeError, match='Change runtime to GPU'):
        _check_gpu()


def test_wrong_vllm_version_fails_before_provider_checks(monkeypatch):
    from sera import demo, runtime
    monkeypatch.setattr(runtime, 'gpu_snapshot', lambda: {'used_mib': 0})
    monkeypatch.setattr(demo.sys, 'platform', 'linux')
    monkeypatch.setattr(demo.importlib.metadata, 'version', lambda name: 'unsupported')
    with pytest.raises(RuntimeError, match='vLLM 0.26.0'):
        demo._check_gpu()
