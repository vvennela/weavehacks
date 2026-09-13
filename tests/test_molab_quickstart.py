"""The portable notebook has no automatic paid runs or stored credentials."""

import ast
from pathlib import Path

NOTEBOOK = Path(__file__).resolve().parents[1] / 'notebooks/molab_quickstart.py'


def test_notebook_keeps_both_examples_and_blank_password_fields():
    text = NOTEBOOK.read_text()
    tree = ast.parse(text)
    assert 'Add your keys here:' in text
    assert 'wandb_v1_' not in text and 'sk-proj-' not in text
    cells = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    runs = [node for node in cells if 'sera.optimize(' in ast.unparse(node)]
    assert len(runs) == 2
    for cell in runs:
        source = ast.unparse(cell)
        assert 'mo.stop(' in source and 'with sera.optimize(' in source
        assert 'result.models' in source and '.generate(' in source
    assert "stages=['latency', 'throughput']" in ast.unparse(tree)
    assert 'k=3.0' in ast.unparse(tree)
    assert 'objective=sera.Objective' in ast.unparse(tree)
    password_fields = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                       and any(kw.arg == 'kind' and isinstance(kw.value, ast.Constant)
                               and kw.value.value == 'password' for kw in node.keywords)]
    assert len(password_fields) == 2
    assert all(not any(kw.arg == 'value' for kw in node.keywords) for node in password_fields)


def test_demo_dependency_uses_the_actual_distribution_not_unrelated_sera_package():
    text = NOTEBOOK.read_text()
    assert 'sera-inference[swarm,litellm]' in text
    assert 'git+https://github.com/vvennela/weavehacks.git@' in text
    assert 'GPU time and hosted investigator calls can cost money' in text
