"""An earlier fit trial consumes the shared budget before investigation starts."""

import pytest

from sera import investigation
from test_investigation import install_fakes, run


def seed_budget(monkeypatch, value):
    original = investigation.investigate

    def seeded(**kwargs):
        return original(**kwargs, initial_trials_used=value)

    monkeypatch.setattr(investigation, 'investigate', seeded)


def test_prior_trial_leaves_only_one_candidate_slot(tmp_path, monkeypatch):
    _, seen, agent = install_fakes(monkeypatch)
    seed_budget(monkeypatch, 1)
    with run(tmp_path, agent) as result:
        search = result.report['search']
        assert search['initial_trials_used'] == 1
        assert search['trials_used'] == 2
        assert search['stop_reason'] == 'budget-exhausted'
        assert len(result.report['search_trials']) == 1
        assert result.report['search_trials'][0]['trial_id'] == 'trial-2'
        assert all(evidence['remaining_trials'] == 1
                   for role, evidence in seen if role == 'proposal')


def test_spent_budget_returns_same_eligible_runner_without_call_or_reload(tmp_path, monkeypatch):
    runners, seen, agent = install_fakes(monkeypatch)
    seed_budget(monkeypatch, 2)
    with run(tmp_path, agent) as result:
        assert result.report['search']['trials_used'] == 2
        assert result.report['search']['rounds'] == []
        assert result.report['search_trials'] == []
        assert result.report['search']['stop_reason'] == 'budget-exhausted'
        assert seen == []
        assert len(runners) == 1
        assert result.models == runners and runners[0].ready


@pytest.mark.parametrize('value', [-1, 3, True, 1.0, '1'])
def test_invalid_seed_rejects_and_closes_transferred_runtime(tmp_path, monkeypatch, value):
    runners, seen, agent = install_fakes(monkeypatch)
    seed_budget(monkeypatch, value)
    with pytest.raises(ValueError):
        run(tmp_path, agent)
    assert seen == []
    assert len(runners) == 1
    assert not runners[0].ready
