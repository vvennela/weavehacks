"""Offline replay uses only the supplied measured record."""

import json
import re
import sys
from types import SimpleNamespace

import pytest

import sera


def trial(name, latency, throughput=20):
    return {'trial_id': name, 'status': 'collected',
            'reduced': {'p95_latency_ms': latency, 'output_tokens_per_second': throughput},
            'task_quality': {'passed': True, 'mean': 1.0},
            'runtime': {'sampled_peak_memory_mib': 900}}


def report():
    return {'status': 'ready', 'model_id': 'my-model', 'objective': {'priority': 'latency'},
            'baseline': trial('baseline', 200), 'search_trials': [trial('trial-1', 150)],
            'decision': {'selected': 'trial-1', 'outcome': 'improved'},
            'returned_runner_closed': False,
            'search': {'stop_reason': 'budget-exhausted', 'rounds': [{
                'round': 1, 'trial_ids': ['trial-1'], 'specialists': [{
                    'investigator_id': 'scheduling', 'status': 'accepted',
                    'initial_proposal': {'changed_lever': 'enable_prefix_caching',
                                         'proposed_value': True, 'reason': 'Repeated inputs'},
                    'proposal': {'changed_lever': 'enforce_eager', 'proposed_value': False,
                                 'reason': 'Peer review changed my proposal'}}],
                'arbiter': {'ranked_proposal_ids': ['scheduling:p1'], 'reason': 'Test graphs'}}]}}


def data(replay):
    return json.loads(re.search(r'<script id="replay-data" type="application/json">(.*?)</script>',
                               replay.html, re.S).group(1))


def test_replay_snapshots_actual_result_and_saves_offline(tmp_path):
    original = report()
    replay = sera.visualize(SimpleNamespace(report=original), speed=4)
    original['baseline']['reduced']['p95_latency_ms'] = 999
    payload = data(replay)
    assert payload['speed'] == 4
    stage = payload['stages'][0]
    assert stage['trials'][0]['metrics']['p95_latency_ms'] == 200
    assert stage['decision']['selected'] == 'trial-1'
    assert stage['rounds'][0]['agents'][0]['final']['reason'] == 'Peer review changed my proposal'
    assert stage['returned_runner_closed'] is False
    assert '19.773' not in replay.html
    assert 'Schematic pacing' in replay.html
    saved = replay.save(tmp_path / 'replay.html')
    assert saved.read_text() == replay.html
    assert 'sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"' in replay._repr_html_()
    assert 'allow-same-origin' not in replay._repr_html_()


def test_saved_stages_use_their_own_measurements_and_limits(tmp_path):
    stage_dir = tmp_path / '001-latency'
    stage_dir.mkdir()
    (stage_dir / 'result.json').write_text(json.dumps(report()))
    staged = {'status': 'closed', 'k_percent': 3, 'returned_runner_closed': True,
              'stages': [{'stage': 'latency', 'output_dir': str(stage_dir),
                          'constraints': {'p95_latency_ms': 206, 'quality_floor': .99}}]}
    source = tmp_path / 'result.json'
    source.write_text(json.dumps(staged))
    payload = data(sera.visualize(source, output_path=tmp_path / 'out.html'))
    assert payload['k_percent'] == 3
    assert payload['stages'][0]['constraints']['p95_latency_ms'] == 206
    assert payload['stages'][0]['trials'][1]['metrics']['p95_latency_ms'] == 150
    assert (tmp_path / 'out.html').exists()


@pytest.mark.parametrize('path', ['../secret', '/etc', 'https://example.com/report'])
def test_stage_paths_cannot_escape_result_folder(tmp_path, path):
    result = SimpleNamespace(report={'stages': [{'output_dir': path}]}, output_dir=tmp_path)
    with pytest.raises(ValueError, match='stage path'):
        sera.visualize(result)


def test_sensitive_fields_are_excluded_and_html_is_escaped():
    source = report()
    attack = '</script><img src=x onerror=alert(1)>'
    source.update(prompts=['private-prompt'], agent_calls=[{'api_key': 'private-key'}],
                  weave_url='javascript:alert(1)')
    source['search']['rounds'][0]['specialists'][0]['proposal']['reason'] = attack
    source['search_trials'][0]['requests'] = [{'output': 'private-output'}]
    replay = sera.visualize(SimpleNamespace(report=source))
    assert all(value not in replay.html for value in ('private-prompt', 'private-key', 'private-output', attack))
    assert data(replay)['stages'][0]['rounds'][0]['agents'][0]['final']['reason'] == attack
    assert data(replay)['stages'][0]['weave_url'] is None
    assert 'textContent' in replay.html


@pytest.mark.parametrize('value', [None, {}, {'status': 'no-safe-configuration'}])
def test_missing_trials_do_not_invent_results(value):
    if value is None:
        with pytest.raises(TypeError):
            sera.visualize(value)
        return
    stage = data(sera.visualize(SimpleNamespace(report=value)))['stages'][0]
    assert stage['trials'] == []
    assert stage['returned_runner_closed'] is None


@pytest.mark.parametrize('speed', [0, -1, float('nan'), float('inf'), True, '8'])
def test_invalid_speed_is_rejected(speed):
    with pytest.raises(ValueError, match='speed'):
        sera.visualize(SimpleNamespace(report=report()), speed=speed)


def test_throughput_objective_and_failed_trials_remain_distinct():
    source = report()
    source['objective']['priority'] = 'throughput'
    source['search_trials'].append({'trial_id': 'failed', 'status': 'startup-failed',
                                    'task_quality': {'passed': False}})
    stage = data(sera.visualize(SimpleNamespace(report=source)))['stages'][0]
    assert stage['objective'] == 'throughput'
    assert stage['trials'][-1]['metrics']['output_tokens_per_second'] is None
    assert stage['trials'][-1]['status'] == 'startup-failed'
    assert stage['trials'][-1]['quality']['passed'] is False


def test_malformed_report_and_missing_stage_record(tmp_path):
    with pytest.raises(ValueError, match='object'):
        sera.visualize(SimpleNamespace(report=[]))
    replay = sera.visualize(SimpleNamespace(report={'stages': [{'stage': 'quantization',
        'output_dir': '002-quantization'}]}, output_dir=tmp_path))
    assert data(replay)['stages'][0]['record_status'] == 'missing'


def test_large_summary_is_rejected_instead_of_silently_truncated():
    source = report()
    source['search']['rounds'] *= 3000
    with pytest.raises(ValueError, match='1 MB'):
        sera.visualize(SimpleNamespace(report=source))


def test_notebook_display_uses_an_isolated_iframe(monkeypatch):
    monkeypatch.setitem(sys.modules, 'marimo', SimpleNamespace(Html=lambda value: ('html', value)))
    replay = sera.visualize(SimpleNamespace(report=report()))
    kind, content = replay._display_()
    assert kind == 'html'
    assert content.startswith('<iframe ')
    assert 'srcdoc="&lt;!doctype html&gt;' in content


def test_symlinked_stage_record_cannot_read_outside_root(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    external = tmp_path / 'external.json'
    external.write_text(json.dumps(report()))
    stage = source / '001-latency'
    stage.mkdir()
    (stage / 'result.json').symlink_to(external)
    with pytest.raises(ValueError, match='stage path'):
        sera.visualize(SimpleNamespace(report={'stages': [{'output_dir': str(stage)}]},
                                       output_dir=source))


def test_trace_link_keeps_only_explicit_https_url():
    source = report()
    source['weave_url'] = 'https://wandb.ai/team/project/r/call/record'
    assert data(sera.visualize(SimpleNamespace(report=source)))['stages'][0]['weave_url'] == source['weave_url']
    source['weave_url'] = 'https://user:password@example.com'
    assert data(sera.visualize(SimpleNamespace(report=source)))['stages'][0]['weave_url'] is None
