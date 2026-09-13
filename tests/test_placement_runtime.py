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


def test_gpu_pid_resolving_to_container_init_is_not_usable_accounting(monkeypatch):
    import sera.placement_runtime as runtime
    monkeypatch.setattr(runtime.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(stdout='test-gpu, 1, 2746\n'))
    monkeypatch.setattr(runtime.os, 'getpgid', lambda pid: 1)
    with pytest.raises(runtime.GPUProcessIdentityError) as failure:
        runtime.gpu_processes()
    assert failure.value.diagnostic == {
        'reported_pid': 1, 'local_process_group': 1,
        'reason': 'reported-pid-is-namespace-init',
        'namespace_mismatch': 'possible-not-proven',
    }


def test_missing_gpu_pid_reports_unresolved_identity_not_assumed_process_exit(monkeypatch):
    import sera.placement_runtime as runtime
    monkeypatch.setattr(runtime.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(stdout='test-gpu, 12345, 2746\n'))
    def missing(pid):
        raise ProcessLookupError(pid)
    monkeypatch.setattr(runtime.os, 'getpgid', missing)
    with pytest.raises(runtime.GPUProcessIdentityError) as failure:
        runtime.gpu_processes()
    assert failure.value.diagnostic['reason'] == 'reported-pid-not-visible'


def test_normal_gpu_child_identity_retains_exact_memory(monkeypatch):
    import sera.placement_runtime as runtime
    monkeypatch.setattr(runtime.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(stdout='test-gpu, 12345, 2746\n'))
    monkeypatch.setattr(runtime.os, 'getpgid', lambda pid: 12300)
    assert runtime.gpu_processes() == [dict(uuid='test-gpu', pid=12345,
                                          process_group=12300, used_mib=2746)]


def test_identity_failure_is_saved_and_cannot_certify_service_cleanup(owned, monkeypatch):
    runtime, owner, _, _ = owned
    def unresolved():
        raise runtime.GPUProcessIdentityError(1, 1, 'reported-pid-is-namespace-init')
    monkeypatch.setattr(runtime, 'gpu_processes', unresolved)
    with pytest.raises(RuntimeError):
        owner.check()
    assert 'gpu-process-identity-unresolved' in owner.record['errors']
    assert owner.record['process_identity_errors'][0]['reported_pid'] == 1
    first = owner.models[0]
    with pytest.raises(CleanupError, match='identity'):
        owner.verify_service_cleanup(first)
    assert first.record['cleanup_pass'] is False


def test_unresolved_gpu_identity_still_attempts_both_closes(owned, monkeypatch):
    runtime, owner, _, _ = owned
    calls = []
    def unresolved():
        raise runtime.GPUProcessIdentityError(1, 1, 'reported-pid-is-namespace-init')
    monkeypatch.setattr(runtime, 'gpu_processes', unresolved)
    def close(model):
        calls.append(model.model_id)
        owner.verify_service_cleanup(model)
    for model in owner.models:
        model.close = lambda model=model: close(model)
    with pytest.raises(CleanupError):
        owner.close()
    assert set(calls) == {MODEL_ID, GLM_MODEL_ID}
    assert owner.record['cleanup_pass'] is False
    assert 'cleanup-accounting-GPUProcessIdentityError' in owner.record['cleanup_errors']


@pytest.fixture
def total_owned(monkeypatch):
    import sera.placement_runtime as runtime
    owner = runtime.SharedGPUOwner(validate_placement_plan(plan_data()), memory_accounting='total-device')
    owner.record.update(status='active', gpu={'uuid':'test-gpu'}, memory_before_mib=0)
    owner.groups = {MODEL_ID:100, GLM_MODEL_ID:200}
    owner.models = [SimpleNamespace(model_id=model, record={'status':'ready'}) for model in owner.groups]
    snapshot = dict(uuid='test-gpu', used_mib=600, total_mib=1000)
    rows = [dict(uuid='test-gpu', pid=1, used_mib=600)]
    monkeypatch.setattr(runtime, 'gpu_snapshot', lambda: snapshot)
    monkeypatch.setattr(runtime, 'gpu_process_rows', lambda: rows)
    monkeypatch.setattr(runtime.os, 'getpgid', lambda pid: pid)
    return runtime, owner, snapshot, rows


def test_accounting_mode_must_be_explicit_and_known():
    from sera.placement_runtime import SharedGPUOwner
    assert SharedGPUOwner(plan_data()).memory_accounting == 'per-service'
    with pytest.raises(ValueError, match='accounting'):
        SharedGPUOwner(plan_data(), memory_accounting='auto')


def test_total_device_mode_accepts_unmapped_pid_without_inventing_service_memory(total_owned):
    _, owner, _, _ = total_owned
    owner.check()
    assert owner.record['memory_accounting'] == 'total-device'
    assert owner.record['service_peak_memory_mib'] == {MODEL_ID:None, GLM_MODEL_ID:None}
    assert owner.record['sampled_peak_memory_mib'] == 600
    assert owner.record['per_service_memory_verified'] is False
    assert owner.record['unresolved_gpu_processes'][0]['pid'] == 1
    assert all(model.record['sampled_peak_memory_mib'] is None for model in owner.models)


@pytest.mark.parametrize('field,value', [('used_mib',801), ('uuid','other-gpu'),
                                        ('total_mib',999), ('used_mib',-1)])
def test_total_device_mode_preserves_device_limits_and_identity(total_owned, field, value):
    _, owner, snapshot, _ = total_owned
    snapshot[field] = value
    with pytest.raises(RuntimeError):
        owner.check()


def test_total_device_rejects_identifiable_unrelated_gpu_process(total_owned):
    _, owner, _, rows = total_owned
    rows.append(dict(uuid='test-gpu', pid=900, used_mib=1))
    with pytest.raises(RuntimeError):
        owner.check()
    assert 'unrelated-gpu-process' in owner.record['errors']


def test_total_device_query_failure_remains_fatal(total_owned, monkeypatch):
    runtime, owner, _, _ = total_owned
    def unavailable():
        raise ValueError('N/A')
    monkeypatch.setattr(runtime, 'gpu_process_rows', unavailable)
    with pytest.raises(RuntimeError):
        owner.check()
    assert owner.record['telemetry_errors'] == 1


def test_total_device_invisible_pid_is_a_declared_limit_not_fake_ownership(total_owned, monkeypatch):
    runtime, owner, _, rows = total_owned
    rows[0]['pid'] = 54321
    def missing(pid):
        raise ProcessLookupError(pid)
    monkeypatch.setattr(runtime.os, 'getpgid', missing)
    owner.check()
    assert owner.record['unresolved_gpu_processes'][0]['pid'] == 54321
    assert owner.record['last_processes'][0]['process_group'] is None


@pytest.mark.parametrize('busy', [False, True])
def test_total_device_acquisition_keeps_idle_check_and_exclusive_lock(total_owned, monkeypatch, tmp_path, busy):
    runtime, owner, snapshot, rows = total_owned
    snapshot['used_mib'] = 0
    if not busy:
        rows.clear()
    lock = tmp_path/'owner.lock'
    monkeypatch.setattr(runtime, 'Path', lambda _: lock)
    if busy:
        with pytest.raises(RuntimeError, match='already in use'):
            owner.acquire()
        assert owner._lock_file is None
    else:
        owner.acquire()
        competitor = runtime.SharedGPUOwner(plan_data(), memory_accounting='total-device')
        try:
            with pytest.raises(BlockingIOError):
                competitor.acquire()
            assert competitor._lock_file is None
        finally:
            owner._release_lock()


def test_total_device_rechecks_idle_memory_after_acquiring_lock(total_owned, monkeypatch, tmp_path):
    runtime, owner, snapshot, rows = total_owned
    rows.clear()
    samples = iter([dict(snapshot, used_mib=0), dict(snapshot, used_mib=129)])
    monkeypatch.setattr(runtime, 'gpu_snapshot', lambda: next(samples))
    monkeypatch.setattr(runtime, 'Path', lambda _: tmp_path/'owner.lock')
    with pytest.raises(RuntimeError, match='already in use'):
        owner.acquire()
    assert owner._lock_file is None


def test_total_device_service_cleanup_checks_local_group_and_defers_gpu_release(total_owned, monkeypatch):
    runtime, owner, _, _ = total_owned
    def signal(group, value):
        assert value == 0
        assert group in owner.groups.values()
        raise ProcessLookupError(group)
    monkeypatch.setattr(runtime.os, 'killpg', signal)
    owner.verify_service_cleanup(owner.models[0])
    record = owner.models[0].record
    assert record['cleanup_pass'] is True
    assert record['owned_local_process_group_released'] is True
    assert record['gpu_release_verification'] == 'deferred-to-owner-final-close'


@pytest.mark.parametrize('remaining', ['gpu-row', 'device-memory', 'local-group', None])
def test_total_device_final_cleanup_requires_all_three_release_checks(total_owned, monkeypatch, remaining):
    runtime, owner, snapshot, rows = total_owned
    calls = []
    for model in owner.models:
        model.close = lambda model=model: calls.append(model.model_id)
    if remaining != 'gpu-row':
        rows.clear()
    snapshot['used_mib'] = 129 if remaining == 'device-memory' else 0
    def signal(group, value):
        assert group in owner.groups.values() and value == 0
        if remaining != 'local-group':
            raise ProcessLookupError(group)
    monkeypatch.setattr(runtime.os, 'killpg', signal)
    tick = iter([0, 20, 40, 60, 80, 100])
    monkeypatch.setattr(runtime.time, 'monotonic', lambda: next(tick))
    if remaining is None:
        owner.close()
    else:
        with pytest.raises(CleanupError):
            owner.close()
    assert owner.record['cleanup_pass'] is (remaining is None)
    assert set(calls) == {MODEL_ID, GLM_MODEL_ID}


def test_total_device_cleanup_query_error_cannot_pass_or_skip_either_close(total_owned, monkeypatch):
    runtime, owner, _, _ = total_owned
    calls = []
    for model in owner.models:
        model.close = lambda model=model: calls.append(model.model_id)
    def no_group(group, signal):
        raise ProcessLookupError(group)
    monkeypatch.setattr(runtime.os, 'killpg', no_group)
    def unavailable():
        raise ValueError('N/A')
    monkeypatch.setattr(runtime, 'gpu_process_rows', unavailable)
    with pytest.raises(CleanupError):
        owner.close()
    assert owner.record['cleanup_pass'] is False
    assert set(calls) == {MODEL_ID, GLM_MODEL_ID}
    assert 'cleanup-accounting-ValueError' in owner.record['cleanup_errors']
