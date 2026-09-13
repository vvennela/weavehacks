from sera.techniques import technique_catalog, techniques_for, specialist_shortlist


def test_catalog_has_twenty_distinct_sourced_techniques():
    rows = technique_catalog({})
    assert len(rows) == len({row['technique_id'] for row in rows}) == 20
    assert all(row['source_url'].startswith('https://docs.vllm.ai/en/v0.26.0/') for row in rows)
    assert all(row['applicability'] and row['risk'] for row in rows)


def test_specialists_receive_their_own_techniques_with_actual_values():
    rows = techniques_for('output_quality', {'enforce_eager': [False]})
    graphs = next(row for row in rows if row['technique_id'] == 'graph-execution')
    assert graphs['status'] == 'available-for-trial'
    assert graphs['active_values'] == {'enforce_eager': [False]}
    assert all(row['owner'] == 'output_quality' for row in rows)
    assert any(row['status'] == 'adapter-required' for row in rows)


def test_hardware_block_is_not_overridden_by_a_proposal_value():
    rows = technique_catalog({'quantization': ['int8']})
    item = next(row for row in rows if row['technique_id'] == 'int8-w8a8')
    assert item['status'] == 'hardware-blocked'
    assert not item['active_values']


def test_specialist_shortlist_is_eight_unique_candidates_not_eight_trials():
    options = [dict(config_hash=str(i), changed={'max_num_batched_tokens': 128 * (i + 1)})
               for i in range(10)]
    graphs = dict(config_hash='graphs', changed={'enforce_eager': False})
    pool = specialist_shortlist('output_quality', options + [graphs, graphs])
    assert len(pool) == len({row['config_hash'] for row in pool}) == 8
    assert pool[0] == graphs
    assert len(specialist_shortlist('scheduling', options[:2])) == 2


def test_peer_candidates_remain_available_during_refinement_without_exceeding_eight():
    options = [dict(config_hash=str(i), changed={'max_num_batched_tokens': 128 * (i + 1)})
               for i in range(12)]
    pool = specialist_shortlist('scheduling', options, peer_hashes=['11'])
    assert len(pool) == 8
    assert pool[0]['config_hash'] == '11'
