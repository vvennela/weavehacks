"""Offline, explicitly synthetic fixtures test evidence checks, not model performance."""

from copy import deepcopy
import json

import pytest

from sera.storage import content_hash
from sera.trace_evidence import request_evidence
from experiments.verify_swarm import verify_swarm, main


ROLES = ('scheduling', 'memory_context', 'output_quality')


def fixture(with_diagnosis=False, query='load_metrics', task_diagnostics=False):
    calls = []

    def call(name, inputs, output, parent='root', start=0, end=100):
        identifier = 'root' if not calls else f'call-{len(calls)}'
        calls.append(dict(id=identifier, trace_id='trace', parent_id=parent,
            op_name=f'weave:///entity/project/op/{name}:version', inputs=deepcopy(inputs),
            output=deepcopy(output), exception=None,
            started_at=f'2026-09-13T00:{start // 60:02d}:{start % 60:02d}+00:00',
            ended_at=f'2026-09-13T00:{end // 60:02d}:{end % 60:02d}+00:00'))
        return identifier

    call('run_investigation', {}, {}, parent=None)
    trials = []
    records = []
    for index, identifier in enumerate(('baseline', 'trial-1')):
        config = {'max_num_batched_tokens': 4096 if index == 0 else 2048}
        trial = dict(trial_id=identifier, status='collected', config_hash=content_hash(config),
            runtime=dict(model_id='model', revision='revision', configuration=config),
            reduced={'request_count': 1, 'p95_latency_ms': 100 - index}, quality=[],
            requests=[], loads=[], self_check=[],
            task_quality={'passed': True, 'mean': 1, 'floor': .99, 'per_prompt': []},
            decision={'selected': 'baseline', 'outcome': 'no-safe-improvement'},
            review={'prediction_outcome': 'refuted', 'selected_trial_id': 'baseline'})
        trials.append(trial)
        identity = {key: trial.get(key, trial['runtime'].get(key))
                    for key in ('trial_id', 'model_id', 'revision', 'config_hash')}
        metric = identity | dict(reduced=trial['reduced'], loads=[dict(concurrency=1,
            reduced=trial['reduced'])], quality_requests=1, self_check_requests=0)
        for name, payload in [('recorded_trial_metrics', metric), ('recorded_model_request',
                identity | dict(phase='measured', latency_ms=100, output='answer')),
                ('recorded_model_request', identity | dict(phase='quality', prompt_index=0,
                    input='question', output='answer', latency_ms=100))]:
            cid = call(name, {'record': payload}, payload)
            records.append(dict(call_id=cid, op_name=name, output=payload,
                                output_sha256=content_hash(payload)))
        if index and with_diagnosis:
            from sera.diagnosis import trial_diagnosis
            trial['diagnosis'] = trial_diagnosis(trials[0], trial, trial['decision'])
            trial['review_evidence'] = dict(diagnosis=deepcopy(trial['diagnosis']))
            trial['diagnosis_trace_export'] = dict(status='complete')
            payload = identity | dict(diagnosis=trial['diagnosis'])
            cid = call('recorded_trial_diagnosis', {}, payload)
            records.append(dict(call_id=cid, op_name='recorded_trial_diagnosis', output=payload,
                                output_sha256=content_hash(payload)))
    report = dict(status='closed', provenance='live', swarm_enabled=True, baseline=trials[0],
        search_trials=[trials[1]], prompts=['question'], objective=dict(priority='latency',
        min_improvement_fraction=.05), constraints=dict(quality_floor=.99),
        search=dict(rounds=[], trials_used=1, initial_trials_used=0,
                    budget=dict(max_candidate_trials=2)),
        decision=dict(selected='baseline', outcome='no-safe-improvement'), trace_status='enabled',
        post_return_task_passed=True, post_return_probe=dict(text='answer', token_ids=[1]),
        returned_runner_closed=True, returned_runtimes=[dict(cleanup_pass=True, memory_after_mib=0)],
        weave_url='https://wandb.ai/entity/project/r/call/root')
    from experiments.weave_evidence import WeaveEvidenceReader
    if task_diagnostics:
        report['evaluation_cases'] = [dict(id='fixture', prompt='question', expected=5)]
    for round_index in range(2):
        scope = [dict(trial_id=t['trial_id'], model_id='model', revision='revision',
                      config_hash=t['config_hash'], task_quality=t['task_quality'])
                 for t in trials[:round_index + 1]]
        history = [] if round_index == 0 else [dict(trial={key: deepcopy(trials[1][key]) for key in
            ('trial_id', 'status', 'config_hash', 'reduced', 'task_quality', 'decision')},
            configuration=trials[1]['runtime']['configuration'], review=trials[1]['review'],
            request_evidence=request_evidence(trials[1], report['prompts']))]
        if with_diagnosis and history:
            history[0]['diagnosis'] = deepcopy(trials[1]['diagnosis'])
        row = dict(round=round_index + 1, trial_ids=['trial-1'] if round_index == 0 else [],
                   specialists=[], swarm=dict(enabled=True))
        for role_index, role in enumerate(ROLES):
            matching = [r for r in records if r['output']['trial_id'] in {s['trial_id'] for s in scope}]
            selected, count = WeaveEvidenceReader._select(query, matching, scope)
            if task_diagnostics and query == 'quality_outputs':
                WeaveEvidenceReader(None, 'trace', evaluation_cases=report['evaluation_cases'])._attach_task_diagnostics(
                    selected, matching)
            result = dict(source='weave', trace_id='trace', query_id=query, records=selected,
                matched_record_count=count, omitted_record_count=count-len(selected),
                cache_status='miss' if role_index == 0 else 'hit',
                visibility='complete-for-declared-request-counts')
            common = dict(investigator_id=role, trace_scope=scope, history=history)
            if with_diagnosis:
                common['failure_diagnoses'] = [] if not round_index else [dict(
                    trial_id='trial-1', diagnosis=deepcopy(trials[1]['diagnosis']))]
            inspect_evidence = common | dict(swarm_phase='inspect')
            inspection = dict(status='complete', query_id=query, result=result,
                              response=dict(ranked_proposal_ids=[query], reason='Inspect'))
            parent = call(f'swarm_{role}_inspection', dict(evidence=inspect_evidence),
                          inspection['response'], start=10 + 30*round_index, end=14 + 30*round_index)
            call(f'weave_inspect_{query}', dict(evidence=inspect_evidence), result,
                 start=15 + 30*round_index, end=16 + 30*round_index)
            proposal = dict(action='trial' if round_index == 0 else 'keep-baseline',
                agent_role='batching', changed_lever='max_num_batched_tokens', proposed_value=2048 + role_index,
                proposal_id=role, reason='Synthetic fixture')
            initial = common | dict(swarm_phase='propose', inspections=[inspection])
            call(f'swarm_{role}_proposal', dict(evidence=initial), proposal,
                 start=17 + 30*round_index, end=20 + 30*round_index)
            check = dict(investigator_id=role, initial_evidence=initial,
                initial_proposal=proposal, proposal=proposal, initial_status='accepted',
                status='accepted' if round_index == 0 else 'abstained', inspections=[inspection],
                phase_timings={phase: dict(started_monotonic=a + round_index*30,
                    ended_monotonic=b + round_index*30) for phase, a, b in
                    [('initial', 10 + role_index, 20 + role_index), ('refine', 25 + role_index, 29 + role_index)]})
            row['specialists'].append(check)
        board = [dict(investigator_id=c['investigator_id'], proposal=c['initial_proposal'],
                      inspections=c['inspections']) for c in row['specialists']]
        row['shared_findings'] = board
        row['swarm']['shared_findings_hash'] = content_hash(board)
        for c in row['specialists']:
            c['evidence'] = {k: deepcopy(v) for k, v in c['initial_evidence'].items()}
            c['evidence'].update(swarm_phase='refine', shared_findings=board,
                                shared_findings_hash=content_hash(board))
            call(f"swarm_{c['investigator_id']}_peer_review", dict(evidence=c['evidence']),
                 c['proposal'], start=25 + 30*round_index, end=29 + 30*round_index)
        row['arbiter'] = dict(ranked_proposal_ids=['scheduling:scheduling'] if round_index == 0 else [])
        row['arbiter_evidence'] = dict(proposal_id_map={'scheduling:scheduling':
            dict(investigator_id='scheduling', original_proposal_id='scheduling')})
        report['search']['rounds'].append(row)
    trials[1].update(investigator_id='scheduling', arbiter_proposal_id='scheduling:scheduling',
                     proposal=report['search']['rounds'][0]['specialists'][0]['proposal'])
    call('recorded_model_request', {}, dict(trial_id='baseline', model_id='model',
         revision='revision', config_hash=trials[0]['config_hash'], phase='post-return-probe',
         output='answer', token_ids=[1]))
    calls[0]['output'] = deepcopy(report)
    return report, dict(root_call_id='root', trace_id='trace', calls=calls)


def test_live_shaped_execution_does_not_require_gain_or_final_disagreement():
    report, dump = fixture()
    result = verify_swarm(report, dump)
    assert result['execution_passed'] is True, result['issues']
    assert result['proposal_diversity']['initial_distinct_candidates'] == [3, 0]
    assert result['improvement']['established'] is False
    assert result['improvement']['best_observed_gain_fraction'] == pytest.approx(.01)
    assert result['source_hashes']['result'] == content_hash(report)


@pytest.mark.parametrize('query', ['latency_outliers', 'quality_outputs'])
def test_bounded_request_queries_are_verified_against_original_output_hashes(query):
    report, dump = fixture(with_diagnosis=True, query=query)
    result = verify_swarm(report, dump)
    assert result['execution_passed'], result['issues']


def test_fixed_task_diagnostics_bind_to_the_saved_question_and_answer_key():
    report, dump = fixture(query='quality_outputs', task_diagnostics=True)
    result = verify_swarm(report, dump)
    assert result['execution_passed'], result['issues']
    report['evaluation_cases'][0]['expected'] = 'changed answer'
    result = verify_swarm(report, dump)
    assert result['execution_passed'] is False
    assert any(issue['check'] == 'inspection-provenance' for issue in result['issues'])


@pytest.mark.parametrize('damage, expected', [
    (lambda r,d: r['search']['rounds'].pop(), 'two-decision-rounds'),
    (lambda r,d: r['search']['rounds'][0]['specialists'][0]['phase_timings']['initial'].update(
        ended_monotonic=10), 'initial-overlap'),
    (lambda r,d: r['search']['rounds'][0]['specialists'][0]['evidence'].update(
        shared_findings_hash='wrong'), 'shared-board'),
    (lambda r,d: r['search']['rounds'][1]['specialists'][0]['initial_evidence'].update(history=[]),
        'measured-feedback'),
    (lambda r,d: d['calls'][1]['output'].update(config_hash='another-run'), 'inspection-provenance'),
    (lambda r,d: d['calls'][1].update(parent_id='not-this-root'), 'trace-lineage'),
    (lambda r,d: r['search']['rounds'][0].update(trial_ids=['trial-1','trial-2']), 'trial-budget'),
    (lambda r,d: r['search']['budget'].update(max_candidate_trials=0), 'trial-budget'),
    (lambda r,d: r['search_trials'][0].update(investigator_id='output_quality'), 'selected-owner'),
    (lambda r,d: r['returned_runtimes'][0].update(memory_after_mib=100), 'returned-cleanup'),
    (lambda r,d: r['post_return_probe'].update(token_ids=[]), 'returned-probe'),
    (lambda r,d: r.update(provenance='synthetic'), 'live-provenance'),
    (lambda r,d: r['search']['rounds'][1]['specialists'][0]['initial_evidence'].update(trace_scope=[]),
        'inspection-scope'),
    (lambda r,d: r['search_trials'][0].update(review=None), 'measured-feedback'),
    (lambda r,d: r['search_trials'][0]['runtime']['configuration'].update(max_num_batched_tokens=1024),
        'selected-owner'),
])
def test_tampered_or_incomplete_evidence_fails(damage, expected):
    report, dump = fixture()
    damage(report, dump)
    result = verify_swarm(report, dump)
    assert result['execution_passed'] is False
    assert expected in {issue['check'] for issue in result['issues']}


def test_missing_data_reports_failure_instead_of_crashing():
    result = verify_swarm({}, [])
    assert result['execution_passed'] is False
    assert result['issues']


def test_typed_weave_metadata_is_not_a_response_mismatch():
    report, dump = fixture()
    for call in dump['calls']:
        if '/op/swarm_' in call['op_name']:
            call['output'].update(_type='Proposal', _class_name='Proposal')
    result = verify_swarm(report, dump)
    assert result['execution_passed'], result['issues']


def test_local_overlap_alone_does_not_establish_concurrent_live_requests():
    report, dump = fixture()
    for index, call in enumerate(c for c in dump['calls'] if '_peer_review:' in c['op_name']):
        call['started_at'] = f'2026-09-13T01:{index:02d}:00+00:00'
        call['ended_at'] = f'2026-09-13T01:{index:02d}:30+00:00'
    result = verify_swarm(report, dump)
    assert result['execution_passed'] is False
    assert any(issue['check'] == 'refine-trace-overlap' for issue in result['issues'])


def test_diagnosis_is_verified_separately_and_does_not_claim_root_cause():
    report, dump = fixture(with_diagnosis=True)
    result = verify_swarm(report, dump)
    assert result['execution_passed'], result['issues']
    assert result['failure_diagnosis']['established'] is True
    assert result['failure_diagnosis']['root_cause_established'] is False
    report['search_trials'][0]['diagnosis']['failure_kind'] = 'invented-cause'
    result = verify_swarm(report, dump)
    assert result['execution_passed'] is False
    assert any(issue['check'] == 'failure-diagnosis' for issue in result['issues'])


def test_missing_diagnosis_is_not_mistaken_for_failure_analysis():
    report, dump = fixture()
    result = verify_swarm(report, dump)
    assert result['execution_passed'] is True
    assert result['failure_diagnosis']['established'] is False


def test_claimed_gain_without_the_required_measured_gain_is_not_established():
    report, dump = fixture()
    report['search_trials'][0]['decision']['selected'] = 'candidate'
    result = verify_swarm(report, dump)
    assert result['improvement']['established'] is False


def test_read_only_cli_prints_json_and_uses_nonzero_exit_for_failed_acceptance(tmp_path, capsys, monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('No network permitted'))
    report, dump = fixture()
    result_path, calls_path = tmp_path/'result.json', tmp_path/'calls.json'
    result_path.write_text(json.dumps(report))
    calls_path.write_text(json.dumps(dump))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert main(['--result', str(result_path), '--calls', str(calls_path)]) == 0
    assert json.loads(capsys.readouterr().out)['execution_passed'] is True
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    result_path.write_text('{}')
    assert main(['--result', str(result_path), '--calls', str(calls_path)]) == 1
    assert json.loads(capsys.readouterr().out)['execution_passed'] is False
