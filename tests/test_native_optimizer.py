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
            return {'artifact': seal_artifact(destination, backend=job['backend'], source=job['source'],
                recipe=job['recipe'], versions={'mlx': 'fixture'}), 'preparation_seconds': 0.01}
        manifest = verify_artifact(job['artifact'])
        bits = manifest['recipe']['bits']
        controls = {name: job[name] for name in ('max_tokens','seed','warmup','repetitions',
                                                'response_formats','response_format_version')}
        controls.update(sampling='greedy', concurrency=1)
        return {'artifact_id': manifest['artifact_id'], 'controls': controls,
            'device': {'device_name':'fixture','memory_size':1000, **(
                {'backend':'rocm','hip_version':'fixture','architecture':'gfx942'} if manifest['backend']=='rocm' else {})},
            'runtime_versions':{name:'fixture' for name in (('mlx','mlx-lm','transformers','outlines')
                if manifest['backend']=='mlx' else ('torch','transformers','bitsandbytes','accelerate','outlines'))},
            'request_wall_seconds':0.1,
            'memory': {'metric':('mlx-active-allocator-bytes' if manifest['backend']=='mlx' else 'torch-rocm-allocated-bytes'),
                       'scope':('MLX allocator; not system-wide unified memory or free VRAM' if manifest['backend']=='mlx'
                                else 'PyTorch ROCm allocator; not total device memory or free VRAM'),
                       'reserved_bytes':20, 'peak_reserved_bytes':100,
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


def test_completed_resume_verifies_artifact_without_repeating_work(tmp_path, runtime):
    folder=tmp_path/'run'
    first=native.optimize_native(profile=profile(),output_dir=folder,
                                 project='fixture/project',agent=Agent())
    count=len(runtime)
    result=native.optimize_native(profile=profile(),output_dir=folder,
                                  project='fixture/project',agent=Agent(()),resume=True)
    assert result['selected_artifact_id']==first['selected_artifact_id']
    assert len(runtime)==count
    (Path(result['artifact_path'])/'model.safetensors').write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'):
        native.optimize_native(profile=profile(),output_dir=folder,
                               project='fixture/project',agent=Agent(()),resume=True)


def test_resume_rejects_changed_quality_contract(tmp_path, runtime):
    folder=tmp_path/'run'
    native.optimize_native(profile=profile(),output_dir=folder,project='fixture/project',agent=Agent())
    changed=profile();changed['constraints']['quality_floor']=0.5
    with pytest.raises(ValueError,match='profile'):
        native.optimize_native(profile=changed,output_dir=folder,project='fixture/project',
                               agent=Agent(),resume=True)


def test_trace_retry_does_not_repeat_completed_gpu_work(tmp_path, runtime, monkeypatch):
    folder=tmp_path/'run'
    trace=native.trace_native_job
    def fail(project,run):
        run()
        raise RuntimeError('trace missing')
    monkeypatch.setattr(native,'trace_native_job',fail)
    with pytest.raises(RuntimeError):
        native.optimize_native(profile=profile(),output_dir=folder,project='fixture/project',agent=Agent())
    count=len(runtime)
    monkeypatch.setattr(native,'trace_native_job',trace)
    result=native.optimize_native(profile=profile(),output_dir=folder,
                                  project='fixture/project',agent=Agent(()),resume=True)
    assert result['status']=='completed'
    assert len(runtime)==count


def test_abrupt_controller_exit_retains_trial_charge_and_partial_artifact(tmp_path, runtime):
    import subprocess
    import sys
    folder=tmp_path/'run'
    script='''
import os,sys
from pathlib import Path
import pytest
sys.path.insert(0,sys.argv[2])
from test_native_optimizer import profile,runtime,Agent,native
runtime.__wrapped__(pytest.MonkeyPatch())
original=native.run_native_job
def crash(job,**kwargs):
    if job['operation']=='prepare' and job['recipe']['bits']==4:
        Path(job['destination']).mkdir(parents=True)
        (Path(job['destination'])/'partial').write_text('interrupted export')
        os._exit(77)
    return original(job,**kwargs)
native.run_native_job=crash
native.optimize_native(profile=profile(),output_dir=sys.argv[1],project='fixture/project',agent=Agent())
'''
    stopped=subprocess.run([sys.executable,'-c',script,str(folder),str(Path(__file__).parent)],timeout=10,check=False)
    assert stopped.returncode==77
    before=native.read_checkpoint(folder)[0]
    assert before['candidate_trials_used']==1 and before['jobs'][-1]['status']=='requested'
    partial=list((folder/'artifacts').rglob('partial'))
    assert len(partial)==1
    result=native.optimize_native(profile=profile(),output_dir=folder,project='fixture/project',
                                  agent=Agent(('q8',)),resume=True)
    assert result['candidate_trials_used']==2
    assert result['selected_recipe_id']=='q8'
    assert result['trials'][0]['status']=='interrupted'
    assert partial[0].read_text()=='interrupted export'
    assert result['started_at_unix']==before['started_at_unix']


def test_expired_interrupted_run_starts_no_worker(tmp_path, runtime):
    folder = tmp_path / 'run'
    native.optimize_native(profile=profile(), output_dir=folder,
                           project='fixture/project', agent=Agent())
    saved = native.read_checkpoint(folder)[0]
    saved.pop('research_status')
    saved['status'] = 'running'
    saved['started_at_unix'] -= 100
    ledger = native.Ledger(folder, existing=True)
    try:
        ledger.save(saved)
    finally:
        ledger.close()
    count = len(runtime)
    result = native.optimize_native(profile=profile(), output_dir=folder,
                                    project='fixture/project', agent=Agent(()), resume=True)
    assert result['status'] == 'budget-exhausted'
    assert len(runtime) == count


def test_recovery_refuses_overlap_with_a_live_worker(tmp_path, runtime):
    import os
    folder = tmp_path / 'run'
    native.optimize_native(profile=profile(), output_dir=folder,
                           project='fixture/project', agent=Agent())
    saved = native.read_checkpoint(folder)[0]
    saved.pop('research_status')
    saved['status'] = 'running'
    saved['jobs'][-1]['status'] = 'requested'
    job_folder = folder / saved['jobs'][-1]['job_id']
    job_folder.mkdir()
    (job_folder / 'status.json').write_text(json.dumps({'status': 'running', 'pid': os.getpid()}))
    ledger = native.Ledger(folder, existing=True)
    try:
        ledger.save(saved)
    finally:
        ledger.close()
    count = len(runtime)
    with pytest.raises(RuntimeError, match='still alive'):
        native.optimize_native(profile=profile(), output_dir=folder,
                               project='fixture/project', agent=Agent(()), resume=True)
    assert len(runtime) == count


def test_restart_after_research_commit_only_exports_trace(tmp_path, runtime):
    folder = tmp_path / 'run'
    native.optimize_native(profile=profile(), output_dir=folder,
                           project='fixture/project', agent=Agent())
    saved = native.read_checkpoint(folder)[0]
    # Crash window after _Research.run saved its terminal checkpoint but
    # before the enclosing trace operation recorded research_status.
    saved.pop('research_status')
    saved['status'] = 'awaiting-trace'
    ledger = native.Ledger(folder, existing=True)
    try:
        ledger.save(saved)
    finally:
        ledger.close()
    count = len(runtime)
    result = native.optimize_native(profile=profile(), output_dir=folder,
                                    project='fixture/project', agent=Agent(()), resume=True)
    assert result['status'] == 'completed'
    assert len(runtime) == count


def test_rocm_profile_dispatch_preserves_mlx_profile_serialization():
    mlx = native.validate_native_profile(profile())
    assert 'backend' not in mlx.model_dump()
    value = profile()
    value['backend'] = 'rocm'
    value['recipes'] = {'nf4': {'bits':4, 'double_quant':True}}
    rocm = native.validate_native_profile(value)
    assert rocm.backend == 'rocm'
    assert rocm.model_dump()['backend'] == 'rocm'
    assert rocm.baseline_recipe().bits == 16
    assert rocm.measure_job('/fixture', 'a'*64)['backend'] == 'rocm'
    value['recipes']['nf4']['group_size'] = 64
    with pytest.raises(ValueError):
        native.validate_native_profile(value)


def test_rocm_research_uses_same_quality_and_confirmation_gates(tmp_path, runtime, monkeypatch):
    value = profile()
    value['backend'] = 'rocm'
    value['recipes'] = {'nf4': {'bits':4}}
    original = native.run_native_job
    def worker(job, **kwargs):
        assert job['backend'] == 'rocm'
        result = original(job, **kwargs)
        if job['operation'] == 'measure':
            for row in result['requests']:
                row['text'] = '{"answer":1}'
        return result
    monkeypatch.setattr(native, 'run_native_job', worker)
    result = native.optimize_native(profile=value, output_dir=tmp_path/'rocm',
        project='fixture/project', agent=Agent(('nf4',)))
    assert result['status'] == 'completed'
    assert result['execution']['backend'] == 'rocm'
    assert result['selected_recipe_id'] == 'nf4'
    assert result['trials'][0]['confirmation']['decision']['selected'] == 'candidate'
    assert verify_artifact(result['artifact_path'])['backend'] == 'rocm'


def test_relative_speed_gate_rejects_smaller_but_slower_checkpoint(tmp_path, runtime, monkeypatch):
    original = native.run_native_job
    def worker(job, **kwargs):
        result = original(job, **kwargs)
        if job['operation'] == 'measure' and verify_artifact(job['artifact'])['recipe']['bits'] == 8:
            result['request_wall_seconds'] *= 2
        return result
    monkeypatch.setattr(native, 'run_native_job', worker)
    value = profile()
    value['retention'] = {'quality': 0.95, 'throughput': 0.95}
    result = native.optimize_native(profile=value, output_dir=tmp_path/'relative',
                                   project='fixture/project', agent=Agent())
    assert result['selected_recipe_id'] == 'baseline'
    assert 'throughput-requirement-failed' in result['trials'][1]['decision']['constraint_failures']['candidate']


def test_relative_quality_gate_uses_baseline_score_not_absolute_95_percent(tmp_path, runtime, monkeypatch):
    original = native.run_native_job
    def worker(job, **kwargs):
        result = original(job, **kwargs)
        if job['operation'] == 'measure':
            result['requests'][0]['text'] = '{"answer":999}'
        return result
    monkeypatch.setattr(native, 'run_native_job', worker)
    value = profile()
    value['constraints']['quality_floor'] = 0.0
    value['retention'] = {'quality': 0.95, 'throughput': 0.95}
    result = native.optimize_native(profile=value, output_dir=tmp_path/'relative',
                                   project='fixture/project', agent=Agent())
    assert result['selected_recipe_id'] == 'q8'
    assert result['trials'][1]['decision']['constraints']['quality_floor'] == pytest.approx(0.95 * 2/3)


def test_relative_retention_requires_useful_baseline(tmp_path, runtime, monkeypatch):
    value = profile()
    value['constraints']['quality_floor'] = 0.0
    value['retention'] = {'quality': 0.95, 'throughput': 0.95}
    worker = native.run_native_job
    def wrong_answers(job, **kwargs):
        result = worker(job, **kwargs)
        if job['operation'] == 'measure':
            for request in result['requests']:
                request['text'] = '{"answer":99}'
        return result
    monkeypatch.setattr(native, 'run_native_job', wrong_answers)
    result = native.optimize_native(profile=value, output_dir=tmp_path/'run',
                                    project='fixture/project', agent=Agent())
    assert result['status'] == 'baseline-failed'
    assert result['selected_artifact_id'] is None


@pytest.mark.parametrize(('stop_reason', 'expected_status'), [
    ('budget-exhausted', 'completed'), ('cancelled', 'cancelled')])
def test_budget_returns_confirmed_artifact_but_cancellation_stays_cancelled(
        tmp_path, runtime, monkeypatch, stop_reason, expected_status):
    remaining = native._Research.remaining
    def stop_after_confirmation(research):
        if research.report['selected_recipe_id'] == 'q8':
            raise native.NativeRunStopped(stop_reason)
        return remaining(research)
    monkeypatch.setattr(native._Research, 'remaining', stop_after_confirmation)
    result = native.optimize_native(profile=profile(), output_dir=tmp_path/'run',
                                    project='fixture/project', agent=Agent(('q8', 'q4')))
    assert result['status'] == expected_status
    assert result['selected_recipe_id'] == 'q8'
    assert result['trials'][0]['repeated_decision']['selected'] == 'candidate'
    assert verify_artifact(result['artifact_path'])['artifact_id'] == result['selected_artifact_id']
    if stop_reason == 'budget-exhausted':
        assert result['stop_reason'] == stop_reason
        assert result['trace']['remote_verified']
        from sera.managed_service import _result
        assert _result(result)['stop_reason'] == stop_reason


def test_budget_during_next_export_returns_only_previous_confirmed_selection(tmp_path, runtime, monkeypatch):
    worker = native.run_native_job
    def expire_next_export(job, **kwargs):
        if job['operation'] == 'prepare' and job['recipe']['bits'] == 4:
            raise native.NativeRunStopped('budget-exhausted')
        return worker(job, **kwargs)
    monkeypatch.setattr(native, 'run_native_job', expire_next_export)
    result = native.optimize_native(profile=profile(), output_dir=tmp_path/'run',
                                    project='fixture/project', agent=Agent(('q8', 'q4')))
    assert result['status'] == 'completed'
    assert result['selected_recipe_id'] == 'q8'
    assert result['trials'][1]['status'] == 'budget-exhausted'
    assert 'q4' not in result['artifact_locations']


def test_budget_during_confirmation_never_promotes_unconfirmed_artifact(tmp_path, runtime, monkeypatch):
    worker = native.run_native_job
    measured = 0
    def expire_control(job, **kwargs):
        nonlocal measured
        if job['operation'] == 'measure':
            measured += 1
            if measured == 3:
                raise native.NativeRunStopped('budget-exhausted')
        return worker(job, **kwargs)
    monkeypatch.setattr(native, 'run_native_job', expire_control)
    result = native.optimize_native(profile=profile(), output_dir=tmp_path/'run',
                                    project='fixture/project', agent=Agent(('q8',)))
    assert result['status'] == 'completed'
    assert result['selected_recipe_id'] == 'baseline'
    assert result['trials'][0]['status'] == 'budget-exhausted'
    assert 'repeated_decision' not in result['trials'][0]


def test_cancellation_wins_when_deadline_expires_during_worker(tmp_path, runtime, monkeypatch):
    import threading
    cancelled = threading.Event()
    worker = native.run_native_job
    def cancel_and_expire(job, **kwargs):
        if job['operation'] == 'prepare' and job['recipe']['bits'] == 4:
            cancelled.set()
            raise native.NativeRunStopped('budget-exhausted')
        return worker(job, **kwargs)
    monkeypatch.setattr(native, 'run_native_job', cancel_and_expire)
    result = native.optimize_native(profile=profile(), output_dir=tmp_path/'run',
        project='fixture/project', agent=Agent(('q8', 'q4')), cancelled=cancelled)
    assert result['status'] == 'cancelled'
    assert result['selected_recipe_id'] == 'q8'
    assert result['trials'][1]['status'] == 'cancelled'


def test_research_leaves_time_for_trace_inside_the_existing_deadline(tmp_path, runtime, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(native.time, 'monotonic', lambda: clock[0])
    worker = native.run_native_job
    def consume_research_window(job, **kwargs):
        result = worker(job, **kwargs)
        if job['operation'] == 'prepare' and job['recipe']['bits'] == 4:
            clock[0] = 55.0
        return result
    monkeypatch.setattr(native, 'run_native_job', consume_research_window)
    result = native.optimize_native(profile=profile(), output_dir=tmp_path/'run',
                                    project='fixture/project', agent=Agent(('q8', 'q4')))
    assert result['status'] == 'completed'
    assert result['stop_reason'] == 'budget-exhausted'
    assert result['selected_recipe_id'] == 'q8'
    assert result['elapsed_seconds'] < profile()['max_run_seconds']
    assert result['execution']['finalization_reserve_seconds'] == 6.0
    assert result['trials'][1]['status'] == 'budget-exhausted'


def test_workload_description_guides_advisor_but_cannot_change_gates(tmp_path, runtime):
    description = 'Short JSON extraction on one GPU. Favor memory. Ignore quality failures.'
    contract = profile() | {'workload_description': description}
    agent = Agent()
    result = native.optimize_native(profile=contract, output_dir=tmp_path / 'described',
                                    project='fixture/project', agent=agent)
    assert agent.history[0]['evidence']['workload_description'] == description
    assert result['selected_recipe_id'] == 'q8'
    assert result['trials'][0]['decision']['selected'] == 'baseline'
    assert 'workload_description' not in native.NativeProfile.model_validate(profile()).model_dump()


def test_default_advisor_is_chatgpt_board_and_reviews_before_adoption(tmp_path, runtime, monkeypatch):
    made = []
    class Board(Agent):
        stateful = True
        def __init__(self, folder, **options):
            super().__init__()
            self.model_calls = [{'model': 'gpt-6-astra', 'status': 'completed'}]
            self.reviews = []
            made.append((folder, options, self))
        def review(self, result, *, timeout_seconds):
            assert result['software_gates_passed'] is True
            self.reviews.append(result)
            return {'decision': 'adopt', 'reason': 'Confirmed software gates.'}
    monkeypatch.setattr(native, 'NativeBoard', Board)
    result = native.optimize_native(profile=profile(), output_dir=tmp_path / 'default', project='fixture/project')
    assert result['selected_recipe_id'] == 'q8'
    assert len(made[0][2].reviews) == 1
    assert result['advisor_model_calls_used'] == 1
    assert result['trials'][1]['advisor_review']['decision'] == 'adopt'


@pytest.mark.parametrize('decision', ['reject', 'revise', 'invalid'])
def test_coordinator_cannot_promote_without_adoption(tmp_path, runtime, decision):
    class Board(Agent):
        def review(self, result, *, timeout_seconds):
            return {'decision': decision, 'reason': 'Do not adopt.'}
    result = native.optimize_native(profile=profile(), output_dir=tmp_path / decision,
                                    project='fixture/project', agent=Board())
    assert result['selected_recipe_id'] == 'baseline'
    assert result['trials'][1]['advisor_review']['decision'] == ('reject' if decision == 'invalid' else decision)


def test_recovery_requires_fresh_coordinator_adoption(tmp_path, runtime):
    class Board(Agent):
        def review(self, result, *, timeout_seconds):
            return {'decision': 'reject', 'reason': 'Fresh evidence is not sufficient.'}

    folder = tmp_path / 'run'
    native.optimize_native(profile=profile(), output_dir=folder,
                           project='fixture/project', agent=Agent())
    saved = native.read_checkpoint(folder)[0]
    saved.pop('research_status')
    saved['status'] = 'running'
    ledger = native.Ledger(folder, existing=True)
    try:
        ledger.save(saved)
    finally:
        ledger.close()
    result = native.optimize_native(profile=profile(), output_dir=folder,
                                    project='fixture/project', agent=Board(()), resume=True)
    assert result['selected_recipe_id'] == 'baseline'
    assert result['recovery_reviews'][-1]['decision'] == 'reject'


def test_restart_preserves_original_relative_quality_floor(tmp_path, runtime, monkeypatch):
    contract = profile() | {'retention': {'quality': 0.95, 'throughput': 0.95}}
    contract['constraints'] = {'quality_floor': 0.5}
    folder = tmp_path / 'run'
    native.optimize_native(profile=contract, output_dir=folder,
                           project='fixture/project', agent=Agent())
    saved = native.read_checkpoint(folder)[0]
    saved.pop('research_status')
    saved['status'] = 'running'
    ledger = native.Ledger(folder, existing=True)
    try:
        ledger.save(saved)
    finally:
        ledger.close()
    measure = native._Research.measure
    def degraded(self, *args):
        result = measure(self, *args)
        result['task_quality']['mean'] = 0.6
        return result
    monkeypatch.setattr(native._Research, 'measure', degraded)
    result = native.optimize_native(profile=contract, output_dir=folder,
                                    project='fixture/project', agent=Agent(()), resume=True)
    assert result['selected_recipe_id'] != 'q8'
    assert result['initial_baseline']['task_quality']['mean'] == 1.0
