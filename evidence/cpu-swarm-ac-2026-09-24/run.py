"""Score a preserved swarm plan on fresh AC controls; retain original failed vote."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import time

from examples.optimize_cpu_kernel import host_observation, require_ac
from sera.codex_agent import CodexJSONAgent
from sera.cpu_kernel_validation import validate_cpu_kernel
from sera.kernel_advisory import KernelAdvisoryTeam
from sera.kernel_advisor_roles import ADVISOR_ROLES
from sera.kernel_search import KernelCandidate, optimize_kernel
from sera.kernel_swarm_plan import rank_experiments
from sera.kernel_tools import HillsKernelEvaluator
from sera.storage import content_hash, save_json

folder=Path(__file__).resolve().parent
repo=folder.parent.parent
prior=repo/'evidence/cpu-swarm-plan-2026-09-24/agent'
prior_state=json.loads((prior/'state.json').read_text())
assert len(prior_state['rounds'])==1
batch=deepcopy(prior_state['rounds'][0])
assert len(batch['roles'])==15 and len(set(batch['roles']))==15
assert set(batch['roles']) <= ADVISOR_ROLES.keys()
assert len(batch['advice'])==15 and all(a['status']=='received' for a in batch['advice'])
expected=[dict(experiment_id=a['role'],recommendation=a['advice'],risks=a['risks'])
          for a in batch['advice'] if not a['abstain']]
assert batch['board']==expected and content_hash(batch['board'])==batch['board_hash']
assert {v['role'] for v in batch['ballots']}==set(batch['roles']) and len(batch['ballots'])==15
assert not batch['implementations']
ids=[p['experiment_id'] for p in batch['board']]
initial_host=host_observation()
require_ac(initial_host)
task='''Optimize single-thread FP32 row-major gemm on Apple M4 Pro toward 1800 GFLOP/s.
ABI void gemm(int n,const float *A,const float *B,float *C). Apple clang21 with fixed
-O3 -march=native -ffast-math -shared -fPIC -lm. Main shape n512, correct general tails
and n<=0. No mixed precision, threads, external libraries, answer caching, or benchmark edits.
All packing and allocation is inside gemm. Fixed error tolerance .002. FP32 SME has four
ZA tile selectors0..3. The swarm board was prepared using noisy historical BATTERY results;
all measured history in this search is a FRESH AC baseline and paired trials. Never compare
those two power conditions as equivalent. Follow the joint experiment ranking. After each
experiment, use its actual correctness and timing evidence for adopt/reject/revise decisions.
'''
team=KernelAdvisoryTeam(work_dir=folder/'agent',task=task,max_rounds=6,batch_size=3,max_calls=108,
    profile=dict(cpu='Apple M4 Pro',power='AC',capabilities=['cpu','arm64','sme','neon','simd','single-thread']))
team.calls=prior_state['calls']
team.rounds=[batch]
batch['prior_failure']=batch.pop('error',None)
batch['status']='repairing-ranking'
team._save()
for index,vote in enumerate(batch['ballots']):
    if vote['status']=='received':
        rank_experiments(ids,[vote['ranking']],limit=1)
        continue
    role=vote['role']
    old=prior/'round-001'/role/'call-002'
    invalid=json.loads((old/'response.json').read_text())
    prompt=(old/'prompt.txt').read_text()
    prompt+='\nYour prior ranking was invalid: duplicate/omitted IDs. Repair it using EACH exact ID once. '
    prompt+='Required IDs: '+json.dumps(ids)+'\nPrior invalid response: '+json.dumps(invalid)
    agent=CodexJSONAgent(work_dir=folder/'ranking-repair'/role,model='gpt-6-luna',reasoning_effort='medium')
    repaired=team._request(agent,prompt,json.loads((old/'schema.json').read_text()),time.monotonic()+180)
    assert set(repaired)=={'ranking','reason'} and isinstance(repaired['reason'],str)
    rank_experiments(ids,[repaired['ranking']],limit=1)
    batch['ballots'][index]=dict(role=role,status='received',**repaired,format_repairs=1,
        prior_invalid_response=str(old/'response.json'))
    team._save()
order=rank_experiments(ids,[v['ranking'] for v in batch['ballots']],limit=3)
batch.update(status='selected',experiment_order=order)
team.pending=list(order)
team._save()
print('SWARM EXPERIMENT ORDER:',order,flush=True)

baseline=repo/'evidence/cpu-specialists-codex-2026-09-24/search/trial-000/source/kernel.c'
modules=('kernel_advisory.py','kernel_swarm_plan.py','codex_agent.py','kernel_search.py',
         'cpu_kernel_validation.py','kernel_advisor_roles.py','kernel_tools.py')
initial_host=host_observation()
require_ac(initial_host)
save_json(folder/'controls.json',dict(implementation_commit=subprocess.check_output(
    ['git','rev-parse','HEAD'],text=True).strip(),implementation_hashes={name:hashlib.sha256(
    (repo/'sera'/name).read_bytes()).hexdigest() for name in modules},
    baseline=str(baseline),baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
    original_plan=str(prior/'state.json'),original_plan_sha256=hashlib.sha256((prior/'state.json').read_bytes()).hexdigest(),
    target_gflops=1800,max_candidates=6,batch_size=3,max_model_calls=108,
    prior_calls=prior_state['calls'],calls_before_scoring=team.calls,max_seconds=1800,
    host=initial_host,power_condition='AC only; unchanged settings required',
    scoring='Frozen hill; 3 validation reports, paired controls, separated ranges plus5%, Astra adjudication, final holdout'))
evaluator=HillsKernelEvaluator(workspace='/Users/vishnuv/Documents/Documents/kernel-opt')
def evaluate(source_dir,report_path,*,final,timeout):
    before=host_observation()
    require_ac(before)
    if before['power_settings']!=initial_host['power_settings']:
        raise RuntimeError('Power settings changed')
    observations=dict(before=before)
    host_path=Path(report_path).with_suffix('.host.json')
    save_json(host_path,observations)
    try:
        report=evaluator(source_dir,report_path,final=final,timeout=timeout)
        print('SCORED',report_path,report.get('passed'),report.get('metrics'),flush=True)
        return report
    finally:
        after=host_observation()
        observations['after']=after
        save_json(host_path,observations)
        require_ac(after)
        if after['power_settings']!=initial_host['power_settings']:
            raise RuntimeError('Power settings changed during scoring')
try:
    report=optimize_kernel(baseline=KernelCandidate('existing-sme',baseline.read_text(),'Unchanged AC baseline'),
        propose=team,evaluate=evaluate,validate=validate_cpu_kernel,output_dir=folder/'search',
        max_candidates=6,target_gflops=1800,max_seconds=1800)
    team.observe(report['trials'])
    print('RESULT',json.dumps({key:report.get(key) for key in
        ('status','target_met','final_gflops','winner_source','stop_reason')}),flush=True)
finally:
    if (folder/'search/result.json').exists():
        latest=json.loads((folder/'search/result.json').read_text())
        team.observe(latest['trials'])
