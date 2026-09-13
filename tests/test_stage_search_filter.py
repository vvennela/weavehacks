"""Stage filters constrain candidate generation, not model quality requirements."""

from copy import deepcopy

import pytest

from sera.config import LARGE_MODEL_ID, MODEL_ID, RuntimeConfig, Workload
from sera.search_policy import expand_search_space, validate_investigation_controls
from test_expanding_search import measured
from test_investigation import install_fakes, run


def expand(reference=None, trials=(), controls=None):
    baseline = reference or measured()
    return expand_search_space(baseline, list(trials),
        model_id=baseline['runtime']['model_id'], workload=Workload(),
        investigation_controls=controls)


def test_none_preserves_existing_policy_exactly():
    baseline = measured()
    original = expand_search_space(baseline, [], model_id=MODEL_ID, workload=Workload())
    assert expand(baseline) == original


def test_cache_only_filters_pool_without_changing_candidate_identity():
    original = expand()
    filtered = expand(controls=('kv_cache_dtype',))
    expected = [item for item in original['candidates']
                if item['changed'] == {'kv_cache_dtype': 'fp8'}]
    assert filtered['candidates'] == expected
    assert filtered['space']['supported_changes'] == {'kv_cache_dtype': ['fp8']}
    assert filtered['space']['candidate_hashes'] == [item['config_hash'] for item in expected]
    assert filtered['candidate_parents'] == original['candidate_parents']
    assert filtered['candidate_filter']['allowed_controls'] == ['kv_cache_dtype']
    assert filtered['candidate_filter']['excluded_candidate_count'] > 0


def test_combination_cannot_inherit_a_disallowed_change():
    batch = measured(RuntimeConfig(max_num_batched_tokens=2048), trial_id='batch')
    cache = measured(RuntimeConfig(kv_cache_dtype='fp8'), trial_id='cache')
    original = expand(trials=[batch, cache])
    assert any(option['changed'] == {'kv_cache_dtype': 'fp8'}
               and option['parent_trial_id'] == 'batch' for option in original['candidates'])
    filtered = expand(trials=[batch, cache], controls=['kv_cache_dtype'])
    assert filtered['candidates'] == []
    assert filtered['space'] is None
    assert filtered['status'] == 'no-candidate'
    assert 'batch' not in filtered['candidate_parents']


def test_allowed_combinations_keep_hashes_and_parent_provenance():
    prefix = measured(RuntimeConfig(enable_prefix_caching=True), trial_id='prefix')
    graphs = measured(RuntimeConfig(enforce_eager=False), trial_id='graphs')
    original = expand(trials=[prefix, graphs])
    filtered = expand(trials=[prefix, graphs], controls=['enable_prefix_caching', 'enforce_eager'])
    assert filtered['candidates'] == [item for item in original['candidates']
                                    if len(item['component_trial_ids']) == 2]
    for option in filtered['candidates']:
        parent_id = option['parent_trial_id']
        assert filtered['candidate_parents'][parent_id] == original['candidate_parents'][parent_id]


@pytest.mark.parametrize('controls', [[], ['kv_cache_dtype']])
def test_empty_pool_is_not_a_policy_error(controls):
    reference = measured(RuntimeConfig(quantization='fp8_per_tensor'))
    reference['runtime']['model_id'] = LARGE_MODEL_ID
    policy = expand(reference, controls=controls)
    assert policy['status'] == 'no-candidate'
    assert policy['space'] is None
    assert policy['candidates'] == []
    assert policy['candidate_filter']['allowed_controls'] == controls


@pytest.mark.parametrize('controls', ['kv_cache_dtype', {'kv_cache_dtype'}, ['quantization'], [None]])
def test_filter_rejects_unknown_controls_and_wrong_container(controls):
    with pytest.raises(ValueError, match='investigation_controls'):
        expand(controls=controls)


def test_allowlist_is_canonical_and_preserves_empty_scope():
    assert validate_investigation_controls(None) is None
    assert validate_investigation_controls([]) == ()
    assert validate_investigation_controls(
        ['max_model_len', 'kv_cache_dtype', 'max_model_len']) == ('kv_cache_dtype', 'max_model_len')


def install_filter(monkeypatch, controls):
    """Exercise the low-level contract before pipeline argument threading lands."""
    from sera import investigation
    original = investigation.investigate

    def filtered(**kwargs):
        kwargs['investigation_controls'] = controls
        return original(**kwargs)

    monkeypatch.setattr(investigation, 'investigate', filtered)


def test_cache_stage_stops_when_its_only_candidate_is_tested(tmp_path, monkeypatch):
    runners, seen, agent = install_fakes(monkeypatch)
    install_filter(monkeypatch, ['kv_cache_dtype'])
    with run(tmp_path, agent, automatic_space=True) as result:
        assert result.report['search']['trials_used'] == 1
        assert result.report['search']['stop_reason'] == 'no-legal-untested-candidate'
        assert result.report['investigation_controls'] == ['kv_cache_dtype']
        assert result.models[0].configuration == RuntimeConfig()
        assert all(model.configuration.max_num_batched_tokens == 4096 for model in runners)
        for role, evidence in seen:
            if role not in {'proposal', 'arbiter'}:
                continue
            assert set(evidence['supported_changes']) == {'kv_cache_dtype'}
            assert evidence['investigation_controls'] == ['kv_cache_dtype']
            assert all(option['changed'] == {'kv_cache_dtype': 'fp8'}
                       for option in evidence['candidate_options'])


@pytest.mark.parametrize('automatic', [False, True])
def test_empty_stage_returns_baseline_without_agent_or_candidate_start(tmp_path, monkeypatch, automatic):
    runners, seen, agent = install_fakes(monkeypatch)
    install_filter(monkeypatch, [])
    with run(tmp_path, agent, automatic_space=automatic) as result:
        assert result.report['search']['stop_reason'] == 'no-legal-untested-candidate'
        assert result.report['search']['trials_used'] == 0
        assert result.report['decision']['selected'] == 'baseline'
        assert result.report['status'] == 'ready'
        assert len(runners) == 1 and runners[0].ready
        assert seen == []
        assert result.report['investigation_controls'] == []


def test_policy_filter_does_not_modify_measured_history():
    trial = measured(RuntimeConfig(max_num_batched_tokens=2048), trial_id='batch')
    before = deepcopy(trial)
    expand(trials=[trial], controls=['kv_cache_dtype'])
    assert trial == before


def test_disallowed_provider_proposal_never_reaches_arbiter_or_runner(tmp_path, monkeypatch):
    runners, seen, agent = install_fakes(monkeypatch)
    request = agent.request

    def propose_disallowed(role, evidence, instruction):
        response = request(role, evidence, instruction)
        if role == 'proposal':
            return response.model_copy(update={
                'changed_lever': 'gpu_memory_utilization', 'proposed_value': .85})
        return response

    agent.request = propose_disallowed
    install_filter(monkeypatch, ['kv_cache_dtype'])
    with run(tmp_path, agent, automatic_space=True) as result:
        assert result.report['search']['trials_used'] == 0
        assert result.report['search']['stop_reason'] == 'no-valid-selected-proposal'
        assert result.rejected[0]['stage'] == 'proposal-validation'
        assert not any(role == 'arbiter' for role, _ in seen)
        assert len(runners) == 1 and runners[0].ready


def test_each_batching_round_exposes_only_allowed_options(tmp_path, monkeypatch):
    import sera

    _, seen, agent = install_fakes(monkeypatch)
    install_filter(monkeypatch, ['max_num_batched_tokens'])
    with run(tmp_path, agent, automatic_space=True,
             budget=sera.Budget(max_candidate_trials=3)) as result:
        rounds = result.report['search']['rounds']
        assert len(rounds) >= 2
        for record in rounds:
            assert record['candidate_policy']['candidate_filter']['allowed_controls'] == ['max_num_batched_tokens']
        for role, evidence in seen:
            if role not in {'proposal', 'arbiter'}:
                continue
            assert set(evidence['supported_changes']) == {'max_num_batched_tokens'}
            for option in evidence['candidate_options']:
                changed = {key for key, value in option['configuration'].items()
                           if value != result.report['baseline_configuration'][key]}
                assert changed == {'max_num_batched_tokens'}
