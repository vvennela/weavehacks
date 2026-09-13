"""Synthetic collector fixtures; no inference or performance evidence."""

from copy import deepcopy
import json

import pytest

from benchmarks.collection import freeze_collection, collect, summarize, MEASUREMENT
from benchmarks.search import run_comparison
from sera.config import MODEL_ID, MODEL_REVISION, RuntimeConfig
from sera.runtime import GENERATION


def plan():
    return {
        'model_id': MODEL_ID, 'model_revision': MODEL_REVISION,
        'tokenizer_revision': MODEL_REVISION, 'profile_name': 'synthetic-unit-test',
        'records': {
            'workload': {'cases': [{'id': 'one', 'prompt': 'Return one', 'expected': 1,
                                    'max_tokens': 64}], 'system_prompt': 'JSON only'},
            'input_token_ids': [[1, 2]],
            'profile': {'concurrency': [1, 2], 'gpu_memory_utilization': 0.9},
            'generation': {**GENERATION, 'enable_thinking': False},
            'quality_gate': {'version': 'sera-task-v1', 'floor': 0.99},
            'measurement': MEASUREMENT,
            'hardware': {'uuid': 'fixture', 'name': 'fixture', 'total_mib': 96000,
                         'compute_capability': '12.0', 'driver': 'fixture'},
            'runtime': {'vllm': '0.26.0', 'torch': 'fixture',
                        'transformers': 'fixture', 'flashinfer-python': 'fixture'},
        },
        'baseline': RuntimeConfig().model_dump(),
        'candidates': [RuntimeConfig(max_num_batched_tokens=2048).model_dump(),
                       RuntimeConfig(enable_prefix_caching=True).model_dump()],
        'budget': 1, 'evidence_kind': 'test-fixture',
    }


def fixture_measure(entry, folder, bundle):
    records = bundle['records']
    return {
        'status': 'collected', 'config_hash': entry['config_hash'],
        'input_token_ids': [[1, 2]], 'generation_errors': 0,
        'runtime': {'configuration': entry['configuration'], 'cleanup_pass': True,
                    'sampled_peak_memory_mib': 2000, 'startup_seconds': 2,
                    'model_id': MODEL_ID, 'revision': MODEL_REVISION,
                    'generation': GENERATION, 'enable_thinking': False},
        'collection_identity': {'hardware': records['hardware'], 'runtime': records['runtime']},
        'workload': {'concurrency': [1, 2], 'quality_concurrency': 1,
                     'latency_reduction': 'worst-per-load-percentile',
                     'cache_evaluation': {'measured_scope': 'repeated-prompts-after-per-load-warmup',
                                          'prefix_caching_enabled': entry['configuration']['enable_prefix_caching'],
                                          'cold_cache_measurement': False, 'warmup_prompts_per_load': 1}},
        'quality': [{'prompt_index': 0, 'text': '{"answer":1}', 'error': None}],
        'loads': [{'concurrency': level, 'reduced': {'p95_latency_ms': level * 10,
                                                    'generation_errors': 0},
                   'requests': [{'latency_ms': level * 10, 'error': None}] * 3}
                  for level in [1, 2]],
        'collection_seconds': 5,
    }


def test_collection_freezes_sources_collects_once_and_replays_twenty_seeds(tmp_path):
    bundle = freeze_collection(plan())
    seen = []

    def measure(*args):
        seen.append(args[0]['candidate_id'])
        return fixture_measure(*args)

    report = collect(bundle, tmp_path / 'collection', measure=measure)
    assert len(seen) == 3
    assert report['complete'] is True
    assert report['rows'][0]['per_load_p95_latency_ms'] == {'1': 10, '2': 20}
    assert report['rows'][0]['startup_seconds'] == 2
    assert report['rows'][0]['quality_score'] == 1
    artifacts = json.loads((tmp_path / 'collection/outcomes.json').read_text())
    assert len(run_comparison(bundle['manifest'], artifacts)['random']) == 20
    assert report['benchmark_claim'] == 'not-assessed'
    assert report['performance_claim_allowed'] is False
    with pytest.raises(FileExistsError):
        collect(bundle, tmp_path / 'collection', measure=measure)
    assert len(seen) == 3


def test_baseline_quality_failure_stops_before_candidates_and_has_no_oracle(tmp_path):
    def wrong(*args):
        trial = fixture_measure(*args)
        trial['quality'][0]['text'] = '{"answer":2}'
        return trial

    report = collect(freeze_collection(plan()), tmp_path / 'bad', measure=wrong)
    assert report['complete'] is False
    assert len(report['rows']) == 1
    assert report['stop_reason'] == 'baseline-failed-gates'
    assert report['oracle'] is None


def test_failed_candidate_stays_in_universe_and_consumes_replay_trial(tmp_path):
    def failed(entry, *args):
        trial = fixture_measure(entry, *args)
        if entry['candidate_id'] != 'sera-baseline-v1':
            trial.update(status='startup-failed', error_type='RuntimeError', loads=[], quality=[])
            trial.pop('input_token_ids')
        return trial

    report = collect(freeze_collection(plan()), tmp_path / 'fail', measure=failed)
    assert report['complete'] is True
    assert report['rows'][1]['status'] == 'startup-failed'
    assert report['rows'][1]['p95_latency_ms'] is None


def test_identity_drift_and_cleanup_failure_stop_collection(tmp_path):
    bundle = freeze_collection(plan())
    for mutation, reason in [('input', 'identity-mismatch'), ('cleanup', 'cleanup-failed')]:
        def changed(*args):
            trial = fixture_measure(*args)
            if mutation == 'input':
                trial['input_token_ids'] = [[99]]
            else:
                trial['runtime']['cleanup_pass'] = False
            return trial
        report = collect(bundle, tmp_path / mutation, measure=changed)
        assert report['complete'] is False
        assert report['stop_reason'] == reason


@pytest.mark.parametrize('field', ['generation', 'workload', 'reduction', 'runtime'])
def test_source_identity_or_reduced_metric_drift_is_not_measured_evidence(tmp_path, field):
    def drift(*args):
        trial = fixture_measure(*args)
        if field == 'generation':
            trial['runtime']['generation'] = dict(GENERATION, temperature=1)
        elif field == 'workload':
            trial['workload']['cache_evaluation']['measured_scope'] = 'cold-cache'
        elif field == 'reduction':
            trial['loads'][0]['reduced']['p95_latency_ms'] = 1
        else:
            trial['collection_identity']['runtime'] = {'vllm': 'wrong'}
        return trial
    report = collect(freeze_collection(plan()), tmp_path / field, measure=drift)
    assert report['complete'] is False
    assert report['stop_reason'] == 'identity-mismatch'


def test_mutating_frozen_sources_fails_before_measurement(tmp_path):
    bundle = freeze_collection(plan())
    bundle['records']['quality_gate']['floor'] = 0.5
    with pytest.raises(ValueError, match='frozen'):
        collect(bundle, tmp_path / 'tampered', measure=fixture_measure)
    assert not (tmp_path / 'tampered').exists()


def test_measured_cannot_use_injected_synthetic_collector(tmp_path):
    supplied = plan()
    supplied['evidence_kind'] = 'measured'
    with pytest.raises(ValueError, match='test-fixture'):
        collect(freeze_collection(supplied), tmp_path / 'lie', measure=fixture_measure)


@pytest.mark.parametrize('startup_fails', [False, True])
def test_live_failure_stage_and_startup_interval_exclude_later_cleanup(monkeypatch, tmp_path, startup_fails):
    from benchmarks.collection import measure_live
    bundle = freeze_collection(plan())
    monkeypatch.setattr('benchmarks.collection.gpu_snapshot', lambda: bundle['records']['hardware'])
    monkeypatch.setattr('benchmarks.collection.importlib.metadata.version',
                        lambda name: bundle['records']['runtime'][name])
    ticks = iter([0, 2, 7])
    monkeypatch.setattr('benchmarks.collection.time.monotonic', lambda: next(ticks))

    class Model:
        def __init__(self, **kwargs):
            self.record = {'configuration': kwargs['configuration'].model_dump()}

        def start(self):
            if startup_fails:
                raise RuntimeError('fixture startup failure')
            self.record['startup_seconds'] = 2

        def close(self):
            self.record['cleanup_pass'] = True

    monkeypatch.setattr('benchmarks.collection.SeraModel', Model)

    def broken(*args, **kwargs):
        raise RuntimeError('fixture post-start measurement failure')

    monkeypatch.setattr('benchmarks.collection.collect_trial', broken)
    trial = measure_live(bundle['manifest']['baseline'], tmp_path / 'runtime', bundle)
    assert trial['status'] == ('startup-failed' if startup_fails else 'request-failed')
    assert trial['runtime']['startup_seconds'] == 2
    assert trial['collection_seconds'] == 7
    assert trial.get('reduced') is None


def test_partial_summary_does_not_compute_oracle(tmp_path):
    bundle = freeze_collection(plan())
    report = summarize(bundle['manifest'], [])
    assert report['complete'] is False
    assert report['oracle'] is None
    assert report['missing_candidate_ids']


@pytest.mark.parametrize('variant', ['full-evidence', 'no-history', 'round-robin'])
def test_current_swarm_replay_uses_production_investigators_and_hides_outcomes(monkeypatch, tmp_path, variant):
    from benchmarks.search_policies import FrozenSwarmPolicy
    from sera.agent import ArbiterDecision, Proposal

    monkeypatch.setattr('benchmarks.search_policies.require_provider_check', lambda *_: {'passed': True})

    class Agent:
        model, project = 'fixture', 'fixture'

        def __init__(self):
            self.history = []

        def fork(self):
            return Agent()

        def request(self, role, evidence, instruction):
            self.history.append({'role': role, 'evidence': deepcopy(evidence)})
            assert 'oracle' not in evidence
            if role == 'arbiter':
                return ArbiterDecision(ranked_proposal_ids=evidence['legal_proposal_ids'][:1], reason='fixture')
            option = evidence['candidate_options'][0]
            lever, value = next(iter(option['changed'].items()))
            from sera.config import CONTROL_ROLES
            return Proposal(action='trial', proposal_id='fixture', agent_role=CONTROL_ROLES[lever],
                            parent_trial_id=evidence['trial_id'], model_id=MODEL_ID,
                            changed_lever=lever, proposed_value=value, evidence_used=['p95_latency_ms'],
                            predicted_metric_change='fixture', confidence=0.5, expected_trial_cost=1,
                            falsification_condition='fixture', reason='fixture')

    bundle = freeze_collection(plan())
    collect(bundle, tmp_path / 'collection', measure=fixture_measure)
    artifacts = json.loads((tmp_path / 'collection/outcomes.json').read_text())
    policy = FrozenSwarmPolicy(bundle['manifest'], Agent(), provider_check='fixture', variant=variant)
    comparison = run_comparison(bundle['manifest'], artifacts, policies={'sera': policy})
    assert comparison['policies']['sera']['trials_used'] == 1
    round_record = policy.export_audit()['rounds'][0]
    assert len(round_record['specialists']) == (1 if variant == 'round-robin' else 3)
    assert all(row['successful_inspections'] == 2 for row in round_record['specialists'])
    if variant == 'round-robin':
        assert 'arbiter' not in round_record
    else:
        assert round_record['arbiter']['ranked_proposal_ids']
    assert round_record['agent_calls']


def test_swarm_no_history_removes_selected_outcomes_from_inspection_reads(monkeypatch, tmp_path):
    from benchmarks.search_policies import FrozenSwarmPolicy
    monkeypatch.setattr('benchmarks.search_policies.require_provider_check', lambda *_: {'passed': True})

    class Client:
        model, project = 'fixture', 'fixture'

        def __init__(self):
            self.history = []

        def fork(self):
            return Client()

    seen = []

    def choose(client, evidence, legal, record, remaining, reader):
        seen.append((deepcopy(evidence), reader('load_metrics', evidence)))
        return [(None, legal[0][3], 'fixture')]

    monkeypatch.setattr('sera.swarm.choose_swarm_experiments', choose)
    bundle = freeze_collection(plan())
    collect(bundle, tmp_path / 'collection', measure=fixture_measure)
    artifacts = json.loads((tmp_path / 'collection/outcomes.json').read_text())
    manifest = bundle['manifest']
    view = {'manifest_hash': manifest['manifest_hash'], 'identity': manifest['identity'],
            'candidates': manifest['candidates'], 'baseline': artifacts[0]['record'],
            'observed': [artifacts[1]['record']], 'remaining_trials': 1, 'proposal_log': [],
            'remaining_candidate_ids': [artifacts[2]['record']['candidate_id']]}
    FrozenSwarmPolicy(manifest, Client(), provider_check='fixture')(view)
    FrozenSwarmPolicy(manifest, Client(), provider_check='fixture', variant='no-history')(view)
    assert len(seen[0][1]['observed']) == 1
    assert seen[1][1]['observed'] == []
    assert 'history' not in seen[1][0]
    assert not any(key.startswith('observed.') for key in seen[1][0]['metrics'])


def test_cli_replay_audits_sources_before_reporting(tmp_path):
    from benchmarks.run_search import main
    bundle = freeze_collection(plan())
    collect(bundle, tmp_path / 'collection', measure=fixture_measure)
    assert main(['replay', '--collection', str(tmp_path / 'collection'),
                 '--output-dir', str(tmp_path / 'report')]) == 0
    comparison = json.loads((tmp_path / 'report/comparison.json').read_text())
    assert len(comparison['random']) == 20
    assert comparison['policies'] == {}
    source = tmp_path / 'collection/sera-baseline-v1-source.json'
    data = json.loads(source.read_text())
    data['quality'][0]['text'] = '{"answer":99}'
    source.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='source evidence'):
        main(['replay', '--collection', str(tmp_path / 'collection'),
              '--output-dir', str(tmp_path / 'bad-report')])
    assert not (tmp_path / 'bad-report').exists()
