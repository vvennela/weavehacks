"""Recompute round wall time from saved real Weave spans. No live calls."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics


def operation(call):
    return call['op_name'].split('/op/')[-1].split(':')[0]


def seconds(start, end):
    elapsed = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    assert elapsed >= 0
    return elapsed


def measure(folder):
    report_path = folder / 'result.json'
    trace_path = folder / 'weave-calls-normalized.json'
    report = json.loads(report_path.read_text())
    calls = json.loads(trace_path.read_text())['calls']
    reviews = sorted((call for call in calls if operation(call) == 'frontier_reviewer'),
                     key=lambda call: call['started_at'])
    rounds = report['search']['rounds']
    assert len(reviews) == len(rounds) + 1  # One initial fit review, then each measured round.
    rows = []
    for index, round_record in enumerate(rounds):
        previous, review = reviews[index:index + 2]
        reviewed_id = review['inputs']['evidence']['candidate_request_evidence']['trial_id']
        assert round_record['trial_ids'] == [reviewed_id]
        starts = [call for call in calls if operation(call).startswith('swarm_')
                  and previous['ended_at'] <= call['started_at'] < review['started_at']]
        start = min(call['started_at'] for call in starts)
        arbiters = [call for call in calls if operation(call) == 'arbiter'
                    and start <= call['started_at'] < review['started_at']]
        decision_end = max(call['ended_at'] for call in arbiters)
        trial = next(trial for trial in report['search_trials'] if trial['trial_id'] == reviewed_id)
        rows.append(dict(round=round_record['round'], trial_id=reviewed_id,
            started_at=start, ended_at=review['ended_at'], review_call_id=review['id'],
            elapsed_seconds=seconds(start, review['ended_at']),
            pretrial_agent_wall_seconds=seconds(start, decision_end),
            startup_seconds=trial['runtime']['startup_seconds'],
            posttrial_review_seconds=seconds(review['started_at'], review['ended_at'])))
    return dict(run=folder.name, rounds=rows,
        mean_seconds=statistics.mean(row['elapsed_seconds'] for row in rows),
        median_seconds=statistics.median(row['elapsed_seconds'] for row in rows),
        mean_pretrial_agent_wall_seconds=statistics.mean(row['pretrial_agent_wall_seconds'] for row in rows),
        mean_startup_seconds=statistics.mean(row['startup_seconds'] for row in rows),
        source_sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in [report_path, trace_path]})


if __name__ == '__main__':
    evidence = Path(__file__).resolve().parents[1]
    print(json.dumps(dict(
        scope='First investigator inspection through post-trial review; excludes initial deployment and final runner restoration.',
        limits=['Three rounds per model, one machine and workload; not a provider speed benchmark.',
                'Pretrial time is wall time, not the sum of parallel model calls.',
                'Luna round two includes the recorded connection interruption.',
                'Astra round two includes a 191-second graph-execution startup.'],
        runs=[measure(evidence / name) for name in ['live-astra-expanded-v1', 'live-luna-expanded-v2']]), indent=2))
