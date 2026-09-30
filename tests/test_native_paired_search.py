from benchmarks.native_paired_search import choose_confirmed, comparison_summary


def test_no_win_without_three_complete_qualified_pairs():
    assert comparison_summary([])['sera_beats_fixed'] is None
    assert comparison_summary([{'block': 0, 'qualified': True, 'sera_peak_mib': 10, 'fixed_peak_mib': 20}])['sera_beats_fixed'] is None


def test_all_three_pairs_must_clear_five_percent():
    rows = [{'block': i, 'qualified': True, 'sera_peak_mib': 10, 'fixed_peak_mib': 20} for i in range(3)]
    assert comparison_summary(rows)['sera_beats_fixed'] is True
    rows[2]['sera_peak_mib'] = 19.5
    assert comparison_summary(rows)['sera_beats_fixed'] is False
    rows[2]['qualified'] = False
    assert comparison_summary(rows)['sera_beats_fixed'] is None


def test_selection_requires_every_control_and_confirmation():
    passed = lambda baseline, candidate, profile: candidate['valid']
    metric = lambda trial, objective: trial['memory']
    controls = [{'valid': True, 'memory': 100}, {'valid': True, 'memory': 100}]
    trials = {'small': [{'valid': True, 'memory': 10}, {'valid': False, 'memory': 10}],
              'safe': [{'valid': True, 'memory': 20}, {'valid': True, 'memory': 21}]}
    assert choose_confirmed(controls, trials, None, gate=passed, metric=metric) == 'safe'


def test_pair_rejects_changed_input_and_runtime(monkeypatch):
    from benchmarks import native_paired_search as module
    monkeypatch.setattr(module, 'heldout_passes', lambda *args: True)
    baseline = {'input_token_ids': [[1]], 'runtime': {'device': {'name': 'a'}, 'versions': {'mlx': '1'}}}
    assert module.same_contract_passes(baseline, baseline, None)
    assert not module.same_contract_passes(baseline, baseline | {'input_token_ids': [[2]]}, None)
    changed = baseline | {'runtime': {'device': {'name': 'b'}, 'versions': {'mlx': '1'}}}
    assert not module.same_contract_passes(baseline, changed, None)


def test_missing_controls_cannot_confirm_a_candidate():
    trials = {'candidate': [{'memory': 10}, {'memory': 10}]}
    assert choose_confirmed([], trials, None, gate=lambda *args: True,
                            metric=lambda item, _: item['memory']) is None


def test_invalid_memory_cannot_establish_a_win():
    rows = [{'block': i, 'qualified': True, 'sera_peak_mib': -1, 'fixed_peak_mib': 20} for i in range(3)]
    assert comparison_summary(rows)['sera_beats_fixed'] is None
