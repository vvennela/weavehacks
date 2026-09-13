"""Repeatable audit of committed real outputs. No collection or invented universe.

Run: python -m benchmarks.release_audit --repo-root .
The JSON report goes to stdout; this command never writes source evidence.
"""

import argparse
import hashlib
import json
from pathlib import Path

from benchmarks.grade import grade_case
from sera.measurement import reduce_loads, reduce_requests
from sera.storage import content_hash


TASK_SOURCES = {
    'verified-agent-v1': ['baseline'],
    'large-fit-v1': ['candidate_trial'],
    'demo-rehearsal-v1': ['candidate_trial'],
    'large-batch-comparison-v1': ['baseline', 'candidate_trial'],
    'glm-bf16-v1': ['trial'],
    'glm-fp8-weights-v1': ['trial'],
    'qwen-fp8-placement-quality-v1': ['trial'],
}


def audit_task_outputs(cases, trial):
    """Reapply the existing strict grader without stripping or repairing output."""
    outputs = trial.get('quality', [])
    valid = bool(cases) and len(outputs) == len(cases)
    results = []
    for index, case in enumerate(cases):
        output = outputs[index] if index < len(outputs) else {}
        slot_valid = output.get('prompt_index') == index and not output.get('error')
        valid = valid and bool(slot_valid)
        grade = grade_case(case, output.get('text') if slot_valid else None)
        results.append({'case_id': case['id'], **grade})
    passed = sum(item['passed'] for item in results)
    score = passed / len(cases) if cases else 0.0
    saved = trial.get('task_quality', {})
    floor = saved.get('floor')
    gate_passed = bool(valid and type(floor) in (int, float) and score >= floor)
    return dict(passed=passed, total=len(cases), score=score, floor=floor,
                gate_passed=gate_passed,
                saved_gate_matches=saved.get('mean') == score and saved.get('passed') is gate_passed,
                per_case=results)


def _trial_identity(trial):
    runtime = trial['runtime']
    return {key: content_hash(value) for key, value in {
        'model': [runtime['model_id'], runtime['revision']],
        'input_token_ids': trial['input_token_ids'],
        'runtime': runtime['versions'], 'hardware': runtime['gpu'],
        'tokenizer': runtime['tokenizer_info'], 'generation': runtime['generation'],
        'workload': trial['workload'],
    }.items()}


def _recompute_loads(trial):
    loads = [{'concurrency': load['concurrency'],
              'reduced': reduce_requests(load['requests'], load['reduced']['request_wall_seconds'])}
             for load in trial['loads']]
    return loads, reduce_loads(loads)


def audit_comparison(record):
    baseline, candidate = record['baseline'], record['candidate_trial']
    base_loads, base_metrics = _recompute_loads(baseline)
    next_loads, next_metrics = _recompute_loads(candidate)
    identities = {name: _trial_identity(trial) for name, trial in
                  [('baseline', baseline), ('candidate', candidate)]}
    saved_match = all(load['reduced'] == saved['reduced']
        for actual, trial in [(base_loads, baseline), (next_loads, candidate)]
        for load, saved in zip(actual, trial['loads']))
    saved_match = saved_match and base_metrics == baseline['reduced'] and next_metrics == candidate['reduced']
    gain = next_metrics['output_tokens_per_second'] / base_metrics['output_tokens_per_second'] - 1
    required = record['objective']['min_improvement_fraction']
    return dict(source='evidence/large-batch-comparison-v1/result.json',
        scope='One measured fixed comparison, not agent search or a statistical speedup',
        identity_hashes=identities, identity_matches=identities['baseline'] == identities['candidate'],
        saved_metrics_match=bool(saved_match), baseline=base_metrics, candidate=next_metrics,
        candidate_throughput_gain_fraction=gain, required_gain_fraction=required,
        meets_required_gain=gain >= required,
        latency_improvement_fraction=1 - next_metrics['p95_latency_ms'] / base_metrics['p95_latency_ms'],
        saved_selection=record['decision']['selected'],
        loads=[dict(concurrency=left['concurrency'], baseline=left['reduced'], candidate=right['reduced'])
               for left, right in zip(base_loads, next_loads)],
        limitation='Saved measurement-window durations are reused; this does not retime model requests.')


def audit_release(repo_root):
    root = Path(repo_root)
    sources, evaluations, records = [], [], {}

    def source(path):
        raw = (root / path).read_bytes()
        sources.append(dict(path=path, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)))
        return raw

    for name, trial_names in TASK_SOURCES.items():
        path = f'evidence/{name}/result.json'
        record = json.loads(source(path))
        records[name] = record
        if (record.get('provenance') or {}).get('kind') == 'synthetic':
            raise ValueError('Synthetic output cannot enter the real-output release audit')
        for trial_name in trial_names:
            trial = record[trial_name]
            if trial.get('provenance') == 'synthetic' or trial['runtime'].get('provenance') == 'synthetic':
                raise ValueError('Synthetic trial cannot enter the real-output release audit')
            evaluations.append(dict(source=path, trial=trial_name, model_id=record['model_id'],
                configuration=trial['runtime']['configuration'],
                **audit_task_outputs(record['evaluation_cases'], trial)))
    pressure = json.loads(source('evidence/pressure-v1/result.json'))
    for path in ['benchmarks/grade.py', 'benchmarks/search.py', 'benchmarks/release_audit.py',
                 'sera/measurement.py']:
        source(path)
    manifests = []
    for path in sorted((root / 'evidence').rglob('*.json')):
        if 'release-benchmark-audit' in path.parts:
            continue
        record = json.loads(path.read_bytes())
        if isinstance(record, dict) and {'manifest_hash', 'candidates', 'identity', 'baseline'} <= record.keys():
            manifests.append(str(path.relative_to(root)))
    return dict(schema_version='sera-release-benchmark-audit-v1',
        evidence_kind='offline-recheck-of-saved-real-output', gpu_trials=0, provider_calls=0,
        sources=sources, task_evaluations=evaluations,
        performance_comparison=audit_comparison(records['large-batch-comparison-v1']),
        pressure={key: pressure[key] for key in
                  ['scenario', 'status', 'peak_kv_percent', 'measured_preemptions', 'reason']},
        search_replay=dict(status='blocked', grid_runs=0, random_runs=0,
            manifest_scan_scope='evidence/**/*.json, excluding this audit directory',
            frozen_manifest_files=manifests,
            blockers=[
                'No audited pre-collection frozen manifest and complete measured outcome envelopes were supplied.',
                'The recorded strict Qwen3-0.6B baseline passes 2/8 tasks and fails its 0.99 quality floor.',
                'The pressure pilot is not established: high KV use but zero preemptions.',
                'Qwen72B has a fixed two-configuration comparison, not the required Qwen3-0.6B search universe.',
                'Existing records do not bind every outcome to a common frozen manifest, all identity hashes, '
                'and the complete owned runtime interval required for GPU collection cost.',
                'No frozen search-success rule or measured agent/ablation comparison establishes a search advantage.',
            ]),
        conclusion='Saved task and performance evidence is auditable; measured search superiority remains unproven.',
        limitations=['Regrading uses unchanged cases, raw outputs, and the existing strict JSON grader.',
                     'No outputs are normalized, no quality floors are lowered, and no candidate universe is invented.',
                     'Source hashes bind this report to saved files; they do not independently attest GPU execution.',
                     'Synthetic search tests validate software only and are not mixed with these real records.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path('.'))
    args = parser.parse_args()
    print(json.dumps(audit_release(args.repo_root), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
