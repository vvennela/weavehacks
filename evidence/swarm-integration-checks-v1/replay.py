import json, weave, faulthandler
faulthandler.dump_traceback_later(30, repeat=True)
print('SMOKE imported',flush=True)
from pathlib import Path
from sera import WandbAgent, RuntimeConfig, Workload, Objective, Constraints
from sera.pipeline import agent_evidence, trial_trace_scope
from sera.investigation import remaining_candidates
from sera.swarm import choose_swarm_experiments
from sera.storage import save_json
from experiments.run_investigation import TracedInvestigationAgent, traced_evidence_reader
from experiments.weave_evidence import WeaveEvidenceReader
saved=json.loads(Path('/marimo/sera-evidence/live-team-investigation-v1/result.json').read_text())
print('SMOKE before weave init',flush=True)
client=weave.init('vvennela-n-a/wandb_agent_default_project')
print('SMOKE weave initialized',flush=True)
@weave.op()
def replay_swarm_provider_smoke():
    print('SMOKE entered root',weave.get_current_call().ui_url,flush=True)
    evidence=agent_evidence(saved['baseline'], Objective(priority='latency'), Constraints(quality_floor=.99),prompts=saved['prompts'])
    evidence['trace_scope']=[trial_trace_scope(saved['deployment']['candidate_trial'])]
    evidence['supported_changes']=saved['investigation_space']['supported_changes']
    evidence['frozen_candidate_hashes']=saved['investigation_space']['candidate_hashes']
    evidence.update(history=[],previous_rounds=[],provenance='Saved GPU measurements replayed for provider/reader smoke; no GPU trial will run.')
    config=RuntimeConfig.model_validate(saved['baseline_configuration'])
    legal=remaining_candidates(evidence,config,{config.config_hash},Workload(concurrency=[1,2,4,8]),saved['baseline'])
    print('SMOKE evidence prepared',flush=True)
    agent=TracedInvestigationAgent(WandbAgent(project='vvennela-n-a/wandb_agent_default_project'),weave)
    reader=traced_evidence_reader(weave,WeaveEvidenceReader(client,'01a09a0f-065a-7361-9a7d-47b805ee4059',evaluation_cases=saved['evaluation_cases']))
    record=dict(round=1,specialists=[],trial_ids=[])
    print('SMOKE choose start',flush=True)
    chosen=choose_swarm_experiments(agent,evidence,legal,record,2,reader)
    print('SMOKE choose done',flush=True)
    result=dict(provenance='Real provider and persisted Weave reads; saved GPU baseline; no new GPU trial.',source_commit='61aad6c',weave_url=weave.get_current_call().ui_url,record=record,agent_calls=agent.history,chosen=[p.model_dump() for p,c,r in chosen],trace_failures=agent.trace_failures)
    save_json(Path('/marimo/sera-evidence/swarm-provider-smoke-v4.json'),result)
    return {'weave_url':result['weave_url'],'investigators':[{'id':c['investigator_id'],'status':c['status'],'degraded':c['degraded'],'initial':c.get('initial_proposal'),'final':c.get('proposal')} for c in record['specialists']],'chosen':result['chosen'],'trace_failures':result['trace_failures']}
print(json.dumps(replay_swarm_provider_smoke()),flush=True)
client.flush()
