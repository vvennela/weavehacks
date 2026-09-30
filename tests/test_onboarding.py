import json
import sys

import pytest

from sera import onboarding


def test_registration_writes_private_reusable_customer_connection(tmp_path):
    profile = onboarding.model_profile(backend='mlx', model_id='Qwen/Qwen3-0.6B',
        revision='a'*40, profile_id='qwen', seconds=300, trials=2, quality_floor=.99, max_tokens=128)
    info = onboarding.register_local(tmp_path, profiles=[profile], project='team/project',
                                     wandb_key='operator-secret', runtime_python=sys.executable)
    config = json.loads((tmp_path/'service.json').read_text())
    assert 'operator-secret' not in json.dumps(config)
    assert 'operator-secret' not in json.dumps(info)
    assert config['profiles'][0]['requires_examples'] is True
    assert config['profiles'][0]['tasks'] == []
    assert (tmp_path/'credentials.json').stat().st_mode & 0o777 == 0o600
    assert (tmp_path/'client.json').stat().st_mode & 0o777 == 0o600
    again = onboarding.register_local(tmp_path, profiles=[profile], project='team/project',
                                      wandb_key='operator-secret', runtime_python=sys.executable)
    assert again['api_key'] == info['api_key']


def test_registration_rejects_missing_quality_and_invalid_budgets(tmp_path):
    with pytest.raises(ValueError):
        onboarding.model_profile(backend='mlx', model_id='Qwen/Qwen3-0.6B', revision='a'*40,
            profile_id='qwen', seconds=-1, trials=2, quality_floor=.99, max_tokens=128)
    with pytest.raises(ValueError):
        onboarding.register_local(tmp_path, profiles=[], project='team/project',
                                  wandb_key='secret', runtime_python=sys.executable)


def test_saved_connection_starts_service_without_repeating_setup(tmp_path, monkeypatch):
    monkeypatch.setenv('SERA_HOME', str(tmp_path))
    profile = onboarding.model_profile(backend='mlx', model_id='Qwen/Qwen3-0.6B', revision='a'*40,
        profile_id='qwen', seconds=300, trials=2, quality_floor=.99, max_tokens=128)
    expected = onboarding.register_local(tmp_path, profiles=[profile], project='team/project',
                                         wandb_key='operator-secret', runtime_python=sys.executable)
    started = []
    monkeypatch.setattr(onboarding, 'start_local', lambda home: started.append(home))
    monkeypatch.setattr(onboarding, 'setup', lambda **kw: pytest.fail('repeated setup'))
    assert onboarding.local_connection() == expected
    assert started == [tmp_path]


def test_noninteractive_first_use_returns_one_actionable_command(tmp_path, monkeypatch):
    monkeypatch.setenv('SERA_HOME', str(tmp_path))
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)
    with pytest.raises(RuntimeError, match='sera setup'):
        onboarding.local_connection()


def test_login_uses_chatgpt_and_rejects_api_key_login(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(onboarding.shutil, 'which', lambda name: '/bin/codex')
    def run(args, **kwargs):
        calls.append(args)
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout='Logged in using an API key', stderr='')
    monkeypatch.setattr(onboarding.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='ChatGPT'):
        onboarding.ensure_codex(tmp_path)
    assert any('forced_login_method="chatgpt"' in arg for args in calls for arg in args)
    assert not any('--with-api-key' in args for args in calls)


def test_private_writer_rejects_symlink(tmp_path):
    target = tmp_path/'outside'
    target.write_text('unchanged')
    (tmp_path/'credentials.json').symlink_to(target)
    with pytest.raises(ValueError, match='symlink'):
        onboarding.private_json(tmp_path/'credentials.json', {'secret': 'value'})
    assert target.read_text() == 'unchanged'


def test_cuda_registration_uses_explicit_calibration_examples():
    result = onboarding.model_profile(backend='cuda', model_id='Qwen/Qwen3-0.6B', revision='a'*40,
        profile_id='qwen', seconds=300, trials=2, quality_floor=.99, max_tokens=128,
        tasks=[{'prompt': 'Classify this ticket', 'expected_json': 'support'}],
        gpu_uuid='GPU-12345678-1234-1234-1234-123456789abc')
    assert result['recipes']['fp8']['format'] == 'fp8'
    assert result['recipes']['fp8']['calibration']['prompts'] == ['Classify this ticket']


def test_guided_setup_connects_install_login_registration_and_start(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(onboarding, 'detect_backend', lambda: ('mlx', None))
    monkeypatch.setattr(onboarding, 'install_runtime', lambda home, backend: calls.append(('install', backend)) or sys.executable)
    monkeypatch.setattr(onboarding, 'ensure_codex', lambda home: calls.append(('login', home)))
    monkeypatch.setattr(onboarding, 'start_local', lambda home: calls.append(('start', home)))
    operator = tmp_path/'operator.json'
    operator.write_text(json.dumps({'WANDB_API_KEY': 'operator-secret', 'SERA_PROJECT': 'team/project'}))
    examples = tmp_path/'examples.json'
    examples.write_text(json.dumps([{'prompt': 'Return the category as JSON', 'expected_json': {'category': 'support'}}]))
    docs = tmp_path/'documents'
    docs.mkdir()
    (docs/'manual.txt').write_text('Support is available daily.')
    answers = iter(['', '', '', 'tickets', str(examples), '300', '2', '.99', '128', 'n', str(docs), 'manuals', '', ''])
    monkeypatch.setattr('builtins.input', lambda _: next(answers))
    monkeypatch.delenv('WANDB_API_KEY', raising=False)
    monkeypatch.delenv('SERA_PROJECT', raising=False)
    value = onboarding.setup(home=tmp_path/'home', operator_config=operator)
    saved = json.loads((tmp_path/'home/service.json').read_text())
    assert saved['profiles'][0]['tasks'][0]['expected_json'] == {'category': 'support'}
    assert saved['profiles'][0]['budget']['max_candidate_trials'] == 2
    assert saved['collections']['manuals']['source'] == str(docs)
    assert [x[0] for x in calls] == ['install', 'login', 'start']
    assert 'operator-secret' not in json.dumps(value)


def test_runtime_install_reuses_callers_virtual_environment(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'prefix', '/venv')
    monkeypatch.setattr(sys, 'base_prefix', '/base')
    monkeypatch.setattr(onboarding, 'package_source', lambda extras: 'sera-inference[' + extras + ']')
    monkeypatch.setattr(onboarding.shutil, 'which', lambda name: '/bin/uv')
    calls = []
    monkeypatch.setattr(onboarding.subprocess, 'run', lambda args, **kwargs: calls.append(args))
    assert onboarding.install_runtime(tmp_path, 'mlx') == sys.executable
    assert calls[0] == ['uv', 'pip', 'install', '--python', sys.executable, 'sera-inference[mlx,swarm]']


def test_cuda_setup_requires_examples_before_collecting_budgets(tmp_path, monkeypatch):
    examples = tmp_path / 'checks.json'
    examples.write_text(json.dumps([{'prompt': 'Extract a field', 'expected_json': {'field': 'value'}}]))
    answers = iter(['', str(examples)])
    prompts = []
    def answer(prompt):
        prompts.append(prompt)
        return next(answers)
    monkeypatch.setattr('builtins.input', answer)
    tasks = onboarding._model_examples('cuda')
    assert tasks[0]['expected_json'] == {'field': 'value'}
    assert len(prompts) == 2
    assert all('required for CUDA' in prompt for prompt in prompts)


def test_mlx_setup_can_defer_examples_to_each_workload(monkeypatch):
    monkeypatch.setattr('builtins.input', lambda _: '')
    assert onboarding._model_examples('mlx') is None
