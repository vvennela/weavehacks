"""The portable notebook has no automatic paid runs or stored credentials."""

import ast
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

NOTEBOOK = Path(__file__).resolve().parents[1] / 'notebooks/FAST_START.py'


def _runs_optimizer(cell):
    return any(isinstance(node, ast.Call) and ast.unparse(node.func) == 'sera.optimize'
               for node in ast.walk(cell))


def test_notebook_keeps_both_examples_and_blank_password_fields():
    text = NOTEBOOK.read_text()
    tree = ast.parse(text)
    assert 'Add your keys here:' in text
    assert 'wandb_v1_' not in text and 'sk-proj-' not in text
    cells = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    runs = [node for node in cells if _runs_optimizer(node)]
    assert len(runs) == 2
    for cell in runs:
        source = ast.unparse(cell)
        assert 'mo.stop(' in source and 'with sera.optimize(' in source
        assert 'SERA_DEMO_READY' in source
        assert 'download=True' in source
        assert 'speed=8' in source and 'speed=16' in source
        assert 'mo.download(' in source
        assert not {'openai_key', 'wandb_key', 'project'} & {
            item.id for item in ast.walk(cell) if isinstance(item, ast.Name)}
        assert 'result.models' in source and '.generate(' in source
    assert "stages=['latency', 'throughput']" in ast.unparse(tree)
    assert 'k=3.0' in ast.unparse(tree)
    assert 'objective=sera.Objective' in ast.unparse(tree)
    password_fields = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                       and any(kw.arg == 'kind' and isinstance(kw.value, ast.Constant)
                               and kw.value.value == 'password' for kw in node.keywords)]
    assert len(password_fields) == 2
    assert all(not any(kw.arg == 'value' for kw in node.keywords) for node in password_fields)
    assert 'run_button' not in text
    assert 'Shift+Enter' in text
    assert 'Clone this notebook first' in text
    assert 'app_title="FAST_START' in text and '# FAST_START' in text
    lines = text.splitlines()
    assert all(lines[node.body[0].lineno - 2].strip().startswith('#') for node in cells)


def test_demo_dependency_uses_the_actual_distribution_not_unrelated_sera_package():
    text = NOTEBOOK.read_text()
    assert 'sera-inference[swarm,litellm]' in text
    assert 'git+https://github.com/vvennela/weavehacks.git@' in text
    assert 'GPU time and hosted investigator calls can cost money' in text
    assert 'vllm==0.26.0' in text
    assert 'nvidia-cuda-nvcc==13.0.88' in text


def test_workflows_explain_the_workload_and_publish_independent_tabs():
    text = NOTEBOOK.read_text()
    for marker in ['# WORKLOAD 1:', '# WORKLOAD 2:']:
        assert marker in text
    tree = ast.parse(text)
    runs = [node for node in tree.body if isinstance(node, ast.FunctionDef)
            and _runs_optimizer(node)]
    for run in runs:
        source = ast.unparse(run)
        assert 'set_demo_runs(' in source
        assert 'get_demo_runs' not in source
    tabs = _cell_function('mo.ui.tabs(')
    rendered = []
    mo = SimpleNamespace(md=lambda x:x, vstack=lambda x:x,
                         ui=SimpleNamespace(tabs=lambda x: rendered.append(x)))
    tabs(lambda: {'Run 1': 'latency downloads'}, mo)
    assert list(rendered[0]) == ['Run 1', 'Run 2']
    assert rendered[0]['Run 1'][-1] == 'latency downloads'
    assert 'Run this workflow' in rendered[0]['Run 2'][-1]
    assert 'priority="latency"' in rendered[0]['Run 1'][0]
    assert 'stages=["latency", "throughput"]' in rendered[0]['Run 2'][0]


def _cell_function(fragment):
    tree = ast.parse(NOTEBOOK.read_text())
    cell = copy.deepcopy(next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                              and fragment in ast.unparse(node)))
    cell.decorator_list = []
    scope = {}
    # Execute only the repository-owned cell with stubbed GPU/provider boundaries.
    exec(compile(ast.Module(body=[cell], type_ignores=[]), str(NOTEBOOK), 'exec'), scope)  # noqa: S102
    return scope['_']


def test_entering_keys_only_arms_manual_execution():
    fields = []
    def text(**kwargs):
        fields.append(kwargs)
        return kwargs
    mo = SimpleNamespace(ui=SimpleNamespace(text=text), md=lambda x:x, vstack=lambda x:x)
    env = {'OPENAI_API_KEY': 'existing', 'WANDB_API_KEY': 'existing', 'SERA_DEMO_READY': '1'}
    _cell_function('def update_demo_key')(mo, SimpleNamespace(environ=env))
    assert env['SERA_DEMO_READY'] == ''
    for field, value in zip(fields, ['new-openai', 'new-weave', 'team/project']):
        field['on_change'](value)
    assert env['SERA_DEMO_READY'] == '1'
    assert env['SERA_PROJECT'] == 'team/project'
    fields[0]['on_change']('')
    assert env['SERA_DEMO_READY'] == ''
    assert 'OPENAI_API_KEY' not in env


@pytest.mark.parametrize('fragment', ['as latency_result', 'as staged_result'])
def test_manual_workflow_downloads_runs_closes_and_saves_two_replays(fragment, tmp_path):
    import sera
    from sera.demo import aria_agent_task, aria_review_prompt
    events = []
    class Result:
        def __init__(self):
            self.output_dir = tmp_path
            self.report = {'status': 'ready', 'model_id': 'test-only', 'decision': {}}
            self.models = [SimpleNamespace(generate=lambda prompt: events.append('request') or
                                          SimpleNamespace(text='test response'))]
        def __enter__(self):
            events.append('start')
            return self
        def __exit__(self, *args):
            events.append('close')
            self.report['returned_runner_closed'] = True
        def print_summary(self):
            events.append('summary')
    def prepare(**kwargs):
        assert kwargs == {'project': 'team/project', 'download': True}
        events.append('prepare')
        return {'prompts': ['task']}
    calls = []
    def optimize(**kwargs):
        calls.append(kwargs)
        return Result()
    def stop(condition, message):
        if condition:
            raise RuntimeError('not armed')
    downloads = []
    mo = SimpleNamespace(stop=stop, md=lambda x:x, vstack=lambda x:x,
        download=lambda data, **kwargs: downloads.append((data, kwargs)))
    api = SimpleNamespace(optimize=optimize, Objective=sera.Objective, visualize=sera.visualize)
    run = _cell_function(fragment)
    published = {}
    def publish(update):
        published.update(update(published))
    with pytest.raises(RuntimeError, match='not armed'):
        run(aria_agent_task, aria_review_prompt, mo, SimpleNamespace(environ={}), prepare, api, publish)
    assert not events
    run(aria_agent_task, aria_review_prompt, mo, SimpleNamespace(environ={'SERA_DEMO_READY': '1', 'SERA_PROJECT': 'team/project'}), prepare, api, publish)
    assert list(published) == ['Run 2' if 'staged' in fragment else 'Run 1']
    assert events == ['prepare', 'start', 'summary', 'request', 'close']
    assert len(downloads) == 4 and len(list(tmp_path.glob('*.html'))) == 2
    assert (tmp_path / 'aria-review-request.md').is_file()
    assert all('Weave' in data.decode() and 'ARIA' in data.decode() for data, _ in downloads)
    if 'staged' in fragment:
        assert calls[0]['stages'] == ['latency', 'throughput'] and calls[0]['k'] == 3
