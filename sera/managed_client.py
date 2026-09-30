"""Customer interface to a Sera-managed local research worker."""
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .model_artifact import verify_artifact


class SeraServiceError(RuntimeError):
    def __init__(self, message, *, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class SeraNeedsInput(SeraServiceError):
    def __init__(self, job_id, questions):
        super().__init__(' '.join(questions))
        self.job_id, self.questions = job_id, questions


class SeraRequirementsNotMet(SeraServiceError):
    def __init__(self, result):
        super().__init__('No candidate met the requested precision and quality/performance limits. '
                         'The verified baseline is available as error.result; it does not meet the requested format.')
        self.result = result


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
    measurements: dict = field(default_factory=dict)

    rag: dict | None = None
    workload: dict | None = None
    requirements: dict | None = None

    def verify(self):
        if self.rag is not None:
            from .rag import RagIndex
            RagIndex(self.rag["index_path"], expected_hash=self.rag["index_hash"])
        return verify_artifact(self.artifact_path, expected_id=self.artifact_id, backend=self.backend)

    def load(self):
        if self.rag is None:
            return self._load_model()
        from .rag import RagIndex, RagPipeline
        index = RagIndex(self.rag['index_path'], expected_hash=self.rag['index_hash'])
        return RagPipeline(self._load_model(), index, top_k=self.rag['top_k'],
                           max_tokens=self.rag['max_tokens'], seed=self.rag['seed'])

    def _load_model(self, *, use_configured_runtime=True):
        if use_configured_runtime:
            import os
            import sys

            from .onboarding import home_path
            config = home_path() / 'runtime.json'
            if config.exists():
                python = json.loads(config.read_text())['python']
                if os.path.abspath(python) != os.path.abspath(sys.executable):
                    from .runtime_model import RuntimeModel
                    return RuntimeModel(python, self)

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
                raise SeraServiceError(f'Sera request failed with HTTP {error.code}', status_code=error.code) from None
            except (URLError, TimeoutError, ConnectionError):
                if attempt == 2:
                    raise SeraServiceError('Sera is unreachable; retry using the same request_id') from None
                time.sleep(0.1 * (attempt + 1))
        raise AssertionError('Unreachable')

    def submit(self, profile_id, *, request_id):
        return self._request('POST', '/v1/jobs', {'profile_id': profile_id, 'request_id': request_id})

    def submit_intent(self, intent, *, request_id, documents=None, examples=None):
        body = {'intent': intent, 'request_id': request_id}
        if documents is not None:
            body['documents'] = documents
        if examples is not None:
            body['examples'] = examples
        return self._request('POST', '/v1/workloads', body)

    def status(self, job_id):
        return self._request('GET', '/v1/jobs/' + self._job_id(job_id))

    def cancel(self, job_id):
        return self._request('DELETE', '/v1/jobs/' + self._job_id(job_id))

    @staticmethod
    def _job_id(job_id):
        if not isinstance(job_id, str) or len(job_id) != 32 or any(c not in '0123456789abcdef' for c in job_id):
            raise ValueError('Invalid Sera job ID')
        return job_id


def Optimize(profile_id, *, api_key=None, endpoint=None, request_id=None,
             on_update=None, poll_interval=1.0, documents=None, examples=None):
    """Describe inference with examples, connect documents, or use a registered profile.

    Reuse request_id after a connection failure to recover the same job.
    Ctrl-C cancels the accepted job. The service owns W&B credentials and gates.
    """
    if type(poll_interval) not in (int, float) or not math.isfinite(poll_interval) or poll_interval <= 0:
        raise ValueError('Supply a positive finite poll interval')
    if api_key is None:
        from .onboarding import local_connection
        connection = local_connection()
        api_key = connection['api_key']
        endpoint = endpoint or connection['endpoint']
    client = SeraClient(api_key=api_key, endpoint=endpoint or 'http://127.0.0.1:8765')
    request_id = request_id if request_id is not None else uuid.uuid4().hex
    try:
        legacy = documents is None and examples is None and isinstance(profile_id, str) and not any(c.isspace() for c in profile_id)
        if legacy:
            try:
                job = client.submit(profile_id, request_id=request_id)
            except SeraServiceError as error:
                if error.status_code != 404:
                    raise
                job = client.submit_intent(profile_id, request_id=request_id)
        else:
            job = client.submit_intent(profile_id, documents=documents, examples=examples, request_id=request_id)
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
                managed = ManagedResult(job_id=job['job_id'], selected_recipe_id=result['selected_recipe_id'],
                    artifact_id=result['selected_artifact_id'], artifact_path=result['artifact_path'],
                    trace_url=result['trace']['url'], elapsed_seconds=result['elapsed_seconds'],
                    backend=result.get('backend', 'mlx'), runtime=result.get('runtime'),
                    stop_reason=result.get('stop_reason'), measurements=result.get('measurements', {}),
                    rag=result.get('rag'), workload=result.get('workload'), requirements=result.get('requirements'))
                if managed.requirements is not None and not managed.requirements['met']:
                    raise SeraRequirementsNotMet(managed)
                return managed
            if job['status'] == 'needs-input':
                raise SeraNeedsInput(job['job_id'], job['result']['questions'])
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
