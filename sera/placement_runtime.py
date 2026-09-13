"""One owner for two registered vLLM process groups on GPU 0.

Unknown GPU processes are never terminated. Per-service memory is attributed by
process group; device memory is reported separately. Sampling can miss peaks.
"""

import os
from pathlib import Path
import subprocess
import threading
import time

from .placement_config import validate_placement_plan
from .runtime import CleanupError, gpu_snapshot


class GPUProcessIdentityError(RuntimeError):
    """Driver process identity cannot safely identify a local owned worker."""

    def __init__(self, pid, group, reason):
        self.diagnostic = dict(reported_pid=pid, local_process_group=group,
            reason=reason, namespace_mismatch='possible-not-proven')
        super().__init__('GPU process identity is unresolved; per-service memory cannot be verified')


def gpu_process_rows():
    """Read driver accounting without assuming its PID namespace is local."""
    output = subprocess.run(['nvidia-smi',
        '--query-compute-apps=gpu_uuid,pid,used_gpu_memory', '--format=csv,noheader,nounits'],
        capture_output=True, text=True, check=True, timeout=10).stdout
    processes = []
    for line in output.splitlines():
        uuid, pid, memory = [part.strip() for part in line.split(',')]
        pid, memory = int(pid), int(memory)
        if pid <= 0 or memory < 0:
            raise ValueError('Invalid GPU process accounting')
        processes.append(dict(uuid=uuid, pid=pid, used_mib=memory))
    return processes


def gpu_processes():
    processes = []
    for row in gpu_process_rows():
        pid = row['pid']
        try:
            group = os.getpgid(pid)
        except ProcessLookupError:
            # Either exit during sampling or an inaccessible driver PID namespace.
            raise GPUProcessIdentityError(pid, None, 'reported-pid-not-visible') from None
        if pid == 1:
            # A Sera-launched worker cannot be the init of our PID namespace.
            # Some sandboxes expose aggregated GPU usage under that identity.
            # Never assign it by launch order or assume it belongs to a service.
            raise GPUProcessIdentityError(pid, group, 'reported-pid-is-namespace-init')
        processes.append(dict(row, process_group=group))
    return processes


class SharedGPUOwner:
    def __init__(self, plan, *, memory_accounting='per-service'):
        if memory_accounting not in {'per-service', 'total-device'}:
            raise ValueError('Unknown placement memory accounting mode')
        self.memory_accounting = memory_accounting
        self.plan = validate_placement_plan(plan)
        self.models = []
        self.groups = {}
        self._lock_file = None
        self._mutex = threading.RLock()
        self.record = dict(status='not-started', errors=[], telemetry_errors=0,
            sampled_peak_memory_mib=0, service_peak_memory_mib={}, process_groups={},
            accounting='nvidia-smi compute processes attributed by owned process group',
            sample_interval_seconds=1, peak_limitations='Samples can miss short startup and request peaks.')
        self.record['memory_accounting'] = memory_accounting
        if memory_accounting == 'total-device':
            self.record.update(accounting='total NVIDIA device memory; local owned process groups',
                accounting_scope='total-device', per_service_memory_verified=False,
                service_allocation_semantics='configured-vllm-budget-not-verified-process-cap',
                accounting_limitations='GPU PIDs can be sandbox aggregates. Per-service memory and '
                    'unmapped process ownership are not verified. No service memory is inferred.',
                service_peak_memory_mib={service.model_id:None for service in self.plan.services})

    def acquire(self):
        import fcntl
        gpu = gpu_snapshot()
        if gpu['total_mib']*1024**2 != self.plan.physical_gpu_bytes:
            raise RuntimeError('Placement physical memory does not match GPU 0')
        # Serializes Sera shared owners. GPU checks still reject independent workloads.
        self._lock_file = Path('/tmp/sera-placement-gpu-0.lock').open('a')
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.memory_accounting == 'total-device':
                fresh_gpu = gpu_snapshot()
                if (fresh_gpu['uuid'] != gpu['uuid'] or
                        fresh_gpu['total_mib']*1024**2 != self.plan.physical_gpu_bytes):
                    raise RuntimeError('GPU identity or capacity changed while acquiring ownership')
                if type(fresh_gpu['used_mib']) is not int or fresh_gpu['used_mib'] < 0:
                    raise ValueError('Invalid device memory accounting')
                gpu = fresh_gpu
            processes = gpu_process_rows() if self.memory_accounting == 'total-device' else gpu_processes()
            if gpu['used_mib'] > 128 or any(p['uuid'] == gpu['uuid'] for p in processes):
                raise RuntimeError('GPU 0 is already in use; refusing placement')
            self.record.update(status='active', gpu=gpu, memory_before_mib=gpu['used_mib'])
            return self
        except BaseException:
            self._release_lock()
            raise

    def _release_lock(self):
        if self._lock_file is not None:
            self._lock_file.close()
            self._lock_file = None

    def _error(self, reason):
        if reason not in self.record['errors']:
            self.record['errors'].append(reason)

    def before_start(self, model, gpu):
        if self.record['status'] != 'active' or gpu['uuid'] != self.record['gpu']['uuid']:
            raise RuntimeError('Shared owner is not active on this GPU')
        service = next((item for item in self.plan.services if item.model_id == model.model_id), None)
        if (model not in self.models or service is None or model.revision != service.revision
                or model.configuration != service.configuration or model.model_id in self.groups):
            raise RuntimeError('Runner does not match the registered placement plan')
        self.check()

    def register(self, model):
        with self._mutex:
            self.groups[model.model_id] = model.process.pid
            self.record['process_groups'][model.model_id] = model.process.pid
            model.record['memory_accounting'] = 'owned-process-group; device peak reported separately'
            if self.memory_accounting == 'total-device':
                model.record.update(memory_accounting='total-device', sampled_peak_memory_mib=None,
                    per_service_memory_verified=False,
                    service_allocation_semantics='configured-vllm-budget-not-verified-process-cap')

    def _total_device_processes(self, uuid):
        processes = []
        for row in gpu_process_rows():
            if row['uuid'] != uuid:
                continue
            group = None
            if row['pid'] != 1:
                try:
                    group = os.getpgid(row['pid'])
                except ProcessLookupError:
                    pass
            processes.append(dict(row, process_group=group))
        self.record['unresolved_gpu_processes'] = [p for p in processes if p['process_group'] is None]
        return processes

    def _validate_total_snapshot(self, gpu):
        if gpu['uuid'] != self.record['gpu']['uuid']:
            raise RuntimeError('GPU identity changed')
        if gpu['total_mib']*1024**2 != self.plan.physical_gpu_bytes:
            raise RuntimeError('GPU physical capacity changed')
        if type(gpu['used_mib']) is not int or gpu['used_mib'] < 0:
            raise ValueError('Invalid device memory accounting')

    def sample(self):
        with self._mutex:
            try:
                gpu = gpu_snapshot()
                if gpu['uuid'] != self.record['gpu']['uuid']:
                    raise RuntimeError('GPU identity changed')
                total_device = self.memory_accounting == 'total-device'
                if total_device:
                    self._validate_total_snapshot(gpu)
                    processes = self._total_device_processes(gpu['uuid'])
                else:
                    processes = [p for p in gpu_processes() if p['uuid'] == gpu['uuid']]
                if any(p['process_group'] is not None and p['process_group'] not in self.groups.values()
                       for p in processes):
                    self._error('unrelated-gpu-process')
                unattributed = gpu['used_mib'] - sum(p['used_mib'] for p in processes)
                if not total_device and unattributed > self.record['memory_before_mib'] + 128:
                    self._error('unattributed-device-memory')
                self.record['sampled_peak_memory_mib'] = max(self.record['sampled_peak_memory_mib'], gpu['used_mib'])
                self.record['last_processes'] = processes
                if gpu['used_mib']*1024**2 > self.plan.declared_budget_bytes:
                    self._error('declared-device-budget-exceeded')
                if gpu['used_mib']*1024**2 > self.plan.physical_gpu_bytes:
                    self._error('physical-device-budget-exceeded')
                for service in self.plan.services:
                    if total_device:
                        self.record['service_peak_memory_mib'][service.model_id] = None
                        for model in self.models:
                            if model.model_id == service.model_id:
                                model.record.update(sampled_peak_memory_mib=None,
                                    per_service_memory_verified=False,
                                    device_sampled_peak_memory_mib=self.record['sampled_peak_memory_mib'])
                        continue
                    group = self.groups.get(service.model_id)
                    used = sum(p['used_mib'] for p in processes if group is not None and p['process_group'] == group)
                    previous = self.record['service_peak_memory_mib'].get(service.model_id, 0)
                    self.record['service_peak_memory_mib'][service.model_id] = max(previous, used)
                    if used*1024**2 > service.allocation_bytes:
                        self._error('service-budget-exceeded:' + service.model_id)
                    for model in self.models:
                        if model.model_id == service.model_id:
                            if model.record.get('status') == 'ready' and used <= 0:
                                self._error('ready-service-accounting-missing:' + service.model_id)
                            model.record['sampled_peak_memory_mib'] = self.record['service_peak_memory_mib'][service.model_id]
                            model.record['device_sampled_peak_memory_mib'] = self.record['sampled_peak_memory_mib']
            except Exception as error:
                self.record['telemetry_errors'] += 1
                self._error('memory-accounting-unavailable:' + type(error).__name__)
                if isinstance(error, GPUProcessIdentityError):
                    self._error('gpu-process-identity-unresolved')
                    diagnostics = self.record.setdefault('process_identity_errors', [])
                    if error.diagnostic not in diagnostics:
                        diagnostics.append(error.diagnostic)
            return self.record

    def check(self):
        self.sample()
        self.ensure_healthy()
        return self.record

    def ensure_healthy(self):
        """Do not run NVIDIA queries inside each timed request."""
        if self.record['errors']:
            raise RuntimeError('Shared runtime failed memory or process ownership checks')

    def service_released(self, model):
        group = self.groups.get(model.model_id)
        if group is None:
            return True
        if self.memory_accounting == 'total-device':
            return not self._local_group_exists(group)
        return not any(p['uuid'] == self.record['gpu']['uuid'] and p['process_group'] == group
                       for p in gpu_processes())

    @staticmethod
    def _local_group_exists(group):
        try:
            os.killpg(group, 0)  # Existence check, never a termination signal.
        except ProcessLookupError:
            return False
        return True

    def verify_service_cleanup(self, model):
        deadline = time.monotonic() + 15
        try:
            while not self.service_released(model) and time.monotonic() < deadline:
                time.sleep(1)
            released = self.service_released(model)
        except GPUProcessIdentityError as error:
            model.record.update(cleanup_pass=False,
                cleanup_error='gpu-process-identity-unresolved',
                cleanup_identity_error=error.diagnostic)
            raise CleanupError('GPU process identity prevents service cleanup verification') from error
        model.record.update(cleanup_pass=released, memory_after_mib=gpu_snapshot()['used_mib'],
                            cleanup_scope='owned GPU process group; registered peers can remain live')
        if self.memory_accounting == 'total-device':
            model.record.update(owned_local_process_group_released=released,
                cleanup_scope='owned local process group only',
                gpu_release_verification='deferred-to-owner-final-close')
        if not released:
            raise CleanupError('Owned placement service retained GPU resources')

    def _total_device_cleanup(self):
        deadline = time.monotonic() + 15
        while True:
            groups = [group for group in self.groups.values() if self._local_group_exists(group)]
            gpu = gpu_snapshot()
            self._validate_total_snapshot(gpu)
            rows = [p for p in gpu_process_rows() if p['uuid'] == gpu['uuid']]
            memory_released = gpu['used_mib'] <= self.record['memory_before_mib'] + 128
            self.record.update(remaining_owned_process_groups=groups,
                remaining_gpu_processes=rows, memory_after_mib=gpu['used_mib'],
                owned_local_process_groups_released=not groups,
                gpu_release_verified=not rows and memory_released,
                cleanup_scope='all owned local process groups, idle device memory, no GPU compute processes')
            if not groups and not rows and memory_released:
                return []
            if time.monotonic() >= deadline:
                errors = []
                if groups:
                    errors.append('owned-processes-remain')
                if rows:
                    errors.append('gpu-compute-processes-remain')
                if not memory_released:
                    errors.append('device-memory-not-released')
                return errors
            time.sleep(1)

    def close(self):
        if self.record.get('cleanup_pass') is True:
            return self.record
        errors = []
        try:
            for model in reversed(self.models):
                try:
                    model.close()
                except BaseException as error:
                    errors.append(type(error).__name__)
            try:
                if self.memory_accounting == 'total-device':
                    errors.extend(self._total_device_cleanup())
                else:
                    remaining = [p for p in gpu_processes()
                        if p['uuid'] == self.record.get('gpu', {}).get('uuid') and p['process_group'] in self.groups.values()]
                    self.record['remaining_owned_processes'] = remaining
                    if remaining:
                        errors.append('owned-processes-remain')
            except Exception as error:
                errors.append('cleanup-accounting-' + type(error).__name__)
            self.record.update(cleanup_pass=not errors, cleanup_errors=errors,
                               status='closed' if not errors else 'cleanup-failed')
        finally:
            self._release_lock()
        if errors:
            raise CleanupError('Could not verify cleanup of both placement services')
        return self.record
