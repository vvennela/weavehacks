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
