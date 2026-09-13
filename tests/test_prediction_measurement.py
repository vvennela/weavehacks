"""A failed launch attempts an experiment but does not measure its latency claim."""

import pytest

from sera.agent import FrontierDecision
from test_investigation import install_fakes, run
from test_fit_investigation import boundaries, run as run_fit


def test_unmeasured_startup_failure_can_be_reviewed_as_not_tested(tmp_path, monkeypatch):
    _, _, agent = install_fakes(monkeypatch, startup_failure=True)
    original_review = agent.review
    def review(evidence):
        if evidence['candidate_status'] == 'startup-failed':
            return FrontierDecision(selected_trial_id=evidence['eligible_trial_ids'][0],
                prediction_outcome='not-tested', reason='The launch failed before latency measurement.')
        return original_review(evidence)
    agent.review = review
    with run(tmp_path, agent) as result:
        failed = result.trials[1]
        assert failed['review']['prediction_outcome'] == 'not-tested'
        assert 'review_error' not in failed
        assert failed['review_evidence']['candidate_attempted'] is True
        assert failed['review_evidence']['candidate_measured'] is False
        assert failed['review_evidence']['candidate_tested'] is False


def test_measured_performance_cannot_be_called_not_tested(tmp_path, monkeypatch):
    _, _, agent = install_fakes(monkeypatch)
    agent.review = lambda evidence: FrontierDecision(selected_trial_id=evidence['eligible_trial_ids'][0],
        prediction_outcome='not-tested', reason='Unsupported missing measurement claim')
    with run(tmp_path, agent) as result:
        assert result.trials[1]['review_error'] == 'ValueError'
        assert result.trials[1]['review_evidence']['candidate_measured'] is True


def test_unmeasured_startup_cannot_confirm_performance(tmp_path, monkeypatch):
    _, _, agent = install_fakes(monkeypatch, startup_failure=True)
    agent.review = lambda evidence: FrontierDecision(selected_trial_id=evidence['eligible_trial_ids'][0],
        prediction_outcome='confirmed', reason='Unsupported speedup claim')
    with run(tmp_path, agent) as result:
        assert result.trials[1]['review_error'] == 'ValueError'


@pytest.mark.parametrize('outcome', ['not-tested', 'confirmed', 'refuted'])
def test_failed_deployment_feasibility_still_requires_refutation(tmp_path, monkeypatch, outcome):
    from sera import fit
    _, _, agent = boundaries(monkeypatch)
    def fail(*_):
        raise RuntimeError('fixture launch failure')
    monkeypatch.setattr(fit.SeraModel, 'start', fail)
    agent.review = lambda evidence: FrontierDecision(selected_trial_id=evidence['eligible_trial_ids'][0],
        prediction_outcome=outcome, reason='The deployment was attempted and failed')
    with run_fit(tmp_path, agent) as result:
        assert ('agent_final_error' in result.report) is (outcome != 'refuted')
