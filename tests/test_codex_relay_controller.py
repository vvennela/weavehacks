import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from experiments import codex_relay_controller as controller
from sera.agent import parse_response, request_schema
from sera.storage import content_hash


def request():
    return dict(request_id='a' * 32, provider='codex-relay', model='gpt-5.6-luna',
                project='test/project', payload=dict(model='gpt-5.6-luna',
                messages=[dict(role='system', content='Use measured evidence.'),
                          dict(role='user', content='{"latency": 12}')],
                response_format=dict(type='json_schema', json_schema=dict(
                    schema={'type': 'object', 'properties': {'action': {'type': 'string'}}}))))


def test_decoder_removes_only_root_anyof_without_mutating_source():
    source = request_schema('proposal', {'metrics': {'p95_latency_ms': 12}})
    original = deepcopy(source)
    decoder = controller.decoder_schema(source)
    assert 'anyOf' not in decoder
    assert decoder == {key: value for key, value in original.items() if key != 'anyOf'}
    assert decoder['properties']['changed_lever']['anyOf'] == original[
        'properties']['changed_lever']['anyOf']
    assert decoder['properties']['evidence_used']['items']['enum'] == ['p95_latency_ms']
    decoder['properties']['evidence_used']['items']['enum'].append('invented')
    assert source == original


def test_decoder_projection_does_not_relax_sera_action_validation():
    evidence = {'metrics': {'p95_latency_ms': 12}}
    controller.decoder_schema(request_schema('proposal', evidence))
    value = dict(action='keep-baseline', proposal_id='p1', agent_role='batching',
        parent_trial_id='baseline', model_id='qwen', changed_lever='max_num_batched_tokens',
        proposed_value=2048, expected_trial_cost=0, evidence_used=['p95_latency_ms'],
        predicted_metric_change='Unmeasured', confidence=0.5,
        falsification_condition='No measured gain', reason='An invalid keep action')
    with pytest.raises(ValueError, match='null lever/value'):
        parse_response('proposal', json.dumps(value), evidence)


def test_codex_environment_keeps_login_context_but_not_service_secrets():
    env = controller.codex_environment(dict(HOME='/home/user', PATH='/bin',
        CODEX_HOME='/home/user/.codex', WANDB_API_KEY='secret', MARIMO_TOKEN='secret',
        OPENAI_API_KEY='secret', OTHER_SECRET='secret', PYTHONPATH='untrusted'))
    assert env == dict(HOME='/home/user', PATH='/bin', CODEX_HOME='/home/user/.codex')


def test_request_rejects_wrong_model_or_unsafe_identity():
    for field, value in [('request_id', '../../escape'), ('provider', 'wandb'),
                         ('model', 'unapproved-model')]:
        item = request()
        item[field] = value
        with pytest.raises(ValueError):
            controller.validate_request(item)
    item = request()
    item['payload']['model'] = 'gpt-6-astra'
    with pytest.raises(ValueError):
        controller.validate_request(item)


def test_expired_requests_fail_before_starting_codex(tmp_path, monkeypatch):
    item = request()
    item['expires_at'] = 1
    monkeypatch.setattr(controller, 'run_process', lambda *a, **k: pytest.fail('spawned'))
    with pytest.raises(ValueError, match='expired'):
        controller.run_request(item, tmp_path)
    assert not list(tmp_path.iterdir())


def test_timeout_kills_and_reaps_exact_child_process_group(monkeypatch):
    actions = []
    class Child:
        pid = 54321
        calls = 0
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def communicate(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired('child', 180)
            actions.append('reaped')
            return '', ''
    monkeypatch.setattr(controller.subprocess, 'Popen', lambda *a, **k: Child())
    monkeypatch.setattr(controller.os, 'killpg', lambda pid, sig: actions.append(pid))
    with pytest.raises(subprocess.TimeoutExpired):
        controller.run_process(['codex'], input='prompt', timeout=180)
    assert actions == [54321, 'reaped']


def test_pair_requires_successful_help_then_uses_only_sentinel(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        output = 'module help' if len(calls) == 1 else 'noise\nSERA_RELAY_DATA []\n'
        return subprocess.CompletedProcess(command, 0, output, '')
    monkeypatch.setattr(controller, 'run_process', run)
    pair = controller.MarimoRelay('https://example.test/', '/pair.sh', '/remote/relay')
    pair.connect()
    assert pair.pending(3) == []
    assert calls[0][1]['input'] == 'import marimo._code_mode as cm; help(cm)'
    assert '--token' not in calls[0][0]
    assert 'pending_requests' in calls[1][1]['input']
    assert calls[0][1]['timeout'] == 60


def test_failed_help_stops_before_polling(monkeypatch):
    monkeypatch.setattr(controller, 'run_process', lambda *a, **k:
                        subprocess.CompletedProcess([], 1, '', 'secret detail'))
    pair = controller.MarimoRelay('https://example.test/', '/pair.sh', '/remote/relay')
    with pytest.raises(RuntimeError, match='marimo command failed'):
        pair.connect()
    with pytest.raises(RuntimeError, match='not connected'):
        pair.pending(3)


def test_codex_preserves_payload_output_and_actual_usage(monkeypatch, tmp_path):
    raw = '{ "action": "trial" }\n'
    seen = {}
    def run(command, **kwargs):
        seen.update(command=command, **kwargs)
        Path(command[command.index('--output-last-message') + 1]).write_text(raw)
        events = [dict(type='thread.started', thread_id='real-thread'),
                  dict(type='item.completed', item=dict(type='agent_message', text=raw)),
                  dict(type='turn.completed', usage=dict(input_tokens=9, output_tokens=4))]
        return subprocess.CompletedProcess(command, 0,
            '\n'.join(json.dumps(e) for e in events), '')
    monkeypatch.setattr(controller, 'run_process', run)
    result = controller.run_request(request(), tmp_path)
    assert result['choices'][0]['message']['content'] == raw
    assert result['usage'] == dict(input_tokens=9, output_tokens=4)
    assert result['transport'] == 'codex-cli'
    assert result['model'] == 'gpt-5.6-luna'
    assert 'id' not in result
    command = seen['command']
    assert command[command.index('--sandbox') + 1] == 'read-only'
    assert '--ignore-user-config' in command and '--ephemeral' in command
    assert seen['timeout'] == 180
    assert json.dumps(request()['payload']['messages'], ensure_ascii=False) in seen['input']
    assert json.loads((tmp_path / ('a' * 32) / 'request.json').read_text()) == request()
    invocation = json.loads((tmp_path / ('a' * 32) / 'invocation.json').read_text())
    source_schema = request()['payload']['response_format']['json_schema']['schema']
    assert invocation['decoder_schema_protocol'] == controller.DECODER_SCHEMA_PROTOCOL
    assert invocation['source_schema_hash'] == content_hash(source_schema)
    assert invocation['decoder_schema_hash'] == content_hash(controller.decoder_schema(source_schema))


@pytest.mark.parametrize('event', [dict(type='item.started', item=dict(type='command_execution')),
    dict(type='item.completed', item=dict(type='mcp_tool_call')),
    dict(type='function_call', name='unexpected-tool'),
    dict(type='turn.failed'), dict(type='thread.started', model='wrong-model')])
def test_tool_calls_errors_and_model_mismatches_fail_closed(event):
    events = [event, dict(type='turn.completed')]
    with pytest.raises(ValueError):
        controller.response_envelope('gpt-5.6-luna', '{}', events)


def test_malformed_missing_or_unfinished_output_is_not_published():
    for raw, events in [('', []), ('not json', [dict(type='turn.completed')]), ('{}', [])]:
        with pytest.raises(ValueError):
            controller.response_envelope('gpt-5.6-luna', raw, events)


@pytest.mark.parametrize('returncode', [0, 1])
def test_missing_final_file_or_nonzero_cli_fails(tmp_path, monkeypatch, returncode):
    monkeypatch.setattr(controller, 'run_process', lambda *a, **k:
        subprocess.CompletedProcess([], returncode, '{"type":"turn.completed"}', ''))
    with pytest.raises((ValueError, RuntimeError)):
        controller.run_request(request(), tmp_path)


def test_controller_services_distinct_requests_once_and_bounds_concurrency(tmp_path, monkeypatch):
    from threading import Barrier, Lock
    barrier = Barrier(3)
    active = 0
    peak = 0
    lock = Lock()
    items = []
    for number in range(3):
        item = deepcopy(request())
        item['request_id'] = f'{number:032x}'
        items.append(item)
    class Relay:
        def connect(self): pass
        def pending(self, limit): return items[:limit]
        def publish(self, request_id, **response): published.append((request_id, response))
    published = []
    def run(item, output_dir):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        barrier.wait(timeout=5)
        with lock:
            active -= 1
        return {'model': item['model']}
    monkeypatch.setattr(controller, 'run_request', run)
    assert controller.serve(Relay(), tmp_path, max_requests=3, idle_timeout=1) == 3
    assert peak == 3
    assert len({row[0] for row in published}) == 3


def test_controller_publishes_safe_error_without_exception_details(tmp_path, monkeypatch):
    published = []
    class Relay:
        def connect(self): pass
        def pending(self, limit): return [request()]
        def publish(self, request_id, **response): published.append(response)
    def fail(*args):
        raise subprocess.TimeoutExpired('secret command', 180, output='secret output')
    monkeypatch.setattr(controller, 'run_request', fail)
    controller.serve(Relay(), tmp_path, max_requests=1)
    assert published == [dict(error='timeout')]
