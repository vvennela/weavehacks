"""Shared ownership tests never query or signal a real GPU process."""

from types import SimpleNamespace
import pytest

from sera.placement_config import validate_placement_plan
from sera.runtime import CleanupError
from test_placement import plan_data, MODEL_ID, GLM_MODEL_ID


@pytest.fixture
def owned(monkeypatch):
    import sera.placement_runtime as runtime
    owner = runtime.SharedGPUOwner(validate_placement_plan(plan_data()))
    owner.record.update(status='active', gpu={'uuid':'test-gpu'}, memory_before_mib=0)
    owner.groups = {MODEL_ID:100, GLM_MODEL_ID:200}
    owner.models = [SimpleNamespace(model_id=model, record={}) for model in owner.groups]
    snapshot = dict(uuid='test-gpu', used_mib=200, total_mib=1000)
    processes = [dict(uuid='test-gpu', pid=101, process_group=100, used_mib=100),
                 dict(uuid='test-gpu', pid=202, process_group=200, used_mib=100)]
    monkeypatch.setattr(runtime, 'gpu_snapshot', lambda: snapshot)
    monkeypatch.setattr(runtime, 'gpu_processes', lambda: processes)
    return runtime, owner, snapshot, processes


def test_child_pids_are_owned_by_group_and_peaks_are_not_device_memory(owned):
    _, owner, _, _ = owned
    owner.check()
    assert owner.record['sampled_peak_memory_mib'] == 200
    assert owner.record['service_peak_memory_mib'] == {MODEL_ID:100, GLM_MODEL_ID:100}
    assert all(model.record['sampled_peak_memory_mib'] == 100 for model in owner.models)


def test_unrelated_gpu_process_is_rejected_without_any_signal(owned):
    _, owner, _, processes = owned
    processes.append(dict(uuid='test-gpu', pid=900, process_group=900, used_mib=1))
    with pytest.raises(RuntimeError, match='ownership'):
        owner.check()
    assert 'unrelated-gpu-process' in owner.record['errors']


def test_service_budget_fails_even_when_total_device_budget_passes(owned):
    _, owner, snapshot, processes = owned
    processes[0]['used_mib'] = 201
    snapshot['used_mib'] = 301
    with pytest.raises(RuntimeError):
        owner.check()
    assert 'service-budget-exceeded:' + MODEL_ID in owner.record['errors']


def test_accounting_failure_cannot_pass(owned, monkeypatch):
    runtime, owner, _, _ = owned
    def unavailable():
        raise ValueError('N/A')
    monkeypatch.setattr(runtime, 'gpu_processes', unavailable)
    with pytest.raises(RuntimeError):
        owner.check()
    assert owner.record['telemetry_errors'] == 1


def test_cleanup_accepts_live_peer_but_checks_the_owned_group(owned):
    _, owner, _, processes = owned
    first = owner.models[0]
    processes.pop(0)
    owner.verify_service_cleanup(first)
    assert first.record['cleanup_pass'] is True
    assert first.record['memory_after_mib'] == 200
    assert owner.service_released(owner.models[1]) is False


def test_close_attempts_both_services_after_cleanup_error(owned):
    _, owner, _, processes = owned
    calls = []
    def close(model_id):
        calls.append(model_id)
        if model_id == GLM_MODEL_ID:
            raise CleanupError('failed')
    for model in owner.models:
        model.close = lambda model_id=model.model_id: close(model_id)
    processes.clear()
    with pytest.raises(CleanupError):
        owner.close()
    assert set(calls) == {MODEL_ID, GLM_MODEL_ID}
    assert owner.record['cleanup_pass'] is False


def test_ready_check_uses_saved_monitor_state_without_latency_probe(owned, monkeypatch):
    _, owner, _, _ = owned
    monkeypatch.setattr(owner, 'sample', lambda: pytest.fail('sampling inside request path'))
    owner.ensure_healthy()
    owner.record['errors'].append('memory-accounting-unavailable')
    with pytest.raises(RuntimeError):
        owner.ensure_healthy()


def test_large_unattributed_device_memory_is_rejected(owned):
    _, owner, snapshot, _ = owned
    snapshot['used_mib'] = 400
    with pytest.raises(RuntimeError):
        owner.check()
    assert 'unattributed-device-memory' in owner.record['errors']


def test_runtime_delegates_busy_gpu_and_cleanup_to_registered_owner(monkeypatch, tmp_path):
    from sera import runtime
    calls = []
    class Owner:
        def before_start(self, model, gpu):
            calls.append('before')
            assert gpu['used_mib'] == 500
        def register(self, model):
            calls.append('register')
            assert model.process.pid == 123
        def ensure_healthy(self):
            calls.append('check')
        def verify_service_cleanup(self, model):
            calls.append('cleanup')
            assert model.record['status'] == 'closing'
            model.record.update(cleanup_pass=True, memory_after_mib=500)
    class Thread:
        def __init__(self, **kwargs):
            pass
        def start(self):
            pass
        def join(self, **kwargs):
            pass
    process = SimpleNamespace(pid=123, poll=lambda: None,
                              terminate=lambda: calls.append('terminate'), wait=lambda **_:0)
    monkeypatch.setattr(runtime.sys, 'platform', 'linux')
    monkeypatch.setattr(runtime.importlib.metadata, 'version', lambda _: '0.26.0')
    monkeypatch.setattr(runtime, 'gpu_snapshot', lambda:dict(used_mib=500, uuid='test', compute_capability='12.0'))
    monkeypatch.setattr(runtime, '_child_environment', lambda *_:{})
    monkeypatch.setattr(runtime.subprocess, 'Popen', lambda *args, **kwargs:process)
    monkeypatch.setattr(runtime.threading, 'Thread', Thread)
    monkeypatch.setattr(runtime.os, 'killpg', lambda pid, signal:calls.append(('signal', pid)))
    monkeypatch.setattr(runtime.SeraModel, '_request', lambda *args, **kwargs:{})
    model = runtime.SeraModel(artifact_dir=tmp_path/'service', placement_owner=Owner())
    model.start()
    model._require_ready()
    model.close()
    assert calls[:3] == ['before', 'register', 'check']
    assert 'cleanup' in calls
    assert model.record['cleanup_pass'] is True
    assert model.record['status'] == 'closed'
    assert all(item[1] == 123 for item in calls if isinstance(item, tuple))


def test_ready_service_without_attributed_gpu_memory_cannot_pass(owned):
    _, owner, _, processes = owned
    owner.models[0].record['status'] = 'ready'
    processes.pop(0)
    with pytest.raises(RuntimeError):
        owner.check()
    assert 'ready-service-accounting-missing:' + MODEL_ID in owner.record['errors']
