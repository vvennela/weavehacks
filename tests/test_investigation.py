"""Offline outcomes for the live investigation controller; no GPU or LM calls."""

from copy import deepcopy
import json

import pytest

import sera
from sera import pipeline
from sera.agent import ArbiterDecision, FrontierDecision, Proposal
from sera.config import MODEL_ID, MODEL_REVISION


def install_fakes(monkeypatch, *, startup_failure=False, cleanup_failure=False, abstain=False,
                  baseline_wrong=False, batch_wrong=False, batch_latency=80.0):
    runners, evidence_seen = [], []

    class Runner:
        def __init__(self, *, artifact_dir, configuration, model_id, revision):
            self.configuration, self.artifact_dir = configuration, artifact_dir
            self.record = dict(configuration=configuration.model_dump(), model_id=model_id,
                               revision=revision, sampled_peak_memory_mib=2000)
            self.ready = False
            runners.append(self)

        def start(self):
            if startup_failure and self.configuration.kv_cache_dtype == 'fp8':
                raise RuntimeError('fixture startup failure')
            assert not any(other.ready for other in runners if other is not self)
            self.ready = True

        def close(self):
            self.ready = False
            if cleanup_failure and self.configuration.kv_cache_dtype == 'fp8':
                raise pipeline.CleanupError('fixture cleanup failure')

        def _require_ready(self):
            assert self.ready

        def generate(self, prompt):
            self._require_ready()
            return 'fresh answer'

    def collect(model, prompts, trial_id, *, baseline=False, workload):
        is_cache = model.configuration.kv_cache_dtype == 'fp8'
        latency = 100.0 if baseline else (10.0 if is_cache else batch_latency)
        wrong = is_cache or (baseline_wrong if baseline else batch_wrong)
        output = dict(prompt_index=0, text='wrong' if wrong else 'correct',
                      token_ids=[1], prompt_token_ids=[1], error=None)
        return dict(trial_id=trial_id, status='collected', runtime=model.record,
                    config_hash=model.configuration.config_hash, input_token_ids=[[1]],
                    quality=[output], self_check=[deepcopy(output)], metrics={},
                    reduced=dict(p95_latency_ms=latency, output_tokens_per_second=100.0,
                                 generation_errors=0))

    class Agent:
        model, project = 'fixture', 'test/project'

        def __init__(self):
            self.history = []

        def request(self, role, evidence, instruction):
            evidence_seen.append((role, deepcopy(evidence)))
            self.history.append(dict(role=role, evidence=deepcopy(evidence)))
            if role == 'arbiter':
                return ArbiterDecision(ranked_proposal_ids=evidence['legal_proposal_ids'][:1], reason='Test first')
            lever, values = next(iter(evidence['supported_changes'].items()))
            return Proposal(action='keep-baseline' if abstain else 'trial',
                proposal_id=evidence['specialist_role'], agent_role=evidence['specialist_role'],
                parent_trial_id=evidence['trial_id'], model_id=evidence['model_id'],
                changed_lever=None if abstain else lever, proposed_value=None if abstain else values[0],
                evidence_used=['p95_latency_ms'], predicted_metric_change='Reduce p95 by 5%',
                confidence=.5, expected_trial_cost=0 if abstain else 1,
                falsification_condition='Quality fails or p95 gain is below 5%', reason='Test evidence')

        def review(self, evidence):
            evidence_seen.append(('frontier', deepcopy(evidence)))
            self.history.append(dict(role='frontier', evidence=deepcopy(evidence)))
            return FrontierDecision(selected_trial_id=evidence['eligible_trial_ids'][0],
                prediction_outcome='refuted' if evidence['decision']['selected'] != 'candidate' else 'confirmed',
                reason='Observed gate result')

    monkeypatch.setattr(pipeline, 'SeraModel', Runner)
    monkeypatch.setattr(pipeline, 'collect_trial', collect)
    monkeypatch.setattr('sera.provider_check.require_provider_check', lambda *_: {'fixture': True})
    return runners, evidence_seen, Agent()


def run(tmp_path, agent, **kwargs):
    budget = kwargs.pop('budget', sera.Budget(max_candidate_trials=2))
    return sera.optimize(models=[MODEL_ID], prompts=['question'], output_dir=tmp_path/'run',
        evaluation=lambda prompt, output: output == 'correct', evaluation_version='fixture-v1',
        constraints=sera.Constraints(quality_floor=.99), agent=agent, provider_check='fixture',
        budget=budget, **kwargs)


def test_two_rounds_use_failure_evidence_and_return_best_eligible_runner(tmp_path, monkeypatch):
    runners, seen, agent = install_fakes(monkeypatch)
    with run(tmp_path, agent) as result:
        assert len(result.trials) == 3
        assert result.trials[1]['decision']['selected'] == 'baseline'
        assert result.models[0].configuration.max_num_batched_tokens == 2048
        assert result.models[0].generate('new question') == 'fresh answer'
        later = [e for role, e in seen if role == 'proposal' and e['remaining_trials'] == 1]
        assert later and later[0]['history'][0]['trial']['task_quality']['passed'] is False
        assert later[0]['history'][0]['review']['prediction_outcome'] == 'refuted'
        assert 'quality' not in later[0]['history'][0]['trial']
        assert 'evidence' not in later[0]['previous_rounds'][0]['specialists'][0]
        assert 'trial_1_p95_latency_ms' in later[0]['metrics']
        assert result.report['search']['trials_used'] == 2
        assert result.report['search']['stop_reason'] == 'budget-exhausted'
        assert result.report['decision']['selected'] == 'trial-2'
        saved = json.loads((tmp_path/'run'/'result.json').read_text())
        assert len(saved['search']['rounds']) == 2
        assert sum(r.ready for r in runners) == 1
    assert not any(r.ready for r in runners)


def test_failed_start_consumes_trial_and_next_round_can_recover(tmp_path, monkeypatch):
    runners, seen, agent = install_fakes(monkeypatch, startup_failure=True)
    with run(tmp_path, agent) as result:
        assert result.report['search']['trials_used'] == 2
        assert result.trials[1]['status'] == 'startup-failed'
        assert result.models[0].configuration.max_num_batched_tokens == 2048


def test_cleanup_failure_stops_before_another_trial(tmp_path, monkeypatch):
    runners, _, agent = install_fakes(monkeypatch, cleanup_failure=True)
    with pytest.raises(pipeline.CleanupError):
        run(tmp_path, agent)
    assert len(runners) == 2


def test_abstention_returns_live_baseline_without_candidate_trials(tmp_path, monkeypatch):
    runners, _, agent = install_fakes(monkeypatch, abstain=True)
    with run(tmp_path, agent) as result:
        assert len(result.trials) == 1
        assert len(runners) == 1
        assert result.report['search']['trials_used'] == 0
        assert result.report['decision']['selected'] == 'baseline'


@pytest.mark.parametrize('value', [True, 0, 9, '2'])
def test_budget_is_strict_and_bounded(value):
    with pytest.raises(ValueError):
        sera.Budget(max_candidate_trials=value)


def test_one_trial_budget_returns_original_after_quality_rejection(tmp_path, monkeypatch):
    runners, seen, agent = install_fakes(monkeypatch)
    with run(tmp_path, agent, budget=sera.Budget(max_candidate_trials=1)) as result:
        assert result.report['search']['trials_used'] == 1
        assert result.report['search']['stop_reason'] == 'budget-exhausted'
        assert result.report['decision']['selected'] == 'baseline'
        assert len(result.trials) == 2
        assert len(runners) == 3  # Reference, rejected candidate, returned reference.
        assert result.models[0].configuration == sera.RuntimeConfig()


def test_two_failed_rounds_stop_and_do_not_return_wrong_baseline(tmp_path, monkeypatch):
    runners, _, agent = install_fakes(monkeypatch, baseline_wrong=True, batch_wrong=True)
    result = run(tmp_path, agent)
    assert result.models == []
    assert result.report['status'] == 'no-safe-configuration'
    assert result.report['search']['stop_reason'] == 'two-rounds-without-frontier-improvement'
    assert result.frontier == []
    assert not any(runner.ready for runner in runners)


def test_correct_candidate_can_replace_wrong_baseline_even_when_slower(tmp_path, monkeypatch):
    _, _, agent = install_fakes(monkeypatch, baseline_wrong=True, batch_latency=150.0)
    with run(tmp_path, agent) as result:
        assert result.report['decision']['selected'] == 'trial-2'
        assert result.report['decision']['outcome'] == 'feasible'
        assert result.models[0].configuration.max_num_batched_tokens == 2048


def test_invalid_proposals_do_not_consume_gpu_trials(tmp_path, monkeypatch):
    runners, _, agent = install_fakes(monkeypatch)
    request = agent.request

    def invalid(role, evidence, instruction):
        parsed = request(role, evidence, instruction)
        if role == 'proposal':
            return parsed.model_copy(update={'parent_trial_id': 'invented-parent'})
        return parsed

    agent.request = invalid
    with run(tmp_path, agent) as result:
        assert result.report['search']['trials_used'] == 0
        assert len(runners) == 1
        assert all(check['status'] == 'rejected'
                   for check in result.report['search']['rounds'][0]['specialists'])


def test_failed_real_provider_certificate_blocks_investigation_before_gpu(tmp_path):
    from sera.agent import WandbAgent
    with pytest.raises(ValueError, match='context'):
        sera.optimize(models=[MODEL_ID], prompts=['question'], output_dir=tmp_path/'blocked',
            agent=WandbAgent(project='vvennela-n-a/wandb_agent_default_project'),
            provider_check='evidence/provider-v4/result.json', budget=sera.Budget(max_candidate_trials=2))
    assert not (tmp_path/'blocked').exists()
