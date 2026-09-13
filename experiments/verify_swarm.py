"""Verify saved live swarm evidence without network, inference, or file writes.

The calls file is a JSON list, or {root_call_id, trace_id, calls: [...]}. Export
id, trace_id, parent_id, op_name, started_at, ended_at, exception, inputs, output.
This checks consistency of supplied artifacts, not their cryptographic origin.
"""

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re

from sera.storage import content_hash
from sera.trace_evidence import request_evidence
from sera.diagnosis import trial_diagnosis
from experiments.weave_evidence import IDENTITY_FIELDS, QUERY_IDS, WeaveEvidenceReader


INVESTIGATORS = ('scheduling', 'memory_context', 'output_quality')


def _identity(record):
    return tuple(record.get(key) for key in IDENTITY_FIELDS)


def _op(call):
    return str(call.get('op_name', '')).split('/op/')[-1].split(':')[0]


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _overlap(intervals):
    return (len(intervals) == 3 and all(_finite(a) and _finite(b) and a < b for a, b in intervals)
            and max(a for a, _ in intervals) < min(b for _, b in intervals))


def _timestamp(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    except (ValueError, TypeError, AttributeError):
        return None


def _candidate_count(checks, key):
    return len({content_hash({name: proposal.get(name) for name in ('changed_lever', 'proposed_value')})
        for check in checks if isinstance(proposal := check.get(key), dict)
        and check.get('initial_status' if key == 'initial_proposal' else 'status') == 'accepted'
        and proposal.get('action') == 'trial'})


def _typed_response_matches(actual, expected):
    # Weave adds type/class metadata to saved Pydantic responses, not their fields.
    return isinstance(actual, dict) and isinstance(expected, dict) and all(
        key in actual and actual[key] == value for key, value in expected.items())


def _historical_record_matches(actual, expected):
    """Allow only known additive fields absent from older saved projections."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        optional = {'prompt_tokens'}
        if expected.get('record_type') == 'load_metrics':
            optional.add('input_token_summary')
        if expected.get('source') == 'saved trial request records; also used for optional Weave export':
            optional.add('prepared_prompt_tokens')
        if expected.get('runtime_failure') is None:
            optional.add('runtime_failure')
        return (not actual.keys() - expected.keys() and not expected.keys() - actual.keys() - optional
                and all(_historical_record_matches(value, expected[key]) for key, value in actual.items()))
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(_historical_record_matches(a, b)
                                                   for a, b in zip(actual, expected))
    return actual == expected


class Audit:
    def __init__(self, report, dump):
        self.report = report
        self.issues = []
        self.calls = dump.get('calls', []) if isinstance(dump, dict) else dump
        self.calls = self.calls if isinstance(self.calls, list) else []
        self.calls = [call for call in self.calls if isinstance(call, dict)]
        url_root = str(report.get('weave_url', '')).rstrip('/').split('/')[-1]
        self.root_id = dump.get('root_call_id', url_root) if isinstance(dump, dict) else url_root
        self.by_id = {call.get('id'): call for call in self.calls if isinstance(call.get('id'), str)}
        self.trace_id = (self.by_id.get(self.root_id) or {}).get('trace_id')
        self.declared_trace_id = dump.get('trace_id', self.trace_id) if isinstance(dump, dict) else self.trace_id
        self.normalized_call_references = 0
        self.calls = self.normalize_references(self.calls)
        self.by_id = {call.get('id'): call for call in self.calls if isinstance(call.get('id'), str)}
        self.records = [dict(call_id=call.get('id'), op_name=_op(call), output=call['output'],
                             output_sha256=content_hash(call['output'])) for call in self.calls
                        if _op(call) in ('recorded_model_request', 'recorded_trial_metrics', 'recorded_trial_diagnosis')
                        and isinstance(call.get('output'), dict)]

    def normalize_references(self, value):
        """Resolve only serialized references to known call IDs, never arbitrary text."""
        if isinstance(value, list):
            return [self.normalize_references(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            if key == 'call_id' and isinstance(item, str) and item.startswith('CallRef('):
                match = re.fullmatch(r"CallRef\(entity='([^']+)', project='([^']+)', id='([^']+)', "
                                     r"_extra=\('attr', 'id'\)\)", item)
                source = self.by_id.get(match[3], {}) if match else {}
                valid = (bool(match) and bool(source) and source.get('trace_id') == self.trace_id
                         and str(source.get('op_name', '')).startswith(f'weave:///{match[1]}/{match[2]}/op/'))
                if self.require(valid, 'call-reference', 'Serialized call references must resolve inside this project and trace.'):
                    item = match[3]
                    self.normalized_call_references += 1
            result[key] = self.normalize_references(item)
        return result

    def require(self, condition, check, detail, round_number=None):
        if not condition:
            self.issues.append(dict(check=check, detail=detail, round=round_number))
        return bool(condition)

    def lineage(self):
        root = self.by_id.get(self.root_id, {})
        self.require(bool(root) and _op(root) == 'run_investigation' and bool(self.trace_id)
                     and self.declared_trace_id == self.trace_id,
                     'trace-root', 'A saved run_investigation root is required.')
        self.require(len(self.by_id) == len(self.calls), 'trace-lineage', 'Call IDs must be unique.')
        for call in self.calls:
            seen = set()
            current = call
            while current.get('id') != self.root_id and current.get('id') not in seen:
                seen.add(current.get('id'))
                current = self.by_id.get(current.get('parent_id'), {})
                if not current:
                    break
            self.require(current.get('id') == self.root_id and call.get('trace_id') == self.trace_id,
                         'trace-lineage', f"Call {call.get('id')} is not owned by this trace root.")
            self.require(call.get('exception') is None and bool(call.get('ended_at')),
                         'trace-completion', f"Call {call.get('id')} failed or is incomplete.")

    def matching_calls(self, name, evidence, output):
        return [call for call in self.calls if _op(call) == name and
                (call.get('inputs') or {}).get('evidence') == evidence and
                _typed_response_matches(call.get('output'), output)]

    def inspections(self, check, round_number, expected_scope):
        evidence = check.get('initial_evidence') or {}
        scope = evidence.get('trace_scope') or []
        allowed = {_identity(item) for item in scope if isinstance(item, dict)}
        self.require(len(scope) == len(expected_scope) and allowed == expected_scope,
                     'inspection-scope', 'Every read must use this model, revision and all measured trial configurations.',
                     round_number)
        saved_trials = [self.report.get('baseline') or {}, *self.report.get('search_trials', [])]
        for item in scope:
            trial = next((t for t in saved_trials if
                t.get('source_trial_id', t.get('trial_id')) == item.get('trial_id') and
                t.get('config_hash') == item.get('config_hash')), {})
            quality = trial.get('task_quality') or {}
            self.require(bool(trial) and all((item.get('task_quality') or {}).get(key) == quality[key]
                         for key in ('version', 'floor', 'passed', 'per_prompt') if key in quality),
                         'inspection-scope', 'Scoped local grades must match the saved trial gate.', round_number)
        records = [record for record in self.records if _identity(record['output']) in allowed]
        complete = [item for item in check.get('inspections', []) if item.get('status') == 'complete']
        self.require(bool(complete), 'inspection-provenance',
                     f"{check.get('investigator_id')} has no completed remote inspection.", round_number)
        for item in complete:
            result = item.get('result') or {}
            query = item.get('query_id')
            valid = (result.get('source') == 'weave' and result.get('trace_id') == self.trace_id
                     and query in QUERY_IDS and result.get('query_id') == query and bool(result.get('records'))
                     and (item.get('response') or {}).get('ranked_proposal_ids') == [query])
            try:
                WeaveEvidenceReader._check_visibility(records, scope)
                _, count = WeaveEvidenceReader._select(query, records, scope)
                valid &= (result.get('matched_record_count') == count and
                          result.get('omitted_record_count') == count - len(result.get('records', [])))
                for selected in result.get('records', []):
                    source = next((r for r in records if r['call_id'] == selected.get('call_id')), None)
                    if source is None or source['output_sha256'] != selected.get('output_sha256'):
                        valid = False
                        continue
                    projected, _ = WeaveEvidenceReader._select(query, [source], scope)
                    if query == 'quality_outputs' and self.report.get('evaluation_cases') is not None:
                        # Projection only: this object has no client and cannot issue a query.
                        WeaveEvidenceReader(None, self.trace_id,
                            evaluation_cases=self.report['evaluation_cases'])._attach_task_diagnostics(projected, [source])
                    valid &= any(_historical_record_matches(selected, projection) for projection in projected)
            except (ValueError, TypeError, KeyError, RuntimeError, AttributeError):
                valid = False
            reads = [call for call in self.calls if _op(call) == f'weave_inspect_{query}'
                and call.get('output') == result
                and (supplied := (call.get('inputs') or {}).get('evidence') or {}).get('investigator_id')
                    == check.get('investigator_id')
                and supplied.get('trace_scope') == scope and supplied.get('history') == evidence.get('history')]
            valid &= bool(reads)
            for read in reads:
                supplied = read['inputs']['evidence']
                valid &= bool(self.matching_calls(f"swarm_{check.get('investigator_id')}_inspection",
                                                  supplied, item.get('response')))
            self.require(valid, 'inspection-provenance',
                         f"{check.get('investigator_id')} {query}: query, source IDs, hashes or scope differ.",
                         round_number)

    def round(self, record, expected_scope):
        number = record.get('round')
        checks = record.get('specialists') or []
        self.require(sorted(c.get('investigator_id', '') for c in checks) == sorted(INVESTIGATORS),
                     'three-investigators', 'Exactly three distinct investigators are required.', number)
        board = record.get('shared_findings')
        board_hash = content_hash(board)
        self.require(bool(board) and (record.get('swarm') or {}).get('shared_findings_hash') == board_hash,
                     'shared-board', 'The saved complete board must match its hash.', number)
        self.require(isinstance(board, list) and len(board) == len(checks) and
                     all(any(item.get('investigator_id') == check.get('investigator_id') and
                             item.get('proposal') == check.get('initial_proposal') and
                             item.get('inspections') == check.get('inspections') for item in board)
                         for check in checks),
                     'shared-board', 'The board must contain each actual initial proposal and inspection.', number)
        for phase, label in [('initial', 'proposal'), ('refine', 'peer_review')]:
            timings = [(c.get('phase_timings', {}).get(phase, {}).get('started_monotonic'),
                        c.get('phase_timings', {}).get(phase, {}).get('ended_monotonic')) for c in checks]
            self.require(_overlap(timings), f'{phase}-overlap',
                         'All three recorded worker intervals must overlap.', number)
            intervals = []
            for check in checks:
                evidence_key, proposal_key = (('initial_evidence', 'initial_proposal')
                                              if phase == 'initial' else ('evidence', 'proposal'))
                matches = self.matching_calls(f"swarm_{check.get('investigator_id')}_{label}",
                                               check.get(evidence_key), check.get(proposal_key))
                self.require(len(matches) == 1, 'provider-evidence',
                             f"{check.get('investigator_id')} {phase} needs one exact traced request.", number)
                if len(matches) == 1:
                    intervals.append((_timestamp(matches[0].get('started_at')),
                                      _timestamp(matches[0].get('ended_at'))))
            # Initial includes inspection, so proposal-only spans need not overlap.
            if phase == 'refine':
                self.require(_overlap(intervals), 'refine-trace-overlap',
                             'The actual traced peer-review calls must overlap.', number)
        initial_ends = [c.get('phase_timings', {}).get('initial', {}).get('ended_monotonic') for c in checks]
        refine_starts = [c.get('phase_timings', {}).get('refine', {}).get('started_monotonic') for c in checks]
        self.require(bool(checks) and all(_finite(t) for t in initial_ends + refine_starts)
                     and max(initial_ends) <= min(refine_starts), 'shared-board',
                     'Every initial investigation must finish before refinement starts.', number)
        for check in checks:
            supplied = check.get('evidence') or {}
            self.require(supplied.get('shared_findings') == board and
                         supplied.get('shared_findings_hash') == board_hash,
                         'shared-board', 'Each refinement must receive the same complete board.', number)
            self.inspections(check, number, expected_scope)
        # Independent initial investigations include inspection plus proposal spans.
        initial_intervals = []
        for check in checks:
            role = check.get('investigator_id')
            calls = [call for call in self.calls if _op(call) in
                (f'swarm_{role}_inspection', f'swarm_{role}_proposal') and
                (e := (call.get('inputs') or {}).get('evidence') or {}).get('trace_scope') ==
                    (check.get('initial_evidence') or {}).get('trace_scope') and
                e.get('history') == (check.get('initial_evidence') or {}).get('history')]
            starts = [_timestamp(call.get('started_at')) for call in calls]
            ends = [_timestamp(call.get('ended_at')) for call in calls]
            if starts and all(_finite(t) for t in starts + ends):
                initial_intervals.append((min(starts), max(ends)))
        self.require(_overlap(initial_intervals), 'initial-trace-overlap',
                     'Actual traced initial-investigation intervals must overlap.', number)

    def feedback(self, rounds, trials):
        actual_feedback = False
        measured_feedback = False
        startup_feedback = False
        rejected_reviews = set()
        previous_ids = []
        for record in rounds:
            for check in record.get('specialists', []):
                for key in ('initial_evidence', 'evidence'):
                    evidence = check.get(key) or {}
                    history = evidence.get('history') or []
                    for trial_id in previous_ids:
                        trial = trials.get(trial_id)
                        if trial is None:
                            continue
                        entry = next((h for h in history if (h.get('trial') or {}).get('trial_id') == trial_id), {})
                        copied = entry.get('trial') or {}
                        failed_startup = trial.get('status') == 'startup-failed' and not trial.get('reduced')
                        raw_review = trial.get('review_response')
                        rejected_review = bool(trial.get('review_error') and raw_review and
                            self.matching_calls('frontier_reviewer', trial.get('review_evidence'), raw_review))
                        review_present = bool(trial.get('review')) or rejected_review
                        observed = bool(trial.get('reduced')) or (failed_startup and bool(trial.get('diagnosis')))
                        valid = observed and review_present and all(copied.get(field) == trial.get(field)
                            for field in ('status', 'config_hash', 'reduced', 'task_quality', 'decision', 'failure_stage', 'error'))
                        valid &= (entry.get('configuration') == trial.get('runtime', {}).get('configuration')
                                  and entry.get('review') == trial.get('review')
                                  and entry.get('review_error') == trial.get('review_error')
                                  and _historical_record_matches(entry.get('request_evidence'),
                                      request_evidence(trial, self.report.get('prompts', []))))
                        self.require(valid, 'measured-feedback',
                                     f'{trial_id} actual outcome, available metrics, gate and review disposition must reach every next-round investigator.',
                                     record.get('round'))
                        actual_feedback |= bool(valid)
                        measured_feedback |= bool(valid and trial.get('reduced'))
                        startup_feedback |= bool(valid and failed_startup)
                        if rejected_review:
                            rejected_reviews.add(trial_id)
            previous_ids.extend(record.get('trial_ids', []))
        self.require(actual_feedback, 'measured-feedback', 'An actual trial outcome must feed a later decision round.')
        return dict(observed_trial_feedback=actual_feedback, measured_candidate_feedback=measured_feedback,
                    startup_failure_feedback=startup_feedback, rejected_raw_reviews=sorted(rejected_reviews),
                    limitation='A recorded startup failure is feedback, not a measured quality or performance result. '
                               'Rejected raw reviews are preserved, not relabeled as validated or delivered to later agents.')

    def trials(self, rounds, trials):
        ids = [identifier for row in rounds for identifier in row.get('trial_ids', [])]
        search = self.report.get('search') or {}
        budget = (search.get('budget') or {}).get('max_candidate_trials')
        self.require(all(len(row.get('trial_ids', [])) <= 1 for row in rounds)
                     and 1 <= len(ids) <= 2 and len(set(ids)) == len(ids) and set(ids) == set(trials)
                     and search.get('trials_used') == len(ids) + search.get('initial_trials_used', 0)
                     and type(budget) is int and 1 <= search['trials_used'] <= budget <= 2,
                     'trial-budget', 'One unique candidate per round, at most two, with matching saved trial counts.')
        configs = [trial.get('config_hash') for trial in trials.values()]
        self.require(len(configs) == len(set(configs)) and
                     (self.report.get('baseline') or {}).get('config_hash') not in configs,
                     'trial-budget', 'Candidates must be unique configurations, not baseline replays.')
        for row in rounds:
            for identifier in row.get('trial_ids', []):
                trial = trials.get(identifier) or {}
                scoped = trial.get('arbiter_proposal_id')
                ranked = (row.get('arbiter') or {}).get('ranked_proposal_ids')
                owner = ((row.get('arbiter_evidence') or {}).get('proposal_id_map') or {}).get(scoped, {})
                config = trial.get('runtime', {}).get('configuration', {})
                proposal = trial.get('proposal') or {}
                self.require(bool(scoped) and ranked == [scoped] and bool(owner) and
                             owner.get('investigator_id') == trial.get('investigator_id') and
                             owner.get('original_proposal_id') == proposal.get('proposal_id') and
                             proposal.get('changed_lever') in config and
                             config.get(proposal.get('changed_lever')) == proposal.get('proposed_value') and
                             content_hash(config) == trial.get('config_hash'),
                             'selected-owner', f'{identifier} must belong to the one selected scoped proposal.', row.get('round'))
                metrics = [r for r in self.records if r['op_name'] == 'recorded_trial_metrics'
                    and r['output'].get('trial_id') == identifier and
                    r['output'].get('config_hash') == trial.get('config_hash')]
                if trial.get('status') == 'startup-failed' and not trial.get('reduced'):
                    diagnoses = [r for r in self.records if r['op_name'] == 'recorded_trial_diagnosis'
                        and r['output'].get('trial_id') == identifier and
                        r['output'].get('config_hash') == trial.get('config_hash')]
                    self.require(not metrics and len(diagnoses) == 1 and
                                 diagnoses[0]['output'].get('diagnosis') == trial.get('diagnosis'),
                                 'startup-trial', f'{identifier} needs a persisted startup diagnosis, not invented metrics.')
                else:
                    self.require(len(metrics) == 1 and metrics[0]['output'].get('reduced') == trial.get('reduced'),
                                 'measured-trial', f'{identifier} needs matching persisted trial metrics.')

    def returned(self):
        report = self.report
        probe = report.get('post_return_probe') or {}
        selected = (report.get('decision') or {}).get('selected')
        records = [r['output'] for r in self.records if r['output'].get('phase') == 'post-return-probe'
                   and r['output'].get('trial_id') == selected]
        self.require(report.get('post_return_task_passed') is True and bool(probe.get('token_ids'))
                     and not probe.get('error') and any(r.get('output') == probe.get('text') and
                         r.get('token_ids') == probe.get('token_ids') for r in records),
                     'returned-probe', 'A fresh successful request from the selected runner must be persisted.')
        runtimes = report.get('returned_runtimes') or []
        self.require(report.get('returned_runner_closed') is True and bool(runtimes) and
                     all(r.get('cleanup_pass') is True and r.get('memory_after_mib') == 0 for r in runtimes),
                     'returned-cleanup', 'Every returned runtime must be closed with zero recorded GPU memory.')

    def diagnoses(self, rounds, trials):
        missing = [identifier for identifier, trial in trials.items() if not trial.get('diagnosis')]
        before = len(self.issues)
        for identifier, trial in trials.items():
            diagnosis = trial.get('diagnosis')
            if not diagnosis:
                continue
            expected = trial_diagnosis(self.report.get('baseline') or {}, trial, trial.get('decision') or {})
            identity = (identifier, trial.get('runtime', {}).get('model_id'),
                        trial.get('runtime', {}).get('revision'), trial.get('config_hash'))
            records = [r for r in self.records if r['op_name'] == 'recorded_trial_diagnosis'
                       and _identity(r['output']) == identity]
            valid = (_historical_record_matches(diagnosis, expected) and len(records) == 1 and
                     records[0]['output'].get('diagnosis') == diagnosis and
                     trial.get('review_evidence', {}).get('diagnosis') == diagnosis and
                     trial.get('diagnosis_trace_export', {}).get('status') == 'complete')
            seen = False
            for row in rounds:
                if seen:
                    for check in row.get('specialists', []):
                        for key in ('initial_evidence', 'evidence'):
                            evidence = check.get(key) or {}
                            entry = next((h for h in evidence.get('history', []) if
                                          h.get('trial', {}).get('trial_id') == identifier), {})
                            valid &= entry.get('diagnosis') == diagnosis
                            if diagnosis.get('failure_kind') != 'accepted':
                                valid &= dict(trial_id=identifier, diagnosis=diagnosis) in evidence.get('failure_diagnoses', [])
                seen |= identifier in row.get('trial_ids', [])
            self.require(valid, 'failure-diagnosis',
                         f'{identifier}: deterministic verdict, persisted event, review or later diagnosis evidence differs.')
        return dict(established=bool(trials) and not missing and len(self.issues) == before,
                    missing_trial_ids=missing, root_cause_established=False,
                    scope='Observed failures and consequences only; no model or hardware cause is inferred. '
                          'Matching diagnosis records do not prove the agents understood or used them.')


def verify_swarm(report, calls_dump):
    """Return independent execution, proposal-diversity and performance verdicts."""
    audit = Audit(report, calls_dump)
    rounds = (report.get('search') or {}).get('rounds') or []
    trials = {trial.get('trial_id'): trial for trial in report.get('search_trials', [])}
    audit.require(report.get('provenance') != 'synthetic' and
                  (report.get('provider_validation') or {}).get('provenance') != 'synthetic',
                  'live-provenance', 'Synthetic evidence cannot establish a live swarm.')
    audit.require(report.get('swarm_enabled') is True and len(rounds) >= 2,
                  'two-decision-rounds', 'Two actual swarm decision rounds are required.')
    audit.require(report.get('trace_status') == 'enabled', 'trace-completion', 'Live tracing must be enabled without errors.')
    audit.lineage()
    baseline = report.get('baseline') or {}
    scoped_trials = [baseline]
    for row in rounds:
        expected_scope = {(t.get('source_trial_id', t.get('trial_id')),
            t.get('runtime', {}).get('model_id'), t.get('runtime', {}).get('revision'), t.get('config_hash'))
            for t in scoped_trials}
        audit.round(row, expected_scope)
        scoped_trials.extend(trials[identifier] for identifier in row.get('trial_ids', []) if identifier in trials)
    audit.trials(rounds, trials)
    feedback = audit.feedback(rounds, trials)
    audit.returned()
    diagnosis = audit.diagnoses(rounds, trials)
    priority = (report.get('objective') or {}).get('priority')
    metric = {'latency': 'p95_latency_ms', 'throughput': 'output_tokens_per_second'}.get(priority)
    baseline = (report.get('baseline') or {}).get('reduced', {}).get(metric)
    gains = []
    improved = False
    threshold = (report.get('objective') or {}).get('min_improvement_fraction')
    floor = (report.get('constraints') or {}).get('quality_floor')
    for trial in trials.values():
        value = trial.get('reduced', {}).get(metric)
        if _finite(baseline) and baseline > 0 and _finite(value):
            gain = (value - baseline if priority == 'throughput' else baseline - value) / baseline
            gains.append(gain)
            quality = trial.get('task_quality') or {}
            improved |= (_finite(threshold) and gain >= threshold and quality.get('passed') is True
                         and _finite(floor) and _finite(quality.get('mean')) and quality['mean'] >= floor
                         and trial.get('decision', {}).get('selected') == 'candidate')
    initial = [_candidate_count(row.get('specialists', []), 'initial_proposal') for row in rounds]
    refined = [_candidate_count(row.get('specialists', []), 'proposal') for row in rounds]
    return dict(schema_version='sera-swarm-evidence-verification-v1', execution_passed=not audit.issues,
        issues=audit.issues, decision_rounds=len(rounds), candidate_trials=len(trials),
        saved_profile=dict(model_id=report.get('model_id'), model_revision=report.get('model_revision'),
            evaluation_cases_sha256=report.get('evaluation_cases_sha256'),
            task_count=len(report.get('evaluation_cases') or []), constraints=report.get('constraints'),
            workload=report.get('workload'), baseline_configuration=(report.get('baseline') or {}).get(
                'runtime', {}).get('configuration')),
        source_hashes=dict(result=content_hash(report), calls=content_hash(calls_dump)),
        root_call_id=audit.root_id, trace_id=audit.trace_id,
        normalized_call_references=audit.normalized_call_references,
        feedback=feedback,
        failure_diagnosis=diagnosis,
        proposal_diversity=dict(initial_distinct_candidates=initial, refined_distinct_candidates=refined,
            initial_alternatives_observed=any(n > 1 for n in initial),
            refined_alternatives_observed=any(n > 1 for n in refined)),
        improvement=dict(priority=priority, required_gain_fraction=threshold,
            best_observed_gain_fraction=max(gains) if gains else None,
            established=bool(improved) and not audit.issues),
        limitations=['Consistency audit of supplied artifacts, not cryptographic proof of origin.',
            'The saved profile is reported, not certification against an external benchmark or hardware profile.',
            'No search-superiority or failure-cause claim follows from execution or proposal diversity.',
            'Cached inspections retain remote source provenance; they are not fresh network requests.'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--calls', type=Path, required=True)
    args = parser.parse_args(argv)
    result = verify_swarm(json.loads(args.result.read_text()), json.loads(args.calls.read_text()))
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['execution_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
