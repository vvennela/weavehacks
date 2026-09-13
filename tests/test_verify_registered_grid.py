"""Synthetic tests for the explicit public-API trace input adapter."""

import json

import pytest

from tests.test_verify_swarm import fixture


def test_registered_adapter_keeps_shared_swarm_checks(monkeypatch, tmp_path):
    from experiments.verify_registered_grid import verify_registered_grid
    from sera.storage import content_hash
    report, dump = fixture()
    root = next(call for call in dump['calls'] if call['id'] == dump['root_call_id'])
    root['op_name'] = root['op_name'].replace('run_investigation', 'sera_optimize')
    registration = {'registration_hash': 'frozen', 'live_search': {'max_candidate_trials': None}}
    monkeypatch.setattr('experiments.verify_registered_grid._audit_import',
                        lambda folder: (registration, report, {}, [], {}, {}))
    launch = {'command': ['python', '-m', 'benchmarks.live_comparison', 'run-live',
                           '--registration', '/remote/registration.json', '--output-dir', '/remote/run'],
              'registration_hash': 'frozen', 'max_candidate_trials': None,
              'source_revision': 'a' * 40}
    (tmp_path / 'actual-launch.json').write_text(json.dumps(launch))
    (tmp_path / 'runner-probe.json').write_text(json.dumps({'passed': True, 'response': report['post_return_probe']}))
    calls = tmp_path / 'calls.json'
    calls.write_text(json.dumps(dump))
    result = verify_registered_grid(tmp_path, calls)
    assert result['execution_passed'], result['issues']
    assert result['source_hashes']['registration'] == content_hash(registration)
    assert result['registered_live_grid']['probe_scope'] == 'separate-source-regraded-by-live-import'

    root['exception'] = 'failed trace'
    calls.write_text(json.dumps(dump))
    assert not verify_registered_grid(tmp_path, calls)['execution_passed']


@pytest.mark.parametrize('damage', [
    lambda launch: launch.update(registration_hash='different'),
    lambda launch: launch.update(max_candidate_trials=8),
    lambda launch: launch['command'].append('--budget=8'),
    lambda launch: launch.update(source_revision='not-a-commit'),
])
def test_registered_launch_requires_exact_driver_and_frozen_binding(damage):
    from experiments.verify_registered_grid import RegisteredGridAudit
    launch = {'command': ['python', '-m', 'benchmarks.live_comparison', 'run-live',
                           '--registration', '/remote/registration.json', '--output-dir', '/remote/run'],
              'registration_hash': 'frozen', 'max_candidate_trials': None,
              'source_revision': 'a' * 40}
    audit = RegisteredGridAudit({}, [], {'registration_hash': 'frozen',
                                        'live_search': {'max_candidate_trials': None}})
    assert audit.valid_plateau_launch(launch)
    damage(launch)
    assert not audit.valid_plateau_launch(launch)
