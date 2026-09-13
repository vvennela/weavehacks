"""Automatic policy is explicit, post-measurement, and never expands a frozen pool."""

from copy import deepcopy
import json

import pytest

import sera
from sera import pipeline, search_policy
from sera.config import LARGE_MODEL_ID, MODEL_ID, SUPPORTED_CHANGES


@pytest.mark.parametrize('value', [None, 0, 1, 'true', [], {}])
def test_flag_is_strict_boolean_before_output_or_runtime(tmp_path, value):
    with pytest.raises(ValueError, match='automatic_space'):
        sera.optimize(models=[MODEL_ID], prompts=['question'], output_dir=tmp_path/'run', automatic_space=value)
    assert not (tmp_path/'run').exists()


@pytest.mark.parametrize('option', ['missing-budget', 'explicit-space', 'fixed-candidate'])
def test_conflicting_modes_are_rejected_before_execution(tmp_path, monkeypatch, option):
    from test_investigation import install_fakes
    runners, calls, agent = install_fakes(monkeypatch)
    kwargs = dict(agent=agent, provider_check='fixture', budget=sera.Budget(max_candidate_trials=1))
    if option == 'missing-budget':
        kwargs.pop('budget')
    elif option == 'explicit-space':
        kwargs['investigation_space'] = sera.InvestigationSpace(supported_changes={'max_num_seqs': [4]})
    else:
        kwargs['candidate'] = sera.Candidate(name='fixed', reason='fixed', config=sera.RuntimeConfig(kv_cache_dtype='fp8'))
    with pytest.raises(ValueError, match='Automatic|automatic'):
        sera.optimize(models=[MODEL_ID], prompts=['question'], output_dir=tmp_path/'run',
                      automatic_space=True, **kwargs)
    assert not runners and not calls
    assert not (tmp_path/'run').exists()


def test_policy_uses_collected_baseline_and_resolves_before_first_agent_call(tmp_path, monkeypatch):
    from test_investigation import install_fakes, run
    runners, seen, agent = install_fakes(monkeypatch)
    actual_policy = search_policy.propose_search_space
    inspected = []

    def inspect(baseline, **kwargs):
        assert baseline['status'] == 'collected'
        assert baseline['input_token_ids'] == [[1]]
        assert not seen
        assert len(runners) == 1 and runners[0].ready
        inspected.append(True)
        return actual_policy(baseline, **kwargs)

    monkeypatch.setattr(search_policy, 'propose_search_space', inspect)
    with run(tmp_path, agent, automatic_space=True, budget=sera.Budget(max_candidate_trials=1)) as result:
        assert inspected == [True]
        assert result.report['automatic_space'] is True
        audit = result.report['candidate_policy']
        assert audit['status'] == 'generated' and audit['evidence'] and audit['rationale']
        scope = result.report['investigation_space']
        assert scope['space_hash']
        assert scope['candidate_hashes'] == audit['space']['candidate_hashes']
        assert scope['supported_changes']['kv_cache_dtype'] == ['fp8']
        evidence = next(e for role, e in seen if role == 'proposal')
        assert all(values == scope['supported_changes'][lever]
                   for lever, values in evidence['supported_changes'].items())
        assert result.report['search_trials'][0]['config_hash'] in scope['candidate_hashes']
    saved = json.loads((tmp_path/'run/result.json').read_text())
    assert saved['candidate_policy'] == audit
    assert all(not runner.ready for runner in runners)


def test_no_policy_candidate_returns_baseline_without_legacy_fallback(tmp_path, monkeypatch):
    from test_investigation import install_fakes, run
    runners, calls, agent = install_fakes(monkeypatch)
    collect = pipeline.collect_trial

    def without_tokens(*args, **kwargs):
        result = collect(*args, **kwargs)
        result.pop('input_token_ids')
        return result

    monkeypatch.setattr(pipeline, 'collect_trial', without_tokens)
    with run(tmp_path, agent, automatic_space=True) as result:
        assert result.report['candidate_policy']['space'] is None
        assert result.report['investigation_space']['supported_changes'] == {}
        assert result.report['search']['trials_used'] == 0
        assert result.report['search']['stop_reason'] == 'no-legal-untested-candidate'
        assert result.report['decision']['selected'] == 'baseline'
        assert len(runners) == 1 and not calls


def test_policy_exception_closes_owned_baseline_and_saves_failure(tmp_path, monkeypatch):
    from test_investigation import install_fakes, run
    runners, _, agent = install_fakes(monkeypatch)

    def broken(*args, **kwargs):
        raise ValueError('policy failure fixture')

    monkeypatch.setattr(search_policy, 'propose_search_space', broken)
    with pytest.raises(ValueError):
        run(tmp_path, agent, automatic_space=True)
    assert len(runners) == 1 and not runners[0].ready
    assert json.loads((tmp_path/'run/result.json').read_text())['status'] == 'failed'


def test_fit_handoff_generates_from_measured_fp8_without_reload(tmp_path, monkeypatch):
    from test_fit_investigation import boundaries, run
    runners, calls, agent = boundaries(monkeypatch)
    actual_policy = search_policy.propose_search_space
    captured = []

    def inspect(baseline, **kwargs):
        assert baseline['status'] == 'collected'
        assert baseline['runtime']['configuration']['quantization'] == 'fp8_per_tensor'
        assert len(runners) == 1 and runners[0].ready
        assert kwargs['model_id'] == LARGE_MODEL_ID
        captured.append(True)
        return actual_policy(baseline, **kwargs)

    monkeypatch.setattr(search_policy, 'propose_search_space', inspect)
    # The total budget has already been spent on the deployment; no search trial starts.
    with run(tmp_path, agent, budget=1, automatic_space=True) as result:
        assert captured == [True]
        assert result.report['automatic_space'] is True
        assert result.report['candidate_policy']['status'] == 'generated'
        assert result.report['search']['initial_trials_used'] == 1
        assert len(runners) == 1 and result.models[0] is runners[0]
        assert 'kv_cache_dtype' not in result.report['investigation_space']['supported_changes']


def test_omitted_flag_keeps_defaults_and_does_not_call_policy(tmp_path, monkeypatch):
    from test_investigation import install_fakes, run
    _, _, agent = install_fakes(monkeypatch)
    before = deepcopy(SUPPORTED_CHANGES)
    monkeypatch.setattr(search_policy, 'propose_search_space', lambda *a, **k: pytest.fail('not opted in'))
    with run(tmp_path, agent, budget=sera.Budget(max_candidate_trials=1)) as result:
        assert 'candidate_policy' not in result.report
        assert result.report['search_trials'][0]['runtime']['configuration']['kv_cache_dtype'] == 'fp8'
    assert SUPPORTED_CHANGES == before


def test_generated_space_still_uses_runtime_validator_before_agent_calls(tmp_path, monkeypatch):
    from test_investigation import install_fakes, run
    runners, calls, agent = install_fakes(monkeypatch)
    config = sera.RuntimeConfig()
    bad_policy = {'status': 'generated',
        'space': {'supported_changes': {'max_model_len': [4096]}, 'candidate_hashes': [config.config_hash]},
        'rationale': ['invalid no-op fixture'],
        'candidate_parents': {'baseline': {'configuration': config.model_dump()}},
        'candidates': [{'parent_trial_id': 'baseline', 'configuration': config.model_dump(),
                        'config_hash': config.config_hash, 'reason': 'Invalid no-op'}]}
    monkeypatch.setattr(search_policy, 'expand_search_space', lambda *a, **k: bad_policy)
    with pytest.raises(ValueError, match='exactly one'):
        run(tmp_path, agent, automatic_space=True)
    assert not calls
    assert len(runners) == 1 and not runners[0].ready
    assert json.loads((tmp_path/'run/result.json').read_text())['candidate_policy'] == bad_policy


def test_failed_baseline_does_not_invoke_policy(tmp_path, monkeypatch):
    from test_investigation import install_fakes, run
    runners, calls, agent = install_fakes(monkeypatch)
    collect = pipeline.collect_trial

    def failed(*args, **kwargs):
        return collect(*args, **kwargs) | {'status': 'failed'}

    monkeypatch.setattr(pipeline, 'collect_trial', failed)
    monkeypatch.setattr(search_policy, 'propose_search_space', lambda *a, **k: pytest.fail('baseline failed'))
    with run(tmp_path, agent, automatic_space=True) as result:
        assert not result.models and not calls
        assert result.report['candidate_policy']['status'] == 'not-generated'
        assert result.report['search']['stop_reason'] == 'baseline-measurement-failed'
    assert all(not runner.ready for runner in runners)


def test_fit_handoff_can_execute_only_a_generated_candidate_with_remaining_budget(tmp_path, monkeypatch):
    from test_fit_investigation import boundaries, run
    runners, calls, agent = boundaries(monkeypatch)
    request = agent.request

    def choose_generated(role, evidence, instruction):
        response = request(role, evidence, instruction)
        if role == 'proposal':
            lever, values = next(iter(evidence['supported_changes'].items()))
            return response.model_copy(update={'changed_lever': lever, 'proposed_value': values[0]})
        return response

    agent.request = choose_generated
    with run(tmp_path, agent, budget=2, automatic_space=True) as result:
        assert result.report['search']['trials_used'] == 2
        trial = result.report['search_trials'][0]
        assert trial['trial_id'] == 'trial-2'
        assert trial['config_hash'] in result.report['investigation_space']['candidate_hashes']
        assert trial['runtime']['configuration']['quantization'] == 'fp8_per_tensor'
        assert trial['runtime']['configuration']['kv_cache_dtype'] == 'auto'
        assert len(runners) == 3  # Deployment, generated candidate, restored reference.
