"""Compact prompts keep measured evidence distinct from prior opinions."""

from copy import deepcopy
import json
from pathlib import Path

from sera.investigation_prompt import build_investigation_prompt
from sera.storage import content_hash


def evidence(phase='refine'):
    failure=dict(failure_kind='startup-failed', observed=dict(status='startup-failed',
        quality=None, error_type='RuntimeError', runtime_failure=dict(category='cutlass-internal-error',
        known_message='cutlass_gemm_caller reported Error Internal.', root_cause_status='not-established'),
        objective=dict(priority='latency',candidate_value=None)),
        root_cause=dict(status='not-established',reason='Cause not proved'),
        evidence_paths=['status'],next_proposal_constraints=['Keep the .99 gate'])
    row=dict(call_id='source-call',output_sha256='a'*64,trial_id='trial-1',config_hash='failed-hash',
        model_id='model',revision='pinned',record_type='trial_diagnosis',diagnosis=failure,secret='DROP_SECRET')
    inspection=dict(status='complete',query_id='load_metrics',result=dict(source='weave',trace_id='trace',
        records=[row],matched_record_count=1,omitted_record_count=0))
    old=dict(action='trial',proposal_id='OLD_JSON',changed_lever='max_num_batched_tokens',proposed_value=2048,
        agent_role='batching',reason='PEER_HYPOTHESIS',predicted_metric_change='Lower p95',
        falsification_condition='No gain',evidence_used=['p95_latency_ms'])
    return dict(swarm_phase=phase,investigator_id='scheduling',trial_id='baseline',model_id='model',
        revision='pinned',remaining_trials=1,configuration={'max_model_len':4096},
        objective={'priority':'latency','min_improvement_fraction':.05},constraints={'quality_floor':.99},
        supported_changes={'max_num_batched_tokens':[2048]},frozen_candidate_hashes=['legal'],
        metrics={'p95_latency_ms':100,'trial_1_p95_latency_ms':None,'queue':0},
        task_quality={'floor':.99,'mean':1,'passed':True,'valid_outputs':True,'per_prompt':[]},
        request_evidence={'prepared_prompt_tokens':{'maximum':81,'minimum':48,'prompt_count':8},
                          'quality_examples':[{'output':'BASELINE_EXAMPLE_NOT_NEEDED'}]},
        history=[{'trial':{'trial_id':'trial-1','status':'startup-failed','config_hash':'failed-hash',
            'task_quality':{'mean':0,'passed':False,'per_prompt':[{'prompt_index':0,'score':0,'error':'missing'}]}},
            'configuration':{'max_model_len':256},'diagnosis':failure,
            'proposal':{'reason':'OLD_OPINION_NEVER_FACT'},'review':{'reason':'OLD_REVIEW_NEVER_FACT'}}],
        inspections=[inspection],shared_findings=[{'investigator_id':'memory_context','status':'accepted',
            'proposal':old,'inspections':[deepcopy(inspection)]}],initial_proposal=old,
        previous_rounds=[{'specialists':[{'proposal':old}]}],required_inspection=True,
        legal_proposal_ids=['latency_outliers','quality_outputs','load_metrics'])


def test_projection_is_pure_retains_limits_metrics_and_puts_fresh_question_last():
    supplied=evidence()
    original=deepcopy(supplied)
    result=build_investigation_prompt(supplied)
    assert supplied==original
    for key in ('configuration','objective','constraints','remaining_trials','supported_changes','frozen_candidate_hashes'):
        assert result[key]==supplied[key]
    assert result['metrics']=={'p95_latency_ms':100,'queue':0}
    assert result['compaction']['source_evidence_sha256']==content_hash(supplied)
    assert list(result)[-1]=='your_task'
    assert result['measured_facts']['baseline']['prepared_prompt_tokens']['maximum']==81
    assert 'BASELINE_EXAMPLE_NOT_NEEDED' not in json.dumps(result)


def test_old_proposal_shapes_do_not_become_facts_and_current_peer_opinions_are_separate():
    result=build_investigation_prompt(evidence())
    facts=json.dumps(result['measured_facts'])
    assert 'PEER_HYPOTHESIS' not in facts
    assert 'OLD_OPINION_NEVER_FACT' not in json.dumps(result)
    assert 'OLD_REVIEW_NEVER_FACT' not in json.dumps(result)
    assert 'OLD_JSON' not in json.dumps(result)
    assert result['peer_opinions'][0]['hypothesis']=='PEER_HYPOTHESIS'
    assert result['peer_opinions'][0]['suggested_change']=={'setting':'max_num_batched_tokens','value':2048}
    assert 'proposal' not in result['peer_opinions'][0]


def test_duplicate_persisted_failure_rows_are_cited_once_and_unmeasured_quality_is_not_accuracy():
    result=build_investigation_prompt(evidence())
    rows=result['measured_facts']['inspection_records']
    assert len(rows)==1 and rows[0]['source_call_id']=='source-call'
    assert rows[0]['diagnosis']['observed']['quality'] is None
    assert rows[0]['diagnosis']['root_cause']['status']=='not-established'
    assert result['compaction']['omitted']['duplicate_inspection_rows']==1
    assert 'DROP_SECRET' not in json.dumps(result)
    assert result['measured_facts']['trials'][0]['quality']['measured'] is False


def test_required_inspection_and_zero_budget_tasks_do_not_force_a_trial():
    supplied=evidence('inspect')
    result=build_investigation_prompt(supplied)
    assert 'required' in result['your_task'].lower()
    supplied.update(swarm_phase='refine',remaining_trials=0,supported_changes={},frozen_candidate_hashes=[])
    result=build_investigation_prompt(supplied)
    assert 'keep-baseline' in result['your_task']
    assert result['constraints']['quality_floor']==.99


def test_empty_reader_quality_shape_does_not_turn_startup_failure_into_a_measurement():
    supplied=evidence()
    for inspection in [supplied['inspections'][0],supplied['shared_findings'][0]['inspections'][0]]:
        inspection['result']['records'][0]['diagnosis']['observed']['quality']={
            'mean':None,'floor':None,'per_prompt':[]}
    result=build_investigation_prompt(supplied)
    assert result['measured_facts']['inspection_records'][0]['diagnosis']['observed']['quality'] is None


def test_bounded_examples_preserve_fixed_quality_facts_and_report_omissions():
    supplied=evidence()
    rows=supplied['inspections'][0]['result']['records']
    for index in range(5):
        rows.append(dict(call_id=f'output-{index}',output_sha256=str(index)*64,record_type='model_request',
            trial_id='baseline',config_hash='base',phase='quality',prompt_index=index,
            output='long output '*100,expected_output='fixed',task_score=0 if index==4 else 1,
            secret='DROP_SECRET'))
    result=build_investigation_prompt(supplied)
    outputs=[row for row in result['measured_facts']['inspection_records'] if row['record_type']=='model_request']
    assert len(outputs)==2 and outputs[0]['prompt_index']==4
    assert outputs[0]['task_score']==0 and outputs[0]['output_truncated'] is True
    assert len(outputs[0]['output'])==300
    assert result['compaction']['omitted']['output_examples']==3
    assert result['compaction']['omitted']['text_truncations']>=2
    assert 'DROP_SECRET' not in json.dumps(result)


def test_failure_summary_survives_without_repeated_history_and_load_omissions_are_counted():
    supplied=evidence()
    diagnosis=deepcopy(supplied['history'][0]['diagnosis'])
    supplied.update(history=[],inspections=[],shared_findings=[],
        failure_diagnoses=[{'trial_id':'trial-1','diagnosis':diagnosis}])
    result=build_investigation_prompt(supplied)
    assert result['measured_facts']['additional_failures'][0]['diagnosis']['failure_kind']=='startup-failed'
    supplied=evidence()
    supplied['inspections'][0]['result']['records'].append(dict(call_id='load-call',output_sha256='f'*64,
        record_type='load_metrics',trial_id='baseline',concurrency=8,
        reduced={'input_tokens':2265,'successful_requests':24,'p95_latency_ms':100,'p99_latency_ms':200},
        input_token_summary={'mean_tokens_per_successful_request':94.375}))
    result=build_investigation_prompt(supplied)
    row=next(row for row in result['measured_facts']['inspection_records'] if row['record_type']=='load_metrics')
    assert row['reduced']['input_tokens']==2265
    assert row['mean_input_tokens_per_successful_request']==94.375
    assert result['compaction']['omitted']['load_metric_fields']==1


def test_arbitration_keeps_current_namespaced_options_not_initial_json():
    supplied=evidence('arbitrate')
    refined=deepcopy(supplied['shared_findings'][0]['proposal'])
    refined.update(proposal_id='scheduling:current',reason='CURRENT_REFINED_HYPOTHESIS')
    supplied.update(proposals=[refined],legal_proposal_ids=['scheduling:current'],
        proposal_id_map={'scheduling:current':{'investigator_id':'scheduling','agent_role':'batching'}})
    result=build_investigation_prompt(supplied)
    assert result['peer_opinions'][0]['candidate_id']=='scheduling:current'
    assert 'CURRENT_REFINED_HYPOTHESIS' in json.dumps(result['peer_opinions'])
    assert 'PEER_HYPOTHESIS' not in json.dumps(result['peer_opinions'])
    assert result['legal_proposal_ids']==['scheduling:current']


def test_all_saved_v2_refinement_prompts_fit_under_20000_characters():
    path=Path(__file__).resolve().parents[1]/'evidence'/'failure-replay-v2'/'result.json'
    report=json.loads(path.read_text())
    sizes=[]
    for round in report['rounds']:
        for investigator in round['specialists']:
            supplied=investigator['evidence']
            result=build_investigation_prompt(supplied)
            assert result['constraints']==supplied['constraints']
            assert result['metrics']=={k:v for k,v in supplied['metrics'].items() if v is not None}
            sizes.append(len(json.dumps(result)))
    assert sizes and max(sizes)<20000, sizes
