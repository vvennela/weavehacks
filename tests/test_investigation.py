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
        assert later[0]['metrics']['trial_1_sampled_peak_memory_mib'] == 2000
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
    with pytest.raises(ValueError):
        sera.optimize(models=[MODEL_ID], prompts=['question'], output_dir=tmp_path/'blocked',
            agent=WandbAgent(project='vvennela-n-a/wandb_agent_default_project'),
            provider_check='evidence/provider-v4/result.json', budget=sera.Budget(max_candidate_trials=2))
    assert not (tmp_path/'blocked').exists()


def use_investigation_space(monkeypatch, supported_changes, candidate_hashes=None):
    """Supply the validated per-run report contract without changing the public API."""
    from sera import investigation
    original = investigation.investigate

    def with_space(**kwargs):
        space = {'supported_changes': supported_changes}
        if candidate_hashes is not None:
            space['candidate_hashes'] = candidate_hashes
        kwargs['result'].report['investigation_space'] = space
        return original(**kwargs)

    monkeypatch.setattr(investigation, 'investigate', with_space)


def test_setup_failure_closes_transferred_baseline(tmp_path, monkeypatch):
    runners, _, agent = install_fakes(monkeypatch)

    def fail_evidence(*args):
        raise ValueError('fixture evidence failure')

    monkeypatch.setattr(pipeline, 'agent_evidence', fail_evidence)
    with pytest.raises(ValueError, match='fixture evidence failure'):
        run(tmp_path, agent)
    assert len(runners) == 1
    assert not runners[0].ready


def test_constructor_failure_is_saved_consumes_budget_and_feeds_next_round(tmp_path, monkeypatch):
    runners, seen, agent = install_fakes(monkeypatch)
    runner = pipeline.SeraModel

    def construct(**kwargs):
        if kwargs['configuration'].kv_cache_dtype == 'fp8':
            raise RuntimeError('fixture constructor failure')
        return runner(**kwargs)

    monkeypatch.setattr(pipeline, 'SeraModel', construct)
    with run(tmp_path, agent) as result:
        failed = result.trials[1]
        assert failed['status'] == 'startup-failed'
        assert failed['failure_stage'] == 'constructor'
        assert result.report['search']['trials_used'] == 2
        assert result.models[0].configuration.max_num_batched_tokens == 2048
        later = [e for role, e in seen if role == 'proposal' and e['remaining_trials'] == 1]
        assert later[0]['history'][0]['trial']['failure_stage'] == 'constructor'
        assert not runners[0].ready


def test_collection_failure_is_not_reported_as_startup_failure(tmp_path, monkeypatch):
    _, seen, agent = install_fakes(monkeypatch)
    collect = pipeline.collect_trial

    def fail_measurement(model, *args, **kwargs):
        if model.configuration.kv_cache_dtype == 'fp8':
            raise RuntimeError('fixture collection failure')
        return collect(model, *args, **kwargs)

    monkeypatch.setattr(pipeline, 'collect_trial', fail_measurement)
    with run(tmp_path, agent) as result:
        assert result.trials[1]['status'] == 'measurement-failed'
        assert result.trials[1]['failure_stage'] == 'measurement'
        later = [e for role, e in seen if role == 'proposal' and e['remaining_trials'] == 1]
        assert later[0]['history'][0]['trial']['status'] == 'measurement-failed'
        assert result.models[0].configuration.max_num_batched_tokens == 2048


def test_duplicate_specialist_ids_remain_distinct_for_arbitration(tmp_path, monkeypatch):
    _, seen, agent = install_fakes(monkeypatch)
    request = agent.request

    def duplicate_ids(role, evidence, instruction):
        response = request(role, evidence, instruction)
        if role == 'proposal':
            return response.model_copy(update={'proposal_id': 'proposal-1'})
        if role == 'arbiter':
            batching = next(p for p in evidence['proposals'] if p['agent_role'] == 'batching')
            return ArbiterDecision(ranked_proposal_ids=[batching['proposal_id']], reason='Batch first')
        return response

    agent.request = duplicate_ids
    with run(tmp_path, agent, budget=sera.Budget(max_candidate_trials=1)) as result:
        checks = result.report['search']['rounds'][0]['specialists']
        assert [check['status'] for check in checks] == ['accepted', 'accepted']
        assert len({check['arbiter_proposal_id'] for check in checks}) == 2
        assert all(check['proposal']['proposal_id'] == 'proposal-1' for check in checks)
        assert result.trials[1]['proposal']['proposal_id'] == 'proposal-1'
        assert result.models[0].configuration.max_num_batched_tokens == 2048


@pytest.mark.parametrize('ranked_ids', [['unknown'], ['batching', 'quantization']])
def test_invalid_arbiter_ranking_stops_without_a_trial(tmp_path, monkeypatch, ranked_ids):
    runners, _, agent = install_fakes(monkeypatch)
    request = agent.request

    def invalid_ranking(role, evidence, instruction):
        response = request(role, evidence, instruction)
        if role == 'arbiter':
            invalid_ids = (evidence['legal_proposal_ids'] if len(ranked_ids) > 1 else ranked_ids)
            return response.model_copy(update={'ranked_proposal_ids': invalid_ids})
        return response

    agent.request = invalid_ranking
    with run(tmp_path, agent) as result:
        assert result.report['search']['trials_used'] == 0
        assert result.report['search']['rounds'][0]['arbiter_error']
        assert result.rejected[0]['stage'] == 'arbiter-validation'
        assert result.report['search']['rounds'][0]['arbiter']['ranked_proposal_ids']
        assert len(runners) == 1


def test_equal_frontier_points_stop_after_two_rounds_without_repeating_configs(tmp_path, monkeypatch):
    _, seen, agent = install_fakes(monkeypatch, batch_latency=100.0)
    use_investigation_space(monkeypatch, {'max_num_batched_tokens': [2048, 2048, 1024, 512]})
    with run(tmp_path, agent, budget=sera.Budget(max_candidate_trials=4)) as result:
        assert result.report['search']['trials_used'] == 2
        assert result.report['search']['stop_reason'] == 'two-rounds-without-frontier-improvement'
        assert len({trial['config_hash'] for trial in result.trials}) == 3
        assert result.report['decision']['selected'] == 'baseline'
        first = next(e for role, e in seen if role == 'proposal')
        assert first['supported_changes'] == {'max_num_batched_tokens': [2048, 1024, 512]}


def test_explicit_frozen_hashes_filter_active_values_before_proposal(tmp_path, monkeypatch):
    _, seen, agent = install_fakes(monkeypatch)
    allowed = sera.RuntimeConfig(max_num_batched_tokens=1024).config_hash
    use_investigation_space(monkeypatch, {'max_num_batched_tokens': [2048, 1024]}, [allowed])
    with run(tmp_path, agent) as result:
        assert result.report['search']['trials_used'] == 1
        assert result.trials[1]['config_hash'] == allowed
        assert result.models[0].configuration.max_num_batched_tokens == 1024
        proposal_evidence = next(e for role, e in seen if role == 'proposal')
        assert proposal_evidence['supported_changes'] == {'max_num_batched_tokens': [1024]}
        assert proposal_evidence['frozen_candidate_hashes'] == [allowed]


def test_save_failure_closes_runner_and_does_not_publish_a_live_return(tmp_path, monkeypatch):
    runners, _, agent = install_fakes(monkeypatch)
    save = pipeline.SeraResult._save
    failed = False

    def fail_return_save(result):
        nonlocal failed
        if result.report['status'] == 'ready' and not failed:
            failed = True
            raise OSError('fixture save failure')
        save(result)

    monkeypatch.setattr(pipeline.SeraResult, '_save', fail_return_save)
    with pytest.raises(OSError, match='fixture save failure'):
        run(tmp_path, agent)
    assert not any(runner.ready for runner in runners)
    report = json.loads((tmp_path/'run'/'result.json').read_text())
    assert report['returned_runtimes'] == []
    assert report['returned_runner_closed'] is True


def test_best_measured_candidate_breaks_objective_ties_by_memory(tmp_path, monkeypatch):
    _, _, agent = install_fakes(monkeypatch)
    collect = pipeline.collect_trial
    use_investigation_space(monkeypatch, {'max_num_batched_tokens': [2048, 1024]})

    def smaller_memory(model, *args, **kwargs):
        trial = collect(model, *args, **kwargs)
        if model.configuration.max_num_batched_tokens == 1024:
            trial['runtime']['sampled_peak_memory_mib'] = 1000
        return trial

    monkeypatch.setattr(pipeline, 'collect_trial', smaller_memory)
    with run(tmp_path, agent) as result:
        assert result.report['decision']['selected'] == 'trial-2'
        assert result.models[0].configuration.max_num_batched_tokens == 1024


def test_failed_best_runner_restore_closes_all_runtimes(tmp_path, monkeypatch):
    runners, _, agent = install_fakes(monkeypatch)
    runner = pipeline.SeraModel

    def fail_restore(**kwargs):
        model = runner(**kwargs)
        if kwargs['artifact_dir'].name == 'returned-best':
            def start_failure():
                model.ready = True
                raise RuntimeError('fixture restore failure')
            model.start = start_failure
        return model

    monkeypatch.setattr(pipeline, 'SeraModel', fail_restore)
    with pytest.raises(RuntimeError, match='fixture restore failure'):
        run(tmp_path, agent, budget=sera.Budget(max_candidate_trials=1))
    assert len(runners) == 3
    assert not any(model.ready for model in runners)


def test_invalid_prediction_review_is_saved_but_cannot_approve_quality_failure(tmp_path, monkeypatch):
    _, seen, agent = install_fakes(monkeypatch)

    def false_review(evidence):
        return FrontierDecision(selected_trial_id='trial-1', prediction_outcome='confirmed',
                                reason='Unsupported approval')

    agent.review = false_review
    with run(tmp_path, agent) as result:
        rejected = result.trials[1]
        assert rejected['decision']['selected'] == 'baseline'
        assert rejected['review_response']['selected_trial_id'] == 'trial-1'
        assert rejected['review_error'] == 'ValueError'
        assert 'review' not in rejected
        assert any(item['stage'] == 'review-validation' for item in result.rejected)
        later = [e for role, e in seen if role == 'proposal' and e['remaining_trials'] == 1]
        assert later[0]['history'][0]['review_error'] == 'ValueError'
