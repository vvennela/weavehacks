from sera.investigation_report import render_investigation


def test_report_shows_rejected_and_abstained_proposals_without_inventing_history():
    report = {
        'status': 'ready', 'decision': {'selected': 'baseline'},
        'search': {'trials_used': 0, 'budget': {'max_candidate_trials': 2},
                   'stop_reason': 'no-valid-selected-proposal', 'rounds': [
            {'round': 1, 'trial_ids': [], 'specialists': [
                {'role': 'quantization', 'status': 'rejected', 'error': 'ValueError'},
                {'role': 'batching', 'status': 'abstained', 'proposal': {
                    'proposal_id': 'batch', 'action': 'keep-baseline',
                    'reason': 'Queue evidence is absent', 'predicted_metric_change': 'No supported gain',
                    'falsification_condition': 'New queue measurements', 'evidence_used': ['p95_latency_ms']}}
            ]}]}, 'search_trials': []}
    text = render_investigation(report)
    assert 'quantization: rejected' in text
    assert 'ValueError' in text
    assert 'batching: abstained' in text
    assert 'Queue evidence is absent' in text
    assert 'No supported gain' in text
    assert 'History supplied: not recorded' in text
    assert 'Final selection: baseline' in text
    assert 'search advantage' in text


def test_report_handles_unfinished_trials_and_missing_optional_fields():
    report = {'search': {'rounds': [{'round': 2, 'trial_ids': ['trial-1'],
        'specialists': [], 'arbiter_error': 'TimeoutError'}]},
        'search_trials': [{'trial_id': 'trial-1', 'status': 'starting'}]}
    text = render_investigation(report)
    assert 'starting' in text
    assert 'Quality gate: not recorded' in text
    assert 'TimeoutError' in text
    assert 'Final selection: not recorded' in text
    assert 'p95: not recorded' in text


def test_non_investigation_report_returns_empty_section():
    assert render_investigation({'status': 'ready'}) == ''


def test_unfinished_synthetic_run_is_labeled_before_final_provenance_is_added():
    report = {'status': 'failed', 'provider_validation': {'provenance': 'synthetic'},
              'search': {'rounds': []}}
    text = render_investigation(report)
    assert 'SYNTHETIC offline rehearsal' in text
    assert 'This is not measured model performance' in text


def test_report_links_scoped_arbitration_id_to_original_proposal():
    report = {'search': {'rounds': [{'round': 1, 'specialists': [
        {'role': 'batching', 'status': 'accepted', 'arbiter_proposal_id': 'batching:one',
         'proposal': {'proposal_id': 'one', 'parent_trial_id': 'baseline'}}],
        'arbiter': {'ranked_proposal_ids': ['batching:one'], 'reason': 'Observed queue delay'}}]}}
    text = render_investigation(report)
    assert 'Proposal one' in text
    assert 'Arbitration ID: batching:one' in text
    assert 'Parent trial: baseline' in text
    assert 'Arbiter chose: batching:one' in text


def test_batching_only_report_shows_values_feedback_and_declined_unrun_proposal():
    report = {'search': {'rounds': [
        {'round': 1, 'specialists': [{'role': 'batching', 'status': 'accepted',
            'proposal': {'proposed_value': 2048}, 'evidence': {'history': []}}],
         'trial_ids': ['trial-1'], 'arbiter': {'ranked_proposal_ids': ['batching:first']}},
        {'round': 2, 'specialists': [{'role': 'batching', 'status': 'accepted',
            'proposal': {'proposed_value': 1024, 'evidence_used': ['trial_1_p95_latency_ms']},
            'evidence': {'metrics': {'trial_1_p95_latency_ms': 773.44},
                         'history': [{'trial': {'trial_id': 'trial-1', 'task_quality': {'passed': True}},
                                      'review': {'prediction_outcome': 'refuted'}}]}}],
         'trial_ids': [], 'arbiter': {'ranked_proposal_ids': [], 'reason': 'Earlier gain was too small'}}]},
        'search_trials': [{'trial_id': 'trial-1', 'status': 'collected'}]}
    text = render_investigation(report)
    assert 'batching-only, not a full specialist swarm' in text
    assert 'trial_1_p95_latency_ms=773.44' in text
    assert 'trial-1: quality=passed; prediction=refuted' in text
    assert 'Arbiter changed from selecting an experiment to declining one' in text
    assert 'Trials executed in this round: none' in text
    assert 'Trial trial-2:' not in text


def test_inactive_participation_is_explicit_and_not_counted_as_specialist_calls():
    report = {'search': {'rounds': [{'round': 1,
        'specialist_participation': [
            {'role': 'quantization', 'status': 'inactive', 'reason': 'No enabled precision control',
             'legal_candidate_count': 0},
            {'role': 'batching', 'status': 'active', 'reason': 'Legal candidate available',
             'legal_candidate_count': 1},
            {'role': 'parallelism', 'status': 'inactive', 'reason': 'Single GPU; tensor parallel size is fixed at 1',
             'legal_candidate_count': 0}],
        'specialists': [{'role': 'batching', 'status': 'abstained', 'evidence': {'history': []}}]}]}}
    text = render_investigation(report)
    assert 'batching-only, not a full specialist swarm' in text
    assert 'quantization: inactive; legal candidates=0; No enabled precision control' in text
    assert 'parallelism: inactive' in text
    assert 'Specialist quantization:' not in text


def test_deployment_stage_separates_estimated_fit_from_measured_search():
    report = {'deployment': {
        'infeasible_baseline': {'status': 'infeasible', 'reason': 'Estimated BF16 exceeds memory',
                                'fit_estimate': {'estimated_peak_bytes': 160000000000}},
        'planning_specialist': {'role': 'quantization', 'status': 'accepted',
            'evidence': {'legal_plan_ids': ['weight-fp8']},
            'response': {'ranked_proposal_ids': ['weight-fp8'], 'reason': 'Estimated FP8 plan fits'}},
        'planning_decision': {'ranked_proposal_ids': ['weight-fp8'], 'reason': 'Measure the legal plan'},
        'candidate_trial': {'trial_id': 'deployment-1', 'status': 'collected',
                            'task_quality': {'passed': True, 'mean': 1.0, 'floor': .99}},
        'decision': {'selected': 'candidate', 'outcome': 'feasible'},
        'agent_final': {'prediction_outcome': 'confirmed', 'reason': 'Loaded and passed tasks'}},
        'search': {'initial_trials_used': 1, 'rounds': [
            {'round': 1, 'specialists': [{'role': 'batching', 'status': 'accepted'}]}]}}
    text = render_investigation(report)
    assert 'quantization and batching' in text
    assert 'batching-only' not in text
    assert '### Deployment stage' in text
    assert 'estimate only; not a measured BF16 run' in text
    assert 'Quantization specialist recommends: weight-fp8' in text
    assert 'Deployment arbiter chose: weight-fp8' in text
    assert 'Quality gate: passed' in text
    assert 'Deployment prediction review: confirmed' in text
    assert 'No BF16 speedup comparison is available' in text
    assert 'Deployment trials included in budget: 1' in text
