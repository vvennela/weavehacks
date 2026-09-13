"""Durable restart tests use fake models; they make no GPU or provider calls."""

from copy import deepcopy
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import sera
from sera import pipeline
from test_investigation import install_fakes, run


def fixture_runtime(monkeypatch):
    runners, seen, agent = install_fakes(monkeypatch)
    collect = pipeline.collect_trial

    def measured(model, *args, **kwargs):
        model.record['gpu'] = dict(uuid='GPU-fixture', name='fixture', total_mib=96000,
            compute_capability='12.0', driver='fixture', used_mib=0)
        return collect(model, *args, **kwargs)

    monkeypatch.setattr(pipeline, 'collect_trial', measured)
    return runners, seen, agent


def resume_options(folder, agent):
    checkpoint = sera.inspect_recovery(folder)
    return dict(output_dir=folder, expected_run_hash=checkpoint['run_hash'],
        agent=agent, provider_check='fixture', evaluation=lambda p, o: o == 'correct',
        evaluation_version=checkpoint['report']['evaluation']['version'], confirm_interrupted=True)


def test_sqlite_is_authoritative_and_has_trials_decisions_and_agent_records(tmp_path, monkeypatch):
    fixture_runtime(monkeypatch)
    _, _, agent = install_fakes(monkeypatch)
    with run(tmp_path, agent) as result:
        with sqlite3.connect(result.output_dir / 'ledger.sqlite3') as database:
            assert database.execute('SELECT count(*) FROM trials').fetchone()[0] == 3
            assert database.execute('SELECT count(*) FROM agent_operations').fetchone()[0] > 0
        saved = sera.inspect_recovery(result.output_dir)
        assert saved['report']['decision'] == result.report['decision']
        (result.output_dir / 'result.json').write_text('{corrupt mirror')
        assert sera.inspect_recovery(result.output_dir)['report']['decision'] == result.report['decision']


def test_resume_after_completed_candidate_does_not_measure_it_again(tmp_path, monkeypatch):
    runners, seen, agent = fixture_runtime(monkeypatch)
    original_save = pipeline.SeraResult._save
    interrupted = False

    def interrupt_after_measurement(result):
        nonlocal interrupted
        original_save(result)
        trials = result.report.get('search_trials', [])
        if trials and 'decision' in trials[0] and not interrupted:
            interrupted = True
            raise KeyboardInterrupt('fixture process interruption')

    monkeypatch.setattr(pipeline.SeraResult, '_save', interrupt_after_measurement)
    with pytest.raises(KeyboardInterrupt):
        run(tmp_path, agent)
    folder = tmp_path / 'run'
    monkeypatch.setattr('sera.recovery.verify_idle_hardware', lambda report: None)
    measured = []
    collect = pipeline.collect_trial

    def count_measurements(model, *args, **kwargs):
        measured.append(model.configuration.config_hash)
        return collect(model, *args, **kwargs)

    monkeypatch.setattr(pipeline, 'collect_trial', count_measurements)
    prior = sera.inspect_recovery(folder)['report']
    with sera.resume(**resume_options(folder, type(agent)())) as result:
        assert result.report['search']['trials_used'] == 2
        assert result.report['decision']['selected'] == 'trial-2'
        assert prior['baseline']['config_hash'] not in measured
        assert prior['search_trials'][0]['config_hash'] not in measured
        assert len(measured) == 1
        assert result.models[0].generate('fresh') == 'fresh answer'
        assert result.report['search']['rounds'][0]['recovery_interrupted'] is True
        assert any(record['role'] == 'proposal' for record in result.report['agent_calls'])
    assert not any(model.ready for model in runners)


def test_resume_refuses_changed_provenance_before_gpu_or_agent(tmp_path, monkeypatch):
    _, _, agent = fixture_runtime(monkeypatch)
    with run(tmp_path, agent):
        pass
    monkeypatch.setattr('sera.recovery.verify_idle_hardware', lambda _: pytest.fail('Must not inspect GPU'))
    options = resume_options(tmp_path / 'run', type(agent)())
    with pytest.raises(ValueError, match='run hash'):
        sera.resume(**(options | dict(expected_run_hash='wrong')))
    with pytest.raises(ValueError, match='evaluation version'):
        sera.resume(**(options | dict(evaluation_version='different')))


def test_second_optimizer_cannot_resume_an_active_owner(tmp_path, monkeypatch):
    _, _, agent = fixture_runtime(monkeypatch)
    with run(tmp_path, agent):
        with pytest.raises(RuntimeError, match='active owner'):
            sera.resume(**resume_options(tmp_path / 'run', type(agent)()))


def test_resume_restores_finished_runner_without_new_experiments(tmp_path, monkeypatch):
    _, _, agent = fixture_runtime(monkeypatch)
    with run(tmp_path, agent) as original:
        decision = deepcopy(original.report['decision'])
    monkeypatch.setattr('sera.recovery.verify_idle_hardware', lambda report: None)
    monkeypatch.setattr(pipeline, 'collect_trial', lambda *a, **kw: pytest.fail('No repeat trials'))
    with sera.resume(**resume_options(tmp_path / 'run', type(agent)())) as result:
        assert result.report['decision'] == decision
        assert result.models[0].generate('fresh') == 'fresh answer'


def test_ledger_detects_report_corruption(tmp_path, monkeypatch):
    _, _, agent = fixture_runtime(monkeypatch)
    with run(tmp_path, agent):
        pass
    with sqlite3.connect(tmp_path / 'run' / 'ledger.sqlite3') as database:
        database.execute("UPDATE checkpoint SET report_json = '{}' WHERE id = 1")
    with pytest.raises(ValueError, match='checksum'):
        sera.inspect_recovery(tmp_path / 'run')


@pytest.mark.parametrize('phase', ['starting', 'measured', 'round-complete'])
def test_sigkill_releases_owner_and_resume_keeps_committed_trials(tmp_path, monkeypatch, phase):
    script = '''
import os, signal, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path.cwd() / 'tests'))
from test_optimizer_recovery import fixture_runtime
from test_investigation import run
from sera import pipeline
patch = pytest.MonkeyPatch()
_, _, agent = fixture_runtime(patch)
save = pipeline.SeraResult._save
def die(result):
    save(result)
    trials = result.report.get('search_trials', [])
    if not trials:
        return
    phase = sys.argv[2]
    matches = ((phase == 'starting' and trials[0]['status'] == 'starting') or
               (phase == 'measured' and 'decision' in trials[0]) or
               (phase == 'round-complete' and result.report['search']['rounds'][0].get('completed')))
    if matches:
        os.kill(os.getpid(), signal.SIGKILL)
pipeline.SeraResult._save = die
run(Path(sys.argv[1]), agent)
'''
    child = subprocess.run([sys.executable, '-c', script, str(tmp_path), phase],
                           cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=30)
    assert child.returncode == -9, child.stderr.decode()
    _, _, agent = fixture_runtime(monkeypatch)
    folder = tmp_path / 'run'
    before = sera.inspect_recovery(folder)['report']
    assert before['status'] == 'running'
    monkeypatch.setattr('sera.recovery.verify_idle_hardware', lambda report: None)
    measured = []
    collect = pipeline.collect_trial
    def measure(model, *args, **kwargs):
        measured.append(model.configuration.config_hash)
        return collect(model, *args, **kwargs)
    monkeypatch.setattr(pipeline, 'collect_trial', measure)
    options = resume_options(folder, agent)
    with pytest.raises(ValueError, match='confirm_interrupted'):
        sera.resume(**(options | dict(confirm_interrupted=False)))
    with sera.resume(**options) as result:
        assert len(measured) == 1
        assert before['search_trials'][0]['config_hash'] not in measured
        assert before['baseline']['config_hash'] not in measured
        assert result.report['search']['trials_used'] == 2
        if phase == 'starting':
            assert result.report['search_trials'][0]['status'] == 'interrupted'
        assert result.models[0].generate('fresh') == 'fresh answer'


@pytest.mark.parametrize('change,match', [({'used_mib': 129}, 'busy'),
    ({'uuid': 'GPU-other'}, 'identity'), ({'driver': 'changed'}, 'identity')])
def test_resume_rejects_busy_or_changed_gpu_without_signals(tmp_path, monkeypatch, change, match):
    from sera.recovery import verify_idle_hardware
    _, _, agent = fixture_runtime(monkeypatch)
    with run(tmp_path, agent) as result:
        report = deepcopy(result.report)
    gpu = report['baseline']['runtime']['gpu'] | change
    monkeypatch.setattr('sera.hardware.discover_gpus', lambda: [gpu])
    with pytest.raises((RuntimeError, ValueError), match=match):
        verify_idle_hardware(report)


def test_resume_rejects_gpu_process_even_with_low_memory(tmp_path, monkeypatch):
    from sera.recovery import verify_idle_hardware
    _, _, agent = fixture_runtime(monkeypatch)
    with run(tmp_path, agent) as result:
        report = deepcopy(result.report)
    monkeypatch.setattr('sera.hardware.discover_gpus', lambda: [report['baseline']['runtime']['gpu']])
    monkeypatch.setattr('sera.recovery.subprocess.run', lambda *args, **kwargs:
                        subprocess.CompletedProcess(args, 0, stdout='GPU-fixture, 5678\n'))
    with pytest.raises(RuntimeError, match='compute process'):
        verify_idle_hardware(report)


def test_traced_swarm_resume_imports_history_then_returns_without_remeasurement(tmp_path, monkeypatch):
    from test_swarm_pipeline import forkable
    _, _, agent = fixture_runtime(monkeypatch)
    with run(tmp_path, forkable(agent), swarm=True, trace_reader=lambda *args: {}) as original:
        previous = deepcopy(original.report['search_trials'])
    seen = []
    client = SimpleNamespace(flush=lambda: seen.append('flush'))
    def op(function=None, *, name=None):
        def decorate(fn):
            def invoke(*args, **kwargs):
                seen.append(name or fn.__name__)
                return fn(*args, **kwargs)
            return invoke
        return decorate(function) if function else decorate
    monkeypatch.setitem(sys.modules, 'weave', SimpleNamespace(op=op,
        init=lambda project: client,
        get_current_call=lambda: SimpleNamespace(trace_id='new-root', ui_url='new-weave-url')))
    monkeypatch.setattr('sera.recovery.verify_idle_hardware', lambda _: None)
    monkeypatch.setattr('sera.recovery._export_saved_evidence',
        lambda result: seen.append(('import', len(result.report['search_trials']))))
    monkeypatch.setattr(pipeline, 'collect_trial', lambda *a, **kw: pytest.fail('No repeat measurement'))
    with sera.resume(**resume_options(tmp_path/'run', forkable(type(agent)())),
                     weave_project='test/project') as result:
        assert result.report['search_trials'] == previous
        assert result.weave_url == 'new-weave-url'
        assert result.report['recovery_events'][-1]['trace_id'] == 'new-root'
        assert ('import', 2) in seen
        assert 'sera_resume' in seen and 'restore_saved_trial_evidence' in seen and 'flush' in seen


def test_ledger_refuses_credentials_in_reports_and_agent_operations(tmp_path, monkeypatch):
    from sera.ledger import Ledger
    monkeypatch.setenv('WANDB_API_KEY', 'fixture-secret-value-do-not-save')
    ledger = Ledger(tmp_path)
    try:
        with pytest.raises(ValueError, match='credential'):
            ledger.save(dict(status='failed', error='fixture-secret-value-do-not-save'))
        with pytest.raises(ValueError, match='credential'):
            ledger.record_operation('one', dict(status='completed', response='fixture-secret-value-do-not-save'))
    finally:
        ledger.close()
    assert all(b'fixture-secret-value-do-not-save' not in path.read_bytes()
               for path in tmp_path.iterdir() if path.is_file())


@pytest.mark.parametrize('count', [1, 2, 4, 8])
def test_portable_resume_preserves_fixed_hardware_assignment(tmp_path, monkeypatch, count):
    from test_portable_optimization import setup, run as portable_run
    runners, _, agent = setup(monkeypatch)
    with portable_run(tmp_path, count, agent=agent, provider_check='fixture',
        budget=sera.Budget(max_candidate_trials=1),
        investigation_space=sera.InvestigationSpace(supported_changes={'max_num_batched_tokens': [2048]})):
        pass
    monkeypatch.setattr('sera.recovery.verify_idle_hardware', lambda _: None)
    monkeypatch.setattr(pipeline, 'collect_trial', lambda *a, **kw: pytest.fail('No repeat measurement'))
    with sera.resume(**resume_options(tmp_path/'run', type(agent)())) as result:
        assert result.models[0].configuration.tensor_parallel_size == count
        assert len(result.models[0].hardware.gpu_uuids) == count


def test_fit_first_resume_keeps_promoted_deployment_and_trial_budget(tmp_path, monkeypatch):
    from test_fit_investigation import boundaries, run as fit_run
    _, _, agent = boundaries(monkeypatch)
    with fit_run(tmp_path, agent, budget=1) as result:
        original = deepcopy(result.report['deployment'])
    monkeypatch.setattr('sera.recovery.verify_idle_hardware', lambda _: None)
    monkeypatch.setattr(pipeline, 'collect_trial', lambda *a, **kw: pytest.fail('No repeat measurement'))
    with sera.resume(**resume_options(tmp_path/'run', type(agent)())) as result:
        assert result.report['deployment'] == original
        assert result.report['baseline']['source_trial_id'] == 'candidate'
        assert result.report['search']['trials_used'] == 1
        assert result.models[0].generate('fresh') == 'correct'
