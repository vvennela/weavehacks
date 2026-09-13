"""The existing quality-gated loop on explicit hardware; all runtimes are fake."""

import pytest

import sera
from sera import pipeline
from sera.agent import schema_hash
from sera.config import MODEL_ID, MODEL_REVISION
from test_investigation import install_fakes
from test_portable_runtime import UUIDS
from test_public_api import configured


def setup(monkeypatch, **options):
    runners, seen, agent = install_fakes(monkeypatch, **options)
    base = pipeline.SeraModel

    class Portable(base):
        def __init__(self, *, model, hardware, artifact_dir, configuration):
            super().__init__(artifact_dir=artifact_dir, configuration=configuration,
                             model_id=model.model_id, revision=model.revision)
            self.hardware = hardware
            self.record.update(adapter='explicit-single-host-v1', model_preflight={'architecture': 'Qwen3ForCausalLM'},
                               hardware_assignment=hardware.model_dump())

    monkeypatch.setattr('sera.portable_runtime.PortableSeraModel', Portable)
    return runners, seen, agent


def run(tmp_path, count, **options):
    return sera.optimize_on_hardware(model=sera.ModelDescriptor(model_id='example/dense-model', revision='a' * 40),
        hardware=sera.HardwareAssignment(gpu_uuids=UUIDS[:count]), prompts=['question'],
        output_dir=tmp_path / 'run', evaluation=lambda p, t: t == 'correct',
        evaluation_version='fixture-v1', constraints=sera.Constraints(quality_floor=.99), **options)


@pytest.mark.parametrize('count', [1, 2, 4, 8])
@pytest.mark.parametrize('wrong', [False, True])
def test_existing_baseline_candidate_gate_and_restore_use_assigned_runtime(monkeypatch, tmp_path, count, wrong):
    runners, _, _ = setup(monkeypatch, batch_wrong=wrong)
    with run(tmp_path, count, mode='fixed') as result:
        assert result.models[0].generate('next prompt') == 'fresh answer'
        assert result.report['decision']['selected'] == ('baseline' if wrong else 'candidate')
        assert result.report['task_quality_verified']
        assert result.report['execution']['hardware_assignment']['gpu_uuids'] == UUIDS[:count]
        for runner in runners:
            assert runner.configuration.tensor_parallel_size == count
            assert runner.record['configuration']['tensor_parallel_size'] == count
            assert runner.hardware.gpu_uuids == UUIDS[:count]
        for trial in result.trials:
            assert trial['config_hash'] == sera.RuntimeConfig.model_validate(trial['runtime']['configuration']).config_hash
        assert len(runners) == (3 if wrong else 2)
    assert not any(runner.ready for runner in runners)


@pytest.mark.parametrize('count', [1, 2, 4, 8])
def test_existing_agent_investigation_preserves_model_assignment_and_quality(monkeypatch, tmp_path, count):
    runners, seen, agent = setup(monkeypatch, batch_wrong=True)
    with run(tmp_path, count, agent=agent, provider_check='fixture',
             budget=sera.Budget(max_candidate_trials=None),
             investigation_space=sera.InvestigationSpace(supported_changes={'max_num_batched_tokens': [2048, 1024]})) as result:
        assert result.report['search']['trials_used'] == 2
        assert result.report['search']['stop_reason'] == 'objective-plateau-confirmed'
        assert result.report['decision']['selected'] == 'baseline'
        assert result.models[0].configuration.tensor_parallel_size == count
        assert all(e['model_id'] == 'example/dense-model' for role, e in seen if role == 'proposal')
        assert all(t['task_quality']['passed'] is False for t in result.report['search_trials'])
        assert all(r.configuration.tensor_parallel_size == count for r in runners)
    assert not any(r.ready for r in runners)


def test_new_model_auto_space_uses_measured_inputs_and_never_adds_fp8(monkeypatch, tmp_path):
    _, _, agent = setup(monkeypatch)
    with run(tmp_path, 2, agent=agent, provider_check='fixture', budget=sera.Budget(max_candidate_trials=1),
             automatic_space=True) as result:
        assert result.report['candidate_policy']['candidates']
        for option in result.report['candidate_policy']['candidates']:
            assert option['configuration']['tensor_parallel_size'] == 2
            assert option['configuration']['kv_cache_dtype'] == 'auto'
        assert result.report['candidate_policy']['evidence']['max_input_tokens'] == 1


def test_portable_small_qwen_does_not_inherit_single_gpu_fp8_certificate(monkeypatch, tmp_path):
    setup(monkeypatch)
    with sera.optimize_on_hardware(model=sera.ModelDescriptor(model_id=MODEL_ID, revision=MODEL_REVISION),
        hardware=sera.HardwareAssignment(gpu_uuids=UUIDS[:2]), prompts=['question'], mode='fixed',
        output_dir=tmp_path / 'run', evaluation=lambda p, t: True, evaluation_version='v1',
        constraints=sera.Constraints(quality_floor=.99)) as result:
        assert result.report['candidate']['config']['kv_cache_dtype'] == 'auto'


@pytest.mark.parametrize('options', [dict(), dict(evaluation=lambda p, t: True),
    dict(evaluation=lambda p, t: True, evaluation_version='v1')])
def test_explicit_hardware_requires_task_requirements_before_runtime(monkeypatch, options):
    monkeypatch.setattr('sera.portable_runtime.PortableSeraModel', lambda **_: pytest.fail('runtime created'))
    with pytest.raises(ValueError):
        sera.optimize_on_hardware(model=sera.ModelDescriptor(model_id='example/model', revision='a' * 40),
            hardware=sera.HardwareAssignment(gpu_uuids=UUIDS[:2]), prompts=['question'], mode='fixed', **options)


def test_provider_response_schema_hash_is_unchanged():
    assert schema_hash() == '89f9f151f3f296759187d7ca2eca87ecb540cc6c94814ba2ed9c141c577b5f79'


def test_default_runner_rejects_parallel_assignment_before_launch(tmp_path):
    with pytest.raises(ValueError, match='Portable'):
        sera.SeraModel(artifact_dir=tmp_path, configuration=sera.RuntimeConfig(tensor_parallel_size=2))


@pytest.mark.parametrize('count', [1, 2, 4, 8])
def test_investigation_restores_nonlatest_winner_through_same_factory(monkeypatch, tmp_path, count):
    runners, _, agent = setup(monkeypatch)
    original = pipeline.collect_trial
    def collect(model, prompts, trial_id, **kwargs):
        record = original(model, prompts, trial_id, **kwargs)
        if trial_id == 'trial-2':
            record['reduced']['p95_latency_ms'] = 90.0
        return record
    monkeypatch.setattr(pipeline, 'collect_trial', collect)
    with run(tmp_path, count, agent=agent, provider_check='fixture', budget=sera.Budget(max_candidate_trials=2),
             investigation_space=sera.InvestigationSpace(supported_changes={'max_num_batched_tokens': [2048, 1024]})) as result:
        assert result.report['decision']['selected'] == 'trial-1'
        assert result.models[0].configuration.model_dump() == result.report['search_trials'][0]['runtime']['configuration']
        assert result.models[0].artifact_dir.name == 'returned-best'
        assert result.models[0].configuration.tensor_parallel_size == count
        assert len(runners) == 4
    assert not any(r.ready for r in runners)


def test_public_default_uses_existing_configured_swarm_and_weave(configured, monkeypatch, tmp_path):
    from test_public_api import boundaries
    seen = boundaries(monkeypatch)
    result = run(tmp_path, 2)
    options = seen['options']
    assert options['swarm'] is True and options['automatic_space'] is True
    assert options['budget'].max_candidate_trials is None
    assert options['_runtime_factory'].hardware.gpu_uuids == UUIDS[:2]
    assert callable(options['trace_reader'])
    assert result.report['weave_url'] == 'fixture-url'
    assert seen['flushed']


@pytest.mark.parametrize('options', [
    dict(baseline_configuration=sera.RuntimeConfig(tensor_parallel_size=4)),
    dict(candidate=sera.Candidate(name='fp8', reason='not certified', config=sera.RuntimeConfig(tensor_parallel_size=2, kv_cache_dtype='fp8'))),
])
def test_incompatible_assignment_or_precision_rejected_before_runtime(monkeypatch, tmp_path, options):
    runners, _, _ = setup(monkeypatch)
    with pytest.raises(ValueError):
        run(tmp_path, 2, mode='fixed', **options)
    assert not runners


def test_explicit_fp8_space_rejected_before_baseline_or_agent(monkeypatch, tmp_path):
    runners, seen, agent = setup(monkeypatch)
    with pytest.raises(ValueError, match='BF16'):
        run(tmp_path, 2, agent=agent, provider_check='fixture', budget=sera.Budget(max_candidate_trials=None),
            investigation_space=sera.InvestigationSpace(supported_changes={'kv_cache_dtype': ['fp8']}))
    assert not runners and not seen


def test_three_investigator_swarm_uses_existing_loop_on_fixed_hardware(monkeypatch, tmp_path):
    from copy import deepcopy
    from sera.agent import ArbiterDecision, Proposal
    runners, _, base_agent = setup(monkeypatch)

    class Swarm(type(base_agent)):
        def fork(self):
            return Swarm()

        def request(self, role, evidence, instruction):
            self.history.append(dict(role=role, evidence=deepcopy(evidence)))
            if evidence.get('swarm_phase') == 'inspect':
                return ArbiterDecision(ranked_proposal_ids=[], reason='Current measured baseline is sufficient')
            if role == 'arbiter':
                return ArbiterDecision(ranked_proposal_ids=evidence['legal_proposal_ids'][:1], reason='Test a legal proposal')
            return Proposal(action='trial', proposal_id='batch', agent_role='batching',
                model_id=evidence['model_id'], parent_trial_id=evidence['trial_id'],
                changed_lever='max_num_batched_tokens',
                proposed_value=evidence['supported_changes']['max_num_batched_tokens'][0],
                evidence_used=['p95_latency_ms'], predicted_metric_change='Lower p95', confidence=.5,
                expected_trial_cost=1, falsification_condition='Quality fails or no gain', reason='Measured latency')

    with run(tmp_path, 4, agent=Swarm(), provider_check='fixture', swarm=True,
             trace_reader=lambda *_: {}, budget=sera.Budget(max_candidate_trials=None),
             investigation_space=sera.InvestigationSpace(supported_changes={'max_num_batched_tokens': [2048, 1024]})) as result:
        rounds = result.report['search']['rounds']
        assert len(rounds) == 2
        assert all(len(row['specialists']) == 3 for row in rounds)
        assert all(all(item['status'] == 'accepted' for item in row['specialists']) for row in rounds)
        assert result.report['search']['trials_used'] == 2
        assert result.models[0].configuration.tensor_parallel_size == 4
        assert all(trial['task_quality']['passed'] for trial in result.trials)
    assert not any(r.ready for r in runners)
