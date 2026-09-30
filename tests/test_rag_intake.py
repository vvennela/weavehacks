import json
import time

import pytest
from test_native_optimizer import profile

from sera.native_optimizer import validate_native_profile
from sera.rag_intake import IntakeNeedsInput, prepare_rag


def setup(tmp_path):
    source = tmp_path / 'docs.jsonl'
    source.write_text('\n'.join(json.dumps(doc) for doc in [
        {'id': 'cedar', 'text': 'Cedar daily backup starts at 03:00 UTC.'},
        {'id': 'birch', 'text': 'Birch daily backup starts at 06:00 UTC.'}]))
    return {'intent': 'Run RAG over my backup documents', 'source': str(source),
            'profiles': [profile()], 'evaluation': None, 'deadline': time.time() + 60,
            'project': 'fixture/project'}


class Planner:
    calls = 0
    def __init__(self, **kwargs):
        assert kwargs['model'] == 'gpt-6-astra'
        assert kwargs['reasoning_effort'] == 'high'
    def request(self, prompt, schema, **kwargs):
        Planner.calls += 1
        if 'INDEPENDENT VALIDATION' in prompt:
            return {'examples': [{'question': 'When does Birch back up?', 'answer': '06:00 UTC',
                                  'document_id': 'birch', 'evidence': '06:00 UTC'}]}
        assert '03:00 UTC' in prompt
        return {'status': 'ready', 'questions': [], 'profile_id': 'fixture', 'chunk_words': 128,
                'top_k': 1, 'reason': 'Grounded document questions.', 'examples': [
                    {'question': 'When does Cedar daily backup start?', 'answer': '03:00 UTC',
                     'document_id': 'cedar', 'evidence': 'starts at 03:00 UTC'}]}


@pytest.fixture(autouse=True)
def trace(monkeypatch):
    monkeypatch.setattr('sera.rag_intake.trace_native_job', lambda project, run:
                        {'result': run(), 'trace': {'remote_verified': True, 'url': 'fixture'}})


def test_intake_creates_grounded_profile_preserves_gates_and_resumes(tmp_path):
    Planner.calls = 0
    request = setup(tmp_path)
    folder = tmp_path / 'job'
    folder.mkdir()
    hardware = {'backends': ['mlx'], 'memory_bytes': 24000000000}
    value = prepare_rag(request, folder, agent_factory=Planner, hardware=hardware)
    assert value['profile']['tasks'][0]['expected_json'] == {'answer': '03:00 UTC', 'source': 'cedar'}
    for key in ['constraints', 'objective', 'budget', 'source', 'recipes']:
        assert value['profile'][key] == validate_native_profile(profile()).model_dump()[key]
    assert value['rag']['quality_scope'] == 'generated-smoke-tests'
    assert value['rag']['validation_questions'] == 1
    assert len(value['profile']['tasks']) == 2
    assert value['rag']['retrieval']['evidence_recall'] == 1.0
    assert value['rag']['intake_trace']['remote_verified']
    again = prepare_rag(request, folder, agent_factory=Planner, hardware=hardware)
    assert value == again
    assert Planner.calls == 2


def test_no_hardware_fit_never_calls_agent(tmp_path):
    with pytest.raises(IntakeNeedsInput, match='runtime'):
        prepare_rag(setup(tmp_path), tmp_path / 'job', agent_factory=Planner, hardware={'backends': []})


def test_untrusted_planner_cannot_change_budget_or_invent_evidence(tmp_path):
    class Malicious(Planner):
        def request(self, *args, **kwargs):
            result = super().request(*args, **kwargs)
            result['max_run_seconds'] = 9000
            return result
    with pytest.raises(ValueError):
        prepare_rag(setup(tmp_path), tmp_path / 'job', agent_factory=Malicious, hardware={'backends': ['mlx']})
    class Invented(Planner):
        def request(self, *args, **kwargs):
            result = super().request(*args, **kwargs)
            result['examples'][0]['evidence'] = 'Fabricated evidence'
            return result
    with pytest.raises(ValueError, match='evidence'):
        prepare_rag(setup(tmp_path), tmp_path / 'other', agent_factory=Invented, hardware={'backends': ['mlx']})


def test_ambiguous_intent_returns_questions_without_gpu_work(tmp_path):
    class Unsure(Planner):
        def request(self, *args, **kwargs):
            return super().request(*args, **kwargs) | {'status': 'needs-input', 'questions': ['What question should the app answer?']}
    with pytest.raises(IntakeNeedsInput, match='question'):
        prepare_rag(setup(tmp_path), tmp_path / 'job', agent_factory=Unsure, hardware={'backends': ['mlx']})


def test_customer_tests_are_kept_out_of_planner_input(tmp_path):
    request = setup(tmp_path)
    evaluation = tmp_path / 'evaluation.json'
    evaluation.write_text(json.dumps([{'question': 'SECRET QUESTION Cedar backup', 'answer': '03:00 UTC',
                                      'document_id': 'cedar', 'evidence': '03:00 UTC'}]))
    request['evaluation'] = str(evaluation)
    class Private(Planner):
        def request(self, prompt, *args, **kwargs):
            assert 'SECRET QUESTION' not in prompt
            return super().request(prompt, *args, **kwargs)
    result = prepare_rag(request, tmp_path / 'job', agent_factory=Private, hardware={'backends': ['mlx']})
    assert result['rag']['quality_scope'] == 'customer-supplied-tests'
    assert 'SECRET QUESTION' in result['profile']['tasks'][0]['prompt'][1]['content']


def test_interrupted_intake_keeps_original_customer_evaluation(tmp_path):
    request = setup(tmp_path)
    evaluation = tmp_path / 'evaluation.json'
    original = {'question': 'When does Cedar back up?', 'answer': '03:00 UTC',
                'document_id': 'cedar', 'evidence': '03:00 UTC'}
    evaluation.write_text(json.dumps([original]))
    request['evaluation'] = str(evaluation)
    class Interrupted(Planner):
        def request(self, *args, **kwargs):
            raise TimeoutError('interrupted')
    folder = tmp_path / 'job'
    with pytest.raises(TimeoutError):
        prepare_rag(request, folder, agent_factory=Interrupted, hardware={'backends': ['mlx']})
    evaluation.write_text('[]')
    resumed = prepare_rag(request, folder, agent_factory=Planner, hardware={'backends': ['mlx']})
    assert resumed['profile']['tasks'][0]['expected_json']['answer'] == original['answer']


def test_changed_compiled_contract_is_rejected(tmp_path):
    request = setup(tmp_path)
    folder = tmp_path / 'job'
    prepare_rag(request, folder, agent_factory=Planner, hardware={'backends': ['mlx']})
    path = folder / 'rag-compiled.json'
    saved = json.loads(path.read_text())
    saved['profile']['constraints']['quality_floor'] = 0.0
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match='changed'):
        prepare_rag(request, folder, agent_factory=Planner, hardware={'backends': ['mlx']})


def test_expired_intake_does_not_request_a_plan(tmp_path):
    request = setup(tmp_path) | {'deadline': time.time() - 1}
    with pytest.raises(TimeoutError):
        prepare_rag(request, tmp_path / 'job', agent_factory=Planner, hardware={'backends': ['mlx']})


def test_validation_cannot_reuse_planning_documents(tmp_path):
    class Reused(Planner):
        def request(self, prompt, *args, **kwargs):
            result = super().request(prompt, *args, **kwargs)
            if 'INDEPENDENT VALIDATION' in prompt:
                result['examples'][0]['document_id'] = 'cedar'
            return result
    with pytest.raises(ValueError, match='independent'):
        prepare_rag(setup(tmp_path), tmp_path / 'job', agent_factory=Reused,
                    hardware={'backends': ['mlx']})


def test_validation_never_sees_planning_tests_or_results(tmp_path):
    class Blind(Planner):
        def request(self, prompt, *args, **kwargs):
            if 'INDEPENDENT VALIDATION' in prompt:
                assert '03:00 UTC' not in prompt
                assert 'Cedar' not in prompt
                assert 'recipe_id' not in prompt
            return super().request(prompt, *args, **kwargs)
    prepare_rag(setup(tmp_path), tmp_path / 'job', agent_factory=Blind,
                hardware={'backends': ['mlx']})
