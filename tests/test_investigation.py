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
        failed_request = later[0]['history'][0]['request_evidence']['quality_examples'][0]
        assert failed_request['output'] == 'wrong'
        assert failed_request['input'] == 'question'
        assert failed_request['task_score'] == 0
        baseline_request = later[0]['request_evidence']['quality_examples'][0]
        assert baseline_request['output'] == 'correct'
        reviews = [e for role, e in seen if role == 'frontier']
        assert reviews[0]['candidate_request_evidence']['quality_examples'][0]['output'] == 'wrong'
        assert 'quality' not in later[0]['history'][0]['trial']
        assert 'evidence' not in later[0]['previous_rounds'][0]['specialists'][0]
        assert 'trial_1_p95_latency_ms' in later[0]['metrics']
        assert later[0]['metrics']['trial_1_sampled_peak_memory_mib'] == 2000
        assert later[0]['metrics']['trial_1_trace_failed_task_count'] == 1
        assert result.report['search']['trials_used'] == 2
        assert result.report['search']['stop_reason'] == 'budget-exhausted'
        assert result.report['decision']['selected'] == 'trial-2'
        saved = json.loads((tmp_path/'run'/'result.json').read_text())
        assert len(saved['search']['rounds']) == 2
        assert sum(r.ready for r in runners) == 1
    assert not any(r.ready for r in runners)


def test_simulated_swarm_rejects_fast_wrong_trial_inspects_failure_and_returns_safe_runner(tmp_path, monkeypatch):
    """Exercise the real controller, not live model intelligence or GPU performance."""
    from sera.config import CONTROL_ROLES
    from sera.storage import content_hash
    from sera.tracing import use_event_sink

    runners, _, base_agent = install_fakes(monkeypatch)
    recorded_diagnoses, failure_reads = {}, []

    def record(event_name, payload):
        if event_name == 'recorded_trial_diagnosis':
            recorded_diagnoses[payload['trial_id']] = deepcopy(payload)

    def read_saved_trace(query_id, supplied):
        assert query_id == 'quality_outputs'
        rows = []
        if supplied['history']:
            # Read the verdict actually produced and saved by this optimize call.
            saved = json.loads((tmp_path/'run'/'result.json').read_text())
            failed = saved['search_trials'][0]
            payload = recorded_diagnoses['trial-1']
            assert payload['diagnosis'] == failed['diagnosis']
            assert failed['task_quality']['mean'] == 0
            assert failed['decision']['selected'] == 'baseline'
            assert supplied['required_inspection'] is True
            assert any(scope['trial_id'] == 'trial-1' and scope['config_hash'] == failed['config_hash']
                       for scope in supplied['trace_scope'])
            failure_reads.append(supplied['investigator_id'])
            rows.append(dict(payload, call_id='simulated-diagnosis-trial-1',
                             output_sha256=content_hash(payload), record_type='trial_diagnosis'))
        return dict(source='simulated offline trace sink', query_id=query_id, records=rows)

    class ScriptedSwarm(type(base_agent)):
        def fork(self):
            return ScriptedSwarm()

        def request(self, role, supplied, instruction):
            self.history.append(dict(role=role, evidence=deepcopy(supplied)))
            if supplied.get('swarm_phase') == 'inspect':
                return ArbiterDecision(ranked_proposal_ids=[] if supplied['inspections'] else ['quality_outputs'],
                                       reason='Inspect the saved quality verdict once')
            if role == 'arbiter':
                return ArbiterDecision(ranked_proposal_ids=supplied['legal_proposal_ids'][:1],
                                       reason='Authorize one experiment, not deployment')
            later_round = bool(supplied['history'])
            if later_round:
                rows = supplied['inspections'][0]['result']['records']
                assert rows[0]['diagnosis']['observed']['quality']['mean'] == 0
                assert supplied['history'][0]['review']['prediction_outcome'] == 'refuted'
                assert 'kv_cache_dtype' not in supplied['supported_changes']
            lever = 'max_num_batched_tokens' if later_round else 'kv_cache_dtype'
            return Proposal(action='trial', proposal_id='same-scripted-id', agent_role=CONTROL_ROLES[lever],
                parent_trial_id=supplied['trial_id'], model_id=supplied['model_id'],
                changed_lever=lever, proposed_value=supplied['supported_changes'][lever][0],
                evidence_used=['p95_latency_ms'], predicted_metric_change='Reduce p95 by at least 5%',
                confidence=.5, expected_trial_cost=1,
                falsification_condition='Reject if quality fails or p95 gain is below 5%',
                reason='Try batching after simulated-diagnosis-trial-1 showed wrong answers'
                       if later_round else 'Test cache precision; gate still decides deployment')

    with use_event_sink(record):
        with run(tmp_path, ScriptedSwarm(), swarm=True, trace_reader=read_saved_trace) as result:
            baseline, wrong, safe = result.trials
            assert wrong['reduced']['p95_latency_ms'] < safe['reduced']['p95_latency_ms'] < baseline['reduced']['p95_latency_ms']
            assert wrong['task_quality']['passed'] is False and wrong['decision']['selected'] == 'baseline'
            assert safe['task_quality']['passed'] is True and safe['decision']['selected'] == 'candidate'
            assert len({trial['config_hash'] for trial in result.trials}) == 3
            rounds = result.report['search']['rounds']
            assert [item['trial_ids'] for item in rounds] == [['trial-1'], ['trial-2']]
            assert all(len(item['arbiter']['ranked_proposal_ids']) == 1 for item in rounds)
            assert sorted(failure_reads) == ['memory_context', 'output_quality', 'scheduling']
            assert all(item['successful_inspections'] == 1 and item['status'] == 'accepted'
                       for item in rounds[1]['specialists'])
            assert result.report['search']['trials_used'] == 2
            assert result.report['decision']['selected'] == 'trial-2'
            assert result.models[0].configuration.max_num_batched_tokens == 2048
            assert result.models[0].configuration.kv_cache_dtype == baseline['runtime']['configuration']['kv_cache_dtype']
            assert result.models[0].generate('new question') == 'fresh answer'
            saved = json.loads((tmp_path/'run'/'result.json').read_text())
            assert saved['search']['rounds'] == rounds
            assert saved['decision']['selected'] == 'trial-2'
            assert sum(runner.ready for runner in runners) == 1
    assert len(runners) == 3 and not any(runner.ready for runner in runners)


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


def plateau_run(tmp_path, monkeypatch, latencies, *, wrong=(), missing=(), failed=()):
    runners, seen, agent = install_fakes(monkeypatch)
    original_collect = pipeline.collect_trial
    def collect(model, prompts, trial_id, **kwargs):
        record = original_collect(model, prompts, trial_id, **kwargs)
        if trial_id != 'baseline':
            number = int(trial_id.split('-')[1])
            if number in failed:
                raise RuntimeError('fixture measurement failed')
            record['reduced']['p95_latency_ms'] = None if number in missing else latencies[number - 1]
            record['runtime']['sampled_peak_memory_mib'] = 2000 - number
            if number in wrong:
                record['quality'][0]['text'] = 'wrong'
        return record
    monkeypatch.setattr(pipeline, 'collect_trial', collect)
    use_investigation_space(monkeypatch, {'max_num_batched_tokens': list(range(128, 128 + len(latencies)))})
    return run(tmp_path, agent, budget=sera.Budget(max_candidate_trials=None)), seen, runners


def test_plateau_mode_can_improve_more_than_eight_times_then_confirms_once(tmp_path, monkeypatch):
    improving = [100 * .9 ** index for index in range(1, 10)]
    result, seen, runners = plateau_run(tmp_path, monkeypatch, improving + [improving[-1]] * 3)
    with result:
        search = result.report['search']
        assert search['trials_used'] == 11
        assert search['stop_reason'] == 'objective-plateau-confirmed'
        assert search['budget']['max_candidate_trials'] is None
        assert len(search['rounds']) == 11
        assert all(len(row['trial_ids']) == 1 for row in search['rounds'])
        assert search['rounds'][-1]['confirmation_round'] is True
        # Existing equal-latency memory tie-break can pick the latest valid trial;
        # that memory change must not count as latency progress.
        assert result.report['decision']['selected'] == 'trial-11'
        evidence = [e for role, e in seen if role == 'proposal']
        assert evidence[-1]['remaining_trials'] is None
        assert evidence[-1]['round_trial_capacity'] == 1
        assert evidence[-1]['plateau']['confirmation_round_pending'] is True
        assert len(evidence[-1]['plateau']['history']) == 10
        prose = (tmp_path / 'run' / 'report.md').read_text()
        assert 'no total trial cap' in prose
        assert 'confirmation round' in prose
        assert '11/None' not in prose
    assert not any(r.ready for r in runners)


def test_qualifying_progress_resets_pending_confirmation(tmp_path, monkeypatch):
    result, _, _ = plateau_run(tmp_path, monkeypatch, [100, 90, 90, 90, 70])
    with result:
        search = result.report['search']
        assert search['trials_used'] == 4
        assert [row['confirmation_round'] for row in search['rounds']] == [False, True, False, True]
        assert [row['objective_progress']['qualifying_progress'] for row in search['rounds']] == [False, True, False, False]


@pytest.mark.parametrize('wrong,missing,failed', [((1, 2), (), ()), ((), (1, 2), ()), ((), (), (1, 2))])
def test_quality_failure_or_missing_objective_cannot_reset_plateau(tmp_path, monkeypatch, wrong, missing, failed):
    result, _, _ = plateau_run(tmp_path, monkeypatch, [10, 5, 1], wrong=wrong, missing=missing, failed=failed)
    with result:
        assert result.report['search']['trials_used'] == 2
        assert result.report['search']['stop_reason'] == 'objective-plateau-confirmed'
        assert result.report['decision']['selected'] == 'baseline'


@pytest.mark.parametrize('latencies,expected', [([95, 95, 95, 90], 3), ([95.001, 95.001, 80], 2)])
def test_plateau_uses_five_percent_boundary_not_memory_noise(tmp_path, monkeypatch, latencies, expected):
    result, _, _ = plateau_run(tmp_path, monkeypatch, latencies)
    with result:
        assert result.report['search']['trials_used'] == expected
        assert result.report['search']['stop_reason'] == 'objective-plateau-confirmed'


def test_exhaustion_during_confirmation_is_not_claimed_as_confirmed(tmp_path, monkeypatch):
    result, _, _ = plateau_run(tmp_path, monkeypatch, [100])
    with result:
        assert result.report['search']['trials_used'] == 1
        assert result.report['search']['stop_reason'] == 'no-legal-untested-candidate'
        assert result.report['search']['plateau']['confirmation_round_pending'] is True


def test_plateau_compares_prior_best_not_original_baseline(tmp_path, monkeypatch):
    result, _, _ = plateau_run(tmp_path, monkeypatch, [96, 92, 70])
    with result:
        assert result.report['search']['trials_used'] == 2
        progress = result.report['search']['rounds'][1]['objective_progress']
        assert progress['prior_best_quality_valid_value'] == 96
        assert progress['qualifying_progress'] is False


@pytest.mark.parametrize('priority,value', [('latency', 95), ('throughput', 105), ('memory', 95)])
def test_objective_plateau_respects_metric_direction_and_boundary(priority, value):
    from sera.investigation import objective_progress
    def trial(name, metric):
        return dict(trial_id=name, status='collected', input_token_ids=[[1]],
            task_quality=dict(mean=1, valid_outputs=True),
            reduced=dict(p95_latency_ms=metric if priority == 'latency' else 100,
                         output_tokens_per_second=metric if priority == 'throughput' else 100),
            runtime=dict(sampled_peak_memory_mib=metric if priority == 'memory' else 100))
    plateau = dict(best_quality_valid_value=100, consecutive_no_progress_rounds=1,
                   confirmation_round_pending=True, history=[])
    result = objective_progress(plateau, trial('baseline', 100), [trial('candidate', value)],
        objective=sera.Objective(priority=priority), constraints=sera.Constraints(quality_floor=.99), round_number=2)
    assert result['qualifying_progress'] is True
    assert plateau['confirmation_round_pending'] is False
    assert plateau['consecutive_no_progress_rounds'] == 0


def test_compact_prompt_preserves_uncapped_policy_and_plateau_history(tmp_path, monkeypatch):
    from sera.investigation_prompt import build_investigation_prompt
    result, seen, _ = plateau_run(tmp_path, monkeypatch, [100, 100, 80])
    with result:
        evidence = [e for role, e in seen if role == 'proposal'][-1]
        projected = build_investigation_prompt(evidence)
        if isinstance(projected, tuple):
            projected = projected[0]
        for key in ('remaining_trials', 'total_trial_cap', 'round_trial_capacity', 'search_policy', 'plateau'):
            assert projected[key] == evidence[key]


def test_uncapped_proposal_requires_explicit_round_capacity():
    from sera.agent import parse_response, validate_proposal
    from sera.provider_check import provider_cases
    evidence = deepcopy(provider_cases()[0]['evidence'])
    evidence.update(remaining_trials=None, search_policy='until-plateau', round_trial_capacity=1)
    value = dict(action='trial', proposal_id='p1', agent_role='quantization',
        parent_trial_id=evidence['trial_id'], model_id=evidence['model_id'],
        changed_lever='kv_cache_dtype', proposed_value='fp8', expected_trial_cost=1,
        evidence_used=['p95_latency_ms'], predicted_metric_change='Test memory', confidence=.5,
        falsification_condition='No measured gain', reason='Test')
    proposal = parse_response('proposal', json.dumps(value), evidence)
    assert validate_proposal(proposal, evidence) is not None
    for field in ('search_policy', 'round_trial_capacity'):
        invalid = deepcopy(evidence)
        invalid.pop(field)
        with pytest.raises(ValueError, match='round capacity'):
            validate_proposal(proposal, invalid)


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

    def fail_evidence(*args, **kwargs):
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
