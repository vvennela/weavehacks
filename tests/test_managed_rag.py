import json
import threading

import pytest
from test_managed_service import OTHER_TOKEN, TOKEN, wait_for
from test_managed_service import manager as manager_fixture

from sera import managed_service as service
from sera.managed_client import Optimize, SeraClient, SeraServiceError

manager = manager_fixture


@pytest.fixture
def endpoint(manager, tmp_path):
    source = tmp_path / 'docs.jsonl'
    source.write_text(json.dumps({'id': 'cedar', 'text': 'Cedar backs up at 03:00 UTC.'}))
    manager.collections = {'manuals': {'source': str(source), 'profiles': ['fixture'],
                                       'owners': ['one'], 'evaluation': None}}
    (manager.folder / 'stall').touch()
    server = service.make_server(manager, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()
    server.server_close()
    thread.join()


def test_natural_language_submission_is_owned_bounded_and_idempotent(manager, endpoint):
    client = SeraClient(api_key=TOKEN, endpoint=endpoint)
    job = client.submit_intent('Run RAG on my manuals', documents='manuals', request_id='rag-1')
    assert client.submit_intent('Run RAG on my manuals', documents='manuals', request_id='rag-1')['job_id'] == job['job_id']
    with pytest.raises(SeraServiceError, match='409'):
        client.submit_intent('Different task', documents='manuals', request_id='rag-1')
    accepted = json.loads((manager.folder / job['job_id'] / 'request.json').read_text())['rag_request']
    assert accepted['intent'] == 'Run RAG on my manuals'
    assert accepted['deadline'] == manager._all()[0]['deadline']
    assert accepted['profiles'][0]['constraints']['quality_floor'] == 0.99
    client.cancel(job['job_id'])
    wait_for(lambda: client.status(job['job_id'])['status'] == 'cancelled')


def test_documents_require_explicit_collection_access(endpoint):
    owner = SeraClient(api_key=TOKEN, endpoint=endpoint)
    other = SeraClient(api_key=OTHER_TOKEN, endpoint=endpoint)
    for client, collection in [(other, 'manuals'), (owner, '/etc/passwd'), (owner, '../manuals')]:
        with pytest.raises(SeraServiceError, match='404'):
            client.submit_intent('Run RAG', documents=collection, request_id='forbidden')


def test_optimize_intent_routes_to_intake_and_cancels_on_interrupt(manager, endpoint):
    jobs = []
    def stop(job):
        jobs.append(job['job_id'])
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        Optimize('Run RAG on my documents', documents='manuals', api_key=TOKEN,
                 endpoint=endpoint, on_update=stop)
    wait_for(lambda: manager.get('one', jobs[0])['status'] == 'cancelled')


def test_needs_input_reaches_customer_as_actionable_questions(monkeypatch):
    from sera.managed_client import SeraNeedsInput
    monkeypatch.setattr(SeraClient, 'submit_intent', lambda *a, **k: {
        'job_id': 'a' * 32, 'status': 'needs-input',
        'result': {'questions': ['Which documents should contain the answers?']}})
    with pytest.raises(SeraNeedsInput) as error:
        Optimize('RAG', documents='manuals', api_key=TOKEN)
    assert error.value.questions == ['Which documents should contain the answers?']


def test_rag_result_loads_retriever_and_checkpoint_together(tmp_path, monkeypatch):
    from sera.backends.mlx import MLXBackend
    from sera.managed_client import ManagedResult
    from sera.rag import RagIndex, RagPipeline
    source = tmp_path / 'docs.jsonl'
    source.write_text(json.dumps({'id': 'x', 'text': 'Some text.'}))
    index = RagIndex.build(source, tmp_path / 'index', chunk_words=128)
    model = object()
    monkeypatch.setattr(MLXBackend, 'load', lambda *a, **k: model)
    result = ManagedResult(job_id='a'*32, selected_recipe_id='q8', artifact_id='b'*64,
                           artifact_path='/checkpoint', trace_url='trace', elapsed_seconds=1.,
                           rag={'index_path': str(index.folder), 'index_hash': index.manifest['index_hash'],
                                'top_k': 1, 'max_tokens': 64, 'seed': 0})
    loaded = result.load()
    assert isinstance(loaded, RagPipeline)
    assert loaded.model is model


def test_general_workload_submission_freezes_examples_and_checks_identity(manager, endpoint):
    client = SeraClient(api_key=TOKEN, endpoint=endpoint)
    examples = [{'prompt': 'Classify broken order', 'expected_json': {'category': 'damage'}}]
    job = client.submit_intent('Classify support tickets', examples=examples, request_id='classification')
    saved = json.loads((manager.folder / job['job_id'] / 'request.json').read_text())['workload_request']
    assert saved['examples'][0]['expected_json'] == {'category': 'damage'}
    assert saved['profiles'][0]['constraints']['quality_floor'] == .99
    assert client.submit_intent('Classify support tickets', examples=examples,
                               request_id='classification')['job_id'] == job['job_id']
    with pytest.raises(SeraServiceError, match='409'):
        client.submit_intent('Classify support tickets', examples=[{'prompt': 'new', 'expected_json': 1}],
                             request_id='classification')
    client.cancel(job['job_id'])
    wait_for(lambda: client.status(job['job_id'])['status'] == 'cancelled')


def test_general_optimize_does_not_require_documents(monkeypatch):
    seen = []
    def submit(self, intent, **kwargs):
        seen.append((intent, kwargs))
        return {'job_id': 'a'*32, 'status': 'needs-input', 'result': {'questions': ['Add test cases']}}
    monkeypatch.setattr(SeraClient, 'submit_intent', submit)
    from sera import SeraNeedsInput
    with pytest.raises(SeraNeedsInput):
        Optimize('Extract invoice fields', api_key=TOKEN, examples=[{'prompt': 'Invoice', 'expected_json': {}}])
    assert seen[0][0] == 'Extract invoice fields'
    assert seen[0][1]['examples'][0]['prompt'] == 'Invoice'


def test_health_check_is_authenticated_and_does_not_expose_credentials(endpoint):
    client = SeraClient(api_key=TOKEN, endpoint=endpoint)
    health = client._request('GET', '/v1/health')
    assert health == {'status': 'ready', 'profiles': ['fixture']}
    with pytest.raises(SeraServiceError, match='401'):
        SeraClient(api_key='invalid', endpoint=endpoint)._request('GET', '/v1/health')
