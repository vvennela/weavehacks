# Audit script used after the completed run. Reads saved evidence and Weave; no GPU trials.
import json, weave, hashlib, subprocess
from pathlib import Path
from collections import Counter
from copy import deepcopy
from sera.tracing import use_event_sink, recorded_model_request
from sera.measurement import export_trial_events
folder=Path('/marimo/sera-evidence/live-team-investigation-v1')
report=json.loads((folder/'result.json').read_text())
client=weave.init('vvennela-n-a/wandb_agent_default_project')
root=client.get_call('01a09a0f-065b-7fcd-b076-d419fd5ae02d')
calls=list(client.get_calls(filter={'trace_ids':[root.trace_id]},limit=1000,columns=['id','parent_id','op_name','inputs','output','exception','ended_at']))
def name(call):
    return call.op_name.split('/op/')[-1].split(':')[0]
def packed(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':'))
expected=[]
with use_event_sink(lambda event,payload: expected.append((event,payload))):
    for trial in [report['deployment']['candidate_trial'],*report['search_trials']]:
        copy=deepcopy(trial)
        copy['trace_export']['emitted_events']=0
        export_trial_events(copy,report['prompts'])
    runtime=report['returned_runtimes'][0]
    recorded_model_request(trial_id=report['decision']['selected'],model_id=report['model_id'],
        revision=report['model_revision'],config_hash=report['baseline']['config_hash'],
        phase='post-return-probe',concurrency=1,prompt_index=0,prompt=report['prompts'][0],
        response=report['post_return_probe'])
checks={}
for event in ['recorded_model_request','recorded_trial_metrics']:
    expected_values=Counter(packed(payload) for kind,payload in expected if kind==event)
    actual_values=Counter(packed(call.output) for call in calls if name(call)==event)
    checks[event+'_exact_match']=expected_values==actual_values
provider_fields=['model','role','attempt','content','reasoning','latency_ms','schema_valid','finish_reason']
expected_provider=[]
for entry in report['agent_calls']:
    for attempt in entry['attempts']:
        choice=attempt['raw_response']['choices'][0]
        expected_provider.append(dict(model=entry['model'],role=entry['role'],attempt=attempt['attempt'],
            content=choice['message'].get('content'),reasoning=choice['message'].get('reasoning'),
            latency_ms=attempt['latency_ms'],schema_valid=attempt['schema_valid'],finish_reason=choice.get('finish_reason')))
actual_provider=[{key:call.output.get(key) for key in provider_fields} for call in calls if name(call)=='record_agent_response']
checks['provider_content_and_reasoning_exact_match']=Counter(map(packed,expected_provider))==Counter(map(packed,actual_provider))
expected_evidence=[entry['evidence'] for entry in report['agent_calls'] if entry['role']=='proposal']
actual_evidence=[call.inputs['evidence'] for call in calls if name(call)=='batching_specialist']
checks['specialist_evidence_exact_match']=Counter(map(packed,expected_evidence))==Counter(map(packed,actual_evidence))
checks['specialists_received_request_examples']=bool(actual_evidence) and all(e['request_evidence']['quality_examples'] and e['request_evidence']['slow_request_examples'] for e in actual_evidence)
checks['later_round_received_measured_history']=any(e.get('history') and e['history'][0]['request_evidence']['slow_request_examples'] for e in actual_evidence)
checks['all_calls_ended_without_exception']=all(call.ended_at is not None and not call.exception for call in calls)
checks['root_selected_baseline_and_closed']=root.output['status']=='closed' and root.output['decision']['selected']=='baseline'
gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True).stdout.strip()
verification=dict(schema_version='sera-weave-live-verification-v1',source_commit='27f877d34b9ef90b8ed4c1010503dbbd277ee562',
    result_sha256=hashlib.sha256((folder/'result.json').read_bytes()).hexdigest(),root_call_id=root.id,trace_id=root.trace_id,
    weave_url=report['weave_url'],call_count=len(calls),op_counts=dict(Counter(map(name,calls))),
    checks=checks,passed=all(checks.values()),gpu_memory_mib_after_exit=int(gpu),
    provider_returned_reasoning_count=sum(bool(item['reasoning']) for item in actual_provider),
    evidence_source='Agents receive selected saved request records, not a remote Weave query. This audit queried the persisted Weave calls.')
print('SERA_VERIFICATION '+json.dumps(verification))
