"""Load an exported checkpoint in the hardware environment installed by setup."""
import json
import os
import select
import subprocess
import sys
import tempfile
from pathlib import Path

from .runtime import INFERENCE_ENVIRONMENT_VARIABLES


class RuntimeModel:
    def __init__(self, python, result):
        self.process = None
        self.parent_fd = None
        self.log = tempfile.TemporaryFile(mode='w+')  # noqa: SIM115 — owned until close()
        environment = {key: os.environ[key] for key in INFERENCE_ENVIRONMENT_VARIABLES if key in os.environ}
        environment['PATH'] = str(Path(python).parent) + os.pathsep + environment.get('PATH', os.defpath)
        read_fd, self.parent_fd = os.pipe()
        environment['SERA_PARENT_FD'] = str(read_fd)
        try:
            self.process = subprocess.Popen([python, '-I', '-m', 'sera.runtime_model'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                text=True, env=environment, pass_fds=(read_fd,), start_new_session=True)
        except BaseException:
            self.close()
            raise
        finally:
            os.close(read_fd)
        try:
            self._request({'backend': result.backend, 'runtime': result.runtime,
                           'artifact_path': result.artifact_path, 'artifact_id': result.artifact_id})
        except BaseException:
            self.close()
            raise

    def _request(self, value):
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError('The Sera inference runtime is closed')
        try:
            self.process.stdin.write(json.dumps(value, allow_nan=False) + '\n')
            self.process.stdin.flush()
            if not select.select([self.process.stdout], [], [], 180)[0]:
                self.close()
                raise RuntimeError('Sera inference exceeded the 180-second runtime deadline')
            response = self.process.stdout.readline(16 * 1024 * 1024)
            if not response:
                raise RuntimeError('The Sera inference runtime exited without a result')
            value = json.loads(response)
            if 'error' in value:
                raise RuntimeError(value['error'])
            return value['result']
        except (BrokenPipeError, OSError, ValueError):
            self.close()
            raise RuntimeError('The Sera inference runtime connection failed') from None

    def generate(self, prompt, *, max_tokens, seed, response_format=None):
        return self._request({'operation': 'generate', 'args': [prompt],
            'kwargs': {'max_tokens': max_tokens, 'seed': seed, 'response_format': response_format}})

    def measure(self, prompts, **kwargs):
        return self._request({'operation': 'measure', 'args': [prompts], 'kwargs': kwargs})

    def close(self):
        process, self.process = self.process, None
        if process is not None:
            if process.stdin:
                process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                from .process_ownership import terminate_group
                terminate_group(process)
            if process.stdout:
                process.stdout.close()
        if self.parent_fd is not None:
            os.close(self.parent_fd)
            self.parent_fd = None
        self.log.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _load(value):
    from .managed_client import ManagedResult
    return ManagedResult(job_id='', selected_recipe_id='', trace_url='', elapsed_seconds=0,
                         **value)._load_model(use_configured_runtime=False)


def serve(source, output, *, loader=_load):
    def send(value):
        output.write(json.dumps(value, allow_nan=False) + '\n')
        output.flush()
    model = None
    try:
        model = loader(json.loads(source.readline(1024 * 1024)))
        send({'result': 'ready'})
        for line in source:
            request = json.loads(line)
            operation = request.get('operation')
            if operation == 'close':
                send({'result': None})
                break
            if operation not in {'generate', 'measure'}:
                send({'error': 'Unsupported inference operation'})
                break
            send({'result': getattr(model, operation)(*request.get('args', []), **request.get('kwargs', {}))})
    except Exception as error:  # noqa: BLE001 — process boundary returns a safe error
        send({'error': f'Inference failed: {type(error).__name__}'})
    finally:
        if model is not None:
            model.close()


def main():
    from .native_worker import _parent_watchdog
    _parent_watchdog()
    # Runtime libraries can write directly to fd 1; reserve a separate protocol fd.
    with os.fdopen(os.dup(sys.stdout.fileno()), 'w') as output:
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
        serve(sys.stdin, output)


if __name__ == '__main__':
    main()
