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


@pytest.mark.parametrize('failure', ['exit', 'timeout'])
def test_read_only_poll_recovers_from_one_connection_failure(monkeypatch, failure):
    calls = []
    def run(command, **kwargs):
        calls.append(kwargs['input'])
        if len(calls) == 1:
            if failure == 'timeout':
                raise subprocess.TimeoutExpired('private connection', 60)
            return subprocess.CompletedProcess(command, 1, '', 'private connection detail')
        return subprocess.CompletedProcess(command, 0, 'SERA_RELAY_DATA []\n', '')
    monkeypatch.setattr(controller, 'run_process', run)
    monkeypatch.setattr(controller.time, 'sleep', lambda _: None)
    pair = controller.MarimoRelay('https://example.test/', '/pair.sh', '/remote/relay')
    pair.connected = True
    assert pair.pending(3) == []
    assert len(calls) == 2
    assert calls[0] == calls[1]


def test_read_connection_retry_is_bounded_and_redacts_details(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 1, '', 'PRIVATE_TOKEN')
    monkeypatch.setattr(controller, 'run_process', run)
    monkeypatch.setattr(controller.time, 'sleep', lambda _: None)
    pair = controller.MarimoRelay('https://example.test/', '/pair.sh', '/remote/relay')
    with pytest.raises(RuntimeError, match='marimo command failed') as error:
        pair.connect()
    assert len(calls) == 3
    assert 'PRIVATE_TOKEN' not in str(error.value)
    assert not pair.connected


def test_ambiguous_response_publication_is_not_blindly_retried(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append(kwargs['input'])
        return subprocess.CompletedProcess(command, 1, '', '')
    monkeypatch.setattr(controller, 'run_process', run)
    monkeypatch.setattr(controller.time, 'sleep', lambda _: None)
    pair = controller.MarimoRelay('https://example.test/', '/pair.sh', '/remote/relay')
    pair.connected = True
    with pytest.raises(RuntimeError):
        pair.publish('a' * 32, error='timeout')
    assert len(calls) == 1


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
        def status(self, request_id, **response): return 'pending'
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
        def status(self, request_id, **response): return 'pending'
        def pending(self, limit): return [request()]
        def publish(self, request_id, **response): published.append(response)
    def fail(*args):
        raise subprocess.TimeoutExpired('secret command', 180, output='secret output')
    monkeypatch.setattr(controller, 'run_request', fail)
    controller.serve(Relay(), tmp_path, max_requests=1)
    assert published == [dict(error='timeout')]


def test_uncapped_controller_exceeds_hundred_requests_and_stops_when_idle(tmp_path, monkeypatch):
    published = []
    class Relay:
        def connect(self): pass
        def status(self, request_id, **response): return 'pending'
        def pending(self, limit):
            if len(published) >= 102:
                return []
            return [request() | {'request_id': f'{len(published):032x}'}]
        def publish(self, request_id, **response): published.append(request_id)
    monkeypatch.setattr(controller, 'run_request', lambda item, output_dir: {'model': item['model']})
    fake_time(monkeypatch)
    assert controller.serve(Relay(), tmp_path, max_requests=None, idle_timeout=.1) == 102


class FakeClock:
    now = 1000.0
    def time(self): return self.now
    def sleep(self, seconds): self.now += seconds


def fake_time(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(controller.time, 'time', clock.time)
    monkeypatch.setattr(controller.time, 'monotonic', clock.time)
    monkeypatch.setattr(controller.time, 'sleep', clock.sleep)
    return clock


def test_controller_recovers_after_more_than_three_transport_failures(tmp_path, monkeypatch, capsys):
    fake_time(monkeypatch)
    calls = []
    def run(command, **kwargs):
        calls.append(kwargs['input'])
        if len(calls) <= 5:
            return subprocess.CompletedProcess(command, 1, '', 'PRIVATE_TOKEN')
        output = 'help' if 'help(cm)' in kwargs['input'] else 'SERA_RELAY_DATA []\n'
        return subprocess.CompletedProcess(command, 0, output, '')
    monkeypatch.setattr(controller, 'run_process', run)
    relay = controller.MarimoRelay('https://example.test/', '/pair.sh', '/relay')
    assert controller.serve(relay, tmp_path, idle_timeout=30) == 0
    assert len(calls) > 5
    events = [json.loads(line) for line in (tmp_path / 'recovery.jsonl').read_text().splitlines()]
    assert any(event['event'] == 'transport-recovered' for event in events)
    assert 'PRIVATE_TOKEN' not in capsys.readouterr().out + json.dumps(events)


def test_publish_ack_loss_is_reconciled_without_duplicate_write_or_lm(tmp_path, monkeypatch):
    fake_time(monkeypatch)
    writes = []
    lm = []
    class Relay:
        def connect(self): pass
        def pending(self, limit): return [request()]
        def status(self, request_id, **response):
            return 'published' if writes else 'pending'
        def publish(self, request_id, **response):
            writes.append(response)
            raise controller.RelayTransportError('PRIVATE_TOKEN')
    monkeypatch.setattr(controller, 'run_request', lambda *args: lm.append(1) or {'model': 'gpt-5.6-luna'})
    assert controller.serve(Relay(), tmp_path, max_requests=1) == 1
    assert len(writes) == len(lm) == 1


def test_outage_stops_at_idle_deadline(tmp_path, monkeypatch):
    clock = fake_time(monkeypatch)
    class Relay:
        def connect(self): raise controller.RelayTransportError('PRIVATE_TOKEN')
    with pytest.raises(controller.RecoveryTimeout):
        controller.serve(Relay(), tmp_path, idle_timeout=7)
    assert clock.now == 1007


def test_expiry_during_publish_outage_does_not_write_late(tmp_path, monkeypatch):
    clock = fake_time(monkeypatch)
    writes = []
    class Relay:
        def connect(self): pass
        def pending(self, limit): return [request() | {'expires_at': 1003}]
        def status(self, request_id, **response): raise controller.RelayTransportError('secret')
        def publish(self, *args, **kwargs): writes.append(1)
    monkeypatch.setattr(controller, 'run_request', lambda *args: {'model': 'gpt-5.6-luna'})
    assert controller.serve(Relay(), tmp_path, max_requests=1) == 1
    assert not writes
    assert clock.now == 1003


def test_restart_reuses_saved_delivery_without_second_lm_call(tmp_path, monkeypatch):
    fake_time(monkeypatch)
    responses = []
    calls = []
    class Relay:
        broken = True
        def connect(self): pass
        def pending(self, limit): return [request()]
        def status(self, request_id, **response):
            if self.broken:
                raise controller.RelayTransportError('secret')
            return 'pending'
        def publish(self, request_id, **response): responses.append(response)
    relay = Relay()
    body = controller.response_envelope('gpt-5.6-luna', '{}', [{'type': 'turn.completed'}])
    monkeypatch.setattr(controller, 'run_request', lambda *args: calls.append(1) or body)
    with pytest.raises(controller.RecoveryTimeout):
        controller.serve(relay, tmp_path, max_requests=1, idle_timeout=3)
    relay.broken = False
    assert controller.serve(relay, tmp_path, max_requests=1) == 1
    assert len(calls) == len(responses) == 1


def test_existing_incomplete_request_is_not_reissued(tmp_path, monkeypatch):
    directory = tmp_path / request()['request_id']
    directory.mkdir()
    (directory / 'request.json').write_text(json.dumps(request()))
    monkeypatch.setattr(controller, 'run_process', lambda *a, **k: pytest.fail('second LM invocation'))
    with pytest.raises(RuntimeError, match='incomplete'):
        controller.run_request(request(), tmp_path)


def test_restart_recovers_completed_cli_artifacts_and_checks_request_identity(tmp_path, monkeypatch):
    directory = tmp_path / request()['request_id']
    directory.mkdir()
    (directory / 'request.json').write_text(json.dumps(request()))
    (directory / 'final.txt').write_text('{"action":"trial"}')
    (directory / 'events.jsonl').write_text('{"type":"turn.completed"}\n')
    (directory / 'completion.json').write_text('{"returncode":0}')
    monkeypatch.setattr(controller, 'run_process', lambda *a, **k: pytest.fail('second LM invocation'))
    assert controller.run_request(request(), tmp_path)['choices'][0]['message']['content'] == '{"action":"trial"}'
    changed = deepcopy(request())
    changed['payload']['messages'][0]['content'] = 'different prompt'
    with pytest.raises(ValueError, match='identity'):
        controller.run_request(changed, tmp_path)


def test_idle_poll_timeout_is_a_clean_stop(tmp_path, monkeypatch):
    clock = fake_time(monkeypatch)
    class Relay:
        def connect(self): pass
        def pending(self, limit):
            clock.sleep(4)
            raise controller.RecoveryTimeout('deadline')
    assert controller.serve(Relay(), tmp_path, idle_timeout=4) == 0


def test_ack_lost_at_expiry_can_be_confirmed_without_second_write(tmp_path, monkeypatch):
    clock = fake_time(monkeypatch)
    writes = []
    reads = []
    class Relay:
        def connect(self): pass
        def pending(self, limit): return [request() | {'expires_at': 1003}]
        def status(self, request_id, **response):
            reads.append(clock.now)
            return 'published' if writes else 'pending'
        def publish(self, request_id, **response):
            writes.append(response)
            clock.sleep(3)
            raise controller.RelayTransportError('lost ACK')
    monkeypatch.setattr(controller, 'run_request', lambda *args: {'model': 'gpt-5.6-luna'})
    assert controller.serve(Relay(), tmp_path, max_requests=1) == 1
    assert len(writes) == 1 and reads == [1000, 1003]
    assert 'response-delivered' in (tmp_path / 'recovery.jsonl').read_text()


def test_publish_not_committed_is_retried_only_after_missing_response_read(tmp_path, monkeypatch):
    fake_time(monkeypatch)
    operations = []
    class Relay:
        def connect(self): pass
        def pending(self, limit): return [request()]
        def status(self, *args, **kwargs):
            operations.append('read-missing')
            return 'pending'
        def publish(self, *args, **kwargs):
            operations.append('publish')
            if operations.count('publish') == 1:
                raise controller.RelayTransportError('outage')
    monkeypatch.setattr(controller, 'run_request', lambda *args: {'model': 'gpt-5.6-luna'})
    controller.serve(Relay(), tmp_path, max_requests=1)
    assert operations == ['read-missing', 'publish', 'read-missing', 'publish']


@pytest.mark.parametrize('saved', ['{', '{}', '{"request":{},"response":{"error":"secret"}}'])
def test_corrupt_saved_delivery_fails_closed_without_any_lm_or_publish(tmp_path, monkeypatch, saved):
    directory = tmp_path / request()['request_id']
    directory.mkdir()
    (directory / 'delivery.json').write_text(saved)
    monkeypatch.setattr(controller, 'run_request', lambda *a: pytest.fail('LM invocation'))
    with pytest.raises(ValueError):
        controller.prepare_response(request(), tmp_path)


def test_remote_conflict_stops_without_overwrite(tmp_path, monkeypatch):
    class Relay:
        def connect(self): pass
        def pending(self, limit): return [request()]
        def status(self, *args, **kwargs): return 'conflict'
        def publish(self, *args, **kwargs): pytest.fail('overwritten')
    monkeypatch.setattr(controller, 'run_request', lambda *args: {'model': 'gpt-5.6-luna'})
    with pytest.raises(ValueError, match='conflicts'):
        controller.serve(Relay(), tmp_path, max_requests=1)


def test_second_controller_cannot_share_output_directory(tmp_path):
    with (tmp_path / '.controller.lock').open('a') as lock:
        controller.fcntl.flock(lock, controller.fcntl.LOCK_EX | controller.fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match='another controller'):
            controller.serve(object(), tmp_path)


@pytest.mark.parametrize('response', [{}, {'error': 'PRIVATE_TOKEN'}, {'body': {}},
                                     {'body': {}, 'error': 'timeout'}, None])
def test_invalid_saved_response_fails_closed(tmp_path, monkeypatch, response):
    directory = tmp_path / request()['request_id']
    directory.mkdir()
    (directory / 'delivery.json').write_text(json.dumps(dict(request=request(), response=response)))
    monkeypatch.setattr(controller, 'run_request', lambda *a: pytest.fail('LM invocation'))
    with pytest.raises(ValueError):
        controller.prepare_response(request(), tmp_path)


def test_expired_request_in_batch_does_not_block_live_request(tmp_path, monkeypatch):
    fake_time(monkeypatch)
    invoked = []
    expired = request() | {'expires_at': 999}
    live = request() | {'request_id': 'b' * 32, 'expires_at': 1100}
    class Relay:
        def connect(self): pass
        def pending(self, limit): return [expired, live][:limit]
        def status(self, *args, **kwargs): return 'pending'
        def publish(self, *args, **kwargs): pass
    monkeypatch.setattr(controller, 'run_request', lambda item, _: invoked.append(item['request_id']) or {})
    assert controller.serve(Relay(), tmp_path, max_requests=2, idle_timeout=1) == 1
    assert invoked == ['b' * 32]
