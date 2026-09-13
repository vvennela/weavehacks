"""Audit the saved passing joint run. No GPU, provider, or Weave network calls."""

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from unittest.mock import patch

from benchmarks.grade import grade_case
from experiments.run_placement import load_manifest
from experiments.requested_answer_types import response_format_for_prompt
from sera.agent import ArbiterDecision
from sera.measurement import reduce_loads, reduce_requests
from sera.placement import _gate
from sera.placement_capacity import capacity_evidence
from sera.placement_reference import _check_requests, bind_placement_reference
from sera.runtime import GENERATION
from sera.storage import content_hash, save_json


def audit(folder):
    sources = {}

    def read(relative):
        raw = (folder / relative).read_bytes()
        sources[relative] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    loaded = load_manifest(folder / 'manifest.json')
    read('manifest.json')
    report = read('result.json')
    assert report['status'] == 'closed' and report['rehearsal_passed'] is True
    assert report['returned_runner_closed'] is True and report['trace_status'] == 'enabled'
    assert not report['trace_export_failures']
    assert report['memory_accounting'] == loaded['memory_accounting'] == 'total-device'
    assert len(report['trials']) == len(report['rounds']) == 1
    assert report['stop_reason'] == 'no-legal-plans' and report['budget']['max_candidate_trials'] is None
    by_id = {plan.plan_hash: plan for plan in loaded['plans']}
    selected = report['selected_plan_id']
    plan = by_id[selected]
    assert plan.declared_budget_bytes == 24 * 1024**3
    assert report['rounds'][0]['selected_plan_id'] == report['trials'][0]['plan_id'] == selected
    round_record = report['rounds'][0]
    assert round_record['evidence']['legal_proposal_ids'] == [selected]
    assert ArbiterDecision.model_validate(round_record['response']).ranked_proposal_ids == [selected]
    assert len(report['rejected']) == 3
    reference_path = folder / 'references' / f'{selected}.json'
    read(f'references/{selected}.json')
    bound = bind_placement_reference(reference_path, plan, loaded['workloads'])
    assert bound['provenance']['sha256'] == report['references'][selected]['sha256']
    placement = read('trial-001/result.json')
    assert placement == report['returned_placement']
    assert placement['plan_hash'] == selected and placement['decision']['outcome'] == 'safe-placement'
    assert placement['workloads'] == {key: profile.manifest() for key, profile in loaded['workloads'].items()}
    assert placement['workload_hash'] == report['workload_hash'] == content_hash(placement['workloads'])
    assert placement['isolated'] == bound['isolated']
    assert placement['service_hard_caps_verified'] is False
    shared = placement['shared_runtime']
    assert shared['memory_accounting'] == 'total-device' and shared['per_service_memory_verified'] is False
    assert all(value is None for value in shared['service_peak_memory_mib'].values())
    assert 0 < shared['sampled_peak_memory_mib'] * 1024**2 <= plan.declared_budget_bytes
    assert shared['cleanup_pass'] and shared['owned_local_process_groups_released'] and shared['gpu_release_verified']
    assert shared['memory_after_mib'] == 0 and not shared['remaining_owned_process_groups']
    assert not shared['remaining_gpu_processes'] and not shared['errors'] and not shared['cleanup_errors']
    assert shared['telemetry_errors'] == 0
    expected_requests = Counter()
    services = {}
    for index, service in enumerate(plan.services):
        model_id = service.model_id
        profile = loaded['workloads'][model_id]
        assert profile.response_formats == [response_format_for_prompt(case['prompt']) for case in loaded['cases']]
        trial = deepcopy(placement['joint']['trials'][model_id])
        isolated = bound['isolated'][model_id]
        runtime = trial['runtime']
        saved_runtime = read(f'trial-001/joint-{index}/runtime.json')
        log_path = f'trial-001/joint-{index}/server.log'
        log_bytes = (folder / log_path).read_bytes()
        sources[log_path] = hashlib.sha256(log_bytes).hexdigest()
        server_log = log_bytes.decode()
        assert f"model='{model_id}'" in server_log and f'revision={service.revision}' in server_log
        assert f'quantization={service.configuration.quantization}' in server_log
        assert 'kv_cache_dtype=auto' in server_log
        assert runtime == saved_runtime
        assert runtime['model_id'] == model_id and runtime['revision'] == service.revision
        assert runtime['configuration'] == service.configuration.model_dump()
        assert runtime['config_hash'] == trial['config_hash'] == service.configuration.config_hash
        assert runtime['generation'] == GENERATION and runtime['enable_thinking'] is False
        assert runtime['gpu']['uuid'] == isolated['runtime']['gpu']['uuid'] == shared['gpu']['uuid']
        assert runtime['versions'] == isolated['runtime']['versions']
        assert runtime['cleanup_pass'] and runtime['owned_local_process_group_released']
        assert runtime['telemetry_errors'] == 0
        tokens = trial['input_token_ids']
        assert tokens == isolated['input_token_ids']
        assert service.constraints.quality_floor == .99
        assert service.constraints.max_p95_slowdown_fraction == .10 and service.constraints.max_generation_errors == 0
        assert [row['concurrency'] for row in trial['loads']] == [1, 2, 4, 8]
        flattened = []
        warmups = []
        for load in trial['loads']:
            _check_requests(load['warmup'], list(range(8)), tokens, profile.response_formats)
            _check_requests(load['requests'], [i % 8 for i in range(24)], tokens, profile.response_formats)
            window = load['measurement_window']
            elapsed = load['reduced']['request_wall_seconds']
            assert math.isclose(window['ended'] - window['started'], elapsed, rel_tol=1e-6, abs_tol=1e-6)
            assert reduce_requests(load['requests'], elapsed) == load['reduced']
            flattened.extend(load['requests'])
            warmups.extend(load['warmup'])
        assert trial['requests'] == flattened and trial['warmup'] == warmups
        assert reduce_loads(trial['loads']) == trial['reduced']
        _check_requests(trial['quality'], list(range(8)), tokens, profile.response_formats)
        for row in [*flattened, *trial['quality']]:
            assert grade_case(loaded['cases'][row['prompt_index']], row['text'])['passed']
        saved_gate = placement['joint']['gates'][model_id]
        gate = _gate(trial, profile, service, isolated_p95_ms=isolated['reduced']['p95_latency_ms'], joint=True)
        assert saved_gate == gate | {'input_tokens_match': True}
        assert gate['passed'] and gate['latency_limit_ms'] == isolated['reduced']['p95_latency_ms'] * 1.10
        for row in [*flattened, *warmups, *trial['quality']]:
            expected_requests[content_hash([model_id, row['prompt_index'], row['text'], row['token_ids'],
                row['latency_ms'], row['response_format']])] += 1
        services[model_id] = {'quality_passes': 8, 'timed_quality_passes': 96,
            'isolated_p95_ms': isolated['reduced']['p95_latency_ms'], 'joint_p95_ms': gate['p95_latency_ms'],
            'joint_limit_ms': gate['latency_limit_ms'],
            'slowdown_fraction': gate['p95_latency_ms'] / isolated['reduced']['p95_latency_ms'] - 1,
            'per_load_p95_ms': {str(load['concurrency']): load['reduced']['p95_latency_ms'] for load in trial['loads']},
            'configuration': runtime['configuration'], 'startup_seconds': runtime['startup_seconds']}
    assert [row['concurrency'] for row in placement['joint']['overlap']] == [1, 2, 4, 8]
    assert placement['joint']['overlap_pass']
    for overlap in placement['joint']['overlap']:
        windows = []
        for model_id, window in overlap['windows'].items():
            load = next(row for row in placement['joint']['trials'][model_id]['loads']
                        if row['concurrency'] == overlap['concurrency'])
            assert window == load['measurement_window']
            windows.append(window)
        duration = max(row['ended'] for row in windows) - min(row['started'] for row in windows)
        intersection = min(row['ended'] for row in windows) - max(row['started'] for row in windows)
        assert intersection > 0 and overlap['overlap_seconds'] == intersection
        assert overlap['coverage_fraction'] == intersection / duration
    assert len(report['returned_runner_probes']) == 2
    assert {probe['model_id'] for probe in report['returned_runner_probes']} == set(loaded['workloads'])
    for probe in report['returned_runner_probes']:
        response = probe['response']
        assert probe['response_format'] == loaded['workloads'][probe['model_id']].response_formats[0]
        assert response['token_ids'] and response['finish_reason'] == 'stop' and not response.get('error')
        assert probe['grade'] == grade_case(loaded['cases'][0], response['text']) and probe['grade']['passed']
    traces = read('weave-calls-normalized.json')
    calls = traces['calls']
    assert len(calls) == len({call['id'] for call in calls})
    by_call = {call['id']: call for call in calls}
    assert all(call['trace_id'] == traces['trace_id'] and call['ended_at'] and not call['exception'] for call in calls)
    assert traces['root_call_id'] == report['weave_url'].rsplit('/', 1)[-1]
    for call in calls:
        current, seen = call, set()
        while current['id'] != traces['root_call_id']:
            assert current['id'] not in seen
            seen.add(current['id'])
            current = by_call[current['parent_id']]
    observed = Counter()
    typed = []
    for call in calls:
        name = call['op_name'].split('/op/')[-1].split(':')[0]
        value = call['output']
        if name == 'recorded_model_request':
            observed[content_hash([value['model_id'], value['prompt_index'], value['output'], value['token_ids'],
                                   value['latency_ms'], value['response_format']])] += 1
        elif name == 'placement_quality_gate':
            assert value['gate'] == placement['joint']['gates'][value['model_id']]
        elif name == 'arbiter':
            assert call['inputs']['evidence'] == round_record['evidence']
            assert all(value.get(key) == item for key, item in round_record['response'].items())
            typed.append(call['id'])
    assert expected_requests == observed and sum(observed.values()) == 272
    assert len(typed) == 1
    capacity = capacity_evidence(plan, report['rejected'], by_id, placement)
    capacity['workload_hash'] = report['workload_hash']
    assert capacity == report['capacity_evidence'] and capacity['established']
    assert capacity['measured_memory_savings_bytes'] is None
    return {'schema_version': 'sera-joint-placement-audit-v1', 'audit_passed': True,
        'joint_acceptance': True, 'source_sha256': sources, 'services': services,
        'overlap': placement['joint']['overlap'], 'sampled_total_peak_mib': shared['sampled_peak_memory_mib'],
        'declared_budget_mib': 24 * 1024, 'cleanup_memory_mib': 0, 'weave_calls': len(calls),
        'weave_request_outputs_matched': 272, 'typed_arbiter_calls_matched': 1,
        'returned_runner_probes_passed': 2, 'capacity_evidence': capacity,
        'weave_url': report['weave_url'], 'gpu_trials_during_audit': 0, 'provider_calls_during_audit': 0,
        'limits': ['Total-device accounting, not separately verified service memory caps; sampled peaks can miss spikes.',
            'Passing fixed FP8 pair versus estimated same-allocation BF16 rejection, not all possible BF16 allocations.',
            'One eligible measured plan and one arbiter choice; not a multi-round placement swarm.',
            'Post-return probes and final cleanup are saved external records, not children of the ended root trace.',
            'Artifact consistency audit, not independent proof of execution.']}


def check_corruption_rejected(folder):
    """Alter in-memory reads only; never edit the source evidence."""
    original_read = Path.read_bytes
    results = {}
    for kind in ('wrong-answer', 'changed-p95'):
        def damaged_read(path):
            raw = original_read(path)
            if path in (folder / 'result.json', folder / 'trial-001/result.json'):
                value = json.loads(raw)
                placement = value.get('returned_placement', value)
                trial = next(iter(placement['joint']['trials'].values()))
                if kind == 'wrong-answer':
                    trial['quality'][0]['text'] = '{"answer":999}'
                else:
                    trial['loads'][0]['reduced']['p95_latency_ms'] += 100
                return json.dumps(value).encode()
            return raw

        try:
            with patch.object(Path, 'read_bytes', damaged_read):
                audit(folder)
        except AssertionError as error:
            import linecache
            trace = error.__traceback__
            while trace.tb_next is not None:
                trace = trace.tb_next
            line = linecache.getline(trace.tb_frame.f_code.co_filename, trace.tb_lineno).strip()
            expected = 'grade_case' if kind == 'wrong-answer' else 'reduce_requests'
            assert expected in line, (kind, line)
            results[kind] = {'rejected': True, 'failed_check': line,
                             'source_edits': False, 'method': 'in-memory file-read substitution'}
        else:
            raise AssertionError(f'The audit accepted {kind} corruption')
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    result = audit(args.source_dir)
    result['negative_checks'] = check_corruption_rejected(args.source_dir)
    save_json(Path(__file__).with_name('audit.json'), result)
    print(json.dumps({key: result[key] for key in ('audit_passed', 'services', 'sampled_total_peak_mib',
                                                  'weave_calls', 'returned_runner_probes_passed')}, indent=2))
