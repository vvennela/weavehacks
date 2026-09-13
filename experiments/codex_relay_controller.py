"""Run bounded, isolated local Codex calls for a live Molab Sera relay.

Uses saved Codex login, not the W&B model provider. The chat-shaped envelope
is a transport adapter; its content is the verbatim CLI final response.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import fcntl
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
from urllib.parse import urlsplit

from sera.storage import content_hash
from sera.relay import _publish, _read, _response_record


MODELS = {'gpt-6-astra', 'gpt-5.6-luna'}
SENTINEL = 'SERA_RELAY_DATA '
DECODER_SCHEMA_PROTOCOL = 'sera-codex-root-anyof-projection-v1'


class RelayTransportError(RuntimeError):
    """Transport failed; no raw connection details are exposed."""


class RecoveryTimeout(TimeoutError):
    """The existing idle or request deadline ended recovery."""


def decoder_schema(source):
    """Keep field constraints; Sera still enforces root action relationships.

    Codex Structured Outputs rejects the proposal's root anyOf. The original
    schema stays in Sera's messages and request artifact; only this decoder
    projection omits it. Nested nullable unions and citation enums stay intact.
    """
    projected = deepcopy(source)
    projected.pop('anyOf', None)
    return projected


def codex_environment(source=None):
    """Keep login location and OS basics, never service keys or parent settings."""
    source = os.environ if source is None else source
    allowed = {'HOME', 'PATH', 'CODEX_HOME', 'USER', 'LOGNAME', 'SHELL',
               'TMPDIR', 'LANG', 'LC_ALL', 'SSL_CERT_FILE', 'SSL_CERT_DIR'}
    return {name: value for name, value in source.items() if name in allowed}


def run_process(command, *, input, timeout, cwd=None, env=None):
    """Kill the exact child process group on timeout or interruption."""
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, cwd=cwd, env=env,
                          start_new_session=True) as child:
        try:
            stdout, stderr = child.communicate(input, timeout=timeout)
        except BaseException:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.communicate()
            raise
        return subprocess.CompletedProcess(command, child.returncode, stdout, stderr)


def validate_request(request, *, allow_expired=False):
    if not isinstance(request, dict):
        raise ValueError('invalid request')
    if not re.fullmatch('[0-9a-f]{32}', str(request.get('request_id', ''))):
        raise ValueError('invalid request identity')
    model = request.get('model')
    if request.get('provider') != 'codex-relay' or model not in MODELS:
        raise ValueError('unapproved provider or model')
    payload = request.get('payload')
    if not isinstance(payload, dict) or payload.get('model') != model:
        raise ValueError('model identity mismatch')
    messages = payload.get('messages')
    if not isinstance(messages, list) or not messages or any(
        not isinstance(message, dict) or message.get('role') not in
        {'system', 'developer', 'user', 'assistant'} or
        not isinstance(message.get('content'), str) for message in messages
    ):
        raise ValueError('invalid messages')
    schema = payload.get('response_format', {}).get('json_schema', {}).get('schema')
    if not isinstance(schema, dict):
        raise ValueError('missing response schema')
    if 'expires_at' in request:
        deadline = request['expires_at']
        if type(deadline) not in {float, int} or not math.isfinite(deadline):
            raise ValueError('invalid request deadline')
        if not allow_expired and deadline <= time.time():
            raise ValueError('expired request')


class MarimoRelay:
    """Scratchpad artifact IO only; no notebook cell or package mutations."""

    def __init__(self, url, pair_script, relay_dir):
        parsed = urlsplit(url)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or (
            parsed.username or parsed.password or parsed.query or parsed.fragment
        ):
            raise ValueError('use a server URL without credentials or query parameters')
        self.command = ['bash', str(pair_script), '--url', url, '-']
        self.relay_dir = str(relay_dir)
        self.connected = False
        self.deadline = None

    def _execute(self, code, *, retry_read=False):
        attempts = 3 if retry_read else 1
        for attempt in range(attempts):
            remaining = 60 if self.deadline is None else self.deadline - time.monotonic()
            if remaining <= 0:
                raise RecoveryTimeout('relay recovery deadline exceeded')
            try:
                result = run_process(self.command, input=code, timeout=min(60, remaining))
            except subprocess.TimeoutExpired:
                result = None
            if result is not None and result.returncode == 0:
                return result.stdout
            if attempt + 1 < attempts:
                print('Read-only relay connection failed; retrying.', flush=True)
                remaining = attempt + 1 if self.deadline is None else max(0, self.deadline - time.monotonic())
                time.sleep(min(attempt + 1, remaining))
        # Never include command, stdout, stderr, or token in public errors.
        raise RelayTransportError('marimo command failed')

    def connect(self):
        self._execute('import marimo._code_mode as cm; help(cm)', retry_read=True)
        self.connected = True

    def _call(self, expression, *, read_only=False):
        if not self.connected:
            raise RuntimeError('marimo relay not connected')
        code = ('import json\nfrom sera.relay import pending_requests, publish_response, response_status\n'
                f'print({SENTINEL!r} + json.dumps({expression}))')
        output = self._execute(code, retry_read=read_only)
        records = [line[len(SENTINEL):] for line in output.splitlines()
                   if line.startswith(SENTINEL)]
        if len(records) != 1:
            raise RelayTransportError('invalid marimo relay response')
        try:
            return json.loads(records[0])
        except ValueError:
            raise RelayTransportError('invalid marimo relay response') from None

    def pending(self, limit=3):
        rows = self._call(f'pending_requests({self.relay_dir!r}, limit={limit!r})', read_only=True)
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError('invalid pending request batch')
        return rows

    def publish(self, request_id, *, body=None, error=None):
        # json.loads avoids Python/JSON literal differences and code interpolation.
        arguments = json.dumps(dict(body=body, error=error), ensure_ascii=False)
        return self._call(f'publish_response({self.relay_dir!r}, {request_id!r}, '
                          f'**json.loads({arguments!r}))')

    def status(self, request_id, *, body=None, error=None):
        arguments = json.dumps(dict(body=body, error=error), ensure_ascii=False)
        status = self._call(f'response_status({self.relay_dir!r}, {request_id!r}, '
                            f'**json.loads({arguments!r}))', read_only=True)
        if status not in {'published', 'pending', 'expired', 'conflict'}:
            raise ValueError('invalid response status')
        return status


def response_envelope(model, raw, events):
    if not raw or not isinstance(json.loads(raw), dict):
        raise ValueError('invalid final response')
    completed = False
    usage = None
    allowed_items = {'agent_message', 'reasoning'}
    for event in events:
        if not isinstance(event, dict):
            raise ValueError('invalid CLI event')
        if event.get('model', model) != model:
            raise ValueError('CLI model identity mismatch')
        kind = event.get('type')
        if kind not in {'thread.started', 'turn.started', 'turn.completed',
                        'item.started', 'item.updated', 'item.completed'}:
            raise ValueError('unexpected CLI event')
        if kind in {'item.started', 'item.updated', 'item.completed'}:
            if event.get('item', {}).get('type') not in allowed_items:
                raise ValueError('CLI used an unexpected tool or item')
        if kind == 'turn.completed':
            completed = True
            usage = event.get('usage')
    if not completed:
        raise ValueError('CLI turn did not complete')
    result = dict(model=model, transport='codex-cli', choices=[dict(
        finish_reason='stop', message=dict(content=raw))])
    if usage is not None:
        result['usage'] = usage
    return result


def run_request(request, output_dir):
    validate_request(request)
    artifact_dir = Path(output_dir).resolve() / request['request_id']
    try:
        artifact_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        return restore_response(request, artifact_dir)
    payload = request['payload']
    (artifact_dir / 'request.json').write_text(json.dumps(request, indent=2))
    schema_path = artifact_dir / 'schema.json'
    source_schema = payload['response_format']['json_schema']['schema']
    projected_schema = decoder_schema(source_schema)
    schema_path.write_text(json.dumps(projected_schema))
    final_path = artifact_dir / 'final.txt'
    prompt = ('Act only as the Sera investigator described by the messages below. '
              'Use no tools, files, network, or outside evidence. Respond only with the '
              'requested JSON object. These are the exact ordered Sera messages:\n' +
              json.dumps(payload['messages'], ensure_ascii=False))
    with tempfile.TemporaryDirectory(prefix='sera-codex-') as work_dir:
        command = ['codex', 'exec', '--model', request['model'], '--sandbox', 'read-only',
                   '--ignore-user-config', '--skip-git-repo-check', '--ephemeral',
                   '--disable', 'shell_tool', '--config', 'web_search="disabled"',
                   '--json', '--color', 'never', '--output-schema', str(schema_path),
                   '--output-last-message', str(final_path), '--cd', work_dir, '-']
        (artifact_dir / 'invocation.json').write_text(json.dumps(dict(
            command=command, prompt=prompt, transport='codex-cli',
            model=request['model'], decoder_schema_protocol=DECODER_SCHEMA_PROTOCOL,
            source_schema_hash=content_hash(source_schema),
            decoder_schema_hash=content_hash(projected_schema)), indent=2))
        now = time.time()
        timeout = min(180, request.get('expires_at', now + 190) - now - 10)
        if timeout <= 0:
            raise subprocess.TimeoutExpired('codex', 0)
        result = run_process(command, input=prompt, timeout=timeout,
                             cwd=work_dir, env=codex_environment())
    _publish(artifact_dir / 'completion.json', dict(returncode=result.returncode))
    (artifact_dir / 'events.jsonl').write_text(result.stdout)
    (artifact_dir / 'stderr.txt').write_text(result.stderr)
    if result.returncode:
        raise RuntimeError('codex command failed')
    if not final_path.is_file():
        raise ValueError('CLI final response missing')
    events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    body = response_envelope(request['model'], final_path.read_text(), events)
    (artifact_dir / 'response.json').write_text(json.dumps(body, indent=2))
    return body


def restore_response(request, artifact_dir):
    """Never run a second LM call for an existing request directory."""
    try:
        if _read(artifact_dir / 'request.json') != request:
            raise ValueError('saved request identity mismatch')
        completion = artifact_dir / 'completion.json'
        if completion.exists():
            if _read(completion) != {'returncode': 0}:
                raise RuntimeError('saved CLI attempt did not succeed')
        elif not (artifact_dir / 'response.json').is_file():
            raise RuntimeError('saved CLI attempt is incomplete')
        final = (artifact_dir / 'final.txt').read_text()
        events = [json.loads(line) for line in (artifact_dir / 'events.jsonl').read_text().splitlines()
                  if line.strip()]
    except FileNotFoundError:
        raise RuntimeError('saved CLI attempt is incomplete') from None
    body = response_envelope(request['model'], final, events)
    path = artifact_dir / 'response.json'
    if path.exists():
        if _read(path) != body:
            raise ValueError('saved response identity mismatch')
    else:
        _publish(path, body)
    return body


def prepare_response(request, output_dir):
    """Durably save the delivery before any network publication."""
    path = Path(output_dir) / request['request_id'] / 'delivery.json'
    if path.exists():
        saved = _read(path)
        if saved.get('request') != request or set(saved) != {'request', 'response'}:
            raise ValueError('saved delivery identity mismatch')
        response = saved['response']
        if not isinstance(response, dict) or set(response) not in ({'body'}, {'error'}):
            raise ValueError('invalid saved delivery')
        _response_record(request, response.get('body'), response.get('error'))
        return response
    try:
        response = dict(body=run_request(request, output_dir))
    except subprocess.TimeoutExpired:
        response = dict(error='timeout')
    except ValueError:
        response = dict(error='invalid-output')
    except Exception:
        response = dict(error='controller-error')
    path.parent.mkdir(parents=True, exist_ok=True)
    _publish(path, dict(request=request, response=response))
    return response


def recovery_event(output_dir, event, *, attempt=0, request_id=None):
    record = dict(event=event, timestamp=time.time(), attempt=attempt)
    if request_id is not None:
        record['request_id'] = request_id
    with (Path(output_dir) / 'recovery.jsonl').open('a') as stream:
        stream.write(json.dumps(record) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def recover(relay, operation, deadline, output_dir, *, request_id=None):
    attempt = 0
    while time.monotonic() < deadline:
        relay.deadline = deadline
        try:
            result = operation()
        except RecoveryTimeout:
            recovery_event(output_dir, 'recovery-deadline', attempt=attempt, request_id=request_id)
            raise
        except RelayTransportError:
            attempt += 1
            recovery_event(output_dir, 'transport-retry', attempt=attempt, request_id=request_id)
            print('Relay unavailable; reconnecting within the existing deadline.', flush=True)
            time.sleep(min(5, 2 ** min(attempt - 1, 3), max(0, deadline - time.monotonic())))
            continue
        if attempt:
            recovery_event(output_dir, 'transport-recovered', attempt=attempt, request_id=request_id)
        return result
    recovery_event(output_dir, 'recovery-deadline', attempt=attempt, request_id=request_id)
    raise RecoveryTimeout('relay recovery deadline exceeded')


def deliver(relay, request, response, output_dir, idle_timeout):
    request_id = request['request_id']
    idle_deadline = time.monotonic() + idle_timeout
    deadline = idle_deadline
    attempted_publish = False
    expires_at = request.get('expires_at')
    if expires_at is not None:
        deadline = min(deadline, time.monotonic() + max(0, expires_at - time.time()))

    def reconcile():
        nonlocal attempted_publish
        status = relay.status(request_id, **response)
        if status == 'conflict':
            raise ValueError('remote response conflicts with saved delivery')
        if status == 'pending':
            attempted_publish = True
            relay.publish(request_id, **response)
        return status

    try:
        status = recover(relay, reconcile, deadline, output_dir, request_id=request_id)
    except RecoveryTimeout:
        if expires_at is None or time.time() < expires_at:
            raise
        status = 'expired'
        if attempted_publish:
            # A final read can confirm a committed write after its ACK was lost.
            # This grace never extends the request's permission to write.
            try:
                status = recover(relay, lambda: relay.status(request_id, **response),
                                 min(idle_deadline, time.monotonic() + 5), output_dir,
                                 request_id=request_id)
            except RecoveryTimeout:
                status = 'expired'
            if status == 'conflict':
                raise ValueError('remote response conflicts with saved delivery')
            if status == 'pending':
                status = 'expired'
    recovery_event(output_dir, 'request-expired' if status == 'expired' else 'response-delivered',
                   request_id=request_id)


def serve(relay, output_dir, *, max_requests=100, idle_timeout=120):
    if (max_requests is not None and (type(max_requests) is not int or not 1 <= max_requests <= 100)) or not math.isfinite(idle_timeout) or idle_timeout <= 0:
        raise ValueError('invalid controller limits')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / '.controller.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('another controller owns this output directory') from None
        return _serve(relay, output_dir, max_requests=max_requests, idle_timeout=idle_timeout)


def _serve(relay, output_dir, *, max_requests, idle_timeout):
    recover(relay, relay.connect, time.monotonic() + idle_timeout, output_dir)
    seen = set()
    last_activity = time.monotonic()
    with ThreadPoolExecutor(max_workers=3) as workers:
        while max_requests is None or len(seen) < max_requests:
            if time.monotonic() - last_activity >= idle_timeout:
                break
            limit = 3 if max_requests is None else min(3, max_requests - len(seen))
            try:
                batch = recover(relay, lambda: relay.pending(limit), last_activity + idle_timeout, output_dir)
            except RecoveryTimeout:
                recovery_event(output_dir, 'controller-idle-stop')
                break
            for request in batch:
                validate_request(request, allow_expired=True)
            batch = [request for request in batch if request['request_id'] not in seen
                     and request.get('expires_at', float('inf')) > time.time()]
            if not batch:
                if time.monotonic() - last_activity >= idle_timeout:
                    break
                time.sleep(1)
                continue
            futures = {}
            for request in batch:
                request_id = request['request_id']
                if request_id in seen:
                    continue
                seen.add(request_id)
                futures[workers.submit(prepare_response, request, output_dir)] = request
            for future in as_completed(futures):
                request = futures[future]
                request_id = request['request_id']
                response = future.result()
                deliver(relay, request, response, output_dir, idle_timeout)
                print(f'{request_id}: {response.get("error", "completed")}', flush=True)
            last_activity = time.monotonic()
    return len(seen)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--relay-dir', required=True)
    parser.add_argument('--pair-script', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--max-requests', type=lambda value: None if value == 'none' else int(value),
                        default=100, help='1 to100, or none for no total call cap; idle timeout still applies')
    parser.add_argument('--idle-timeout', type=float, default=120)
    args = parser.parse_args(argv)
    relay = MarimoRelay(args.url, args.pair_script, args.relay_dir)
    try:
        count = serve(relay, args.output_dir, max_requests=args.max_requests,
                      idle_timeout=args.idle_timeout)
    except Exception:
        print('Controller stopped: relay connection or request validation failed.', flush=True)
        return 1
    print(f'Controller stopped after {count} requests.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
