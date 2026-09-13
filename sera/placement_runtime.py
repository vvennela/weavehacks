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


def gpu_processes():
    output = subprocess.run(['nvidia-smi',
        '--query-compute-apps=gpu_uuid,pid,used_gpu_memory', '--format=csv,noheader,nounits'],
        capture_output=True, text=True, check=True, timeout=10).stdout
    processes = []
    for line in output.splitlines():
        uuid, pid, memory = [part.strip() for part in line.split(',')]
        pid, memory = int(pid), int(memory)
        if pid <= 0 or memory < 0:
            raise ValueError('Invalid GPU process accounting')
        try:
            group = os.getpgid(pid)
        except ProcessLookupError:
            # A process exiting during a query requires a fresh sample, not invented accounting.
            raise RuntimeError('GPU process exited during ownership accounting') from None
        processes.append(dict(uuid=uuid, pid=pid, process_group=group, used_mib=memory))
    return processes


class SharedGPUOwner:
    def __init__(self, plan):
        self.plan = validate_placement_plan(plan)
        self.models = []
        self.groups = {}
        self._lock_file = None
        self._mutex = threading.RLock()
        self.record = dict(status='not-started', errors=[], telemetry_errors=0,
            sampled_peak_memory_mib=0, service_peak_memory_mib={}, process_groups={},
            accounting='nvidia-smi compute processes attributed by owned process group',
            sample_interval_seconds=1, peak_limitations='Samples can miss short startup and request peaks.')

    def acquire(self):
        import fcntl
        gpu = gpu_snapshot()
        if gpu['total_mib']*1024**2 != self.plan.physical_gpu_bytes:
            raise RuntimeError('Placement physical memory does not match GPU 0')
        # Serializes Sera shared owners. GPU checks still reject independent workloads.
        self._lock_file = Path('/tmp/sera-placement-gpu-0.lock').open('a')
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if gpu['used_mib'] > 128 or any(p['uuid'] == gpu['uuid'] for p in gpu_processes()):
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

    def sample(self):
        with self._mutex:
            try:
                gpu = gpu_snapshot()
                if gpu['uuid'] != self.record['gpu']['uuid']:
                    raise RuntimeError('GPU identity changed')
                processes = [p for p in gpu_processes() if p['uuid'] == gpu['uuid']]
                if any(p['process_group'] not in self.groups.values() for p in processes):
                    self._error('unrelated-gpu-process')
                unattributed = gpu['used_mib'] - sum(p['used_mib'] for p in processes)
                if unattributed > self.record['memory_before_mib'] + 128:
                    self._error('unattributed-device-memory')
                self.record['sampled_peak_memory_mib'] = max(self.record['sampled_peak_memory_mib'], gpu['used_mib'])
                self.record['last_processes'] = processes
                if gpu['used_mib']*1024**2 > self.plan.declared_budget_bytes:
                    self._error('declared-device-budget-exceeded')
                if gpu['used_mib']*1024**2 > self.plan.physical_gpu_bytes:
                    self._error('physical-device-budget-exceeded')
                for service in self.plan.services:
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
        return not any(p['uuid'] == self.record['gpu']['uuid'] and p['process_group'] == group
                       for p in gpu_processes())

    def verify_service_cleanup(self, model):
        deadline = time.monotonic() + 15
        while not self.service_released(model) and time.monotonic() < deadline:
            time.sleep(1)
        released = self.service_released(model)
        model.record.update(cleanup_pass=released, memory_after_mib=gpu_snapshot()['used_mib'],
                            cleanup_scope='owned GPU process group; registered peers can remain live')
        if not released:
            raise CleanupError('Owned placement service retained GPU resources')

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
