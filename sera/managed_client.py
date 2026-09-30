"""Customer interface to a Sera-managed local research worker."""
import json
import math
import time
import uuid
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .model_artifact import verify_artifact


class SeraServiceError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


@dataclass(frozen=True)
class ManagedResult:
    job_id: str
    selected_recipe_id: str
    artifact_id: str
    artifact_path: str
    trace_url: str
    elapsed_seconds: float
    backend: str = 'mlx'
    runtime: dict | None = None
    stop_reason: str | None = None

    def verify(self):
        return verify_artifact(self.artifact_path, expected_id=self.artifact_id, backend=self.backend)

    def load(self):
        from .backends.cuda import CUDABackend
        from .backends.mlx import MLXBackend
        from .backends.rocm import ROCmBackend
        adapters = {'mlx': MLXBackend, 'rocm': ROCmBackend}
        if self.backend == 'cuda':
            return CUDABackend(self.runtime).load(self.artifact_path, expected_id=self.artifact_id)
        if self.backend not in adapters:
            raise ValueError('Unsupported checkpoint backend')
        return adapters[self.backend]().load(self.artifact_path, expected_id=self.artifact_id)


class SeraClient:
    def __init__(self, *, api_key, endpoint='http://127.0.0.1:8765'):
        url = urlsplit(endpoint)
        if (url.scheme != 'http' or url.hostname not in {'127.0.0.1', 'localhost', '::1'}
                or url.username or url.password or url.path not in {'', '/'} or url.query or url.fragment):
            raise ValueError('This release requires a local loopback Sera endpoint')
        if not isinstance(api_key, str) or not api_key or any(c.isspace() for c in api_key):
            raise ValueError('Supply a Sera access key')
        self.endpoint = endpoint.rstrip('/')
        self._api_key = api_key
        # Neither proxy environment variables nor redirects may forward the key.
        self._http = build_opener(ProxyHandler({}), _NoRedirect())

    def _request(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = Request(self.endpoint + path, data=data, method=method,
                          headers={'Authorization': 'Bearer ' + self._api_key,
                                   'Content-Type': 'application/json'})
        for attempt in range(3):
            try:
                with self._http.open(request, timeout=10) as response:
                    return json.loads(response.read(1024 * 1024))
            except HTTPError as error:
                raise SeraServiceError(f'Sera request failed with HTTP {error.code}') from None
            except (URLError, TimeoutError, ConnectionError):
                if attempt == 2:
                    raise SeraServiceError('Sera is unreachable; retry using the same request_id') from None
                time.sleep(0.1 * (attempt + 1))
        raise AssertionError('Unreachable')

    def submit(self, profile_id, *, request_id):
        return self._request('POST', '/v1/jobs', {'profile_id': profile_id, 'request_id': request_id})

    def status(self, job_id):
        return self._request('GET', '/v1/jobs/' + self._job_id(job_id))

    def cancel(self, job_id):
        return self._request('DELETE', '/v1/jobs/' + self._job_id(job_id))

    @staticmethod
    def _job_id(job_id):
        if not isinstance(job_id, str) or len(job_id) != 32 or any(c not in '0123456789abcdef' for c in job_id):
            raise ValueError('Invalid Sera job ID')
        return job_id


def Optimize(profile_id, *, api_key, endpoint='http://127.0.0.1:8765', request_id=None,
             on_update=None, poll_interval=1.0):
    """Run one registered workload and return its confirmed checkpoint.

    Reuse request_id after a connection failure to recover the same job.
    Ctrl-C cancels the accepted job. The service owns W&B credentials and gates.
    """
    if type(poll_interval) not in (int, float) or not math.isfinite(poll_interval) or poll_interval <= 0:
        raise ValueError('Supply a positive finite poll interval')
    client = SeraClient(api_key=api_key, endpoint=endpoint)
    request_id = request_id if request_id is not None else uuid.uuid4().hex
    try:
        job = client.submit(profile_id, request_id=request_id)
    except SeraServiceError as error:
        recovered = SeraServiceError(f'{error}; retry with request_id={request_id!r}')
        recovered.request_id = request_id
        raise recovered from None
    try:
        while True:
            if on_update is not None:
                try:
                    on_update(job)
                except Exception as error:
                    if job['status'] in {'pending', 'running', 'interrupted'}:
                        try:
                            client.cancel(job['job_id'])
                        except SeraServiceError:
                            error.add_note(f"Cancellation could not reach Sera; job ID: {job['job_id']}")
                    raise
            if job['status'] == 'completed':
                result = job['result']
                if not result.get('trace', {}).get('remote_verified'):
                    raise SeraServiceError('The required trace has not been verified')
                return ManagedResult(job_id=job['job_id'], selected_recipe_id=result['selected_recipe_id'],
                    artifact_id=result['selected_artifact_id'], artifact_path=result['artifact_path'],
                    trace_url=result['trace']['url'], elapsed_seconds=result['elapsed_seconds'],
                    backend=result.get('backend', 'mlx'), runtime=result.get('runtime'),
                    stop_reason=result.get('stop_reason'))
            if job['status'] not in {'pending', 'running', 'interrupted'}:
                raise SeraServiceError(f"Sera job {job['job_id']} ended: {job['status']}")
            time.sleep(poll_interval)
            job = client.status(job['job_id'])
    except KeyboardInterrupt as error:
        try:
            client.cancel(job['job_id'])
        except SeraServiceError:
            error.add_note(f"Cancellation could not reach Sera; job ID: {job['job_id']}")
        raise
