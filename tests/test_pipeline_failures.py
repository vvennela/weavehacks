"""Error reporting must not prevent cleanup or hide the original failure."""

import pytest

from sera import pipeline
from test_investigation import install_fakes, run


def test_final_save_failure_does_not_mask_controller_failure(tmp_path, monkeypatch):
    runners, _, agent = install_fakes(monkeypatch)
    save = pipeline.SeraResult._save

    def fail_setup(*args, **kwargs):
        raise LookupError('fixture evidence failure')

    def fail_final_save(result):
        if result.report['status'] == 'failed':
            raise OSError('fixture persistence failure')
        save(result)

    monkeypatch.setattr(pipeline, 'agent_evidence', fail_setup)
    monkeypatch.setattr(pipeline.SeraResult, '_save', fail_final_save)
    with pytest.raises(LookupError, match='fixture evidence failure'):
        run(tmp_path, agent)
    assert len(runners) == 1
    assert not any(runner.ready for runner in runners)
