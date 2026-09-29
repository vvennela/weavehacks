"""Bound a service-owned advisor call with a disposable provider process."""

import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .agent import ProviderTransportError, WandbAgent
from .native_worker import _parent_watchdog
from .storage import save_json


def _command(path):
    return [sys.executable, '-m', 'sera.native_provider', str(path)]


def complete(payload, *, project, timeout_seconds, cancelled=None):
    if not os.environ.get('WANDB_API_KEY'):
        raise ProviderTransportError('Missing operator W&B credential')
    if (type(timeout_seconds) not in (float, int) or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0):
        raise ValueError('Supply a positive provider deadline')
    env = {name: os.environ[name] for name in (
        'PATH', 'HOME', 'TMPDIR', 'LANG', 'SSL_CERT_FILE', 'SSL_CERT_DIR',
        'HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'no_proxy',
        'WANDB_API_KEY') if name in os.environ}
    with tempfile.TemporaryDirectory(prefix='sera-provider-') as directory:
        folder = Path(directory)
        request = folder / 'request.json'
        save_json(request, {'payload': payload, 'project': project, 'timeout_seconds': timeout_seconds})
        read_fd, write_fd = os.pipe()
        env['SERA_PARENT_FD'] = str(read_fd)
        process = None
        started = time.monotonic()
        try:
            process = subprocess.Popen(_command(request), env=env, pass_fds=(read_fd,),
                start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            while True:
                if cancelled is not None and cancelled.is_set():
                    raise ProviderTransportError('Provider call cancelled')
                remaining = timeout_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    raise ProviderTransportError('Provider wall-clock deadline exceeded')
                try:
                    process.wait(timeout=min(remaining, 0.1))
                    break
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode != 0:
                raise ProviderTransportError('Provider process failed')
            result = json.loads((folder / 'response.json').read_text())
            if 'error' in result:
                raise ProviderTransportError(result['error'], http_status=result.get('http_status'))
            return result['body']
        finally:
            os.close(write_fd)
            os.close(read_fd)
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()


def main():
    _parent_watchdog()
    path = Path(sys.argv[1])
    request = json.loads(path.read_text())
    client = WandbAgent(project=request['project'], model=request['payload']['model'])
    client.timeout_seconds = request['timeout_seconds']
    try:
        result = {'body': client._complete(request['payload'])}
    except ProviderTransportError as error:
        result = {'error': str(error), 'http_status': error.http_status}
    save_json(path.parent / 'response.json', result)


if __name__ == '__main__':
    main()
