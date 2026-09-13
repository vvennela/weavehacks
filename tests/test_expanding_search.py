"""Behavior checks for the normal-mode, evidence-driven candidate generator."""

from copy import deepcopy

import pytest

from sera.agent import Proposal, validate_proposal
from sera.config import (CONTROL_ROLES, InvestigationSpace, LARGE_MODEL_ID, MODEL_ID,
                         RuntimeConfig, Workload, resolve_investigation_space)
from sera.search_policy import expand_search_space


def measured(config=None, *, trial_id='baseline', latency=100, passed=True):
    config = config or RuntimeConfig()
    return dict(trial_id=trial_id, status='collected', config_hash=config.config_hash,
                runtime=dict(configuration=config.model_dump(), model_id=MODEL_ID,
                             sampled_peak_memory_mib=2000),
                input_token_ids=[list(range(100))],
                task_quality=dict(passed=passed, mean=1.0 if passed else 0.0,
                                  valid_outputs=True, floor=.99),
                reduced=dict(p95_latency_ms=latency, output_tokens_per_second=10,
                             generation_errors=0), loads=[])


def expand(reference=None, trials=()):
    return expand_search_space(reference or measured(), list(trials), model_id=MODEL_ID,
                               workload=Workload(concurrency=[1, 2, 4, 8]))


@pytest.mark.parametrize('lever,value', [('enable_prefix_caching', True),
    ('enable_chunked_prefill', False), ('enforce_eager', False),
    ('gpu_memory_utilization', .85)])
def test_new_controls_are_typed_and_explicitly_validated(lever, value):
    config = RuntimeConfig.model_validate(RuntimeConfig().model_dump() | {lever: value})
    space = InvestigationSpace(supported_changes={lever: [value]})
    resolved = resolve_investigation_space(space, baseline=RuntimeConfig(), model_id=MODEL_ID,
                                          workload=Workload())
    assert config.config_hash in resolved['candidate_hashes']
    evidence = dict(trial_id='baseline', model_id=MODEL_ID, configuration=RuntimeConfig().model_dump(),
                    metrics={'p95_latency_ms': 100}, remaining_trials=1,
                    supported_changes={lever: [value]})
    proposal = Proposal(action='trial', proposal_id='new-control', agent_role=CONTROL_ROLES[lever],
        parent_trial_id='baseline', model_id=MODEL_ID, changed_lever=lever, proposed_value=value,
        evidence_used=['p95_latency_ms'], predicted_metric_change='Test latency change',
        confidence=.5, expected_trial_cost=1, falsification_condition='No measured improvement',
        reason='Check the declared runtime control')
    assert validate_proposal(proposal, evidence).config == config


def test_dynamic_pool_has_multiple_values_and_execution_controls():
    policy = expand()
    changes = policy['space']['supported_changes']
    assert len(changes['max_num_batched_tokens']) >= 3
    assert changes['enable_prefix_caching'] == [True]
    assert changes['enforce_eager'] == [False]
    assert len(policy['candidates']) > 2
    assert all(c['configuration']['max_model_len'] >= 164 for c in policy['candidates'])


def test_next_round_generates_neighbors_and_never_repeats_attempted_hash():
    reference = measured()
    first = expand(reference)
    trial = measured(RuntimeConfig(max_num_batched_tokens=2048), trial_id='trial-1', latency=90)
    second = expand(reference, [trial])
    assert trial['config_hash'] not in {c['config_hash'] for c in second['candidates']}
    assert second['history_trial_ids'] == ['trial-1']
    assert {c['config_hash'] for c in second['candidates']} != {c['config_hash'] for c in first['candidates']}
    assert any(c['changed'] == {'max_num_batched_tokens': 1024} for c in second['candidates'])


def test_failed_trial_does_not_create_combination_parent_or_repeat():
    trial = measured(RuntimeConfig(enable_prefix_caching=True), trial_id='bad', passed=False)
    policy = expand(trials=[trial])
    assert trial['config_hash'] not in {c['config_hash'] for c in policy['candidates']}
    assert all(c['parent_trial_id'] != 'bad' for c in policy['candidates'])


def test_combination_requires_two_measured_quality_passing_component_trials():
    prefix = measured(RuntimeConfig(enable_prefix_caching=True), trial_id='prefix', latency=80)
    graphs = measured(RuntimeConfig(enforce_eager=False), trial_id='graphs', latency=70)
    policy = expand(trials=[prefix, graphs])
    combinations = [c for c in policy['candidates'] if len(c['component_trial_ids']) == 2]
    assert combinations
    combo = combinations[0]
    assert set(combo['component_trial_ids']) == {'prefix', 'graphs'}
    assert combo['configuration']['enable_prefix_caching'] is True
    assert combo['configuration']['enforce_eager'] is False
    assert combo['parent_trial_id'] in {'prefix', 'graphs'}


def test_large_model_does_not_unlock_unverified_combined_precision():
    reference = measured(RuntimeConfig(quantization='fp8_per_tensor'))
    reference['runtime']['model_id'] = LARGE_MODEL_ID
    policy = expand_search_space(reference, [], model_id=LARGE_MODEL_ID, workload=Workload())
    assert 'kv_cache_dtype' not in policy['space']['supported_changes']


def test_expansion_does_not_mutate_history():
    trial = measured(RuntimeConfig(max_num_batched_tokens=2048), trial_id='prior')
    saved = deepcopy(trial)
    expand(trials=[trial])
    assert trial == saved


def test_combination_proposal_binds_measured_parent_and_generated_hash():
    prefix = measured(RuntimeConfig(enable_prefix_caching=True), trial_id='prefix', latency=80)
    graphs = measured(RuntimeConfig(enforce_eager=False), trial_id='graphs', latency=70)
    policy = expand(trials=[prefix, graphs])
    combo = next(c for c in policy['candidates'] if len(c['component_trial_ids']) == 2)
    lever, value = next(iter(combo['changed'].items()))
    evidence = dict(trial_id='baseline', model_id=MODEL_ID, configuration=RuntimeConfig().model_dump(),
        metrics={'p95_latency_ms': 100}, remaining_trials=1,
        supported_changes=policy['space']['supported_changes'],
        frozen_candidate_hashes=policy['space']['candidate_hashes'],
        candidate_options=policy['candidates'], candidate_parents=policy['candidate_parents'])
    proposal = Proposal(action='trial', proposal_id='combine', agent_role=CONTROL_ROLES[lever],
        parent_trial_id=combo['parent_trial_id'], model_id=MODEL_ID, changed_lever=lever,
        proposed_value=value, evidence_used=['p95_latency_ms'], predicted_metric_change='Test combined gain',
        confidence=.5, expected_trial_cost=1, falsification_condition='Either gate fails', reason='Use tested components')
    assert validate_proposal(proposal, evidence).config.config_hash == combo['config_hash']
    with pytest.raises(ValueError):
        validate_proposal(proposal.model_copy(update={'parent_trial_id': 'invented'}), evidence)


def test_live_controller_refreshes_policy_after_each_trial(tmp_path, monkeypatch):
    import sera
    from test_investigation import install_fakes, run
    _, _, agent = install_fakes(monkeypatch)
    with run(tmp_path, agent, automatic_space=True, budget=sera.Budget(max_candidate_trials=3)) as result:
        rounds = result.report['search']['rounds']
        assert len(rounds) >= 2
        assert rounds[0]['candidate_policy']['history_trial_ids'] == []
        assert rounds[1]['candidate_policy']['history_trial_ids']
        first_hash = result.report['search_trials'][0]['config_hash']
        assert first_hash not in rounds[1]['candidate_policy']['space']['candidate_hashes']
        assert 'enforce_eager' in rounds[0]['candidate_policy']['space']['supported_changes']
        assert result.report['candidate_ledger']


def test_controller_executes_combination_with_both_parent_trials_and_original_gate(tmp_path, monkeypatch):
    import sera
    from sera import pipeline
    from test_investigation import install_fakes, run
    _, _, original = install_fakes(monkeypatch)
    collect = pipeline.collect_trial

    def collect_flags(model, *args, **kwargs):
        trial = collect(model, *args, **kwargs)
        config = model.configuration
        trial['reduced']['p95_latency_ms'] = (60 if config.enable_prefix_caching and not config.enforce_eager
            else 90 if config.enable_prefix_caching else 80 if not config.enforce_eager else 100)
        return trial

    class CombiningAgent(type(original)):
        def request(self, role, evidence, instruction):
            if role != 'proposal':
                return super().request(role, evidence, instruction)
            count = len(evidence['history'])
            options = evidence['candidate_options']
            chosen = next((option for option in options if
                (count == 0 and option['changed'] == {'enable_prefix_caching': True})
                or (count == 1 and option['changed'] == {'enforce_eager': False})
                or (count == 2 and len(option['component_trial_ids']) == 2)), None)
            keep = evidence['specialist_role'] != 'batching' or chosen is None
            lever, value = (None, None) if keep else next(iter(chosen['changed'].items()))
            return Proposal(action='keep-baseline' if keep else 'trial', proposal_id='experiment',
                agent_role=evidence['specialist_role'], parent_trial_id='baseline' if keep else chosen['parent_trial_id'],
                model_id=MODEL_ID, changed_lever=lever, proposed_value=value,
                evidence_used=['p95_latency_ms'], predicted_metric_change='Test combined latency',
                confidence=.5, expected_trial_cost=0 if keep else 1,
                falsification_condition='Quality fails or latency does not improve', reason='Test declared parents')

    monkeypatch.setattr(pipeline, 'collect_trial', collect_flags)
    with run(tmp_path, CombiningAgent(), automatic_space=True, budget=sera.Budget(max_candidate_trials=3)) as result:
        combination = result.report['search_trials'][-1]
        assert combination['component_trial_ids'] == ['trial-1', 'trial-2']
        assert combination['parent_trial_id'] == 'trial-1'
        assert combination['decision']['objective_improvement_fraction'] == .4
        assert result.report['decision']['selected'] == 'trial-3'
        assert result.models[0].configuration.enable_prefix_caching is True
        assert result.models[0].configuration.enforce_eager is False
