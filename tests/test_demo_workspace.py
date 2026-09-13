"""All workspace views describe the same saved, measured demo run."""
import json
from pathlib import Path
import threading
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def test_public_demo_data_matches_audited_gpu_results():
    saved = json.loads((ROOT / 'output/demo-run.json').read_text())
    audit = json.loads((ROOT / 'evidence/openai-example-v2/audit-summary.json').read_text())
    assert saved['run_id'] == 'openai-example-v2'
    assert saved['trials'] == audit['trials']
    assert saved['rounds'] == audit['rounds']
    assert saved['decision'] == audit['decision']
    assert saved['weave_url'] == audit['weave']['url']
    assert saved['source'] == 'measured GPU recording'
    assert 'invocation' not in saved and 'source_records' not in saved


def test_workspace_has_only_the_three_demo_views():
    for name in ['sera-lab-preview.html', 'lab-notebook.html']:
        page = (ROOT / 'output' / name).read_text()
        for label in ['Overview', 'Workflow', 'Trial ledger']:
            assert label in page
        for old in ['source-filter', 'model-filter', 'phase-filter', 'data-substrate',
                    '/lab/performance', '/lab/models', 'sera-notebook.js', 'sera-lab.js']:
            assert old not in page
        assert 'sera-workspace.js' in page
        assert 'demo-replay.html' in page
        assert 'id="demo-player"' in page
        assert 'id="replay-frame"' not in page
        assert 'sera-demo-replay.js' in page
        assert 'sera-landing.css' in page and 'sera-lab.css' in page


def test_workspace_does_not_load_the_old_simulator_ledger():
    script = (ROOT / 'output/sera-workspace.js').read_text()
    assert '/demo-run.json' in script
    assert '/api/metrics' not in script
    assert 'round.proposals' in script and 'round.arbiter' in script
    assert 'showModal' in script
    assert 'data.weave_url' in script
    assert 'notebook-app' not in script


def test_demo_replay_is_the_measured_run_not_a_generated_example():
    replay = (ROOT / 'output/demo-replay.html').read_text()
    assert '618.587946' in replay
    assert '771.046407' in replay
    assert replay.lower().startswith('<!doctype html>')


def test_replay_evidence_links_resolve_outside_the_embedded_frame():
    replay = (ROOT / 'output/demo-replay.html').read_text()
    assert 'href="../docs/' not in replay
    assert 'href="../evidence/' not in replay
    assert 'github.com/vvennela/weavehacks/blob/main/evidence/' in replay


def test_local_server_serves_the_public_demo_record(tmp_path):
    from web.server import Server
    server = Server(0, tmp_path / 'accounts.sqlite3', demo_account=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f'http://localhost:{server.server_port}/demo-run.json', timeout=5) as response:
            data = json.load(response)
        assert data['run_id'] == 'openai-example-v2'
        assert len(data['trials']) == 4
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_native_replay_keeps_the_recorded_measurements_and_scopes_its_dom():
    script = (ROOT / 'output/sera-demo-replay.js').read_text()
    assert '771.0464070005401' in script and '618.5879460026626' in script
    assert 'root.querySelector' in script
    assert "element('theme-toggle')" not in script
    assert 'demo:pause' in script
    assert '19.773' in script
