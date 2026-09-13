"""Read-only audit of the installed-package rehearsal, not task correctness."""

import hashlib
import json
from collections import Counter
from pathlib import Path


def audit(folder):
    report = json.loads((folder / 'result.json').read_text())
    rehearsal = json.loads((folder / 'rehearsal.json').read_text())
    trace = json.loads((folder / 'weave-calls-normalized.json').read_text())
    calls = trace['calls']
    root = next(call for call in calls if call['id'] == trace['root_call_id'])
    assert root['ended_at'] is not None
    assert all(call['exception'] is None for call in calls)
    assert report['public_api_mode'] == 'configured-swarm'
    assert report['status'] == 'closed'
    assert report['swarm_enabled'] is True
    assert report['search']['budget']['max_candidate_trials'] is None
    assert report['workload']['concurrency'] == [1, 2, 4, 8]
    assert report['search']['stop_reason'] == 'objective-plateau-confirmed'
    rounds = report['search']['rounds']
    assert len(rounds) == 3 and rounds[-1]['confirmation_round'] is True
    assert report['search']['trials_used'] == len(report['search_trials']) == 3
    assert report['decision']['selected'] == 'trial-1'
    assert report['returned_runner_closed'] is True
    assert report['returned_runtimes']
    assert all(runtime['cleanup_pass'] and runtime['memory_after_mib'] == 0
               for runtime in report['returned_runtimes'])
    assert rehearsal['post_return_nonempty'] is True
    assert report['task_quality_verified'] is False
    assert rehearsal['probe_matches_four'] is False

    # Bind actual CLI final outputs to the accepted responses saved by the loop.
    controller_outputs = []
    controller = folder.parent / 'public-api-controller-v1'
    for final in controller.glob('*/final.txt'):
        controller_outputs.append(json.dumps(json.loads(final.read_text()), sort_keys=True))
    accepted_outputs = []
    for record in report['agent_calls']:
        assert record['model'] == 'gpt-5.6-luna'
        assert record['provider'] == 'codex-relay'
        assert len(record['attempts']) == 1
        attempt = record['attempts'][0]
        assert attempt['schema_valid'] is True
        accepted_outputs.append(json.dumps(attempt['parsed'], sort_keys=True))
    assert len(accepted_outputs) == 41
    assert Counter(controller_outputs) == Counter(accepted_outputs)

    names = Counter(call['op_name'].split('/op/')[-1].split(':')[0] for call in calls)
    for specialist in ['memory_context', 'output_quality', 'scheduling']:
        assert names[f'swarm_{specialist}_proposal'] == 3
        assert names[f'swarm_{specialist}_peer_review'] == 3
    typed_names = {'arbiter', 'frontier_reviewer'}
    typed_outputs = [json.dumps(call['output'], sort_keys=True) for call in calls
                     if call['op_name'].split('/op/')[-1].split(':')[0] in typed_names
                     or call['op_name'].split('/op/')[-1].split(':')[0].startswith('swarm_')]
    assert Counter(typed_outputs) == Counter(accepted_outputs)
    recovery = Counter(json.loads(line)['event'] for line in
                       (controller / 'recovery.jsonl').read_text().splitlines())
    assert recovery == {'response-delivered': 41}
    return {
        'passed': True,
        'scope': 'Installed API, agent provenance, trace completion, runner ownership, cleanup',
        'task_correctness_passed': False,
        'live_outage_recovery_exercised': False,
        'rounds': len(rounds),
        'candidate_trials': 3,
        'baseline_measurements': 1,
        'trace_calls': len(calls),
        'typed_responses_bound_to_cli_and_trace': len(accepted_outputs),
        'source_sha256': {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
                          for name in ['result.json', 'rehearsal.json', 'weave-calls-normalized.json']},
        'limits': [
            'One prompt; token agreement is not task correctness.',
            'Declared concurrency levels do not prove sustained load.',
            'No search-efficiency or general speedup claim.',
            'Caller generation and cleanup occur after the optimization root span ends.',
        ],
    }


if __name__ == '__main__':
    print(json.dumps(audit(Path(__file__).resolve().parent), indent=2))
