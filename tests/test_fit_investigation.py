"""Fit planning and search share one live owner and one total trial budget."""

from copy import deepcopy
import json

import pytest

import sera
from sera import fit, pipeline
from sera.agent import ArbiterDecision, FrontierDecision, Proposal
from sera.config import LARGE_MODEL_ID


def boundaries(monkeypatch, *, wrong=False, decline=False, invalid=False):
    runners, calls = [], []

    class Runner:
        def __init__(self, *, artifact_dir, configuration, model_id, revision):
            self.configuration = configuration
            self.record = dict(configuration=configuration.model_dump(), model_id=model_id,
                               revision=revision, sampled_peak_memory_mib=88000)
            self.ready = False
            runners.append(self)

        def start(self):
            assert not any(r.ready for r in runners)
            self.ready = True

        def close(self):
            self.ready = False
            self.record['cleanup_verified'] = True

        def _require_ready(self):
            assert self.ready

        def generate(self, prompt):
            self._require_ready()
            return 'correct'

    def collect(model, prompts, trial_id, **kwargs):
        output = dict(prompt_index=0, text='wrong' if wrong else 'correct',
                      token_ids=[1], prompt_token_ids=[1], error=None)
        return dict(trial_id=trial_id, status='collected', runtime=model.record,
                    config_hash=model.configuration.config_hash, input_token_ids=[[1]],
                    quality=[output], self_check=[], metrics={},
                    reduced=dict(p95_latency_ms=100.0, output_tokens_per_second=50.0,
                                 generation_errors=0))

    class Agent:
        model, project = 'fixture', 'test/project'

        def __init__(self):
            self.history = []

        def request(self, role, evidence, instruction):
            entry = dict(role=role, evidence=deepcopy(evidence), instruction=instruction)
            calls.append(entry)
            self.history.append(entry)
            if role == 'arbiter':
                ids = evidence.get('legal_plan_ids', evidence.get('legal_proposal_ids', []))
                if evidence.get('specialist_role') == 'quantization':
                    ids = ['invented'] if invalid else ([] if decline else ids)
                return ArbiterDecision(ranked_proposal_ids=ids[:1], reason='Fixture plan')
            return Proposal(action='trial', proposal_id='batch', agent_role='batching',
                parent_trial_id='baseline', model_id=LARGE_MODEL_ID,
                changed_lever='max_num_batched_tokens', proposed_value=2048,
                evidence_used=['p95_latency_ms'], predicted_metric_change='Lower latency',
                confidence=.5, expected_trial_cost=1,
                falsification_condition='Less than 5% gain', reason='Measured latency')

        def review(self, evidence):
            self.history.append(dict(role='frontier', evidence=deepcopy(evidence)))
            return FrontierDecision(selected_trial_id=evidence['eligible_trial_ids'][0],
                prediction_outcome='refuted' if wrong or evidence.get('proposal') else 'confirmed',
                reason='Observed gate')

    monkeypatch.setattr(fit, 'gpu_snapshot', lambda: dict(used_mib=0, total_mib=97887,
                                                       compute_capability='12.0'))
    monkeypatch.setattr(fit, 'SeraModel', Runner)
    monkeypatch.setattr(pipeline, 'SeraModel', Runner)
    monkeypatch.setattr(fit, 'collect_trial', collect)
    monkeypatch.setattr(pipeline, 'collect_trial', collect)
    monkeypatch.setattr('sera.provider_check.require_provider_check', lambda *_: {'fixture': True})
    return runners, calls, Agent()


def run(tmp_path, agent, budget=2, **kwargs):
    return sera.optimize(models=[LARGE_MODEL_ID], prompts=['question'],
        output_dir=tmp_path/'run', agent=agent, provider_check='fixture',
        budget=sera.Budget(max_candidate_trials=budget),
        evaluation=lambda prompt, output: output == 'correct', evaluation_version='fixture',
        constraints=sera.Constraints(quality_floor=.99), **kwargs)


def test_fit_advisor_and_arbiter_feed_measured_search_with_one_total_budget(tmp_path, monkeypatch):
    runners, calls, agent = boundaries(monkeypatch)
    with run(tmp_path, agent) as result:
        deployment = result.report['deployment']
        assert deployment['infeasible_baseline']['status'] == 'infeasible'
        assert deployment['candidate_trial']['trial_id'] == 'candidate'
        assert deployment['planning_specialist']['status'] == 'accepted'
        assert calls[0]['evidence']['specialist_role'] == 'quantization'
        assert calls[1]['evidence']['specialist_recommendation'] == {
            'ranked_proposal_ids': ['weight-fp8'], 'reason': 'Fixture plan'}
        assert result.report['baseline']['trial_id'] == 'baseline'
        assert result.report['baseline']['runtime']['configuration']['quantization'] == 'fp8_per_tensor'
        assert result.report['search']['trials_used'] == 2
        assert result.report['search']['initial_trials_used'] == 1
        assert len(result.report['search_trials']) == 1
        assert result.report['search_trials'][0]['trial_id'] == 'trial-2'
        assert result.report['decision']['selected'] == 'baseline'
        assert result.models[0].generate('new') == 'correct'
        assert len(runners) == 3  # deployment, candidate, restored reference; no handoff reload
        assert all(call['evidence'].get('remaining_trials', 1) <= 2 for call in calls)
    assert all(not runner.ready for runner in runners)


def test_deployment_uses_last_trial_and_returns_same_runner_without_search(tmp_path, monkeypatch):
    runners, calls, agent = boundaries(monkeypatch)
    with run(tmp_path, agent, budget=1) as result:
        assert len(runners) == 1
        assert result.models[0] is runners[0]
        assert result.report['search']['stop_reason'] == 'budget-exhausted'
        assert result.report['search']['rounds'] == []
        assert not any(call['role'] == 'proposal' for call in calls)


@pytest.mark.parametrize('failure', ['wrong', 'decline', 'invalid'])
def test_failed_fit_never_enters_search(tmp_path, monkeypatch, failure):
    runners, calls, agent = boundaries(monkeypatch, **{failure: True})
    with run(tmp_path, agent) as result:
        assert not result.models
        assert 'search' not in result.report
        assert result.report['decision']['selected'] is None
        assert not any(call['role'] == 'proposal' for call in calls)
    assert all(not runner.ready for runner in runners)


def test_invalid_search_space_is_rejected_before_fit_probe_or_artifacts(tmp_path, monkeypatch):
    _, _, agent = boundaries(monkeypatch)
    monkeypatch.setattr(fit, 'gpu_snapshot', lambda: pytest.fail('GPU probe must not run'))
    with pytest.raises(ValueError, match='Combined'):
        run(tmp_path, agent, investigation_space=sera.InvestigationSpace(
            supported_changes={'kv_cache_dtype': ['fp8']}))
    assert not (tmp_path/'run').exists()


def test_malformed_fit_arbiter_response_cannot_start_a_runtime(tmp_path, monkeypatch):
    runners, calls, agent = boundaries(monkeypatch)
    request = agent.request

    def malformed_arbiter(role, evidence, instruction):
        response = request(role, evidence, instruction)
        if role == 'arbiter' and 'legal_plan_ids' in evidence and 'specialist_role' not in evidence:
            return response.model_copy(update={'reason': ''})
        return response

    agent.request = malformed_arbiter
    with run(tmp_path, agent) as result:
        assert result.models == []
        assert runners == []
        assert result.report['planning_error'] == 'ValidationError'
        assert result.report['planning_decision']['reason'] == ''
        assert result.report['decision']['selected'] is None
        assert 'search' not in result.report
        assert not any(call['role'] == 'proposal' for call in calls)


def test_transfer_setup_failure_closes_fit_runner_and_keeps_original_trial(tmp_path, monkeypatch):
    runners, _, agent = boundaries(monkeypatch)
    transfer = fit.continue_fit_investigation

    def break_transfer(result, active, **kwargs):
        active.configuration = object()
        return transfer(result, active, **kwargs)

    monkeypatch.setattr(fit, 'continue_fit_investigation', break_transfer)
    with pytest.raises(AttributeError):
        run(tmp_path, agent)
    assert len(runners) == 1
    assert not runners[0].ready
    saved = json.loads((tmp_path/'run'/'result.json').read_text())
    assert saved['status'] == 'failed'
    assert saved['candidate_trial']['trial_id'] == 'candidate'
    assert saved['baseline']['status'] == 'infeasible'
    assert saved['returned_runtimes'] == []
    assert saved['returned_runner_closed'] is True


def test_promoted_reference_does_not_mutate_historical_deployment(tmp_path, monkeypatch):
    _, _, agent = boundaries(monkeypatch)
    with run(tmp_path, agent, budget=1) as result:
        original = deepcopy(result.report['deployment']['candidate_trial'])
        result.report['baseline']['runtime']['extra_live_state'] = True
        result.report['baseline']['quality'][0]['text'] = 'changed reference field'
        assert result.report['deployment']['candidate_trial'] == original


def test_frozen_search_space_still_rejects_an_out_of_space_proposal_after_fit(tmp_path, monkeypatch):
    runners, _, agent = boundaries(monkeypatch)
    allowed = sera.RuntimeConfig(quantization='fp8_per_tensor', max_num_batched_tokens=1024).config_hash
    space = sera.InvestigationSpace(supported_changes={'max_num_batched_tokens': [2048, 1024]},
                                    candidate_hashes=[allowed])
    with run(tmp_path, agent, investigation_space=space) as result:
        assert len(runners) == 1
        assert result.models[0] is runners[0]
        assert result.report['investigation_space']['candidate_hashes'] == [allowed]
        assert result.report['search']['trials_used'] == 1
        assert result.report['search_trials'] == []
        assert result.report['search']['stop_reason'] == 'no-valid-selected-proposal'
        assert result.report['search']['rounds'][0]['specialists'][0]['status'] == 'rejected'


def test_final_fit_save_failure_closes_runner_and_clears_published_models(tmp_path, monkeypatch):
    runners, _, agent = boundaries(monkeypatch)
    save = pipeline.SeraResult._save
    failed = False

    def fail_save(result):
        nonlocal failed
        if result.report['status'] == 'ready' and not failed:
            failed = True
            raise OSError('fixture save failure')
        return save(result)

    monkeypatch.setattr(pipeline.SeraResult, '_save', fail_save)
    with pytest.raises(OSError, match='fixture save failure'):
        run(tmp_path, agent)
    assert len(runners) == 1
    assert not runners[0].ready
    saved = json.loads((tmp_path/'run'/'result.json').read_text())
    assert saved['returned_runtimes'] == []
    assert saved['returned_runner_closed'] is True


def test_search_receives_compact_fit_context_without_counting_fit_twice(tmp_path, monkeypatch):
    _, calls, agent = boundaries(monkeypatch)
    space = sera.InvestigationSpace(supported_changes={'max_num_batched_tokens': [2048, 1024]})
    with run(tmp_path, agent, budget=3, investigation_space=space) as result:
        searches = [call['evidence'] for call in calls if call['role'] == 'proposal']
        assert len(searches) == 2
        context = searches[0]['deployment_context']
        assert context['bf16_baseline_measured'] is False
        assert context['infeasible_baseline']['status'] == 'infeasible'
        assert context['infeasible_baseline']['fit_estimate']['estimated_fit'] is False
        assert context['selected_configuration']['quantization'] == 'fp8_per_tensor'
        assert context['task_quality']['passed'] is True
        assert context['task_quality']['floor'] == .99
        assert context['feasibility_prediction']['kind'] == 'deployment-feasibility'
        assert context['feasibility_review']['prediction_outcome'] == 'confirmed'
        assert 'not BF16 performance' in context['comparison_scope']
        assert 'requests' not in context and 'quality' not in context
        assert 'per_prompt' not in context['task_quality']
        assert searches[0]['history'] == []
        assert searches[1]['deployment_context'] == context
        assert len(searches[1]['history']) == 1
        assert searches[1]['history'][0]['trial']['trial_id'] == 'trial-2'
        assert result.report['search']['initial_trials_used'] == 1
        assert result.report['search']['trials_used'] == 2
