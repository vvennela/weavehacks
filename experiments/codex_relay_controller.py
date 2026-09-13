"""Run bounded, isolated local Codex calls for a live Molab Sera relay.

Uses saved Codex login, not the W&B model provider. The chat-shaped envelope
is a transport adapter; its content is the verbatim CLI final response.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
from urllib.parse import urlsplit

from sera.storage import content_hash


MODELS = {'gpt-6-astra', 'gpt-5.6-luna'}
SENTINEL = 'SERA_RELAY_DATA '
DECODER_SCHEMA_PROTOCOL = 'sera-codex-root-anyof-projection-v1'


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


def validate_request(request):
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
    if 'expires_at' in request and request['expires_at'] <= time.time():
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

    def _execute(self, code):
        result = run_process(self.command, input=code, timeout=60)
        if result.returncode:
            # Never include command, stdout, stderr, or token in public errors.
            raise RuntimeError('marimo command failed')
        return result.stdout

    def connect(self):
        self._execute('import marimo._code_mode as cm; help(cm)')
        self.connected = True

    def _call(self, expression):
        if not self.connected:
            raise RuntimeError('marimo relay not connected')
        code = ('import json\nfrom sera.relay import pending_requests, publish_response\n'
                f'print({SENTINEL!r} + json.dumps({expression}))')
        output = self._execute(code)
        records = [line[len(SENTINEL):] for line in output.splitlines()
                   if line.startswith(SENTINEL)]
        if len(records) != 1:
            raise RuntimeError('invalid marimo relay response')
        return json.loads(records[0])

    def pending(self, limit=3):
        rows = self._call(f'pending_requests({self.relay_dir!r}, limit={limit!r})')
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError('invalid pending request batch')
        return rows

    def publish(self, request_id, *, body=None, error=None):
        # json.loads avoids Python/JSON literal differences and code interpolation.
        arguments = json.dumps(dict(body=body, error=error), ensure_ascii=False)
        return self._call(f'publish_response({self.relay_dir!r}, {request_id!r}, '
                          f'**json.loads({arguments!r}))')


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
    artifact_dir.mkdir(parents=True, exist_ok=False)
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


def serve(relay, output_dir, *, max_requests=100, idle_timeout=120):
    if (max_requests is not None and (type(max_requests) is not int or not 1 <= max_requests <= 100)) or idle_timeout <= 0:
        raise ValueError('invalid controller limits')
    relay.connect()
    seen = set()
    last_activity = time.monotonic()
    with ThreadPoolExecutor(max_workers=3) as workers:
        while max_requests is None or len(seen) < max_requests:
            batch = relay.pending(3 if max_requests is None else min(3, max_requests - len(seen)))
            for request in batch:
                validate_request(request)
            batch = [request for request in batch if request['request_id'] not in seen]
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
                futures[workers.submit(run_request, request, output_dir)] = request_id
            for future in as_completed(futures):
                request_id = futures[future]
                try:
                    response = dict(body=future.result())
                except subprocess.TimeoutExpired:
                    response = dict(error='timeout')
                except ValueError:
                    response = dict(error='invalid-output')
                except Exception:
                    response = dict(error='controller-error')
                relay.publish(request_id, **response)
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
