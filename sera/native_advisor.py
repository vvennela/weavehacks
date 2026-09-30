"""Keep the ChatGPT board on the operator host behind an SSH loopback tunnel."""
import argparse
import hmac
import json
import math
import os
import select
import socket
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request

from pydantic import BaseModel, ConfigDict, Field

from .kernel_tools import research_environment
from .managed_client import SeraClient
from .native_agent import NativeProposal
from .native_board import NativeBoard as NativeBoardFactory
from .native_worker import _parent_watchdog
from .process_ownership import terminate_group
from .storage import content_hash, save_json

MAX_BODY = 2 * 1024 * 1024
MAX_RESPONSE = 8 * 1024 * 1024


class AdvisorRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', allow_inf_nan=False)
    run_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    max_model_calls: int = Field(ge=1, le=512)
    operation: Literal['state', 'propose', 'review']
    evidence: dict
    timeout_seconds: float = Field(gt=0, le=180)


class NativeAdvisorClient:
    stateful = True

    def __init__(self, folder, *, max_model_calls, endpoint, token, timeout_seconds=10.0, cancelled=None):
        self.transport = SeraClient(api_key=token, endpoint=endpoint)
        self.run_id = content_hash(str(Path(folder).resolve()))
        self.max_model_calls = max_model_calls
        self.history, self.model_calls = [], []
        if cancelled is None or not cancelled.is_set():
            self._call('state', {}, timeout_seconds)

    def _call(self, operation, evidence, timeout):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('Supply a positive finite advisor deadline')
        payload = AdvisorRequest(run_id=self.run_id, max_model_calls=self.max_model_calls,
            operation=operation, evidence=evidence, timeout_seconds=float(min(180, timeout)))
        body = payload.model_dump_json().encode()
        if len(body) > MAX_BODY:
            raise ValueError('Advisor evidence exceeds the request limit')
        request = Request(self.transport.endpoint + '/v1/board', data=body,
            headers={'Authorization': 'Bearer ' + self.transport._api_key,
                     'Content-Type': 'application/json'}, method='POST')
        try:
            with self.transport._http.open(request, timeout=payload.timeout_seconds) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise RuntimeError('Advisor response exceeds the size limit')
            result = json.loads(raw)
            self.history, self.model_calls = result['history'], result['model_calls']
            return result['result']
        except HTTPError as error:
            raise RuntimeError(f'Operator advisor returned HTTP {error.code}') from None
        except URLError:
            raise RuntimeError('Operator advisor is unreachable') from None

    def propose(self, evidence, *, timeout_seconds, cancelled=None):
        if cancelled is not None and cancelled.is_set():
            return None
        result = self._call('propose', evidence, timeout_seconds)
        return NativeProposal.model_validate(result) if result is not None else None

    def review(self, results, *, timeout_seconds):
        return self._call('review', results, timeout_seconds)


def _worker_command(request):
    return [sys.executable, '-m', 'sera.native_advisor', '--worker', str(request)]


def run_worker(path):
    _parent_watchdog()
    request = AdvisorRequest.model_validate_json(path.read_text())
    board_folder = path.parent / 'board'
    board = NativeBoardFactory(board_folder, max_model_calls=request.max_model_calls,
                               resume=(board_folder / 'state.json').exists())
    result = None
    if request.operation == 'propose':
        proposal = board.propose(request.evidence, timeout_seconds=request.timeout_seconds)
        result = proposal.model_dump() if proposal is not None else None
    elif request.operation == 'review':
        result = board.review(request.evidence, timeout_seconds=request.timeout_seconds)
    save_json(path.with_suffix('.response.json'), {'result': result, 'history': board.history,
                                                  'model_calls': board.model_calls})


def _connected(connection):
    readable, _, _ = select.select([connection], [], [], 0)
    return not readable or bool(connection.recv(1, socket.MSG_PEEK))


def _execute(request, folder, connection):
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = folder / (uuid.uuid4().hex + '.json')
    save_json(path, request.model_dump())
    read_fd, write_fd = os.pipe()
    environment = research_environment() | {'SERA_PARENT_FD': str(read_fd)}
    process = None
    deadline = time.monotonic() + request.timeout_seconds
    try:
        with path.with_suffix('.log').open('w') as log:
            process = subprocess.Popen(_worker_command(path), env=environment,
                pass_fds=(read_fd,), start_new_session=True, stdout=log, stderr=subprocess.STDOUT)
            while process.poll() is None:
                if time.monotonic() >= deadline or not _connected(connection):
                    raise TimeoutError('Advisor request expired or disconnected')
                time.sleep(0.02)
            if process.returncode != 0:
                raise RuntimeError('Advisor worker failed')
        raw = path.with_suffix('.response.json').read_bytes()
        if len(raw) > MAX_RESPONSE:
            raise ValueError('Advisor response exceeds the size limit')
        return raw
    finally:
        os.close(write_fd)
        os.close(read_fd)
        if process is not None:
            terminate_group(process)


def make_server(folder, *, token, port):
    if not isinstance(token, str) or len(token) < 32 or any(c.isspace() for c in token):
        raise ValueError('Configure a private advisor token of at least 32 characters')
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder.chmod(0o700)
    active = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            acquired = False
            try:
                if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                    self.send_error(401)
                    return
                if self.path != '/v1/board':
                    self.send_error(404)
                    return
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_BODY or self.headers.get('Transfer-Encoding'):
                    self.send_error(400)
                    return
                request = AdvisorRequest.model_validate_json(self.rfile.read(length))
                acquired = active.acquire(blocking=False)
                if not acquired:
                    self.send_error(429)
                    return
                raw = _execute(request, folder / request.run_id, self.connection)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(raw)
            except (ValueError, TypeError):
                self.send_error(400)
            except (TimeoutError, ConnectionError, OSError):
                self.close_connection = True
            except Exception:  # noqa: BLE001 - keep operator diagnostics private
                self.send_error(502)
            finally:
                if acquired:
                    active.release()

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        def get_request(self):
            connection, address = super().get_request()
            connection.settimeout(5)
            return connection, address

    return Server(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description='Operator ChatGPT board behind a loopback SSH tunnel')
    parser.add_argument('--state', type=Path)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        run_worker(args.worker)
        return
    if args.state is None:
        parser.error('--state is required')
    server = make_server(args.state, token=os.environ.get('SERA_ADVISOR_TOKEN'), port=args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
