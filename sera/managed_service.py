"""Local Sera service: authenticated profiles, durable jobs and one accelerator owner."""
import argparse
import fcntl
import hashlib
import hmac
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .ledger import read_checkpoint
from .model_artifact import verify_artifact
from .native_optimizer import validate_native_profile
from .process_ownership import LIFETIME_FD, terminate_group, tree_is_alive
from .runtime import INFERENCE_ENVIRONMENT_VARIABLES
from .storage import content_hash, save_json

ACTIVE = {'pending', 'running', 'interrupted', 'cleanup-blocked'}
IDENTIFIER = re.compile(r'^[a-zA-Z0-9_-]{1,128}$')


class ServiceError(RuntimeError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def _device_lock_path():
    # Retain the lock path used by earlier MLX deployments.
    return Path.home() / '.cache' / 'sera' / 'mlx-service.lock'


def _controller_command(folder):
    return [sys.executable, '-m', 'sera.native_controller', str(folder)]


def _result(report):
    if report.get('status') != 'completed' or not report.get('trace', {}).get('remote_verified'):
        raise ValueError('Research did not complete with verified tracing')
    verify_artifact(report['artifact_path'], expected_id=report['selected_artifact_id'], backend=report['execution']['backend'])
    result = {key: report[key] for key in ('selected_recipe_id', 'selected_artifact_id',
            'artifact_path', 'trace', 'candidate_trials_used', 'elapsed_seconds')}
    result['measurements'] = _measurements(report)
    result['backend'] = report['execution']['backend']
    return result


def _measurements(report):
    def summary(measured):
        return {'peak_bytes': measured.get('runtime', {}).get('memory', {}).get('peak_bytes'),
                'quality': measured.get('task_quality', {}).get('mean')}
    trials = []
    for trial in report.get('trials', []):
        trials.append({'recipe_id': trial['recipe_id'], 'status': trial['status'],
                       'measurement': summary(trial.get('measurement', {})),
                       'confirmation': summary(trial.get('confirmation', {}).get('candidate', {})),
                       'accepted': trial.get('repeated_decision', {}).get('selected') == 'candidate'})
    return {'baseline': summary(report.get('baseline', {})), 'trials': trials,
            'scope': report.get('baseline', {}).get('runtime', {}).get('memory', {}).get('scope')}


class ManagedService:
    def __init__(self, *, folder, profiles, clients, project):
        self.profiles = {p.profile_id: p for item in profiles
                         for p in [validate_native_profile(item)]}
        self.clients = clients
        if not self.profiles or not clients:
            raise ValueError('Register profiles and customers before starting the service')
        for digest, client in clients.items():
            if (not re.fullmatch(r'[a-f0-9]{64}', digest)
                    or set(client) != {'id', 'profiles'} or not IDENTIFIER.fullmatch(client['id'])
                    or not client['profiles'] or not set(client['profiles']) <= self.profiles.keys()):
                raise ValueError('Invalid customer access configuration')
        if not os.environ.get('WANDB_API_KEY'):
            raise ValueError('The operator must configure WANDB_API_KEY')
        if len(project.split('/')) != 2 or any(not part.strip() for part in project.split('/')):
            raise ValueError('Supply the operator W&B entity/project')
        self.project = project
        self.folder = Path(folder).resolve()
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.folder.chmod(0o700)
        lock_path = _device_lock_path()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._device_lock = lock_path.open('a+')
        try:
            fcntl.flock(self._device_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._device_lock.close()
            raise RuntimeError('The device already has a Sera service owner') from None
        self._mutex = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._cleanup_blocked = False
        try:
            with closing(sqlite3.connect(self.folder / 'service.sqlite3')) as db:
                db.execute('PRAGMA journal_mode=WAL')
                db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, record TEXT NOT NULL)')
                db.commit()
            for job in self._all():
                if job['status'] in ACTIVE:
                    deadline = time.monotonic() + 5
                    while tree_is_alive(self.folder / job['job_id']):
                        if time.monotonic() >= deadline:
                            raise RuntimeError('A prior process tree is still alive; refusing overlap')
                        time.sleep(0.05)
            self._thread = threading.Thread(target=self._monitor, name='sera-controller', daemon=True)
            self._thread.start()
        except BaseException:
            self._device_lock.close()
            raise

    def _all(self):
        with closing(sqlite3.connect(self.folder / 'service.sqlite3')) as db:
            return [json.loads(row[0]) for row in db.execute('SELECT record FROM jobs ORDER BY rowid')]

    def _save(self, job):
        with closing(sqlite3.connect(self.folder / 'service.sqlite3')) as db:
            db.execute('PRAGMA synchronous=FULL')
            with db:
                db.execute('INSERT OR REPLACE INTO jobs VALUES (?, ?)', (job['job_id'], json.dumps(job)))

    def authenticate(self, token):
        digest = hashlib.sha256(token.encode()).hexdigest()
        for expected, customer in self.clients.items():
            if hmac.compare_digest(digest, expected):
                return customer['id']
        raise ServiceError(401, 'Invalid Sera access key')

    def submit(self, owner, profile_id, request_id):
        if not isinstance(request_id, str) or not IDENTIFIER.fullmatch(request_id):
            raise ServiceError(400, 'Supply a request_id of 1-128 letters, digits, underscores or hyphens')
        if not isinstance(profile_id, str) or not any(
            c['id'] == owner and profile_id in c['profiles'] for c in self.clients.values()
        ):
            raise ServiceError(404, 'Profile not found')
        with self._mutex:
            if self._stop.is_set() or not self._thread.is_alive():
                raise ServiceError(503, 'Service is stopping')
            jobs = self._all()
            for job in jobs:
                if job['owner'] == owner and job['request_id'] == request_id:
                    if job['profile_id'] != profile_id:
                        raise ServiceError(409, 'Request ID belongs to a different profile')
                    return self._public(job)
            if any(job['status'] in ACTIVE for job in jobs):
                raise ServiceError(429, 'The worker is busy')
            profile = self.profiles[profile_id]
            request = {'profile': profile.model_dump(), 'project': self.project}
            job = {'job_id': uuid.uuid4().hex, 'owner': owner, 'request_id': request_id,
                   'profile_id': profile_id, 'status': 'pending', 'result': None,
                   'created_at': time.time(), 'deadline': time.time() + profile.max_run_seconds,
                   'cancel_requested': False, 'pid': None, 'request_hash': content_hash(request)}
            folder = self.folder / job['job_id']
            folder.mkdir(mode=0o700)
            save_json(folder / 'request.json', request)
            self._save(job)
            return self._public(job)

    def _owned(self, owner, job_id):
        for job in self._all():
            if job['job_id'] == job_id and job['owner'] == owner:
                return job
        raise ServiceError(404, 'Job not found')

    def _public(self, job):
        result = {key: job[key] for key in ('job_id', 'profile_id', 'status', 'result')}
        folder = self.folder / job['job_id'] / 'research'
        if (folder / 'ledger.sqlite3').exists():
            try:
                report = read_checkpoint(folder)[0]
                result['progress'] = {'measurements': _measurements(report),
                    'candidate_trials_used': report['candidate_trials_used'],
                    'research_status': report['status'],
                    'phase': 'agent' if 'pending_agent_call' in report else
                             (report['jobs'][-1]['operation'] if report['jobs'] else 'starting')}
            except (ValueError, sqlite3.Error):
                pass  # The first transaction may not yet have committed.
        return result

    def get(self, owner, job_id):
        with self._mutex:
            return self._public(self._owned(owner, job_id))

    def cancel(self, owner, job_id):
        with self._mutex:
            job = self._owned(owner, job_id)
            if job['status'] in ACTIVE:
                job['cancel_requested'] = True
                self._save(job)
            return self._public(job)

    def _monitor(self):
        while not self._stop.is_set():
            with self._mutex:
                job = next((j for j in self._all() if j['status'] in ACTIVE), None)
            if job is None:
                self._stop.wait(0.05)
                continue
            self._execute(job)

    def _execute(self, job):
        folder = self.folder / job['job_id']
        process = None
        read_fd, write_fd = os.pipe()
        lifetime = (folder / 'process-tree.lock').open('a+')
        fcntl.flock(lifetime.fileno(), fcntl.LOCK_SH)
        env = {key: os.environ[key] for key in INFERENCE_ENVIRONMENT_VARIABLES | {'WANDB_API_KEY'}
               if key in os.environ}
        env['SERA_PARENT_FD'] = str(read_fd)
        env[LIFETIME_FD] = str(lifetime.fileno())
        deadline = time.monotonic() + max(0, job['deadline'] - time.time())
        outcome, result = 'failed', None
        try:
            if content_hash(json.loads((folder / 'request.json').read_text())) != job.get('request_hash'):
                raise ValueError('The accepted workload contract changed on disk')
            with (folder / 'controller.log').open('a') as log:
                with self._mutex:
                    current = self._owned(job['owner'], job['job_id'])
                    if current['cancel_requested']:
                        outcome = 'cancelled'
                        return
                    if time.monotonic() >= deadline:
                        outcome = 'timed-out'
                        return
                    process = subprocess.Popen(_controller_command(folder), env=env,
                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True, pass_fds=(read_fd, lifetime.fileno()))
                    current.update(status='running', pid=process.pid)
                    self._save(current)
                os.close(read_fd)
                read_fd = None
                lifetime.close()
                while True:
                    with self._mutex:
                        current = self._owned(job['owner'], job['job_id'])
                    if current['cancel_requested']:
                        outcome = 'cancelled'
                        break
                    if self._stop.is_set():
                        outcome = 'interrupted'
                        break
                    if time.monotonic() >= deadline:
                        outcome = 'timed-out'
                        break
                    if process.poll() is not None:
                        if process.returncode == 0:
                            result = _result(read_checkpoint(folder / 'research')[0])
                            outcome = 'completed'
                            if time.monotonic() >= deadline:
                                outcome, result = 'timed-out', None
                        break
                    self._stop.wait(0.05)
        except Exception as error:  # noqa: BLE001 - private process-boundary error record
            save_json(folder / 'failure.json', {'error_type': type(error).__name__})
        finally:
            lifetime.close()
            os.close(write_fd)
            if read_fd is not None:
                os.close(read_fd)
            if process is not None:
                terminate_group(process)
            cleanup_deadline = time.monotonic() + 5
            while tree_is_alive(folder):
                if time.monotonic() >= cleanup_deadline:
                    outcome, result = 'cleanup-blocked', None
                    self._cleanup_blocked = True
                    self._stop.set()
                    break
                time.sleep(0.02)
            with self._mutex:
                current = self._owned(job['owner'], job['job_id'])
                current.update(status=outcome, result=result, pid=None)
                self._save(current)

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                raise RuntimeError('Controller cleanup did not finish; device lock retained')
        if self._cleanup_blocked or any(tree_is_alive(self.folder / j['job_id']) for j in self._all()):
            raise RuntimeError('An owned process is still alive; device lock retained')
        self._device_lock.close()


class _HTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address


def make_server(service, *, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Request headers and credentials never enter access logs.

        def _send(self, status, value):
            encoded = json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(encoded)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(encoded)

        def _handle(self):
            try:
                header = self.headers.get('Authorization', '')
                if not header.startswith('Bearer '):
                    raise ServiceError(401, 'Sera access key required')
                owner = service.authenticate(header[7:])
                parts = self.path.split('/')
                if self.command == 'POST' and self.path == '/v1/jobs':
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 4096 or self.headers.get('Transfer-Encoding'):
                        raise ServiceError(400, 'Supply a JSON request of at most 4096 bytes')
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict) or set(body) != {'profile_id', 'request_id'}:
                        raise ServiceError(400, 'Supply only profile_id and request_id')
                    result = service.submit(owner, **body)
                elif len(parts) == 4 and parts[:3] == ['', 'v1', 'jobs'] and IDENTIFIER.fullmatch(parts[3]):
                    if self.command == 'GET':
                        result = service.get(owner, parts[3])
                    elif self.command == 'DELETE':
                        result = service.cancel(owner, parts[3])
                    else:
                        raise ServiceError(405, 'Method not allowed')
                else:
                    raise ServiceError(404, 'Route not found')
                self._send(200, result)
            except ServiceError as error:
                self._send(error.status, {'error': str(error)})
            except (ValueError, TypeError):
                self._send(400, {'error': 'Invalid request'})
            except Exception:  # noqa: BLE001 - never expose internal errors over HTTP
                self._send(500, {'error': 'Internal service error'})

        do_GET = do_POST = do_DELETE = _handle

    # Local deployment only. Public ingress needs a separately validated TLS gateway.
    return _HTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description='Start the local Sera native service')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    service = ManagedService(folder=args.state, **config)
    try:
        server = make_server(service, port=args.port)
        try:
            print(f'Sera listening on http://127.0.0.1:{server.server_port}', flush=True)
            server.serve_forever()
        finally:
            server.server_close()
    except KeyboardInterrupt:
        pass
    finally:
        service.close()


if __name__ == '__main__':
    main()
