
from benchmarks.native_search import FixedPolicy, RandomPolicy, plan_blocks, summarize


def evidence():
    return {'available_recipes': [
        {'recipe_id': 'eight', 'recipe': {'bits': 8, 'group_size': 64}},
        {'recipe_id': 'four-small', 'recipe': {'bits': 4, 'group_size': 32}},
        {'recipe_id': 'four-large', 'recipe': {'bits': 4, 'group_size': 128}}]}


def test_fixed_policy_prioritizes_memory_without_using_hidden_outcomes():
    policy = FixedPolicy()
    assert policy.propose(evidence(), timeout_seconds=1).recipe_id == 'four-large'
    assert len(policy.history) == 1
    assert 'evidence' in policy.history[0]


def test_random_is_seeded_and_only_selects_available_candidates():
    left, right = RandomPolicy(7), RandomPolicy(7)
    value = evidence()
    for _ in range(3):
        a = left.propose(value, timeout_seconds=1).recipe_id
        assert a == right.propose(value, timeout_seconds=1).recipe_id
        value['available_recipes'] = [x for x in value['available_recipes'] if x['recipe_id'] != a]


def test_blocks_rotate_order_for_time_drift():
    assert plan_blocks(3) == [['sera', 'fixed', 'random'], ['fixed', 'random', 'sera'], ['random', 'sera', 'fixed']]


def test_summary_cannot_claim_win_from_missing_or_failed_pairs():
    rows = [{'block': 0, 'policy': 'sera', 'status': 'completed', 'memory_fraction': 0.4,
             'wall_seconds': 10, 'heldout_passed': True},
            {'block': 0, 'policy': 'fixed', 'status': 'failed'}]
    result = summarize(rows, blocks=3)
    assert result['complete'] is False
    assert result['sera_beats_fixed'] is None


def test_summary_reports_tie_and_includes_agent_time():
    rows = [{'block': block, 'policy': policy, 'status': 'completed', 'heldout_passed': True,
                 'memory_fraction': 0.4, 'wall_seconds': 20 if policy == 'sera' else 10}
            for block in range(3) for policy in ['sera','fixed','random']]
    result = summarize(rows, blocks=3)
    assert result['complete'] is True
    assert result['sera_beats_fixed'] is False
    assert result['policy_summary']['sera']['median_wall_seconds'] == 20


def test_heldout_gate_rejects_invalid_quality_and_uses_heldout_constraints(monkeypatch):
    from types import SimpleNamespace

    from benchmarks import native_search as search
    profile = SimpleNamespace(constraints='heldout-constraints',
                              retention=SimpleNamespace(quality=.95, throughput=.95))
    monkeypatch.setattr(search, 'objective_value', lambda trial, metric: trial[metric])
    monkeypatch.setattr(search, 'constraint_failures',
                        lambda trial, constraints: [] if constraints == 'heldout-constraints' else ['wrong'])
    good = {'memory': 100, 'throughput': 10,
            'task_quality': {'mean': 1., 'passed': True, 'valid_outputs': True}}
    bad = {**good, 'task_quality': {'mean': 1., 'passed': False, 'valid_outputs': False}}
    assert search.heldout_passes(good, good, profile)
    assert not search.heldout_passes(good, bad, profile)
    assert not search.heldout_passes(good, {**good, 'memory': None}, profile)
    assert not search.heldout_passes(good, {**good, 'throughput': 9.4}, profile)
