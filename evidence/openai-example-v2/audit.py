# Audit the pinned GPU checkout.
"""Audit the completed direct-API dry run. Never export credentials."""
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, '/marimo/sera-openai-example-v2')
import weave

from sera.storage import content_hash, save_json
from sera.weave_evidence import RECORDED_OPS

folder = Path('/marimo/sera-evidence/openai-example-v2')
run = folder / 'swarm-59bf8318c3fa'
report = json.loads((run / 'result.json').read_text())
invocation = json.loads((folder / 'invocation.json').read_text())
certificate = json.loads(Path(invocation['provider_check']['certificate']).read_text())
assert invocation['passed'] and report['status'] == 'closed'
trials = [report['baseline'], *report['search_trials']]
assert all(t['task_quality']['passed'] and t['task_quality']['mean'] == 1 for t in trials)
assert all(t['reduced']['successful_requests'] == 96 and t['reduced']['generation_errors'] == 0 for t in trials)
assert invocation['gpu_after_cleanup']['used_mib'] == 0
assert certificate['passed'] and certificate['first_pass_valid'] == 34
assert report['search']['budget']['max_candidate_trials'] is None
assert report['search']['stop_reason'] == 'objective-plateau-confirmed'
reads, rounds = {}, []
for round_record in report['search']['rounds']:
    specialists = round_record['specialists']
    assert len(specialists) == 3
    round_reads = []
    for investigator in round_record['swarm']['investigators']:
        for inspection in investigator['inspections']:
            assert inspection['status'] == 'complete'
            result = inspection['result']
            assert result['source'] == 'weave'
            round_reads.append({'investigator': investigator['investigator_id'],
                                    'query': result['query_id'],
                                    'matched': result['matched_record_count'],
                                    'returned': len(result['records'])})
            for record in result['records']:
                identifier, digest = record['call_id'], record['output_sha256']
                assert identifier not in reads or reads[identifier] == digest
                reads[identifier] = digest
    rounds.append({'round': round_record['round'], 'confirmation': round_record['confirmation_round'],
                       'trial_ids': round_record['trial_ids'], 'reads': round_reads,
                       'proposals': [{'investigator': s['investigator_id'], 'status': s['status'],
                                       'proposal': s.get('proposal')} for s in specialists],
                       'arbiter': round_record['arbiter']})
client = weave.init('vvennela-n-a/wandb_agent_default_project')
root_id = report['weave_url'].rstrip('/').split('/')[-1]
root = client.get_call(root_id)
assert root.ended_at is not None and root.exception is None
metadata = list(client.get_calls(filter={'trace_ids': [str(root.trace_id)]}, limit=None,
    columns=['id', 'op_name', 'ended_at', 'exception']))
assert all(c.ended_at is not None for c in metadata)
project = f'{client.entity}/{client.project}'
calls = list(client.get_calls(filter={'trace_ids': [str(root.trace_id)],
    'op_names': [f'weave:///{project}/op/{name}:*' for name in RECORDED_OPS]},
    limit=None, columns=['id', 'output', 'ended_at', 'exception']))
remote = {str(c.id): c for c in calls}
for identifier, digest in reads.items():
    assert identifier in remote
    call = remote[identifier]
    assert call.ended_at is not None and call.exception is None
    output = json.loads(json.dumps(call.output, allow_nan=False))
    assert content_hash(output) == digest
selected = next(t for t in trials if t['trial_id'] == report['decision']['selected'])
assert selected['reduced']['p95_latency_ms'] == min(t['reduced']['p95_latency_ms'] for t in trials)
assert selected['component_trial_ids'] == ['trial-1', 'trial-2']
summary = {'passed': True, 'invocation': invocation, 'decision': report['decision'],
    'stop_reason': report['search']['stop_reason'], 'plateau': report['search']['plateau'],
    'trials': [{'trial_id': t['trial_id'], 'configuration': t['runtime']['configuration'],
        'startup_seconds': t['runtime'].get('startup_seconds'),
        'sampled_peak_memory_mib': t['runtime'].get('sampled_peak_memory_mib'),
        'reduced': t['reduced'], 'task_quality': t['task_quality'],
        'component_trial_ids': t.get('component_trial_ids', [])} for t in trials],
    'rounds': rounds,
    'weave': {'url': report['weave_url'], 'trace_id': str(root.trace_id),
        'completed_calls': len(metadata),
        'exceptions': [{'id': str(c.id), 'exception': str(c.exception)} for c in metadata if c.exception],
        'operations': dict(Counter(c.op_name.split('/op/')[-1].split(':')[0] for c in metadata)),
        'unique_read_outputs_checked': len(reads), 'read_hashes': reads},
    'source_records': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                    [run/'result.json', folder/'invocation.json', Path(invocation['provider_check']['certificate'])]}}
encoded = json.dumps(summary, indent=2, allow_nan=False)
for key in ('OPENAI_API_KEY', 'WANDB_API_KEY'):
    value = os.environ.get(key)
    assert not value or value not in encoded
save_json(folder/'audit-summary.json', summary)
print(json.dumps({'passed': True, 'trace': report['weave_url'],
    'calls': len(metadata), 'reads_verified': len(reads),
    'exceptions': summary['weave']['exceptions'],
    'elapsed_seconds': invocation['elapsed_seconds'],
    'improvement_pct': invocation['comparison']['p95_improvement_pct']}), flush=True)
