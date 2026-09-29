"""A native research run must return only a confirmed, quality-passing artifact."""

import json
from pathlib import Path

import pytest

from sera import native_optimizer as native
from sera.model_artifact import seal_artifact, verify_artifact
from sera.native_agent import NativeProposal


def profile():
    return {'profile_id': 'fixture', 'source': {'model_id': 'Qwen/Qwen3-0.6B', 'revision': 'a'*40},
            'tasks': [{'prompt': 'question', 'expected_json': {'answer': 1}}],
            'evaluation_version': 'fixture-v1', 'recipes': {'q4': {'bits': 4}, 'q8': {'bits': 8}},
            'constraints': {'quality_floor': 0.99}, 'objective': {'priority': 'memory'},
            'budget': {'max_candidate_trials': 2}, 'max_run_seconds': 60.0,
            'job_timeout_seconds': 10.0, 'max_tokens': 64, 'seed': 0, 'warmup': 1, 'repetitions': 3}


class Agent:
    def __init__(self, choices=('q4', 'q8')):
        self.choices = iter(choices)
        self.history = []

    def propose(self, evidence, **kwargs):
        assert 'expected_json' not in json.dumps(evidence)
        choice = next(self.choices)
        self.history.append({'evidence': evidence, 'choice': choice})
        return NativeProposal(recipe_id=choice, reason='Fixture proposal', prediction='Test memory and quality')


@pytest.fixture
def runtime(monkeypatch):
    calls = []
    def worker(job, *, output_dir, **kwargs):
        calls.append(job)
        if job['operation'] == 'prepare':
            destination = Path(job['destination'])
            destination.mkdir(parents=True)
            (destination/'config.json').write_text('{}')
            (destination/'model.safetensors').write_bytes(b'fixture')
            return {'artifact': seal_artifact(destination, backend='mlx', source=job['source'],
                recipe=job['recipe'], versions={'mlx': 'fixture'}), 'preparation_seconds': 0.01}
        manifest = verify_artifact(job['artifact'])
        bits = manifest['recipe']['bits']
        controls = {name: job[name] for name in ('max_tokens','seed','warmup','repetitions',
                                                'response_formats','response_format_version')}
        controls.update(sampling='greedy', concurrency=1)
        return {'artifact_id': manifest['artifact_id'], 'controls': controls,
            'device': {'device_name':'fixture','memory_size':1000},
            'runtime_versions':{name:'fixture' for name in ('mlx','mlx-lm','transformers','outlines')},
            'request_wall_seconds':0.1,
            'memory': {'metric':'mlx-active-allocator-bytes',
                       'scope':'MLX allocator; not system-wide unified memory or free VRAM',
                       'resident_bytes':20,'active_bytes':20,'cache_bytes':0,
                       'peak_bytes':100 if bits == 16 else 40 if bits == 4 else 60},
            'requests':[{'repetition':r, 'prompt_index':0, 'text':json.dumps({'answer':2 if bits==4 else 1}),
                         'token_ids':[1], 'prompt_token_ids':[2], 'latency_ms':10., 'error':None,
                         'finish_reason':'stop', 'response_format':None} for r in range(job['repetitions'])]}
    monkeypatch.setattr(native, 'run_native_job', worker)
    monkeypatch.setattr(native, 'trace_native_job', lambda project,run:
        {'result':run(), 'trace':{'remote_verified':True, 'url':'fixture-trace'}})
    return calls


def test_research_rejects_quality_loss_then_returns_confirmed_smaller_artifact(tmp_path, runtime):
    result = native.optimize_native(profile=profile(), output_dir=tmp_path/'run',
                                    project='fixture/project', agent=Agent())
    assert result['status'] == 'completed'
    assert result['selected_recipe_id'] == 'q8'
    assert result['trials'][0]['decision']['selected'] == 'baseline'
    assert result['trials'][1]['confirmation']['decision']['selected'] == 'candidate'
    assert verify_artifact(result['artifact_path'])['recipe']['bits'] == 8
    assert result['trace']['remote_verified'] is True
    assert len([x for x in runtime if x['operation'] == 'measure']) == 5


def test_unlisted_agent_proposal_never_reaches_worker(tmp_path, runtime):
    result = native.optimize_native(profile=profile(), output_dir=tmp_path/'run',
                                    project='fixture/project', agent=Agent(('unknown',)))
    assert result['status'] == 'agent-failed'
    assert result['selected_recipe_id'] == 'baseline'
    assert len(runtime) == 2


def test_trace_failure_cannot_produce_a_completed_public_result(tmp_path, runtime, monkeypatch):
    def fail(project,run):
        run()
        raise RuntimeError('trace missing')
    monkeypatch.setattr(native,'trace_native_job',fail)
    with pytest.raises(RuntimeError,match='trace missing'):
        native.optimize_native(profile=profile(),output_dir=tmp_path/'run',
                               project='fixture/project',agent=Agent())
    saved=json.loads((tmp_path/'run'/'result.json').read_text())
    assert saved['status'] != 'completed'


def test_profile_rejects_unbounded_research():
    value=profile();value['budget']['max_candidate_trials']=None
    with pytest.raises(ValueError,match='bounded'):
        native.NativeProfile.model_validate(value)


def test_profile_rejects_conflicting_expected_answers():
    value=profile()
    value['tasks'].append({'prompt':'question','expected_json':{'answer':2}})
    with pytest.raises(ValueError,match='conflicting'):
        native.NativeProfile.model_validate(value)


def test_cancellation_during_baseline_is_reported_as_cancelled(tmp_path, runtime, monkeypatch):
    import threading
    cancelled=threading.Event()
    def cancel(*args,**kwargs):
        cancelled.set()
        raise native.NativeWorkerError('Native worker cancelled')
    monkeypatch.setattr(native,'run_native_job',cancel)
    result=native.optimize_native(profile=profile(),output_dir=tmp_path/'run',
        project='fixture/project',agent=Agent(),cancelled=cancelled)
    assert result['status']=='cancelled'
    assert result['selected_recipe_id'] is None
