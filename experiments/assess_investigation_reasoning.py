"""Read-only reasoning review panels. No model calls and no automatic semantic pass.

Run: python -m experiments.assess_investigation_reasoning --report result.json
     --source-report ORIGINAL/result.json [--calls weave-calls.json]
The command prints JSON. It does not change the source files.
"""

import argparse
import hashlib
import json
import math
import re


RUBRIC = [
    {'id': 'units', 'question': 'Does the response distinguish total load tokens from tokens per request, using the supplied count and prompt lengths?'},
    {'id': 'startup', 'question': 'Does it distinguish the observed startup signature from an unknown root cause, without reporting missing outputs as measured model accuracy?'},
    {'id': 'objective', 'question': 'Does it distinguish passing task quality from missing the objective threshold, using the actual baseline and candidate values?'},
    {'id': 'legal-action', 'question': 'Is the proposed action available, untested, and within the current budget? Does zero budget cause abstention?'},
    {'id': 'causality', 'question': 'Are memory pressure, KV allocation changes, precision effects, and speed gains identified as hypotheses unless measured?'},
    {'id': 'peer-revision', 'question': 'Does refinement identify the peer evidence that changed or confirmed the initial view, rather than copy an unsupported assertion?'},
    {'id': 'failure-feedback', 'question': 'Does the next round use the actual revealed failure or measured outcome without claiming a new trial was executed in this replay?'},
]


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _prompt_facts(source):
    rows = (source.get('baseline') or {}).get('input_token_ids')
    if not isinstance(rows, list) or not rows or any(
        not isinstance(row, list) or not row or any(type(t) is not int or t < 0 for t in row)
        for row in rows
    ):
        return None
    lengths = [len(row) for row in rows]
    return dict(source_path='source_report.baseline.input_token_ids', unit='tokens per prepared prompt',
                count=len(rows), minimum=min(lengths), maximum=max(lengths), mean=sum(lengths)/len(lengths))


def _numeric_claims(reason):
    """Extract only two explicit affirmative forms; all other prose needs review."""
    pattern = re.compile(r'(?:the workload uses(?: only)?\s*[~≈]?|would truncate the\s+)'
                         r'((?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?)\s+input tokens per request', re.I)
    for sentence in re.split(r'(?<=[.!?])\s+', reason):
        if re.search(r'\b(?:not|incorrect|wrong|false|unsupported|claim|if|unless|hypothetical)\b|["“”]', sentence, re.I):
            continue
        for match in pattern.finditer(sentence):
            yield dict(value=float(match[1].replace(',', '')), quote=match[0])


def _violations(proposal, evidence, facts):
    violations = []
    if proposal.get('action') == 'trial':
        allowed = evidence.get('supported_changes')
        if isinstance(allowed, dict) and proposal.get('proposed_value') not in allowed.get(proposal.get('changed_lever'), []):
            violations.append(dict(kind='unavailable-action', lever=proposal.get('changed_lever'),
                                   value=proposal.get('proposed_value'), source_path='evidence.supported_changes'))
        remaining = evidence.get('remaining_trials')
        if type(remaining) is int and remaining <= 0:
            violations.append(dict(kind='exhausted-budget', remaining_trials=remaining,
                                   source_path='evidence.remaining_trials'))
    if facts:
        for claim in _numeric_claims(proposal.get('reason') or ''):
            if claim['value'] > facts['maximum'] or claim['value'] < facts['minimum']:
                violations.append(dict(kind='input-token-unit', claim=claim,
                                       expected_range=[facts['minimum'], facts['maximum']],
                                       source_path=facts['source_path']))
    return violations


def _provider_attempts(report, evidence, investigator, calls):
    attempts = []
    for record in report.get('agent_calls', []):
        owner = record.get('investigator_id') or record.get('role')
        if record.get('evidence') != evidence or owner != investigator:
            continue
        for attempt in record.get('attempts', []):
            raw = attempt.get('raw_response') or {}
            choices = raw.get('choices') or []
            message = choices[0].get('message', {}) if choices else {}
            matches = [call for call in calls if isinstance(call.get('output'), dict)
                       and raw.get('id') and call['output'].get('id') == raw['id']]
            attempts.append(dict(provider_id=raw.get('id'), content=message.get('content'),
                                 reasoning=message.get('reasoning'), schema_valid=attempt.get('schema_valid'),
                                 persisted_call_ids=[call.get('id') for call in matches]))
    return attempts


def _objective(source, trial):
    objective = source.get('objective') or {}
    priority = objective.get('priority')
    metric = {'latency': 'p95_latency_ms', 'throughput': 'output_tokens_per_second'}.get(priority)
    baseline = ((source.get('baseline') or {}).get('reduced') or {}).get(metric)
    candidate = (trial.get('reduced') or {}).get(metric) if trial.get('status') == 'collected' else None
    required = objective.get('min_improvement_fraction')
    valid = lambda x: type(x) in (int, float) and math.isfinite(x)
    gain = None
    if valid(baseline) and baseline > 0 and valid(candidate):
        gain = (baseline-candidate)/baseline if priority == 'latency' else (candidate-baseline)/baseline
    return dict(priority=priority, metric=metric, baseline_value=baseline, candidate_value=candidate,
                improvement_fraction=gain, required_improvement_fraction=required,
                meets_threshold=gain >= required if gain is not None and valid(required) else None,
                source_paths=['source_report.baseline.reduced', 'source_report.search_trials[].reduced'])


def _facts(source):
    trials = []
    for trial in source.get('search_trials', []):
        diagnosis = trial.get('diagnosis') or {}
        observed = diagnosis.get('observed') or {}
        decision = trial.get('decision') or {}
        measured = trial.get('status') == 'collected'
        trials.append(dict(trial_id=trial.get('trial_id'), status=trial.get('status'),
            task_quality=trial.get('task_quality') if measured else None,
            selection_reason=decision.get('selection_reason') or trial.get('selection_reason'),
            observed_failure=observed.get('runtime_failure') or (trial.get('runtime') or {}).get('startup_failure'),
            measured_quality_available=measured, objective=_objective(source, trial),
            root_cause=diagnosis.get('root_cause') or {'status': 'not-established-in-source'}))
    return dict(prepared_prompt_tokens=_prompt_facts(source), source_trials=trials,
                objective=source.get('objective'), constraints=source.get('constraints'))


def assess(report, source=None, calls=None):
    """Produce review material, not a model-generated or keyword-based semantic grade."""
    source = source or {}
    calls = calls.get('calls', []) if isinstance(calls, dict) else calls or []
    facts = _facts(source)
    panels = []
    rounds = report.get('rounds', (report.get('search') or {}).get('rounds', []))
    for row in rounds:
        entries = [(s, phase, evidence_key, proposal_key) for s in row.get('specialists', [])
                   for phase, evidence_key, proposal_key in (
                       ('initial', 'initial_evidence', 'initial_proposal'), ('refined', 'evidence', 'proposal'))]
        if row.get('arbiter'):
            entries.append((dict(investigator_id='arbiter', evidence=row.get('arbiter_evidence', {}),
                                 proposal=row['arbiter']), 'arbiter', 'evidence', 'proposal'))
        for entry, phase, evidence_key, proposal_key in entries:
            evidence = entry.get(evidence_key) or {}
            proposal = entry.get(proposal_key) or {}
            panels.append(dict(round=row.get('round'), investigator=entry.get('investigator_id'), phase=phase,
                proposal=proposal, initial_proposal=entry.get('initial_proposal') if phase == 'refined' else None,
                evidence_sha256=_hash(evidence), remaining_trials=evidence.get('remaining_trials'),
                supported_changes=evidence.get('supported_changes'), legal_proposal_ids=evidence.get('legal_proposal_ids'),
                supplied_prompt_summary=(evidence.get('request_evidence') or {}).get('prepared_prompt_tokens'),
                observed_failures=evidence.get('failure_diagnoses'),
                inspection_decisions=[{key: item.get(key) for key in ('query_id', 'status', 'response', 'error')}
                                      for item in entry.get('inspections', [])] if phase == 'initial' else [],
                shared_findings=[dict(investigator_id=f.get('investigator_id'), proposal=f.get('proposal'))
                                 for f in evidence.get('shared_findings', [])],
                provider_attempts=_provider_attempts(report, evidence, entry.get('investigator_id'), calls),
                violations=_violations(proposal, evidence, facts['prepared_prompt_tokens']),
                manual_review={item['id']: 'unverified' for item in RUBRIC}))
    return dict(schema_version='sera-reasoning-assessment-v1', semantic_status='unverified',
                deterministic_status='failed' if any(p['violations'] for p in panels) else 'no-detected-contradiction',
                limitations=['No detected contradiction is not a semantic pass.',
                             'Numeric extraction covers only explicit affirmative forms; other prose requires review.',
                             'Source facts are review inputs, not new GPU measurements. Call IDs are references, not a trace-integrity audit.'],
                facts=facts, rubric=RUBRIC, panels=panels)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True)
    parser.add_argument('--source-report')
    parser.add_argument('--calls')
    args = parser.parse_args(argv)
    def read(path):
        if path is None:
            return None
        with open(path) as stream:
            return json.load(stream)
    result = assess(read(args.report), read(args.source_report), read(args.calls))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
