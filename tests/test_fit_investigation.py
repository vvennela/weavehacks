"""Fit planning and search share one live owner and one total trial budget."""

from copy import deepcopy

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
