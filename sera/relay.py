"""Bounded file relay for a local Codex controller. This module never runs commands."""

import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import uuid

from .agent import ProviderTransportError, WandbAgent


MODELS = frozenset({'gpt-6-astra', 'gpt-5.6-luna'})
ERROR_CODES = frozenset({'controller-error', 'invalid-output', 'model-unavailable', 'timeout'})
MAX_RECORD_BYTES = 8 * 1024 * 1024


def _directory(relay_dir):
    path = Path(relay_dir)
    if path.is_symlink():
        raise ValueError('Relay directory must not be a symlink')
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise ValueError('Relay path must be a directory')
    return path.resolve()


def _request_id(value):
    if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{32}', value) is None:
        raise ValueError('Invalid relay request ID')
    return value


def _read(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Relay record must be a regular file')
        raw = stream.read(MAX_RECORD_BYTES + 1)
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError('Relay record is too large')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('Relay record must be an object')
    return value


def _publish(path, record):
    data = json.dumps(record, allow_nan=False).encode()
    if len(data) > MAX_RECORD_BYTES:
        raise ValueError('Relay record is too large')
    # A hard link publishes the complete file atomically and refuses any existing target.
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.relay-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.link(temporary, path)
        finally:
            temporary.unlink()


def _validate_request(record, request_id):
    if record.get('request_id') != _request_id(request_id):
        raise ValueError('Relay request ID does not match file')
    if record.get('provider') != 'codex-relay' or record.get('model') not in MODELS:
        raise ValueError('Unsupported relay provider or model')
    if not isinstance(record.get('project'), str) or not record['project']:
        raise ValueError('Relay project is required')
    deadline = record.get('expires_at')
    if (not isinstance(deadline, (int, float)) or isinstance(deadline, bool)
            or not math.isfinite(deadline)):
        raise ValueError('Relay deadline must be finite')
    if deadline <= time.time():
        raise ValueError('Relay request expired')
    payload = record.get('payload')
    if not isinstance(payload, dict) or payload.get('model') != record['model']:
        raise ValueError('Relay payload model mismatch')
    messages = payload.get('messages')
    if not isinstance(messages, list) or not messages:
        raise ValueError('Relay payload needs messages')
    for message in messages:
        if (not isinstance(message, dict) or message.get('role') not in {'system', 'user', 'assistant'}
                or not isinstance(message.get('content'), str)):
            raise ValueError('Invalid relay message')
    return record


def _validate_body(body, model):
    if not isinstance(body, dict) or body.get('model') != model:
        raise ValueError('Relay response model mismatch')
    choices = body.get('choices')
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ValueError('Relay response needs one choice')
    choice = choices[0]
    message = choice.get('message')
    if (not isinstance(choice.get('finish_reason'), str) or not isinstance(message, dict)
            or not isinstance(message.get('content'), str)):
        raise ValueError('Invalid relay response content')
    return body | {'provider': 'codex-relay', 'synthetic': True}


def pending_requests(relay_dir, limit=3):
    """Return live, unanswered requests; malformed or expired files are never work."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Relay request limit must be between 1 and 100')
    directory = _directory(relay_dir)
    records = []
    for path in sorted(directory.glob('*.request.json')):
        request_id = path.name.removesuffix('.request.json')
        try:
            _request_id(request_id)
            if os.path.lexists(directory / f'{request_id}.response.json'):
                continue
            record = _validate_request(_read(path), request_id)
        except (OSError, ValueError, TypeError):
            continue
        records.append(record)
        if len(records) == limit:
            break
    return records


def publish_response(relay_dir, request_id, body=None, error=None):
    """Publish one response to an existing live request, without replacing prior data."""
    request_id = _request_id(request_id)
    directory = _directory(relay_dir)
    request = _validate_request(_read(directory / f'{request_id}.request.json'), request_id)
    if (body is None) == (error is None):
        raise ValueError('Supply exactly one response body or safe error code')
    if error is not None:
        if not isinstance(error, str) or error not in ERROR_CODES:
            raise ValueError('Unknown relay error code')
        response = {'request_id': request_id, 'error': error}
    else:
        response = {'request_id': request_id, 'body': _validate_body(body, request['model'])}
    _publish(directory / f'{request_id}.response.json', response)
    return {'request_id': request_id, 'published': True}


class RelayAgent(WandbAgent):
    """Use local Codex inference, keeping Sera prompts, validation, and audit history."""

    provider = 'codex-relay'

    def __init__(self, *, project, model, relay_dir, timeout=180, poll_interval=.2):
        if model not in MODELS:
            raise ValueError('Unsupported Codex relay model')
        for value in (timeout, poll_interval):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError('Relay wait settings must be positive and finite')
        super().__init__(project=project, model=model)
        self.relay_dir = _directory(relay_dir)
        self.timeout = timeout
        self.poll_interval = poll_interval

    def fork(self):
        return RelayAgent(project=self.project, model=self.model, relay_dir=self.relay_dir,
                          timeout=self.timeout, poll_interval=self.poll_interval)

    def _complete(self, payload):
        request_id = uuid.uuid4().hex
        deadline = time.monotonic() + self.timeout
        request = {'request_id': request_id, 'provider': self.provider, 'model': self.model,
                   'project': self.project, 'payload': payload, 'expires_at': time.time() + self.timeout}
        _validate_request(request, request_id)
        _publish(self.relay_dir / f'{request_id}.request.json', request)
        response_path = self.relay_dir / f'{request_id}.response.json'
        while time.monotonic() < deadline:
            try:
                response = _read(response_path)
            except FileNotFoundError:
                time.sleep(min(self.poll_interval, max(0, deadline - time.monotonic())))
                continue
            if response.get('request_id') != request_id:
                raise ValueError('Relay response request ID mismatch')
            if set(response) == {'request_id', 'error'}:
                error = response['error']
                if not isinstance(error, str) or error not in ERROR_CODES:
                    raise ValueError('Unknown relay error code')
                raise ProviderTransportError(f'Codex relay {error}')
            if set(response) != {'request_id', 'body'}:
                raise ValueError('Invalid relay response fields')
            return _validate_body(response['body'], self.model)
        raise TimeoutError('Codex relay response deadline exceeded')
