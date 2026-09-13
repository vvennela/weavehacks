import pytest

from experiments.audit_codex_fit_run import require_completed_run


def test_completed_saved_run_is_closed_and_traced():
    require_completed_run({'status': 'closed', 'trace_status': 'enabled',
                           'swarm_enabled': True, 'returned_runner_closed': True})


@pytest.mark.parametrize('change', [
    {'status': 'ready'}, {'status': 'failed'}, {'trace_status': 'failed'},
    {'swarm_enabled': False}, {'returned_runner_closed': False},
])
def test_incomplete_or_untraced_run_is_not_accepted(change):
    report = {'status': 'closed', 'trace_status': 'enabled', 'swarm_enabled': True,
              'returned_runner_closed': True} | change
    with pytest.raises(ValueError, match='closed, traced swarm result'):
        require_completed_run(report)
