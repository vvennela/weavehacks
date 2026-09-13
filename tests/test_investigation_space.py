"""Explicit candidate scopes do not silently broaden live defaults."""

from copy import deepcopy

import pytest

import sera
from sera.config import LARGE_MODEL_ID, MODEL_ID, SUPPORTED_CHANGES
from sera import pipeline


def resolve(space, *, model=MODEL_ID, baseline=None, workload=None):
    from sera.config import resolve_investigation_space
    return resolve_investigation_space(space, model_id=model,
        baseline=baseline or sera.RuntimeConfig(), workload=workload or sera.Workload())


def test_explicit_values_resolve_to_frozen_single_setting_candidates():
    old_defaults = deepcopy(SUPPORTED_CHANGES)
    space = sera.InvestigationSpace(supported_changes={
        'max_num_batched_tokens': [1024, 2048], 'max_num_seqs': [4]})
    resolved = resolve(space)
    expected = [sera.RuntimeConfig(max_num_batched_tokens=1024).config_hash,
                sera.RuntimeConfig(max_num_batched_tokens=2048).config_hash,
                sera.RuntimeConfig(max_num_seqs=4).config_hash]
    assert sorted(resolved['candidate_hashes']) == sorted(expected)
    assert resolved['supported_changes'] == space.supported_changes
    assert SUPPORTED_CHANGES == old_defaults


@pytest.mark.parametrize('changes', [
    {}, {'max_num_seqs': []}, {'max_num_seqs': [True]}, {'max_num_seqs': [4, 4]},
    {'max_num_seqs': [257]}, {'max_model_len': ['2048']},
    {'quantization': ['fp8_per_tensor']}, {'max_num_batched_tokens': list(range(1, 34))},
])
def test_invalid_or_unbounded_scope_fails(changes):
    with pytest.raises(ValueError):
        sera.InvestigationSpace(supported_changes=changes)


def test_hash_subset_cannot_add_or_duplicate_a_configuration():
    batch_hash = sera.RuntimeConfig(max_num_batched_tokens=2048).config_hash
    space = sera.InvestigationSpace(supported_changes={'max_num_batched_tokens': [1024, 2048]},
                                    candidate_hashes=[batch_hash])
    resolved = resolve(space)
    assert resolved['candidate_hashes'] == [batch_hash]
    assert resolved['supported_changes'] == {'max_num_batched_tokens': [2048]}
    with pytest.raises(ValueError, match='outside'):
        resolve(sera.InvestigationSpace(supported_changes=space.supported_changes,
                                       candidate_hashes=['0' * 64]))
    for hashes in [[], ['not-a-hash'], [batch_hash, batch_hash]]:
        with pytest.raises(ValueError):
            sera.InvestigationSpace(supported_changes=space.supported_changes, candidate_hashes=hashes)


@pytest.mark.parametrize('changes', [
    {'max_num_batched_tokens': [4096]},  # No change from the named parent.
    {'max_num_batched_tokens': [1]},     # Cannot cover eight sequences.
    {'max_num_seqs': [4]},              # Smaller than declared load.
])
def test_parent_and_workload_legality_are_checked_before_loading(changes):
    with pytest.raises(ValueError):
        resolve(sera.InvestigationSpace(supported_changes=changes),
                workload=sera.Workload(concurrency=[8]))


def test_unverified_large_weight_and_cache_combination_stays_disabled():
    with pytest.raises(ValueError, match='Combined FP8'):
        resolve(sera.InvestigationSpace(supported_changes={'kv_cache_dtype': ['fp8']}),
                model=LARGE_MODEL_ID, baseline=sera.RuntimeConfig(quantization='fp8_per_tensor'))


def test_scope_requires_explicit_agent_investigation_budget(tmp_path):
    with pytest.raises(ValueError, match='budget'):
        sera.optimize(models=[MODEL_ID], prompts=['question'], output_dir=tmp_path/'invalid',
            investigation_space=sera.InvestigationSpace(supported_changes={'max_num_seqs': [4]}))
    assert not (tmp_path/'invalid').exists()


def test_scope_is_saved_and_passed_to_controller_without_changing_defaults(tmp_path, monkeypatch):
    # Reuse the existing offline boundary fixtures; no actual API or GPU calls.
    from test_investigation import install_fakes
    _, _, agent = install_fakes(monkeypatch)
    supplied = {}

    def inspect_controller(*, result, active, **kwargs):
        supplied.update(result.report['investigation_space'])
        active.close()
        return result

    monkeypatch.setattr('sera.investigation.investigate', inspect_controller)
    sera.optimize(models=[MODEL_ID], prompts=['question'], output_dir=tmp_path/'explicit',
        evaluation=lambda prompt, output: True, evaluation_version='fixture-v1',
        constraints=sera.Constraints(quality_floor=.99), agent=agent, provider_check='fixture',
        budget=sera.Budget(max_candidate_trials=2),
        investigation_space=sera.InvestigationSpace(supported_changes={'max_num_batched_tokens': [1024, 2048]}))
    assert supplied['supported_changes'] == {'max_num_batched_tokens': [1024, 2048]}
    assert len(supplied['candidate_hashes']) == 2


def test_explicit_pool_runs_only_selected_unseen_candidates(tmp_path, monkeypatch):
    from test_investigation import install_fakes
    runners, seen, agent = install_fakes(monkeypatch)
    options = sera.InvestigationSpace(supported_changes={'max_num_batched_tokens': [1024, 2048, 3072]})
    with sera.optimize(models=[MODEL_ID], prompts=['question'], output_dir=tmp_path/'pool',
        evaluation=lambda prompt, output: True, evaluation_version='fixture-v1',
        constraints=sera.Constraints(quality_floor=.99), agent=agent, provider_check='fixture',
        budget=sera.Budget(max_candidate_trials=2), investigation_space=options) as result:
        executed = result.report['search_trials']
        assert len(executed) == 2
        assert len({trial['config_hash'] for trial in executed}) == 2
        allowed = result.report['investigation_space']['candidate_hashes']
        assert len(allowed) == 3
        assert all(trial['config_hash'] in allowed for trial in executed)
        assert all(trial['runtime']['configuration']['kv_cache_dtype'] == 'auto' for trial in executed)
        proposals = [e for role, e in seen if role == 'proposal']
        assert len(proposals) == 2
        assert len(proposals[0]['frozen_candidate_hashes']) == 3
        assert len(proposals[1]['frozen_candidate_hashes']) == 2
        assert executed[0]['config_hash'] not in proposals[1]['frozen_candidate_hashes']
        assert options.supported_changes == {'max_num_batched_tokens': [1024, 2048, 3072]}
        summary = (tmp_path/'pool'/'report.md').read_text()
        assert '### Round 2' in summary
        assert 'Prediction:' in summary
