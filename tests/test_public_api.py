"""Public setup uses fake boundaries: no provider calls, GPU, or Weave service."""

from types import SimpleNamespace
import sys

import pytest

import sera
from sera import pipeline
from sera.config import MODEL_ID


@pytest.fixture
def configured(monkeypatch, tmp_path):
    for key, value in {'SERA_AGENT_PROVIDER': 'codex-relay',
                       'SERA_AGENT_MODEL': 'gpt-5.6-luna', 'SERA_PROJECT': 'test/project',
                       'SERA_PROVIDER_CHECK': str(tmp_path/'certificate.json'),
                       'SERA_RELAY_DIR': str(tmp_path/'relay'),
                       'WANDB_API_KEY': 'fixture-not-a-real-key'}.items():
        monkeypatch.setenv(key, value)
    return tmp_path


def boundaries(monkeypatch):
    from sera import provider_check
    seen = {}
    monkeypatch.setattr(provider_check, 'require_provider_check',
                        lambda path, agent: seen.update(certificate=(path, agent.provider)) or {})
    def run(**options):
        seen['options'] = options
        assert seen['certificate']
        result = SimpleNamespace(report={'status': 'ready'}, models=[])
        result._save = lambda: seen.update(saved=True)
        result.close = lambda: seen.update(closed=True)
        return result
    monkeypatch.setattr(pipeline, 'optimize', run)
    client = SimpleNamespace(flush=lambda: seen.update(flushed=True))
    monkeypatch.setitem(sys.modules, 'weave', SimpleNamespace(
        init=lambda project: seen.update(project=project) or client,
        op=lambda fn=None, **kwargs: fn if fn else lambda actual: actual,
        get_current_call=lambda: SimpleNamespace(trace_id='fixture-trace', ui_url='fixture-url')))
    return seen


def test_minimum_call_prepares_full_uncapped_swarm(configured, monkeypatch):
    seen = boundaries(monkeypatch)
    result = sera.optimize(models=[MODEL_ID], prompts=['What is 1 + 1?'])
    options = seen['options']
    assert options['budget'].max_candidate_trials is None
    assert options['automatic_space'] is True and options['swarm'] is True
    assert options['workload'].concurrency == [1, 2, 4, 8]
    assert options['agent'].provider == 'codex-relay'
    assert callable(options['trace_reader'])
    assert seen['saved'] and seen['flushed'] and not seen.get('closed')
    assert result.report['weave_url'] == 'fixture-url'


def test_missing_route_fails_before_pipeline_or_weave(monkeypatch):
    monkeypatch.delenv('SERA_AGENT_PROVIDER', raising=False)
    monkeypatch.setattr(pipeline, 'optimize', lambda **kw: pytest.fail('No GPU work'))
    with pytest.raises(ValueError, match='SERA_AGENT_PROVIDER'):
        sera.optimize(models=[MODEL_ID], prompts=['question'])


def test_missing_key_or_invalid_certificate_fails_before_weave(configured, monkeypatch):
    from sera import provider_check
    seen = boundaries(monkeypatch)
    monkeypatch.delenv('WANDB_API_KEY')
    with pytest.raises(ValueError, match='WANDB_API_KEY'):
        sera.optimize(models=[MODEL_ID], prompts=['question'])
    assert 'project' not in seen and 'options' not in seen
    monkeypatch.setenv('WANDB_API_KEY', 'fixture')
    def reject(*args):
        raise ValueError('Certificate rejected')
    monkeypatch.setattr(provider_check, 'require_provider_check', reject)
    with pytest.raises(ValueError, match='Certificate rejected'):
        sera.optimize(models=[MODEL_ID], prompts=['question'])
    assert 'project' not in seen and 'options' not in seen


@pytest.mark.parametrize('options', [dict(candidate=sera.Candidate(name='fixed', reason='fixed',
    config=sera.RuntimeConfig(kv_cache_dtype='fp8'))), dict(swarm=False), dict(mode='fixed')])
def test_explicit_legacy_path_does_not_read_provider_environment(monkeypatch, options):
    monkeypatch.delenv('SERA_AGENT_PROVIDER', raising=False)
    seen = {}
    monkeypatch.setattr(pipeline, 'optimize', lambda **kw: seen.update(kw) or 'legacy-result')
    assert sera.optimize(models=[MODEL_ID], prompts=['question'], **options) == 'legacy-result'
    assert 'mode' not in seen


def test_explicit_workload_and_quality_rules_are_unchanged(configured, monkeypatch):
    seen = boundaries(monkeypatch)
    evaluator = lambda prompt, text: text == '2'
    constraints = sera.Constraints(quality_floor=1.0)
    sera.optimize(models=[MODEL_ID], prompts=['1+1'], workload=sera.Workload(concurrency=[2]),
                  evaluation=evaluator, evaluation_version='exact-v1', constraints=constraints)
    assert seen['options']['workload'].concurrency == [2]
    assert seen['options']['evaluation'] is evaluator
    assert seen['options']['constraints'] is constraints


def test_invalid_mode_is_rejected(monkeypatch):
    with pytest.raises(ValueError, match='mode'):
        sera.optimize(models=[MODEL_ID], prompts=['question'], mode='unknown')


@pytest.mark.parametrize('name', ['SERA_AGENT_MODEL', 'SERA_PROJECT', 'SERA_PROVIDER_CHECK', 'SERA_RELAY_DIR'])
def test_partial_configuration_does_not_fall_back(configured, monkeypatch, name):
    seen = boundaries(monkeypatch)
    monkeypatch.delenv(name)
    with pytest.raises(ValueError, match=name):
        sera.optimize(models=[MODEL_ID], prompts=['question'])
    assert 'options' not in seen and 'project' not in seen


@pytest.mark.parametrize('options', [dict(mode='fixed', agent=object()),
    dict(mode='swarm', swarm=False), dict(mode='swarm', budget=None),
    dict(mode='swarm', trace_reader=object()),
    dict(mode='swarm', automatic_space=True,
         investigation_space=sera.InvestigationSpace(supported_changes={'max_num_seqs': [4]})),
    dict(mode='swarm', candidate=sera.Candidate(name='fixed', reason='fixed',
         config=sera.RuntimeConfig(kv_cache_dtype='fp8')))])
def test_conflicting_modes_fail_before_setup(configured, monkeypatch, options):
    seen = boundaries(monkeypatch)
    with pytest.raises(ValueError):
        sera.optimize(models=[MODEL_ID], prompts=['question'], **options)
    assert 'options' not in seen and 'project' not in seen


def test_hosted_provider_is_only_selected_explicitly(configured, monkeypatch):
    seen = boundaries(monkeypatch)
    monkeypatch.setenv('SERA_AGENT_PROVIDER', 'wandb')
    monkeypatch.setenv('SERA_AGENT_MODEL', 'explicit-hosted-model')
    with pytest.raises(ValueError, match='SERA_RELAY_DIR'):
        sera.optimize(models=[MODEL_ID], prompts=['question'])
    monkeypatch.delenv('SERA_RELAY_DIR')
    sera.optimize(models=[MODEL_ID], prompts=['question'])
    assert seen['options']['agent'].provider == 'wandb'
    assert seen['options']['agent'].model == 'explicit-hosted-model'


def test_large_model_keeps_required_task_gate_before_setup(configured, monkeypatch):
    from sera.config import LARGE_MODEL_ID
    seen = boundaries(monkeypatch)
    with pytest.raises(ValueError, match='task evaluator'):
        sera.optimize(models=[LARGE_MODEL_ID], prompts=['question'])
    assert 'options' not in seen and 'project' not in seen


def test_swarm_mode_honors_explicit_budget_and_frozen_space(configured, monkeypatch):
    seen = boundaries(monkeypatch)
    space = sera.InvestigationSpace(supported_changes={'max_num_batched_tokens': [2048]})
    sera.optimize(models=[MODEL_ID], prompts=['question'], mode='swarm',
                  budget=sera.Budget(max_candidate_trials=2), investigation_space=space)
    assert seen['options']['budget'].max_candidate_trials == 2
    assert seen['options']['automatic_space'] is False
    assert seen['options']['investigation_space'] is space


def test_setup_failure_after_return_closes_owned_runner(configured, monkeypatch):
    seen = boundaries(monkeypatch)
    original = pipeline.optimize
    def run(**kwargs):
        result = original(**kwargs)
        result._save = lambda: (_ for _ in ()).throw(RuntimeError('fixture save failure'))
        return result
    monkeypatch.setattr(pipeline, 'optimize', run)
    with pytest.raises(RuntimeError, match='fixture save failure'):
        sera.optimize(models=[MODEL_ID], prompts=['question'])
    assert seen['closed'] and seen['flushed']


def test_flush_error_recording_failure_closes_inaccessible_runner(configured, monkeypatch):
    seen = boundaries(monkeypatch)
    weave = sys.modules['weave']
    def fail_flush():
        raise RuntimeError('fixture flush failure')
    weave.init = lambda project: SimpleNamespace(flush=fail_flush)
    original = pipeline.optimize
    def run(**kwargs):
        result = original(**kwargs)
        def save():
            if 'trace_flush_error' in result.report:
                raise OSError('fixture flush record failure')
        result._save = save
        return result
    monkeypatch.setattr(pipeline, 'optimize', run)
    with pytest.raises(OSError, match='fixture flush record failure'):
        sera.optimize(models=[MODEL_ID], prompts=['question'])
    assert seen['closed']
