"""Verify signed replay reports and retain all timing samples; no benchmarking."""
import hashlib
import json
from pathlib import Path
from statistics import median
import subprocess

from examples.optimize_cpu_kernel import check_power,power_source
from sera.kernel_search import _score

FOLDER=Path(__file__).resolve().parent
BASELINE='04fc3ff86669c2ca123e3b390b662637cd69c21f3d63fa26f7a5f0f0a882317c'
CANDIDATE='eb091b1eca431f0760d0d61e4c0c6e748c1a9e34466a87ac15ad9cb238b5aecf'


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summarize(trial):
    scores=trial['scores'];controls=trial['control_scores']
    return dict(name=trial['name'],source_hash=trial['source_hash'],minimum=min(scores),median=median(scores),maximum=max(scores),
        control_minimum=min(controls) if controls else None,control_median=median(controls) if controls else None,
        control_maximum=max(controls) if controls else None,
        paired_wins=sum(a>b for a,b in zip(scores,controls)),promoted=trial.get('promoted',False))


def main():
    result=read(FOLDER/'search/result.json');settings=read(FOLDER/'controls.json');state=read(FOLDER/'agent/state.json')
    assert result['status']!='running'
    assert [t['source_hash'] for t in result['trials']]==[BASELINE,CANDIDATE]
    assert result['policy']==dict(max_candidates=6,repeats=10,min_improvement=.05,max_seconds=1800)
    assert state['calls']==1 and state['implementations']==0
    reports=[]
    identity=result['comparison_identity']
    def verify(path,score,kind,ordinal,final=False):
        path=Path(path)
        subprocess.run(['hills','verify',str(path)],cwd='/Users/vishnuv/Documents/Documents/kernel-opt',capture_output=True,check=True,timeout=15)
        report=read(path)
        assert _score(report,final=final,identity=identity)==score
        times=report['details']['timings_seconds']
        assert len(times)==3 and all(t>0 for t in times)
        assert min(times)==report['details']['seconds_best_of_3']
        assert abs(2*512**3/min(times)/1e9-score)<1e-8
        host=read(path.with_suffix('.host.json'))
        check_power(host['before'],settings['host']);check_power(host['after'],settings['host'])
        reports.append(dict(path=str(path.relative_to(FOLDER)),sha256=sha(path),kind=kind,ordinal=ordinal,
            score=score,raw_timings_seconds=times,slowest_over_fastest=max(times)/min(times),
            fastest_call_index=times.index(min(times))+1,signature_verified=True))
    for index,trial in enumerate(result['trials']):
        assert sha(trial['source'])==trial['source_hash']
        public=trial['public_correctness']
        assert public['passed'] and public['source_hash']==trial['source_hash']
        assert len(public['sizes'])*len(public['input_kinds'])==48 and public['tolerance']==.002
        assert len(trial['scores'])==len(trial['reports'])==10
        for i,(path,score) in enumerate(zip(trial['reports'],trial['scores'])):
            verify(path,score,'baseline' if index==0 else 'candidate',i)
        if index:
            assert len(trial['control_scores'])==len(trial['control_reports'])==10
            eligible=min(trial['scores'])>1.05*max(trial['control_scores'])
            assert trial['eligible_for_promotion']==eligible
            if trial['promoted']:assert eligible
            for i,(path,score) in enumerate(zip(trial['control_reports'],trial['control_scores'])):
                verify(path,score,'paired_control',i)
    verify(result['final_report'],result['final_gflops'],'final',0,True)
    selected=next(t for t in result['trials'] if t['source']==result['selected_source'])
    assert result['final_minimum_gflops']==.95*min(selected['scores'])
    assert result['winner_source'] in (None,result['selected_source'])
    baseline,candidate=result['trials']
    comparisons={name:dict(peak=peak,candidate_exceed_count=sum(s>peak for s in candidate['scores'])) for name,peak in
        dict(fresh_initial=max(baseline['scores']),fresh_paired=max(candidate['control_scores']),
        historical_battery_automatic=settings['historical_imported_peak_gflops'],
        historical_ac_initial=settings['prior_ac_initial_baseline_peak_gflops'],
        historical_ac_control=settings['prior_ac_control_peak_gflops']).items()}
    raw_summary={kind:dict(median_slowest_over_fastest=median(r['slowest_over_fastest'] for r in reports if r['kind']==kind),
        fastest_call_counts={str(i):sum(r['fastest_call_index']==i for r in reports if r['kind']==kind) for i in (1,2,3)})
        for kind in ('baseline','candidate','paired_control')}
    verification=dict(status=result['status'],signed_reports=len(reports),raw_timing_count=sum(len(r['raw_timings_seconds']) for r in reports),
        power=power_source(settings['host']),power_settings_unchanged=True,source_hashes_verified=True,
        trials=[summarize(t) for t in result['trials']],comparisons=comparisons,raw_timing_summary=raw_summary,
        final_gflops=result['final_gflops'],final_source_hash=selected['source_hash'],calls=state['calls'],
        new_implementations=0,performance_executed_by_verifier=False,reports=reports)
    (FOLDER/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
    print(json.dumps({k:v for k,v in verification.items() if k!='reports'},indent=2))


if __name__=='__main__':main()
