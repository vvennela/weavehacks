"""Recompute isolated gates and compare saved Weave outputs. No live calls."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.run_placement import load_manifest
from sera.placement_reference import bind_placement_reference
from sera.storage import content_hash


def audit():
    folder = Path(__file__).parent
    loaded = load_manifest(folder/'manifest.json')
    index = json.loads((folder/'references/result.json').read_text())
    assert index['manifest'] == loaded['manifest']
    assert index['status'] == 'references-ready' and index['passing_references'] == 1
    traces = json.loads((folder/'weave-calls.json').read_text())
    by_plan = {trace['plan_hash']:trace for trace in traces}
    rows = []
    for plan in loaded['plans']:
        path = folder/'references'/plan.plan_hash/'result.json'
        record = json.loads(path.read_text())
        trace = by_plan[plan.plan_hash]
        assert all(call['ended_at'] and not call['exception'] for call in trace['calls'])
        fit = {service.model_id:loaded['memory_estimates'][plan.plan_hash][service.model_id].total_bytes
               <= service.allocation_bytes for service in plan.services}
        if not all(fit.values()):
            assert record['status'] == 'rejected' and record['isolated_runtimes'] == []
            assert record['decision']['reason'] == 'estimated-memory-does-not-fit'
            rows.append(dict(plan_hash=plan.plan_hash, status='estimate-rejected-not-measured', fits=fit))
            continue
        bound = bind_placement_reference(path, plan, loaded['workloads'])
        expected, observed = Counter(), Counter()
        services = {}
        for service in plan.services:
            trial = bound['isolated'][service.model_id]
            runtime = trial['runtime']
            assert runtime['memory_after_mib'] == 0
            assert len(trial['quality']) == 8 and len(trial['requests']) == 96
            records = trial['quality'] + trial['requests'] + [request for load in trial['loads'] for request in load['warmup']]
            for request in records:
                expected[content_hash([service.model_id, request['prompt_index'], request['text'],
                    request['token_ids'], request['latency_ms'], request['response_format']])] += 1
            services[service.model_id] = dict(task_passes=8, timed_passes=96,
                p95_latency_ms=bound['gates'][service.model_id]['p95_latency_ms'],
                joint_p95_limit_ms=bound['gates'][service.model_id]['p95_latency_ms']*1.10,
                peak_mib=runtime['sampled_peak_memory_mib'], allocation_bytes=service.allocation_bytes,
                cleanup_memory_mib=0, startup_seconds=runtime['startup_seconds'])
        for call in trace['calls']:
            name = call['op_name'].split('/op/')[-1].split(':')[0]
            value = call['output']
            if name == 'placement_quality_gate':
                assert value['gate'] == bound['gates'][value['model_id']]
            if name == 'recorded_model_request':
                observed[content_hash([value['model_id'], value['prompt_index'], value['output'],
                    value['token_ids'], value['latency_ms'], value['response_format']])] += 1
        assert expected == observed and sum(observed.values()) == 272
        rows.append(dict(plan_hash=plan.plan_hash, status='isolated-references-pass', services=services,
                         trace_request_outputs_matched=272))
    accounting = json.loads((folder/'process-accounting.json').read_text())
    assert accounting['nvml_processes'][0]['pid'] == 1
    assert accounting['api_pid'] != 1 and accounting['engine_pid'] != 1
    return dict(audit_passed=True, plans=rows, weave_calls=sum(len(t['calls']) for t in traces),
        source_sha256={str(path.relative_to(folder)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(folder.rglob('*')) if path.is_file() and path.name not in {'audit.json','README.md'}},
        joint_status='not-run-process-identity-unresolved', joint_acceptance=False,
        quantization_enabled_placement=False, gpu_trials_during_audit=0, provider_calls_during_audit=0)


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
