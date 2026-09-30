"""A required trace is complete only after the saved call is read back."""

from types import SimpleNamespace

import pytest

from sera.native_trace import trace_native_job


class Client:
    def __init__(self, *, flush_fails=False, stored=True):
        self.flush_fails = flush_fails
        self.stored = stored

    def flush(self):
        if self.flush_fails:
            raise RuntimeError('fixture export failure')

    def get_calls(self, **kwargs):
        return [SimpleNamespace(id='call', ended_at=1, exception=None)] if self.stored else []


def setup(monkeypatch, client):
    import sys
    call = SimpleNamespace(id='call', trace_id='trace', ui_url='https://wandb.ai/fixture')
    monkeypatch.setitem(sys.modules, 'weave', SimpleNamespace(
        init=lambda project: client, get_client=lambda: None, get_current_call=lambda: call,
        op=lambda **kwargs: lambda function: function))
    monkeypatch.setenv('WANDB_API_KEY', 'fixture')


@pytest.mark.parametrize('client', [Client(flush_fails=True), Client(stored=False)])
def test_missing_remote_trace_does_not_return_verified_result(monkeypatch, client):
    setup(monkeypatch, client)
    with pytest.raises(RuntimeError):
        trace_native_job(project='fixture/project', run=lambda: {'measured': True})


def test_completed_remote_call_is_bound_to_returned_result(monkeypatch):
    setup(monkeypatch, Client())
    result = trace_native_job(project='fixture/project', run=lambda: {'measured': True})
    assert result['trace']['remote_verified'] is True
    assert result['trace']['call_id'] == 'call'
    assert result['result'] == {'measured': True}


def test_missing_key_fails_before_running_work(monkeypatch):
    monkeypatch.delenv('WANDB_API_KEY', raising=False)
    with pytest.raises(ValueError, match='operator'):
        trace_native_job(project='fixture/project', run=lambda: pytest.fail('No trace key'))


def test_active_matching_project_client_is_reused(monkeypatch):
    import sys
    client = Client()
    client.entity, client.project = 'fixture', 'project'
    setup(monkeypatch, client)
    weave = sys.modules['weave']
    weave.get_client = lambda: client
    weave.init = lambda project: pytest.fail('An active matching client must not be reinitialized')
    assert trace_native_job(project='fixture/project', run=lambda: 7)['result'] == 7
