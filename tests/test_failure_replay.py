"""Failure replay uses saved evidence and stubbed Weave/agents, never a GPU."""

from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from experiments import replay_failure_investigation as replay
from sera.config import LARGE_MODEL_ID, LARGE_MODEL_REVISION, RuntimeConfig
from sera.agent import ArbiterDecision, Proposal
from benchmarks.grade import SYSTEM_PROMPT, dataset_hash, load_cases
from sera.storage import save_json


@pytest.fixture(autouse=True)
def no_gpu(monkeypatch):
    def forbidden(*args,**kwargs): pytest.fail('Replay must not access GPU execution')
    for path in ('sera.optimize','sera.pipeline.SeraModel','sera.runtime.SeraModel',
                 'sera.pipeline.collect_trial','sera.runtime.gpu_snapshot'):
        monkeypatch.setattr(path,forbidden)


@pytest.fixture
def source(tmp_path):
    folder = tmp_path/'source'
    (folder/'trial-1').mkdir(parents=True)
    cases = load_cases(replay.CASES_PATH)
    prompts = [[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': c['prompt']}]
               for c in cases]
    base = RuntimeConfig(quantization='fp8_per_tensor')
    def trial(name, config, status='collected'):
        return dict(trial_id=name, status=status, config_hash=config.config_hash,
            runtime=dict(configuration=config.model_dump(), model_id=LARGE_MODEL_ID,
                         revision=LARGE_MODEL_REVISION, sampled_peak_memory_mib=90000),
            input_token_ids=[[1]], quality=[], self_check=[],
            reduced=dict(p95_latency_ms=100., output_tokens_per_second=20., request_count=0),
            task_quality=dict(version='sera-easy-strict-json-v1', floor=.99, mean=1.,
                              valid_outputs=True, passed=True, per_prompt=[]),
            decision=dict(selected='baseline', reason='fixture', objective={'priority':'latency','min_improvement_fraction':.05}),
            diagnosis={'failure_kind':'objective-not-improved'})
    baseline = trial('baseline', base)
    failed = trial('trial-1', base.model_copy(update={'max_model_len':256}), 'startup-failed')
    failed.update(failure_stage='startup', error='RuntimeError')
    batch = trial('trial-2', base.model_copy(update={'max_num_batched_tokens':2048}))
    report = dict(model_id=LARGE_MODEL_ID, model_revision=LARGE_MODEL_REVISION,
        baseline=baseline, baseline_configuration=base.model_dump(), search_trials=[failed,batch],
        objective={'priority':'latency','min_improvement_fraction':.05}, constraints={'quality_floor':.99},
        evaluation={'version':'sera-easy-strict-json-v1'}, evaluation_cases=cases,
        evaluation_cases_sha256=dataset_hash(cases), prompts=prompts, workload={'concurrency':[1,2,4,8]})
    calls = []
    for record in (baseline,batch):
        payload = dict(trial_id=record['trial_id'], config_hash=record['config_hash'],
            model_id=LARGE_MODEL_ID, revision=LARGE_MODEL_REVISION, reduced=record['reduced'],
            quality_requests=0,self_check_requests=0,loads=[])
        calls.append(dict(id=record['trial_id']+'-metrics', trace_id='original-trace',
            op_name='weave:///fixture/project/op/recorded_trial_metrics:v1',
            ended_at='saved', exception=None, output=payload))
    save_json(folder/'result.json',report)
    save_json(folder/'weave-calls.json', {'trace_id':'original-trace','calls':calls})
    (folder/'trial-1'/'server.log').write_text('RuntimeError: cutlass_gemm_caller.cuh:62, Error Internal\n')
    return folder


class Agent:
    model, project = 'fixture', 'fixture/project'
    def __init__(self): self.history=[]
    def fork(self): return Agent()
    def request(self, role, evidence, instruction):
        self.history.append(dict(role=role,evidence=deepcopy(evidence)))
        if role=='arbiter':
            return ArbiterDecision(ranked_proposal_ids=evidence['legal_proposal_ids'][:1],reason='Use saved evidence')
        keep=not evidence['supported_changes']
        return Proposal(action='keep-baseline' if keep else 'trial', proposal_id='batch',agent_role='batching',
            parent_trial_id='baseline',model_id=LARGE_MODEL_ID,changed_lever=None if keep else 'max_num_batched_tokens',
            proposed_value=None if keep else 2048,evidence_used=['p95_latency_ms'],confidence=.5,
            expected_trial_cost=0 if keep else 1,predicted_metric_change='Test latency',
            falsification_condition='No measured improvement',reason='Read saved evidence')


def boundaries(monkeypatch):
    observed={'exports':[], 'reads':[]}
    monkeypatch.setattr(replay,'TracedInvestigationAgent',lambda agent,weave: agent)
    monkeypatch.setattr(replay,'traced_evidence_reader',lambda weave,reader:reader)
    monkeypatch.setattr(replay,'weave_event_sink',lambda weave:lambda name,payload:observed['exports'].append((name,deepcopy(payload))))
    def reader(client,trace_id,**kwargs):
        def read(query,evidence):
            observed['reads'].append(deepcopy(evidence))
            return {'source':'weave','trace_id':trace_id,'records':[{'call_id':'persisted-fixture'}]}
        return read
    monkeypatch.setattr(replay,'WeaveEvidenceReader',reader)
    weave=SimpleNamespace(get_current_call=lambda:SimpleNamespace(trace_id='replay-trace',ui_url='https://fixture/replay'))
    return observed,weave


def test_replay_reveals_saved_batch_only_between_rounds_and_keeps_source_unchanged(source,tmp_path,monkeypatch):
    loaded=replay.load_source(source)
    observed,weave=boundaries(monkeypatch)
    before={path:path.read_bytes() for path in source.rglob('*') if path.is_file()}
    result=replay.run_replay(loaded,Agent(),object(),weave,tmp_path/'output')
    first,second=result['rounds']
    assert first['proposed_config_hashes']==[loaded['trials'][1]['config_hash']]
    assert second['proposed_config_hashes']==[]
    assert all(item['status']=='abstained' for item in second['specialists'])
    assert result['gpu_trials_executed']==0 and result['mechanical_passed'] is True
    assert result['factual_reasoning_verified'] is False
    assert before=={path:path.read_bytes() for path in before}
    first_reads=[e for e in observed['reads'] if e['remaining_trials']==1]
    assert all([t['trial_id'] for t in e['trace_scope']]==['baseline','trial-1'] for e in first_reads)
    second_reads=[e for e in observed['reads'] if e['remaining_trials']==0]
    assert all([t['trial_id'] for t in e['trace_scope']]==['baseline','trial-1','trial-2'] for e in second_reads)
    original=loaded['calls'][0]['output']
    exported=observed['exports'][0][1]
    assert {k:v for k,v in exported.items() if k!='replay_source'}==original
    assert exported['replay_source']['source_call_id']==loaded['calls'][0]['id']


def test_required_read_failure_is_saved_not_claimed_success(source,tmp_path,monkeypatch):
    loaded=replay.load_source(source)
    _,weave=boundaries(monkeypatch)
    from sera.tracing import InspectionReadError
    def reader(*args,**kwargs):
        def fail(*_): raise InspectionReadError('incomplete-diagnosis')
        return fail
    monkeypatch.setattr(replay,'WeaveEvidenceReader',reader)
    result=replay.run_replay(loaded,Agent(),object(),weave,tmp_path/'output')
    assert result['mechanical_passed'] is False
    assert all(not round['proposed_config_hashes'] for round in result['rounds'])


def test_round_one_full_evidence_contains_no_unrevealed_trial_name_outcome_or_metric(source,tmp_path,monkeypatch):
    loaded=replay.load_source(source)
    loaded['trials'][1]['reduced']['p95_latency_ms']=123456.789123
    loaded['trials'][1]['decision']['reason']='future-outcome-marker'
    loaded['trials'][1]['diagnosis']['failure_kind']='objective-not-improved'
    _,weave=boundaries(monkeypatch)
    result=replay.run_replay(loaded,Agent(),object(),weave,tmp_path/'output')
    first_calls=[call for call in result['agent_calls'] if call['evidence']['remaining_trials']==1]
    assert first_calls
    first=json.dumps({'round':result['rounds'][0],'calls':first_calls}).lower()
    leaked=[hidden for hidden in ('trial-2','objective-threshold miss','objective-not-improved',
                                  'future-outcome-marker','123456.789123') if hidden in first]
    assert leaked==[]
    for call in first_calls:
        evidence=call['evidence']
        assert evidence['replay_source']['replay'] is True
        assert 'NO quality or latency measurement' in evidence['failure_interpretation']
        assert 'not 0/8 model accuracy' in evidence['failure_interpretation']
    later=[call for call in result['agent_calls'] if call['evidence']['remaining_trials']==0]
    assert any('future-outcome-marker' in json.dumps(call) for call in later)
    assert all('Saved trial-2 is independent historical evidence' in
               call['evidence']['replay_revelation']['note'] for call in later)


def test_changed_gate_or_missing_saved_metrics_is_rejected_before_service_calls(source):
    report=json.loads((source/'result.json').read_text())
    report['constraints']['quality_floor']=.5
    save_json(source/'result.json',report)
    with pytest.raises(ValueError): replay.load_source(source)


def test_post_return_output_is_not_revealed_with_baseline(source):
    path=source/'weave-calls.json'
    dump=json.loads(path.read_text())
    later=deepcopy(dump['calls'][0])
    later.update(id='later-probe',op_name='weave:///fixture/project/op/recorded_model_request:v1')
    later['output'].update(phase='post-return-probe',output='future output')
    dump['calls'].append(later)
    save_json(path,dump)
    loaded=replay.load_source(source)
    assert all(call['id']!='later-probe' for call in loaded['calls'])


def test_export_failure_saves_failed_replay_without_changing_source(source,tmp_path,monkeypatch):
    loaded=replay.load_source(source)
    _,weave=boundaries(monkeypatch)
    def failing_sink(*args):
        def fail(*_): raise RuntimeError('fixture export failed')
        return fail
    monkeypatch.setattr(replay,'weave_event_sink',failing_sink)
    with pytest.raises(RuntimeError):
        replay.run_replay(loaded,Agent(),object(),weave,tmp_path/'output')
    saved=json.loads((tmp_path/'output'/'result.json').read_text())
    assert saved['mechanical_passed'] is False and saved['error_type']=='RuntimeError'
    assert replay.file_hashes(source)==loaded['hashes']


@pytest.mark.parametrize('flush_failure',[False,True])
def test_command_names_replay_root_and_flushes_without_gpu(source,tmp_path,monkeypatch,flush_failure):
    loaded=replay.load_source(source)
    observed,weave=boundaries(monkeypatch)
    names=[]
    def flush():
        observed['flushed']=True
        if flush_failure: raise RuntimeError('fixture flush failure')
    weave.init=lambda project:SimpleNamespace(flush=flush)
    def op(**kwargs):
        names.append(kwargs['name'])
        return lambda function:function
    weave.op=op
    monkeypatch.setitem(sys.modules,'weave',weave)
    monkeypatch.setattr(replay,'load_source',lambda path:loaded)
    monkeypatch.setattr(replay,'WandbAgent',lambda **kwargs:Agent())
    monkeypatch.setattr(replay,'require_provider_check',lambda *args:{'verified':'fixture'})
    monkeypatch.setenv('WANDB_API_KEY','fixture-key-not-live')
    exit_code=replay.main(['--source-dir',str(source),'--project','fixture/project',
        '--output-dir',str(tmp_path/'output'),'--provider-check','fixture'])
    assert exit_code==(1 if flush_failure else 0)
    assert names==['replay_failure_investigation'] and observed['flushed']
    saved=json.loads((tmp_path/'output'/'result.json').read_text())
    assert saved['provider_validation']=={'verified':'fixture'}
    assert saved['mechanical_passed'] is not flush_failure
