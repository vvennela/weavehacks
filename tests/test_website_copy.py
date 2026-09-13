"""The website describes FAST_START without changing the existing page layout."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'output'


@pytest.mark.parametrize('name', ['index.html', 'product.html', 'sera-design-preview.html'])
def test_specialists_match_the_live_swarm(name):
    page = (OUTPUT / name).read_text()
    for role in ['scheduling', 'memory_context', 'output_quality']:
        assert f'data-specialist="{role}"' in page
    assert 'data-specialist="parallelism"' not in page
    assert 'Weave' in page and 'ARIA' in page
    assert 'specialist-workbench' in page and 'sera-landing.css' in page


@pytest.mark.parametrize('name', ['index.html', 'models.html', 'sera-design-preview.html'])
def test_models_match_the_measured_workloads(name):
    page = (OUTPUT / name).read_text()
    assert 'Qwen2.5-72B' in page and 'Qwen3-0.6B' in page and 'GLM-4-9B' in page
    for old in ['Qwen3-8B', 'DeepSeek-R1-Distill', 'Moonlight-16B', 'Three open-weight models']:
        assert old not in page
    assert '24 GiB' in page and '99%' in page


@pytest.mark.parametrize('name', ['index.html', 'resources.html', 'sera-design-preview.html'])
def test_faq_separates_live_execution_from_offline_demo(name):
    page = (OUTPUT / name).read_text()
    assert 'Live demo' in page and 'API keys' in page
    assert 'simulator' in page and '19.77%' in page
    assert 'interactive design walkthrough' not in page


def test_notebook_instructions_and_missing_gpu_are_explicit():
    page = (OUTPUT / 'lab-notebook.html').read_text()
    assert 'notebooks/FAST_START.py' in page
    assert 'Clone' in page and 'Shift+Enter' in page
    assert 'Run 1' in page and 'Run 2' in page
    assert 'notebooks/molab_lab.py' not in page
    assert 'The demo stops' in page
    assert 'id="live-notebook"' in page and 'id="demo-player"' in page


def test_hosted_accounts_and_dashboard_do_not_claim_local_or_live_data():
    for name in ['sign-in.html', 'get-started.html']:
        assert 'Stored on this Mac' not in (OUTPUT / name).read_text()
    page = (OUTPUT / 'sera-lab-preview.html').read_text()
    assert 'One saved run across all three views' in page
    assert 'demo' in page and 'Weave' in page
    assert 'These new runs do not replace the recording' in page
    script = (OUTPUT / 'sera-workspace.js').read_text()
    assert '/demo-run.json' in script and '/api/metrics' not in script


def test_public_demo_labels_do_not_expose_the_internal_notebook_name():
    for name in ['index.html', 'product.html', 'models.html', 'solutions.html',
                 'resources.html', 'sera-design-preview.html', 'lab-notebook.html']:
        page = (OUTPUT / name).read_text().replace('notebooks/FAST_START.py', '')
        assert 'FAST_START' not in page
    home = (OUTPUT / 'index.html').read_text()
    assert 'href="/notebook">Open demo' in home
    assert 'See demo results' in home


def test_interactive_role_copy_matches_buttons():
    script = (OUTPUT / 'sera-landing.js').read_text()
    for role in ['scheduling:', 'memory_context:', 'output_quality:']:
        assert role in script
    assert 'parallelism:' not in script
