"""Recheck saved provider replays and pressure pilots; no model or GPU calls."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess

from prometheus_client.parser import text_string_to_metric_families

from benchmarks.live_comparison import _audit_import
from benchmarks.search import StopSearch, replay
from sera.agent import SCHEMAS
from sera.metrics import parse_vllm_metrics
from sera.storage import content_hash, save_json


def dictionaries(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from dictionaries(item)
    elif isinstance(value, list):
        for item in value:
            yield from dictionaries(item)


def main(root):
    sources = {}

    def read(path, raw=False):
        data = (root / path).read_bytes()
        sources[path] = hashlib.sha256(data).hexdigest()
        return data.decode() if raw else json.loads(data)

    replay_folder = 'live-grid-agent-replay-v1'
    comparison = read(f'{replay_folder}/comparison.json')
    _, _, bundle, artifacts, summary, _ = _audit_import(root / 'live-grid-comparison-v1')
    assert summary['complete'] and comparison['manifest_hash'] == bundle['manifest']['manifest_hash']
    results = {}
    for variant in ('full-evidence', 'no-history', 'round-robin'):
        audit = read(f'{replay_folder}/{variant}-policy.json')
        assert audit['policy_hash'] == content_hash(audit['settings'])
        assert audit['settings']['manifest_hash'] == comparison['manifest_hash']
        assert audit['settings']['variant'] == variant
        selected = [row['selected_candidate_id'] for row in audit['rounds']]
        saved = comparison['policies'][variant]
        assert selected == [row['candidate_id'] for row in saved['proposals'] if row['status'] == 'selected']
        choices = iter(selected)

        def choose(view):
            try:
                return next(choices)
            except StopIteration:
                raise StopSearch() from None

        recomputed = replay(bundle['manifest'], artifacts, policy=choose, policy_name=variant)
        for key in ('curve', 'oracle', 'trials_to_near_oracle', 'trials_used', 'invalid_trials', 'quality_failures'):
            assert recomputed[key] == saved[key], (variant, key)
        visible = {bundle['manifest']['baseline']['candidate_id']}
        call_count, attempt_count, invalid_attempts, rejected = 0, 0, 0, 0
        for index, row in enumerate(audit['rounds']):
            specialists = row['specialists']
            expected = (['scheduling', 'memory_context', 'output_quality'][index % 3:index % 3 + 1]
                        if variant == 'round-robin' else ['scheduling', 'memory_context', 'output_quality'])
            assert sorted(item['investigator_id'] for item in specialists) == sorted(expected)
            if variant == 'round-robin':
                assert 'arbiter' not in row and 'shared_findings' not in row
            else:
                assert content_hash(row['shared_findings']) == row['swarm']['shared_findings_hash']
            for specialist in specialists:
                rejected += sum(specialist.get(key) == 'rejected' for key in ('status', 'initial_status'))
            for call in row['agent_calls']:
                call_count += 1
                assert call['model'] == 'gpt-5.6-luna' and call['provider'] == 'codex-relay'
                evidence = call['evidence']
                assert evidence['identity'] == bundle['manifest']['identity']
                assert content_hash(evidence) == call['source_evidence_sha256']
                assert content_hash(call['prompt_evidence']) == call['prompt_evidence_sha256']
                assert json.loads(call['messages'][1]['content']) == call['prompt_evidence']
                allowed = {bundle['manifest']['baseline']['candidate_id']} if variant == 'no-history' else visible
                for item in dictionaries(evidence):
                    assert 'oracle' not in item
                    if 'trial_id' in item:
                        assert item['trial_id'] in allowed, (variant, item['trial_id'])
                if variant == 'no-history':
                    assert not evidence.get('history')
                    assert not any(key.startswith('observed.') for key in evidence.get('metrics', {}))
                for attempt in call['attempts']:
                    attempt_count += 1
                    if attempt.get('schema_valid'):
                        SCHEMAS[call['role']].model_validate(attempt['parsed'])
                    else:
                        invalid_attempts += 1
            visible.add(selected[index])
        results[variant] = {
            'first_hit': saved['trials_to_near_oracle'], 'trials': saved['trials_used'],
            'final_p95_ms': saved['curve'][-1]['p95_latency_ms'],
            'policy_wall_seconds': saved['policy_seconds'], 'provider_calls': call_count,
            'provider_attempts': attempt_count,
            'invalid_provider_attempts': invalid_attempts, 'rejected_specialist_responses': rejected,
            'selected_ids': selected, 'selected_only_evidence_verified': True,
        }

    pressure_folder = 'pressure-pair-v3'
    registration = read(f'{pressure_folder}/registration.json')
    assert registration['registration_hash'] == content_hash(
        {key: value for key, value in registration.items() if key != 'registration_hash'})
    pressure = {}
    for name in ('cache-v2', 'queue-v1'):
        prefix = f'{pressure_folder}/{name}'
        record = read(f'{prefix}/result.json')
        profile = registration['profiles'][name]
        assert record['profile'] == profile and record['profile_hash'] == content_hash(profile)
        assert content_hash(record['source_prompts']) == record['source_prompts_hash'] == registration['source_prompts_hash']
        assert content_hash(record['input_token_ids']) == record['workload_hash']
        before, after = read(f'{prefix}/metrics-before.prom', True), read(f'{prefix}/metrics-after.prom', True)
        assert parse_vllm_metrics(before, 'sera-model') == record['metrics_before']
        assert parse_vllm_metrics(after, 'sera-model') == record['metrics_after']

        def total(raw, metric):
            values = [sample.value for family in text_string_to_metric_families(raw)
                      for sample in family.samples if sample.name == f'vllm:{metric}'
                      and sample.labels.get('model_name') == 'sera-model']
            assert values and all(math.isfinite(value) and value >= 0 for value in values)
            return sum(values)

        count = total(after, 'request_queue_time_seconds_count') - total(before, 'request_queue_time_seconds_count')
        queue_sum = total(after, 'request_queue_time_seconds_sum') - total(before, 'request_queue_time_seconds_sum')
        assert count == 24 and queue_sum >= 0
        queue = queue_sum / count * 1000
        assert queue == record['measured_queue_ms']
        preemptions = total(after, 'num_preemptions_total') - total(before, 'num_preemptions_total')
        assert preemptions == record['measured_preemptions'] == 0
        peak = max(row['kv_cache_percent'] for row in record['samples'])
        assert peak == record['peak_kv_percent']
        assert parse_vllm_metrics(read(f'{prefix}/metrics-at-peak.prom', True), 'sera-model')['kv_cache_percent'] == peak
        requests = record['requests']
        assert len(requests) == 24 == record['measured_requests']
        assert {(row['wave'], row['prompt_index']) for row in requests} == {(wave, i) for wave in range(3) for i in range(8)}
        assert all(not row['error'] and row['token_ids'] and row['text'].strip()
                   and row['finish_reason'] in ('stop', 'length')
                   and row['prompt_token_ids'] == record['input_token_ids'][row['prompt_index']]
                   and len(row['prompt_token_ids']) == 2304
                   and math.isfinite(row['latency_ms']) and row['latency_ms'] > 0 for row in requests)
        runtime = record['runtime']
        assert runtime['cleanup_pass'] and runtime['memory_after_mib'] == 0
        assert runtime['configuration']['gpu_memory_utilization'] == profile['gpu_memory_utilization']
        assert record['sampling_errors'] == record['request_errors'] == record['candidate_trials'] == 0
        assert record['task_quality_verified'] is False
        established = (queue >= profile['minimum_measured_queue_ms']
                       and peak < profile['maximum_kv_percent_exclusive'] and preemptions == 0
                       if name == 'queue-v1' else peak >= profile['high_kv_percent']
                       and preemptions >= profile['minimum_preemptions'])
        assert record['scenario'] == ('established' if established else 'not-established')
        latencies = sorted(row['latency_ms'] for row in requests)
        pressure[name] = {'scenario': record['scenario'], 'peak_kv_percent': peak,
            'preemptions': preemptions, 'measured_queue_ms': queue, 'queue_count_delta': count,
            'request_count': 24, 'errors': 0, 'cleanup_memory_mib': 0,
            'median_request_ms': statistics.median(latencies),
            'p95_request_ms': latencies[math.ceil(len(latencies) * .95) - 1],
            'startup_seconds': runtime['startup_seconds'], 'profile_hash': record['profile_hash']}
    same_modules = ('swarm', 'agent', 'investigation_prompt', 'provider_check', 'relay',
                    'storage', 'tracing', 'techniques', 'diagnosis', 'trace_evidence')
    hashes = {name: {revision: hashlib.sha256(subprocess.check_output(
        ['git', 'show', f'{revision}:sera/{name}.py'])).hexdigest()
        for revision in ('d8c7304', '3a9cb31')} for name in same_modules}
    assert all(len(set(values.values())) == 1 for values in hashes.values())
    assert all(entry['configuration']['tensor_parallel_size'] == 1 for entry in
               [bundle['manifest']['baseline'], *bundle['manifest']['candidates']])
    return {'schema_version': 'sera-final-benchmark-audit-v1', 'audit_passed': True,
            'gpu_trials_during_audit': 0, 'provider_calls_during_audit': 0,
            'policies': results, 'pressure': pressure, 'source_sha256': sources,
            'replay_source': {'driver_revision': '3a9cb31', 'installed_library_revision': 'd8c7304',
                'identical_replay_module_hashes': hashes,
                'config_difference': '3a9cb31 permits TP 1/2/4/8; d8c7304 permits TP1. All frozen configs use TP1.',
                'scope': 'Retrospective git comparison. No new placement, portable-runtime, or GPU execution in replay.'},
            'ablation_win': False, 'strict_section_19_4_claim': False,
            'limitations': ['Saved-artifact consistency audit, not cryptographic proof of execution.',
                            'Provider replay inspected selected cached metrics, not fresh Weave calls.',
                            'All policy first-hit counts tie; neither intelligence ablation was beaten.',
                            'Neither preregistered pressure profile was established.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, required=True)
    args = parser.parse_args()
    report = main(args.evidence_root)
    save_json(Path(__file__).with_name('result.json'), report)
    print(json.dumps({key: report[key] for key in ('audit_passed', 'policies', 'pressure')}, indent=2))
