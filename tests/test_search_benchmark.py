"""Synthetic fixtures test replay mechanics, not model performance."""

from copy import deepcopy

import pytest

from benchmarks.search import freeze_manifest, replay, run_comparison
from sera.config import BASELINE_NAME, MODEL_ID, MODEL_REVISION, RuntimeConfig
from sera.storage import content_hash


def fixture_bundle():
    identity = {
        'model_id': MODEL_ID, 'model_revision': MODEL_REVISION,
        'tokenizer_revision': MODEL_REVISION,
        **{key: content_hash(key) for key in (
            'workload_hash', 'input_token_ids_hash', 'profile_hash', 'generation_hash',
            'quality_gate_hash', 'measurement_hash', 'hardware_hash', 'runtime_hash')},
        'profile_name': 'test-fixture-not-measured',
    }
    baseline = RuntimeConfig()
    candidates = [RuntimeConfig(max_num_batched_tokens=value) for value in (1024, 2048, 3072)]
    manifest = freeze_manifest(identity, baseline, candidates, budget=2,
                               evidence_kind='test-fixture')
    artifacts = []
    for index, item in enumerate([manifest['baseline'], *manifest['candidates']]):
        record = {
            'manifest_hash': manifest['manifest_hash'], 'identity': identity,
            'candidate_id': item['candidate_id'], 'configuration': item['configuration'],
            'config_hash': item['config_hash'], 'evidence_kind': 'test-fixture',
            'source_evidence_hash': content_hash({'fixture': index}),
            'status': 'completed', 'feasibility_passed': True,
            'reliability_passed': True, 'quality_passed': True,
            'p95_latency_ms': [100, 90, 50, 70][index],
            'peak_memory_mib': 1000 + index, 'startup_seconds': 1,
            'gpu_collection_seconds': 2,
        }
        artifacts.append({'record': record, 'artifact_hash': content_hash(record)})
    return manifest, artifacts


def test_fixed_grid_budget_curve_and_oracle_are_separate():
    manifest, artifacts = fixture_bundle()
    result = replay(manifest, artifacts)
    assert result['trials_used'] == 2
    assert [point['p95_latency_ms'] for point in result['curve']] == [100, 90, 50]
    assert result['trials_to_near_oracle'] == 2
    assert result['oracle']['p95_latency_ms'] == 50
    assert result['performance_claim_allowed'] is False
    assert result['gpu_collection_seconds'] == 8


def test_policy_only_sees_baseline_and_selected_outcomes_and_cannot_mutate_them():
    manifest, artifacts = fixture_bundle()
    views = []

    def policy(view):
        views.append(deepcopy(view))
        assert 'oracle' not in view
        assert all(set(item) == {'candidate_id', 'configuration', 'config_hash'}
                   for item in view['candidates'])
        assert len(view['observed']) == 2 - view['remaining_trials']
        view['baseline']['p95_latency_ms'] = -1000
        return view['remaining_candidate_ids'][-1]

    result = replay(manifest, artifacts, policy=policy, policy_name='callback')
    assert result['curve'][0]['p95_latency_ms'] == 100
    assert len(views) == 2
    assert len(views[1]['observed']) == 1


def test_invalid_and_repeated_proposals_do_not_cost_gpu_trials():
    manifest, artifacts = fixture_bundle()
    first = manifest['candidates'][0]['candidate_id']
    last = manifest['candidates'][-1]['candidate_id']
    choices = iter(['outside', first, first, last])
    result = replay(manifest, artifacts, policy=lambda _: next(choices))
    assert result['trials_used'] == 2
    assert [p['status'] for p in result['proposals']] == [
        'out-of-universe', 'selected', 'repeated', 'selected']
    assert result['repeated_proposals'] == 1


def test_failed_cached_trial_consumes_budget_but_cannot_improve_curve():
    manifest, artifacts = fixture_bundle()
    record = artifacts[1]['record']
    record.update(status='startup-failed', reliability_passed=False,
                  p95_latency_ms=None, peak_memory_mib=None)
    artifacts[1]['artifact_hash'] = content_hash(record)
    result = replay(manifest, artifacts)
    assert result['trials_used'] == 2
    assert result['invalid_trials'] == 1
    assert result['curve'][1]['p95_latency_ms'] == 100


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'hash', 'identity', 'config', 'manifest'])
def test_incomplete_or_mismatched_evidence_fails_closed(change):
    manifest, artifacts = fixture_bundle()
    if change == 'missing':
        artifacts.pop()
    elif change == 'duplicate':
        artifacts[-1] = artifacts[0]
    else:
        record = artifacts[-1]['record']
        if change == 'hash':
            record['p95_latency_ms'] += 1
        elif change == 'identity':
            record['identity'] = dict(record['identity'], workload_hash='0' * 64)
        elif change == 'config':
            record['configuration'] = RuntimeConfig().model_dump()
        else:
            record['manifest_hash'] = '0' * 64
        if change != 'hash':
            artifacts[-1]['artifact_hash'] = content_hash(record)
    with pytest.raises(ValueError):
        replay(manifest, artifacts)


def test_manifest_budget_baseline_and_order_are_enforced():
    manifest, artifacts = fixture_bundle()
    identity = manifest['identity']
    configs = [RuntimeConfig.model_validate(c['configuration']) for c in manifest['candidates']]
    with pytest.raises(ValueError, match='budget'):
        freeze_manifest(identity, RuntimeConfig(), configs, budget=3)
    with pytest.raises(ValueError, match='baseline'):
        freeze_manifest(identity, RuntimeConfig(kv_cache_dtype='fp8'), configs, budget=2)
    assert manifest['baseline']['candidate_id'] == BASELINE_NAME
    manifest['candidates'].reverse()
    with pytest.raises(ValueError):
        replay(manifest, artifacts)


def test_random_comparison_uses_twenty_recorded_seeds_and_common_budget():
    manifest, artifacts = fixture_bundle()
    results = run_comparison(manifest, artifacts)
    assert len(results['random']) == 20
    assert [r['seed'] for r in results['random']] == list(range(20))
    assert all(r['trials_used'] == 2 for r in results['random'])
    repeat = run_comparison(manifest, artifacts)
    assert [[p['candidate_id'] for p in r['proposals']] for r in results['random']] == [
        [p['candidate_id'] for p in r['proposals']] for r in repeat['random']]
    assert results['benchmark_claim'] == 'not-assessed'


def test_quality_failure_cannot_be_oracle_and_memory_breaks_latency_ties():
    manifest, artifacts = fixture_bundle()
    artifacts[1]['record'].update(p95_latency_ms=1, quality_passed=False)
    artifacts[2]['record'].update(p95_latency_ms=70, peak_memory_mib=1200)
    artifacts[3]['record'].update(p95_latency_ms=70, peak_memory_mib=1100)
    for artifact in artifacts:
        artifact['artifact_hash'] = content_hash(artifact['record'])
    result = replay(manifest, artifacts)
    assert result['oracle']['candidate_id'] == manifest['candidates'][2]['candidate_id']
    assert result['quality_failures'] == 1
    assert result['trials_to_near_oracle'] == 2


@pytest.mark.parametrize('field,value', [
    ('quality_passed', 1), ('p95_latency_ms', None), ('peak_memory_mib', -1),
    ('gpu_collection_seconds', None), ('status', 'unknown'),
])
def test_invalid_or_missing_gates_and_measurements_fail_closed(field, value):
    manifest, artifacts = fixture_bundle()
    artifacts[1]['record'][field] = value
    artifacts[1]['artifact_hash'] = content_hash(artifacts[1]['record'])
    with pytest.raises(ValueError):
        replay(manifest, artifacts)


def test_fixture_cannot_be_mixed_into_measured_manifest():
    manifest, artifacts = fixture_bundle()
    artifacts[1]['record']['evidence_kind'] = 'measured'
    artifacts[1]['artifact_hash'] = content_hash(artifacts[1]['record'])
    with pytest.raises(ValueError):
        replay(manifest, artifacts)


def test_precision_requires_preflight_hash_and_proposal_limit_is_bounded():
    manifest, _ = fixture_bundle()
    with pytest.raises(ValueError, match='compatibility'):
        freeze_manifest(manifest['identity'], RuntimeConfig(), [
            RuntimeConfig(kv_cache_dtype='fp8'), RuntimeConfig(max_num_seqs=4)], budget=1)
    manifest, artifacts = fixture_bundle()
    result = replay(manifest, artifacts, policy=lambda _: 'never-legal')
    assert result['trials_used'] == 0
    assert len(result['proposals']) == manifest['max_proposals']
    assert result['stop_reason'] == 'proposal-limit'


def test_comparison_freezes_input_copy_across_injected_policies():
    manifest, artifacts = fixture_bundle()

    def mutating_callback(view):
        artifacts.clear()
        return view['remaining_candidate_ids'][0]

    result = run_comparison(manifest, artifacts, policies={
        'first': mutating_callback,
        'second': lambda view: view['remaining_candidate_ids'][0],
    })
    assert result['policies']['second']['trials_used'] == 2


def adapter_manifest():
    identity = fixture_bundle()[0]['identity']
    return freeze_manifest(identity, RuntimeConfig(), [
        RuntimeConfig(kv_cache_dtype='fp8'), RuntimeConfig(max_num_batched_tokens=2048),
    ], budget=1, compatibility={'kv-fp8': content_hash('passed-fixture-check')},
        evidence_kind='test-fixture')


def adapter_view(manifest):
    baseline = fixture_bundle()[1][0]['record']
    baseline.update(manifest_hash=manifest['manifest_hash'], telemetry={'queue_ms': 47.0})
    return {
        'manifest_hash': manifest['manifest_hash'], 'identity': manifest['identity'],
        'baseline': baseline, 'candidates': manifest['candidates'], 'observed': [],
        'remaining_candidate_ids': [c['candidate_id'] for c in manifest['candidates']],
        'remaining_trials': 1, 'proposal_log': [],
    }


class StubWandbClient:
    """Only structured in-memory replies. Never calls W&B or another service."""
    model = 'test-model'
    project = 'test-project'

    def __init__(self):
        self.history = []

    def request(self, role, evidence, instruction):
        from sera.agent import ArbiterDecision, Proposal
        self.history.append({'role': role, 'evidence': deepcopy(evidence),
                             'instruction': instruction, 'attempts': [{'schema_valid': True}]})
        if role == 'arbiter':
            return ArbiterDecision(ranked_proposal_ids=[evidence['legal_proposal_ids'][-1]], reason='fixture')
        specialist = evidence['specialist_role']
        lever = 'kv_cache_dtype' if specialist == 'quantization' else 'max_num_batched_tokens'
        value = 'fp8' if specialist == 'quantization' else 2048
        return Proposal(
            action='trial', proposal_id=specialist, agent_role=specialist,
            parent_trial_id=evidence['trial_id'], model_id=MODEL_ID,
            changed_lever=lever, proposed_value=value, evidence_used=['p95_latency_ms'],
            predicted_metric_change='fixture only', confidence=0.5, expected_trial_cost=1,
            falsification_condition='fixture only', reason='fixture only',
        )


def test_full_adapter_calls_two_specialists_then_arbiter_and_preserves_audit(monkeypatch):
    from benchmarks.search_policies import WandbSearchPolicy
    monkeypatch.setattr('benchmarks.search_policies.require_provider_check', lambda *_: {'passed': True})
    manifest = adapter_manifest()
    client = StubWandbClient()
    policy = WandbSearchPolicy(manifest, client, provider_check='fixture')
    selected = policy(adapter_view(manifest))
    assert selected in [c['candidate_id'] for c in manifest['candidates']]
    assert [call['role'] for call in client.history] == ['proposal', 'proposal', 'arbiter']
    assert len(policy.export_audit()['calls']) == 3
    assert policy.export_audit()['decisions'][0]['selected_candidate_id'] == selected
    for call in client.history:
        assert 'oracle' not in call['evidence']
        assert 'artifacts' not in call['evidence']


def test_ablations_remove_evidence_instead_of_only_changing_labels():
    from benchmarks.search_policies import project_evidence
    view = adapter_view(adapter_manifest())
    observed = deepcopy(view['baseline'])
    observed.update(candidate_id='visited-candidate', p95_latency_ms=17,
                    telemetry={'secret_prior_queue': 83})
    view['observed'] = [observed]
    view['proposal_log'] = [{'candidate_id': 'visited-candidate', 'reason': 'prior response'}]
    full = project_evidence(view, 'full-evidence')
    without_history = project_evidence(view, 'no-history')
    no_telemetry = project_evidence(view, 'no-reduced-telemetry')
    assert full['history'][0]['metrics']['p95_latency_ms'] == 17
    assert 'history' not in without_history
    assert 'proposal_log' not in without_history
    assert 'secret_prior_queue' not in json_text(without_history)
    assert without_history['metrics']['p95_latency_ms'] == 100
    assert no_telemetry['metrics'] == {}
    assert no_telemetry['history'][0]['metrics'] == {}
    assert 'queue_ms' not in json_text(no_telemetry)


def json_text(value):
    import json
    return json.dumps(value, sort_keys=True)


def test_round_robin_calls_one_specialist_without_arbiter(monkeypatch):
    from benchmarks.search_policies import WandbSearchPolicy
    monkeypatch.setattr('benchmarks.search_policies.require_provider_check', lambda *_: {'passed': True})
    manifest = adapter_manifest()
    client = StubWandbClient()
    policy = WandbSearchPolicy(manifest, client, provider_check='fixture', variant='round-robin')
    policy(adapter_view(manifest))
    assert len(client.history) == 1
    assert client.history[0]['role'] == 'proposal'
    assert client.history[0]['evidence']['specialist_role'] == 'quantization'


def test_adapter_rejects_unrepresentable_universe_and_exact_telemetry_ablation(monkeypatch):
    from benchmarks.search_policies import UnsupportedPolicy, WandbSearchPolicy
    monkeypatch.setattr('benchmarks.search_policies.require_provider_check', lambda *_: {'passed': True})
    with pytest.raises(UnsupportedPolicy, match='represent'):
        WandbSearchPolicy(fixture_bundle()[0], StubWandbClient(), provider_check='fixture')
    with pytest.raises(UnsupportedPolicy, match='evidence_used'):
        WandbSearchPolicy(adapter_manifest(), StubWandbClient(), provider_check='fixture',
                         variant='no-reduced-telemetry')


def test_adapter_rejects_wrong_manifest_before_provider_call(monkeypatch):
    from benchmarks.search_policies import WandbSearchPolicy
    monkeypatch.setattr('benchmarks.search_policies.require_provider_check', lambda *_: {'passed': True})
    manifest = adapter_manifest()
    client = StubWandbClient()
    policy = WandbSearchPolicy(manifest, client, provider_check='fixture')
    view = adapter_view(manifest)
    view['manifest_hash'] = '0' * 64
    with pytest.raises(ValueError):
        policy(view)
    assert client.history == []


def test_invalid_arbiter_is_not_replaced_with_a_grid_choice(monkeypatch):
    from benchmarks.search_policies import WandbSearchPolicy
    from sera.agent import ArbiterDecision
    monkeypatch.setattr('benchmarks.search_policies.require_provider_check', lambda *_: {'passed': True})

    class InvalidArbiter(StubWandbClient):
        def request(self, role, evidence, instruction):
            parsed = super().request(role, evidence, instruction)
            return ArbiterDecision(ranked_proposal_ids=['invented'], reason='fixture') if role == 'arbiter' else parsed

    manifest = adapter_manifest()
    policy = WandbSearchPolicy(manifest, InvalidArbiter(), provider_check='fixture')
    assert policy(adapter_view(manifest)) is None
    assert policy.export_audit()['decisions'][0]['status'] == 'invalid-arbiter-output'


def test_provider_request_cap_stops_calls_and_records_reason(monkeypatch):
    from benchmarks.search import StopSearch
    from benchmarks.search_policies import WandbSearchPolicy
    monkeypatch.setattr('benchmarks.search_policies.require_provider_check', lambda *_: {'passed': True})
    manifest = adapter_manifest()
    client = StubWandbClient()
    policy = WandbSearchPolicy(manifest, client, provider_check='fixture', max_provider_requests=1)
    with pytest.raises(StopSearch):
        policy(adapter_view(manifest))
    assert len(client.history) == 1
    assert policy.export_audit()['decisions'][0]['stop_reason'] == 'provider-request-budget'


def test_provider_check_is_required_and_no_history_prompt_is_stripped(monkeypatch):
    from benchmarks.search_policies import WandbSearchPolicy
    validation_calls = []

    def check(path, client):
        validation_calls.append((path, client.project))
        return {'passed': True}

    monkeypatch.setattr('benchmarks.search_policies.require_provider_check', check)
    manifest = adapter_manifest()
    client = StubWandbClient()
    policy = WandbSearchPolicy(manifest, client, provider_check='fixture', variant='no-history')
    policy(adapter_view(manifest))
    assert validation_calls == [('fixture', 'test-project')]
    for call in client.history:
        assert 'history' not in call['evidence']
        assert 'proposal_log' not in call['evidence']


def test_explicit_policy_stop_is_not_an_error_or_trial():
    from benchmarks.search import StopSearch

    def stop(_):
        raise StopSearch()

    manifest, artifacts = fixture_bundle()
    result = replay(manifest, artifacts, policy=stop)
    assert result['stop_reason'] == 'policy-stopped'
    assert result['trials_used'] == 0
    assert result['proposals'][0]['status'] == 'stopped'


def test_combined_precision_requires_a_combined_preflight():
    identity = fixture_bundle()[0]['identity']
    candidates = [RuntimeConfig(quantization='fp8_per_tensor', kv_cache_dtype='fp8'),
                  RuntimeConfig(max_num_batched_tokens=2048)]
    compatibility = {'weights-fp8': content_hash('weights-check'),
                     'kv-fp8': content_hash('kv-check')}
    with pytest.raises(ValueError, match='weights-and-kv-fp8'):
        freeze_manifest(identity, RuntimeConfig(), candidates, budget=1,
                        compatibility=compatibility)
    compatibility['weights-and-kv-fp8'] = content_hash('combined-check')
    manifest = freeze_manifest(identity, RuntimeConfig(), candidates, budget=1,
                               compatibility=compatibility)
    assert len(manifest['candidates']) == 2


def test_collection_time_includes_startup():
    manifest, artifacts = fixture_bundle()
    artifacts[1]['record'].update(gpu_collection_seconds=0.5, startup_seconds=1.0)
    artifacts[1]['artifact_hash'] = content_hash(artifacts[1]['record'])
    with pytest.raises(ValueError, match='startup'):
        replay(manifest, artifacts)
