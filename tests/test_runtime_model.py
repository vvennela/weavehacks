import io
import json


def test_runtime_protocol_loads_generates_and_closes():
    from sera.runtime_model import serve
    calls = []
    class Model:
        def generate(self, prompt, **kwargs):
            calls.append(prompt)
            return {'text': 'answer', 'tokens': 1}
        def close(self):
            calls.append('closed')
    source = io.StringIO('\n'.join(json.dumps(item) for item in [
        {'backend': 'mlx', 'artifact_path': '/model', 'artifact_id': 'a'*64},
        {'operation': 'generate', 'args': ['question'], 'kwargs': {'max_tokens': 8, 'seed': 0}},
        {'operation': 'close'}]) + '\n')
    output = io.StringIO()
    serve(source, output, loader=lambda value: Model())
    rows = [json.loads(line) for line in output.getvalue().splitlines()]
    assert rows == [{'result': 'ready'}, {'result': {'text': 'answer', 'tokens': 1}}, {'result': None}]
    assert calls == ['question', 'closed']


def test_runtime_protocol_rejects_arbitrary_methods_and_closes():
    from sera.runtime_model import serve
    closed = []
    class Model:
        def close(self): closed.append(True)
    output = io.StringIO()
    serve(io.StringIO('{}\n{"operation":"__class__"}\n'), output, loader=lambda value: Model())
    assert json.loads(output.getvalue().splitlines()[1])['error'] == 'Unsupported inference operation'
    assert closed == [True]


def test_result_load_uses_configured_separate_runtime(tmp_path, monkeypatch):
    from sera import runtime_model
    from sera.managed_client import ManagedResult
    monkeypatch.setenv('SERA_HOME', str(tmp_path))
    (tmp_path/'runtime.json').write_text(json.dumps({'python': '/separate/python'}))
    seen = []
    monkeypatch.setattr(runtime_model, 'RuntimeModel', lambda python, result: seen.append(python) or 'loaded')
    result = ManagedResult('a'*32, 'int8', 'b'*64, '/model', 'trace', 1.)
    assert result.load() == 'loaded'
    assert seen == ['/separate/python']
