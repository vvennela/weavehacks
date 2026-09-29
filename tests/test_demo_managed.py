from contextlib import contextmanager
from types import SimpleNamespace

from scripts import demo_managed as demo


def test_demo_survives_missing_quality_and_reads_completed_result(monkeypatch, capsys):
    monkeypatch.setenv('SERA_ACCESS_KEY', 'fixture-key')
    monkeypatch.setattr('sys.argv', ['demo_managed.py', '--request-id', 'fixture'])
    @contextmanager
    def load():
        yield SimpleNamespace(generate=lambda *a, **k: {'text': '{"answer":15}'})
    def optimize(*args, **kwargs):
        kwargs['on_update']({'status': 'running', 'progress': {'measurements': {
            'baseline': {'peak_bytes': 100, 'quality': None}, 'scope': 'Fixture memory scope',
            'trials': [{'recipe_id': 'bad', 'status': 'failed', 'measurement': {
                'peak_bytes': 50, 'quality': None}, 'confirmation': {}, 'accepted': False}]}}})
        kwargs['on_update']({'status': 'completed', 'result': {'measurements': {
            'baseline': {'peak_bytes': 100, 'quality': 1.0}, 'scope': 'Fixture memory scope',
            'trials': [{'recipe_id': 'good', 'status': 'measured', 'measurement': {
                'peak_bytes': 60, 'quality': 1.0, 'p95_latency_ms': 30.0},
                'confirmation': {'peak_bytes': 65, 'p95_latency_ms': 31.0},
                'baseline_control': {'peak_bytes': 90}, 'accepted': True}]}}})
        return SimpleNamespace(selected_recipe_id='good', load=load, trace_url='fixture-trace')
    monkeypatch.setattr(demo.Sera, 'Optimize', optimize)
    demo.main()
    output = capsys.readouterr().out
    assert 'quality unavailable' in output
    assert 'Fixture memory scope' in output
    assert '27.78%' in output
    assert 'p95 latency 31.0 ms' in output
    assert 'conservative' in output
    assert 'Independent request' in output
