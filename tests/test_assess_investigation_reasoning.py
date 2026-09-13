from copy import deepcopy
import json
from pathlib import Path

from experiments.assess_investigation_reasoning import assess


def fixture(reason='The workload uses ~2265 input tokens per request.'):
    evidence = {'remaining_trials': 1, 'supported_changes': {'max_num_batched_tokens': [2048]}}
    proposal = {'action': 'trial', 'changed_lever': 'max_num_batched_tokens',
                'proposed_value': 2048, 'reason': reason}
    report = {'rounds': [{'round': 1, 'specialists': [{'investigator_id': 'scheduling',
        'initial_evidence': evidence, 'evidence': evidence, 'initial_proposal': proposal,
        'proposal': proposal}]}]}
    source = {'baseline': {'input_token_ids': [[1] * 85, [1] * 109]}}
    return report, source


def test_exact_affirmative_unit_contradiction_is_flagged():
    report, source = fixture()
    result = assess(report, source)
    assert result['deterministic_status'] == 'failed'
    assert result['panels'][0]['violations'][0]['kind'] == 'input-token-unit'
    assert result['facts']['prepared_prompt_tokens']['maximum'] == 109
    assert result['semantic_status'] == 'unverified'


def test_negation_quotation_and_hypothesis_do_not_become_automatic_failures():
    for reason in ('The workload does not use 2265 input tokens per request.',
                   'The prior claim "the workload uses 2265 input tokens per request" is wrong.',
                   'If the workload uses 2265 input tokens per request, inspect it.',
                   'The workload uses 2265 input tokens per request is false.',
                   'No OOM is established; the observed CUTLASS error has unknown cause.'):
        report, source = fixture(reason)
        result = assess(report, source)
        assert result['deterministic_status'] == 'no-detected-contradiction'
        assert result['semantic_status'] == 'unverified'


def test_legal_action_and_zero_budget_are_independent_of_prose():
    report, source = fixture('There is no observed OOM.')
    specialist = report['rounds'][0]['specialists'][0]
    specialist['evidence'] = {'remaining_trials': 0, 'supported_changes': {}}
    specialist['proposal'] = dict(specialist['proposal'], changed_lever='kv_cache_dtype', proposed_value='fp8')
    violations = assess(report, source)['panels'][1]['violations']
    assert {v['kind'] for v in violations} == {'unavailable-action', 'exhausted-budget'}


def test_missing_or_malformed_facts_are_not_invented():
    report, _ = fixture()
    result = assess(report, {'baseline': {'input_token_ids': [[], ['bad']]}})
    assert result['facts']['prepared_prompt_tokens'] is None
    assert result['deterministic_status'] == 'no-detected-contradiction'
    assert result['semantic_status'] == 'unverified'


def test_source_objective_math_excludes_startup_zeros_and_explains_threshold():
    report, source = fixture('Use the measured values.')
    source['objective'] = {'priority': 'latency', 'min_improvement_fraction': .05}
    source['baseline']['reduced'] = {'p95_latency_ms': 100.0}
    source['search_trials'] = [
        {'trial_id': 'failed', 'status': 'startup-failed', 'reduced': {'p95_latency_ms': 0},
         'task_quality': {'mean': 0, 'passed': False}},
        {'trial_id': 'measured', 'status': 'collected', 'reduced': {'p95_latency_ms': 99.0},
         'task_quality': {'mean': 1, 'passed': True}}]
    facts = assess(report, source)['facts']['source_trials']
    assert facts[0]['task_quality'] is None
    assert facts[0]['objective']['candidate_value'] is None
    assert facts[1]['objective']['improvement_fraction'] == .01
    assert facts[1]['objective']['meets_threshold'] is False
    assert facts[1]['task_quality']['passed'] is True


def test_shared_board_panel_is_bounded_and_arbiter_attempt_is_found():
    report, source = fixture('Keep the baseline.')
    specialist = report['rounds'][0]['specialists'][0]
    specialist['evidence'] = dict(specialist['evidence'], shared_findings=[{
        'investigator_id': 'peer', 'proposal': {'action': 'abstain', 'reason': 'No measured support.'},
        'inspections': [{'result': {'large': 'x' * 10000}}]}])
    report['rounds'][0].update(arbiter={'ranked_proposal_ids': []}, arbiter_evidence={'remaining_trials': 0})
    report['agent_calls'] = [{'role': 'arbiter', 'evidence': {'remaining_trials': 0},
        'attempts': [{'raw_response': {'id': 'arbiter-1', 'choices': [{'message': {'content': '{}'}}]}}]}]
    panels = assess(report, source)['panels']
    assert 'inspections' not in panels[1]['shared_findings'][0]
    assert panels[-1]['provider_attempts'][0]['provider_id'] == 'arbiter-1'


def test_inspection_decisions_remain_available_for_manual_failure_review():
    report, source = fixture('Inspect the actual record.')
    report['rounds'][0]['specialists'][0]['inspections'] = [{
        'query_id': 'load_metrics', 'status': 'complete',
        'response': {'reason': 'The observed CUTLASS signature does not establish OOM.'},
        'result': {'large': 'x' * 10000}}]
    inspection = assess(report, source)['panels'][0]['inspection_decisions'][0]
    assert inspection['response']['reason'].startswith('The observed CUTLASS')
    assert 'result' not in inspection


def test_assessment_preserves_input_and_keeps_provider_reasoning_separate():
    report, source = fixture('Inspect the actual record.')
    evidence = report['rounds'][0]['specialists'][0]['initial_evidence']
    report['agent_calls'] = [{'investigator_id': 'scheduling', 'evidence': evidence,
        'attempts': [{'raw_response': {'id': 'provider-1', 'choices': [{'message': {
            'content': '{"reason":"Inspect the actual record."}', 'reasoning': 'Hidden analysis'}}]}}]}]
    before = deepcopy(report)
    result = assess(report, source)
    assert report == before
    assert result['panels'][0]['provider_attempts'][0]['reasoning'] == 'Hidden analysis'
    assert result['semantic_status'] == 'unverified'


def test_saved_replays_keep_real_factual_failures_and_do_not_claim_semantic_pass():
    root = Path(__file__).resolve().parents[1]
    source = json.loads((root / 'evidence/live-swarm-investigation-v1/result.json').read_text())
    for version in ('v1', 'v2'):
        report = json.loads((root / f'evidence/failure-replay-{version}/result.json').read_text())
        result = assess(report, source)
        assert result['semantic_status'] == 'unverified'
        assert result['deterministic_status'] == 'failed'
        refined = [p for p in result['panels'] if p['phase'] == 'refined']
        assert len(refined) == 6
        assert any(v['kind'] == 'input-token-unit' for p in refined for v in p['violations'])
        if version == 'v2':
            assert all(any(v['kind'] == 'exhausted-budget' for v in p['violations'])
                       for p in refined if p['round'] == 2)
