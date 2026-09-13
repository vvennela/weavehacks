"""The provider certificate must cover the expanded controls and actual evidence."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from sera.agent import AGENT_MODEL, schema_hash
from sera.config import MODEL_ID, CONTROL_ROLES
from sera.provider_check import provider_cases, require_provider_check
from sera.storage import content_hash


def valid_response(case):
    evidence = case['evidence']
    if case['role'] == 'proposal':
        active = evidence['supported_changes'] and evidence['remaining_trials'] > 0
        lever, values = next(iter(evidence['supported_changes'].items())) if active else (None, [None])
        return dict(action='trial' if active else 'keep-baseline', proposal_id='p1',
                    agent_role=CONTROL_ROLES.get(lever, 'batching'),
                    parent_trial_id=evidence['trial_id'], model_id=MODEL_ID,
                    changed_lever=lever, proposed_value=values[0], evidence_used=['p95_latency_ms'],
                    predicted_metric_change='Lower latency', confidence=0.5,
                    expected_trial_cost=1 if active else 0,
                    falsification_condition='Latency does not improve', reason='Format fixture')
    if case['role'] == 'arbiter':
        return dict(ranked_proposal_ids=evidence['legal_proposal_ids'][:1], reason='Eligible')
    return dict(selected_trial_id=evidence['deterministic_selection'],
                prediction_outcome='confirmed' if evidence['candidate_quality_pass'] else
                    ('refuted' if evidence['candidate_tested'] else 'not-tested'), reason='Measured gate')


def certificate():
    from sera.agent import request_schema
    cases = provider_cases()
    return dict(schema_version='sera-provider-check-v1', model=AGENT_MODEL, project='test/project',
                schema_hash=schema_hash(), cases_hash=content_hash(cases), requests=[
                    dict(role=case['role'], evidence=deepcopy(case['evidence']),
                         request_schema=request_schema(case['role'], case['evidence']),
                         schema_hash=content_hash(request_schema(case['role'], case['evidence'])), attempts=[
                        dict(raw_response={'choices': [{'finish_reason': 'stop',
                              'message': {'content': json.dumps(valid_response(case))}}]})])
                    for case in cases])


def verify(tmp_path, record):
    path = tmp_path / 'result.json'
    path.write_text(json.dumps(record))
    return require_provider_check(path, SimpleNamespace(model=AGENT_MODEL, project='test/project'))


def test_cases_cover_each_control_and_nondefault_parent():
    cases = provider_cases()
    assert len(cases) == 34
    assert {role: sum(case['role'] == role for case in cases)
            for role in ('proposal', 'arbiter', 'frontier')} == dict(proposal=14, arbiter=10, frontier=10)
    proposals = [case['evidence'] for case in cases if case['role'] == 'proposal']
    assert any(e['supported_changes'] == {'max_num_seqs': [4]} for e in proposals)
    assert any(e['supported_changes'] == {'max_model_len': [2048]} for e in proposals)
    assert any(e.get('configuration', {}).get('max_num_batched_tokens') == 2048
               and e['supported_changes'] == {'max_num_batched_tokens': [4096]} for e in proposals)
    for lever, value in [('enable_prefix_caching', True), ('enable_chunked_prefill', False),
                         ('enforce_eager', False), ('gpu_memory_utilization', .85)]:
        assert any(e['supported_changes'] == {lever: [value]} for e in proposals)


def test_current_certificate_passes_and_stale_schema_fails(tmp_path):
    record = certificate()
    assert verify(tmp_path, record)['valid_with_one_retry'] == 34
    record['schema_hash'] = 'old-schema'
    with pytest.raises(ValueError, match='schemas'):
        verify(tmp_path, record)


def test_schema_valid_but_out_of_scope_response_does_not_certify_provider(tmp_path):
    record = certificate()
    entry = record['requests'][0]
    message = entry['attempts'][0]['raw_response']['choices'][0]['message']
    response = json.loads(message['content'])
    response['parent_trial_id'] = 'invented-parent'
    message['content'] = json.dumps(response)
    with pytest.raises(ValueError, match='context'):
        verify(tmp_path, record)


def test_request_explains_output_schema_to_model_as_well_as_decoder(monkeypatch):
    import sys
    from sera.agent import WandbAgent, request_schema
    case = provider_cases()[0]
    captured = {}

    def create(**payload):
        captured.update(payload)
        return SimpleNamespace(model_dump=lambda **_: {'choices': [{
            'finish_reason': 'stop', 'message': {'content': json.dumps(valid_response(case))}}]})

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setenv('WANDB_API_KEY', 'not-a-real-test-key')
    monkeypatch.setitem(sys.modules, 'openai', SimpleNamespace(OpenAI=Client))
    agent = WandbAgent(project='test/project')
    parsed = agent.request('proposal', case['evidence'], 'Propose one trial.')
    assert parsed is not None
    system = captured['messages'][0]['content']
    assert 'Output JSON schema:\n' in system
    expected = request_schema('proposal', case['evidence'])
    assert json.loads(system.split('Output JSON schema:\n', 1)[1]) == expected
    assert captured['response_format']['json_schema']['strict'] is True
    assert captured['response_format']['json_schema']['schema'] == expected
    assert agent.history[0]['request_schema'] == expected
    assert agent.history[0]['schema_hash'] == content_hash(expected)


def test_swarm_sends_focused_question_but_preserves_full_audit_evidence(monkeypatch):
    import sys
    from sera.agent import WandbAgent, request_schema
    from sera.investigation_prompt import build_investigation_prompt, PROMPT_PROJECTION_VERSION
    case = provider_cases()[0]
    source = deepcopy(case['evidence']) | dict(swarm_phase='refine', investigator_id='scheduling',
        previous_rounds=[{'untrusted_old_proposal': 'not the answer'}])
    compact = build_investigation_prompt(source)
    captured = {}

    def create(**payload):
        captured.update(payload)
        return SimpleNamespace(model_dump=lambda **_: {'choices': [{
            'finish_reason': 'stop', 'message': {'content': json.dumps(valid_response(case))}}]})

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setenv('WANDB_API_KEY', 'not-a-real-test-key')
    monkeypatch.setitem(sys.modules, 'openai', SimpleNamespace(OpenAI=Client))
    agent = WandbAgent(project='test/project')
    parsed = agent.request('proposal', source, 'Investigate independently.')
    assert parsed is not None
    assert json.loads(captured['messages'][1]['content']) == compact
    assert 'fresh decision' in captured['messages'][0]['content']
    entry = agent.history[0]
    assert entry['evidence'] == source
    assert entry['prompt_evidence'] == compact
    assert entry['prompt_projection_version'] == PROMPT_PROJECTION_VERSION
    assert entry['source_evidence_sha256'] == content_hash(source)
    assert entry['prompt_evidence_sha256'] == content_hash(compact)
    assert entry['request_schema'] == request_schema('proposal', source)


def test_old_static_certificate_cannot_enable_dynamic_protocol(tmp_path):
    from sera.agent import SCHEMAS
    record = certificate()
    record['schema_hash'] = content_hash({name: schema.model_json_schema()
                                          for name, schema in SCHEMAS.items()})
    with pytest.raises(ValueError, match='schemas'):
        verify(tmp_path, record)


@pytest.mark.parametrize('field', ['schema_hash', 'request_schema'])
def test_certificate_recomputes_each_request_schema(tmp_path, field):
    record = certificate()
    record['requests'][0][field] = 'untrusted'
    record['passed'] = True
    with pytest.raises(ValueError, match='request schema'):
        verify(tmp_path, record)


@pytest.mark.parametrize('retry_passes', [True, False])
def test_invalid_metric_response_uses_retry_and_keeps_both_raw_responses(monkeypatch, retry_passes):
    import sys
    from sera.agent import WandbAgent
    case = provider_cases()[0]
    bad = valid_response(case) | {'evidence_used': ['metrics.p95_latency_ms']}
    responses = [bad, valid_response(case) if retry_passes else bad]
    calls = []

    def create(**payload):
        calls.append(payload)
        response = responses.pop(0)
        return SimpleNamespace(model_dump=lambda **_: {'choices': [{
            'finish_reason': 'stop', 'message': {'content': json.dumps(response)}}]})

    class Client:
        def __init__(self, **kwargs):
            assert kwargs['max_retries'] == 0
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setenv('WANDB_API_KEY', 'not-a-real-test-key')
    monkeypatch.setitem(sys.modules, 'openai', SimpleNamespace(
        OpenAI=Client, APIStatusError=type('APIStatusError', (Exception,), {}),
        APIConnectionError=type('APIConnectionError', (Exception,), {})))
    agent = WandbAgent(project='test/project')
    parsed = agent.request('proposal', case['evidence'], 'Format check')
    if retry_passes:
        assert parsed.evidence_used == ['p95_latency_ms']
    else:
        assert parsed is None
    assert len(calls) == 2
    assert all(call['max_tokens'] == 2048 for call in calls)
    attempts = agent.history[0]['attempts']
    assert [attempt['schema_valid'] for attempt in attempts] == [False, retry_passes]
    assert json.loads(attempts[0]['raw_response']['choices'][0]['message']['content']) == bad


def test_certificate_retries_invalid_metric_but_does_not_count_it_as_first_valid(tmp_path):
    record = certificate()
    entry = record['requests'][0]
    failed = deepcopy(entry['attempts'][0])
    message = failed['raw_response']['choices'][0]['message']
    response = json.loads(message['content']) | {'evidence_used': ['invented_metric']}
    message['content'] = json.dumps(response)
    failed['schema_valid'] = True  # Recompute; never trust this flag.
    entry['attempts'].insert(0, failed)
    assert verify(tmp_path, record)['first_pass_valid'] == 33
    record['requests'][3]['attempts'].insert(0, deepcopy(failed))
    with pytest.raises(ValueError, match='33 first-pass'):
        verify(tmp_path, record)


def test_provider_certificate_cannot_cross_transports(tmp_path):
    record = certificate()
    path = tmp_path / 'result.json'
    path.write_text(json.dumps(record))
    relay = SimpleNamespace(model=AGENT_MODEL, project='test/project', provider='codex-relay')
    with pytest.raises(ValueError, match='provider'):
        require_provider_check(path, relay)
    record['provider'] = 'codex-relay'
    for entry in record['requests']:
        entry['provider'] = 'codex-relay'
    path.write_text(json.dumps(record))
    assert require_provider_check(path, relay)['provider'] == 'codex-relay'
    record['requests'][0]['provider'] = 'wandb'
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='provider'):
        require_provider_check(path, relay)


def test_format_check_accepts_explicit_agent_and_preserves_all_thirty_cases(tmp_path):
    from sera.agent import parse_response
    from sera.provider_check import check_provider
    rows = certificate()['requests']

    class Agent:
        provider = 'codex-relay'
        model = AGENT_MODEL
        project = 'test/project'

        def __init__(self):
            self.history = []

        def request(self, role, evidence, instruction):
            row = deepcopy(rows[len(self.history)])
            row['provider'] = self.provider
            row['attempts'][0]['schema_valid'] = True
            self.history.append(row)
            return parse_response(role, row['attempts'][0]['raw_response']['choices'][0]['message']['content'], evidence)

        def review(self, evidence):
            return self.request('frontier', evidence, '')

    agent = Agent()
    record = check_provider(project=agent.project, model=agent.model,
                            output_dir=tmp_path / 'check', agent=agent)
    assert record['passed'] and record['completed_requests'] == 34
    assert record['provider'] == 'codex-relay'
    assert require_provider_check(tmp_path / 'check/result.json', agent)['first_pass_valid'] == 34
