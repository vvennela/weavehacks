"""Disposable native jobs. This is a process boundary, not a remote service.

The operator supplies a deadline and owns the job directory. The worker receives
no W&B or agent key, never grades answers, and cannot select a winning artifact.
"""

import json
import math
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from .backends.cuda import CUDABackend, CUDAOptions, assign_device
from .backends.mlx import MLXBackend, MLXRecipe
from .backends.modelopt_export import ModelOptRecipe, prepare_modelopt
from .backends.rocm import ROCmBackend, ROCmRecipe
from .hardware import HardwareAssignment, ModelDescriptor
from .placement_decoding import validate_formats
from .process_ownership import inherit_lifetime
from .runtime import INFERENCE_ENVIRONMENT_VARIABLES
from .storage import content_hash, save_json


class NativeWorkerError(RuntimeError):
    pass


class PrepareJob(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')
    operation: Literal['prepare']
    backend: Literal['mlx']
    source: ModelDescriptor
    destination: str = Field(min_length=1)
    recipe: MLXRecipe


class ROCmPrepareJob(PrepareJob):
    backend: Literal['rocm']
    recipe: ROCmRecipe


class CUDAPrepareJob(PrepareJob):
    backend: Literal['cuda']
    recipe: ModelOptRecipe
    gpu_uuid: str

    @model_validator(mode='after')
    def assigned_gpu(self):
        HardwareAssignment(gpu_uuids=[self.gpu_uuid])
        return self


class MeasureJob(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')
    operation: Literal['measure']
    backend: Literal['mlx', 'rocm']
    artifact: str = Field(min_length=1)
    artifact_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    prompts: list[str | list[dict[str, str]]] = Field(min_length=1)
    max_tokens: int = Field(ge=1)
    seed: int
    warmup: int = Field(ge=0)
    repetitions: int = Field(ge=1)
    response_formats: list[dict] | None = None
    response_format_version: str | None = None

    @model_validator(mode='after')
    def validate_workload(self):
        for prompt in self.prompts:
            if not prompt:
                raise ValueError('Prompts must be nonempty')
            if isinstance(prompt, list) and any(
                set(message) != {'role', 'content'} or not message['content']
                or message['role'] not in {'system', 'user', 'assistant'} for message in prompt
            ):
                raise ValueError('Supply text chat messages with valid roles')
        validate_formats(self.prompts, self.response_formats, self.response_format_version)
        return self


class CUDAMeasureJob(MeasureJob):
    backend: Literal['cuda']
    runtime: CUDAOptions


PREPARE_JOB = Annotated[PrepareJob | ROCmPrepareJob | CUDAPrepareJob, Field(discriminator='backend')]
MEASURE_JOB = Annotated[MeasureJob | CUDAMeasureJob, Field(discriminator='backend')]
JOB = TypeAdapter(Annotated[PREPARE_JOB | MEASURE_JOB, Field(discriminator='operation')])


def _command(path):
    return [sys.executable, '-m', 'sera.native_worker', str(path)]


def _execute(job):
    if isinstance(job, CUDAPrepareJob):
        assign_device(job.gpu_uuid)
        return prepare_modelopt(source=job.source, destination=job.destination, recipe=job.recipe)
    if isinstance(job, CUDAMeasureJob):
        backend = CUDABackend(job.runtime)
    else:
        backend = MLXBackend() if job.backend == 'mlx' else ROCmBackend()
    if isinstance(job, PrepareJob):
        return backend.prepare(source=job.source, destination=job.destination, recipe=job.recipe)
    with backend.load(job.artifact, expected_id=job.artifact_id) as model:
        return model.measure(job.prompts, max_tokens=job.max_tokens, seed=job.seed,
                             warmup=job.warmup, repetitions=job.repetitions,
                             response_formats=job.response_formats,
                             response_format_version=job.response_format_version)


def run_native_job(job, *, output_dir, timeout_seconds, cancelled=None):
    """Run one validated job with a hard deadline; keep all failure evidence."""
    request = JOB.validate_python(job).model_dump(mode='json')
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0):
        raise ValueError('Supply a positive finite worker deadline')
    if os.name != 'posix':
        raise RuntimeError('Native workers require POSIX process cleanup')
    folder = Path(output_dir).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    request_path = folder / 'job.json'
    save_json(request_path, request)
    record = {'job_hash': content_hash(request), 'status': 'starting', 'cleanup_pass': False}
    save_json(folder / 'status.json', record)
    env = {key: os.environ[key] for key in INFERENCE_ENVIRONMENT_VARIABLES if key in os.environ}
    # Absolute Python invocation does not activate its environment. Native
    # runtimes also execute installed helpers such as ninja by their short name.
    env['PATH'] = os.pathsep.join((str(Path(sys.executable).parent), env.get('PATH', os.defpath)))
    # Use the installed package, never inherit a caller's PYTHONPATH or executable hooks.
    process = None
    read_fd, write_fd = os.pipe()
    env['SERA_PARENT_FD'] = str(read_fd)
    started = time.monotonic()
    try:
        with (folder / 'worker.log').open('w') as log:
            process = subprocess.Popen(_command(request_path), env=env, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True,
                                       pass_fds=inherit_lifetime(env, (read_fd,)))
            os.close(read_fd)
            read_fd = None
            record.update(pid=process.pid, status='running')
            save_json(folder / 'status.json', record)
            while True:
                if cancelled is not None and cancelled.is_set():
                    record['status'] = 'cancelled'
                    raise NativeWorkerError('Native worker cancelled')
                remaining = timeout_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    record['status'] = 'timeout'
                    raise NativeWorkerError('Native worker timeout')
                try:
                    process.wait(timeout=min(0.1, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode != 0:
                raise NativeWorkerError('Native worker failed; inspect worker.log')
        response = json.loads((folder / 'output.json').read_text())
        if (not isinstance(response, dict) or set(response) != {'job_hash', 'result'}
                or response['job_hash'] != record['job_hash'] or not isinstance(response['result'], dict)):
            raise NativeWorkerError('Worker output identity does not match the job')
        record['status'] = 'completed'
        return response['result']
    except BaseException:
        if record['status'] not in {'timeout', 'cancelled'}:
            record['status'] = 'failed'
        raise
    finally:
        os.close(write_fd)
        if read_fd is not None:
            os.close(read_fd)
        if process is not None:
            # Kill the entire group, including children left after its leader exits.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        record.update(cleanup_pass=True, elapsed_seconds=time.monotonic() - started)
        save_json(folder / 'status.json', record)


def _parent_watchdog():
    descriptor = os.environ.pop('SERA_PARENT_FD', None)
    if descriptor is None:
        return
    descriptor = int(descriptor)
    def watch():
        try:
            os.read(descriptor, 1)
        finally:
            # This worker is a session leader. EOF means its controller no
            # longer owns the pipe, including SIGKILL and controller crashes.
            os.killpg(os.getpid(), signal.SIGKILL)
    threading.Thread(target=watch, name='sera-parent-watchdog', daemon=True).start()


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python -m sera.native_worker JOB.json')
    _parent_watchdog()
    path = Path(sys.argv[1])
    request = json.loads(path.read_text())
    job = JOB.validate_python(request)
    result = _execute(job)
    save_json(path.parent / 'output.json', {'job_hash': content_hash(request), 'result': result})


if __name__ == '__main__':
    main()
