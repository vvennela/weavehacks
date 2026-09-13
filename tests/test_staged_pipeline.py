"""Real staged/swarm controller with synthetic GPU, provider, and trace boundaries.

These tests prove control flow and gates, not measured inference performance.
"""

import json
from copy import deepcopy

import pytest

import sera
from sera import api, pipeline
from sera.agent import ArbiterDecision, FrontierDecision, Proposal
from sera.config import CONTROL_ROLES, MODEL_ID
from sera.storage import content_hash


@pytest.fixture
def staged_boundaries(monkeypatch):
    state = {'runners': [], 'measurements': [], 'requests': [], 'trace_reads': [], 'stages': [],
                 'cache_latency': 90.0, 'cache_memory': 1700, 'cache_correct': True}

    class Runner:
        def __init__(self, *, artifact_dir, configuration, model_id, revision):
            self.artifact_dir = artifact_dir
            self.configuration = configuration
            self.ready = False
            self.record = {'configuration': configuration.model_dump(), 'model_id': model_id,
                'revision': revision, 'gpu': {'uuid': 'synthetic-single-gpu'},
                'versions': {'vllm': 'synthetic-version'}, 'sampled_peak_memory_mib': 2000,
                'telemetry_errors': 0, 'provenance': 'synthetic'}
            if artifact_dir.parent.name == '002-quantization':
                self.record['gpu']['uuid'] = state.get('second_stage_gpu', 'synthetic-single-gpu')
            state['runners'].append(self)

        def start(self):
            assert not any(runner.ready for runner in state['runners']), 'GPU owners overlap'
            self.ready = True

        def close(self):
            self.ready = False

        def _require_ready(self):
            assert self.ready

        def generate(self, prompt):
            self._require_ready()
            return '15' if prompt == '7+8' else '5'

    def collect(model, prompts, trial_id, *, baseline=False, workload):
        model._require_ready()
        config = model.configuration
        cache = config.kv_cache_dtype == 'fp8'
        latency = (state['cache_latency'] if cache else
                   {4096: 100.0, 2048: 98.0, 1024: 90.0}[config.max_num_batched_tokens])
        prefix = config.enable_prefix_caching
        if prefix:
            latency += state.get('prefix_latency_delta', 1.0)
        throughput = (state.get('prefix_throughputs', {}).get(config.max_num_batched_tokens, 120.0)
                      if prefix else 100.0)
        model.record['sampled_peak_memory_mib'] = state['cache_memory'] if cache else 2000
        output = {'prompt_index': 0, 'text': 'wrong' if cache and not state['cache_correct'] else '5',
                      'token_ids': [5], 'prompt_token_ids': [1, 2], 'error': None}
        if prefix and not state.get('prefix_correct', True):
            output['text'] = 'wrong'
        state['measurements'].append({'folder': str(model.artifact_dir), 'baseline': baseline,
            'configuration': config.model_dump(), 'workload': workload.model_dump()})
        tokens = (state.get('second_stage_tokens', [[1, 2]])
                  if model.artifact_dir.parent.name == '002-quantization' else [[1, 2]])
        return {'trial_id': trial_id, 'status': 'collected', 'config_hash': config.config_hash,
            'runtime': model.record, 'input_token_ids': tokens, 'quality': [output],
            'self_check': [deepcopy(output)] if baseline else [], 'loads': [], 'metrics': {},
            'provenance': 'synthetic', 'reduced': {'p95_latency_ms': latency,
                'output_tokens_per_second': throughput, 'generation_errors': 0}}

    class Agent:
        model, project = 'synthetic-stage-agent', 'offline/stage-test'

        def __init__(self):
            self.history = []

        def fork(self):
            return Agent()

        def request(self, role, evidence, instruction):
            state['requests'].append((role, deepcopy(evidence)))
            self.history.append({'role': role, 'evidence': deepcopy(evidence), 'provenance': 'synthetic'})
            if role == 'arbiter':
                return ArbiterDecision(ranked_proposal_ids=evidence['legal_proposal_ids'][:1],
                    reason='Read a saved fixture trace or select one typed experiment')
            history = evidence['history']
            quantization = evidence.get('investigation_controls') == ['kv_cache_dtype']
            target = ({'kv_cache_dtype': 'fp8'} if quantization else
                      {'max_num_batched_tokens': 2048 if not history else 1024})
            done = (bool(history) if quantization else len(history) >= 2)
            if evidence['objective']['priority'] == 'throughput':
                target = {'enable_prefix_caching': True}
                done = bool(history)
            option = None if done else next((item for item in evidence['candidate_options']
                if item['changed'] == target and item['parent_trial_id'] == 'baseline'), None)
            lever, value = next(iter(target.items()))
            return Proposal(action='keep-baseline' if option is None else 'trial',
                proposal_id='synthetic-option', agent_role=CONTROL_ROLES[lever],
                parent_trial_id='baseline', model_id=MODEL_ID,
                changed_lever=lever if option is not None else None,
                proposed_value=value if option is not None else None,
                evidence_used=['p95_latency_ms'], confidence=.5,
                expected_trial_cost=1 if option is not None else 0,
                predicted_metric_change='Synthetic positive gain, subject to the declared objective gate',
                falsification_condition='Quality fails, inherited latency exceeds its 3% allowance, or gain fails its own threshold',
                reason='Use the recorded synthetic measurements; this does not predict a real speedup')

        def review(self, evidence):
            response = FrontierDecision(selected_trial_id=evidence['eligible_trial_ids'][0],
                prediction_outcome='confirmed' if evidence['decision']['selected'] == 'candidate' else 'refuted',
                reason='Use the deterministic measured gate, not the agent prediction')
            self.history.append({'role': 'frontier', 'response': response.model_dump()})
            return response

    def trace_reader(query_id, evidence):
        state['trace_reads'].append((query_id, deepcopy(evidence)))
        return {'provenance': 'synthetic-saved-trace', 'query_id': query_id,
                    'history': deepcopy(evidence['history'])}

    def run_traced(arguments):
        state['stages'].append(deepcopy({key: arguments[key] for key in
            ('output_dir', 'constraints', 'objective', 'baseline_configuration', 'investigation_controls')
            if key in arguments}))
        return pipeline.optimize(**(arguments | {'trace_reader': trace_reader}))

    monkeypatch.setattr(pipeline, 'SeraModel', Runner)
    monkeypatch.setattr(pipeline, 'collect_trial', collect)
    monkeypatch.setattr(api, '_run_traced', run_traced)
    monkeypatch.setattr(api, '_configured_agent', Agent)
    monkeypatch.setattr('sera.provider_check.require_provider_check', lambda *_: {'synthetic': True})
    monkeypatch.setenv('WANDB_API_KEY', 'offline-test-not-a-secret')
    monkeypatch.setenv('SERA_PROVIDER_CHECK', '/synthetic/certificate')
    return state


def run_stages(tmp_path, min_improvement_pct=None):
    options = {} if min_improvement_pct is None else {'min_improvement_pct': min_improvement_pct}
    return sera.optimize(models=[MODEL_ID], prompts=['2+3'], stages=['latency', 'quantization'],
        k=3.0, output_dir=tmp_path/'stages',
        evaluation=lambda prompt, output: output == '5', evaluation_version='synthetic-stages-v1',
        constraints=sera.Constraints(quality_floor=.99), **options)


@pytest.mark.parametrize('cache_latency,cache_memory,cache_correct,expected_cache,expected_reason,min_gain', [
    (90.9, 1960, True, 'fp8', None, None),
    (90.0, 2000, True, 'auto', 'objective-improvement-below-threshold', None),
    (93.6, 1700, True, 'auto', 'candidate-constraints-failed', None),
    (80.0, 1700, False, 'auto', 'candidate-constraints-failed', None),
    (90.0, 1970, True, 'auto', 'objective-improvement-below-threshold', 3.0),
])
def test_real_ordered_pipeline_rebases_runs_swarm_and_gates_candidates(
        tmp_path, staged_boundaries, cache_latency, cache_memory, cache_correct, expected_cache, expected_reason, min_gain):
    state = staged_boundaries
    state.update(cache_latency=cache_latency, cache_memory=cache_memory, cache_correct=cache_correct)
    with run_stages(tmp_path, min_improvement_pct=min_gain) as result:
        assert result.report['status'] == 'ready'
        assert len(result.checkpoints) == 2
        first, second = result.checkpoints
        assert first['configuration']['max_num_batched_tokens'] == 1024
        assert first['p95_latency_ms'] == 90.0
        assert second['configuration']['max_num_batched_tokens'] == 1024
        assert second['configuration']['kv_cache_dtype'] == expected_cache
        assert state['stages'][1]['baseline_configuration'].model_dump() == first['configuration']
        assert state['stages'][1]['constraints'].p95_latency_ms == pytest.approx(92.7)
        assert all(stage['objective'].min_improvement_fraction == (min_gain or 0.0) / 100
                   for stage in state['stages'])
        baselines = [item for item in state['measurements'] if item['baseline']]
        assert len(baselines) == 2
        assert baselines[1]['configuration'] == first['configuration']
        assert baselines[1]['folder'].endswith('002-quantization/baseline')
        assert all(item['workload']['concurrency'] == [1, 2, 4, 8] for item in state['measurements'])
        first_report = json.loads((tmp_path/'stages/001-latency/result.json').read_text())
        first_decision = first_report['search_trials'][0]['decision']
        assert first_decision['objective_improvement_fraction'] == pytest.approx(.02)
        if min_gain is None:
            assert first_decision['selected'] == 'candidate'
            assert first_decision['outcome'] == 'improved'
        else:
            assert first_decision['reason'] == 'objective-improvement-below-threshold'
            assert first_decision['selected'] == 'baseline'
        assert first_report['decision']['selected'] == 'trial-2'
        assert first_report['returned_runner_closed'] is True
        second_report = json.loads((tmp_path/'stages/002-quantization/result.json').read_text())
        assert second_report['baseline']['config_hash'] == first['config_hash']
        assert second_report['search']['trials_used'] == 1
        assert second_report['investigation_controls'] == ['kv_cache_dtype']
        if expected_reason:
            assert second_report['search_trials'][0]['decision']['reason'] == expected_reason
            assert second_report['decision']['selected'] == 'baseline'
        else:
            assert second_report['decision']['selected'] == 'trial-1'
        for stage_report in (first_report, second_report):
            assert stage_report['swarm_enabled'] is True
            assert stage_report['search']['budget']['max_candidate_trials'] is None
            assert all(len(record['swarm']['investigators']) == 3 for record in stage_report['search']['rounds'])
        for _, evidence in state['requests']:
            if evidence.get('investigation_controls') == ['kv_cache_dtype']:
                assert set(evidence['supported_changes']) == {'kv_cache_dtype'}
                assert all(option['changed'] == {'kv_cache_dtype': 'fp8'}
                           for option in evidence['candidate_options'])
        assert state['trace_reads']
        assert result.models[0].generate('7+8') == '15'
        assert sum(runner.ready for runner in state['runners']) == 1
        for index, checkpoint in enumerate(result.checkpoints, 1):
            saved = json.loads((tmp_path/f'stages/checkpoints/{index:03d}.json').read_text())
            assert saved == checkpoint
            assert saved['checkpoint_hash'] == content_hash({key: value for key, value in saved.items()
                                                             if key != 'checkpoint_hash'})
    assert not any(runner.ready for runner in state['runners'])
    saved = json.loads((tmp_path/'stages/result.json').read_text())
    assert saved['status'] == 'closed' and saved['returned_runner_closed'] is True
    assert len(saved['checkpoints']) == 2
    rendered = (tmp_path/'stages/report.md').read_text()
    assert 'Stage 1: latency; completed' in rendered
    assert 'Stage 2: quantization; completed' in rendered
    assert '3.0%' in rendered


@pytest.mark.parametrize('change', [
    {'second_stage_gpu': 'different-synthetic-gpu'},
    {'second_stage_tokens': [[3, 4]]},
])
def test_checkpoint_scope_drift_closes_runner_and_preserves_only_valid_checkpoint(
        tmp_path, staged_boundaries, change):
    state = staged_boundaries
    state.update(change)
    with pytest.raises(RuntimeError, match='workload or runtime identity changed'):
        run_stages(tmp_path)
    assert not any(runner.ready for runner in state['runners'])
    saved = json.loads((tmp_path/'stages/result.json').read_text())
    assert saved['status'] == 'failed'
    assert saved['returned_runner_closed'] is True
    assert len(saved['checkpoints']) == 1
    assert saved['stages'][0]['status'] == 'completed'
    assert saved['stages'][1]['status'] == 'failed'
    assert (tmp_path/'stages/checkpoints/001.json').is_file()
    assert not (tmp_path/'stages/checkpoints/002.json').exists()


@pytest.mark.parametrize('delta,correct,expected_prefix', [(1, True, True),
    (4, True, False), (1, False, False)])
def test_latency_then_throughput_keeps_latency_and_quality_gates(
        tmp_path, staged_boundaries, delta, correct, expected_prefix):
    staged_boundaries.update(prefix_latency_delta=delta, prefix_correct=correct)
    with sera.optimize(models=[MODEL_ID], prompts=['2+3'], stages=['latency', 'throughput'],
        k=3, output_dir=tmp_path/'stages', evaluation=lambda prompt, output: output == '5',
        evaluation_version='synthetic-stages-v1', constraints=sera.Constraints(quality_floor=.99)) as result:
        assert result.report['status'] == 'ready'
        first, second = result.checkpoints
        assert first['p95_latency_ms'] == 90
        assert second['constraints']['p95_latency_ms'] == pytest.approx(92.7)
        assert second['configuration']['enable_prefix_caching'] is expected_prefix
        assert second['output_tokens_per_second'] == (120 if expected_prefix else 100)
        stage = json.loads((tmp_path/'stages/002-throughput/result.json').read_text())
        assert stage['search']['trials_used'] == 1
        assert stage['search_trials'][0]['decision']['selected'] == ('candidate' if expected_prefix else 'baseline')


@pytest.mark.parametrize('throughput,expected_tokens', [(117, 1024), (110, 2048)])
def test_repeated_throughput_then_latency_preserves_floor(
        tmp_path, staged_boundaries, throughput, expected_tokens):
    staged_boundaries['prefix_throughputs'] = {1024: throughput}
    with sera.optimize(models=[MODEL_ID], prompts=['2+3'],
        stages=['throughput', 'throughput', 'latency'], k=3, output_dir=tmp_path/'stages',
        evaluation=lambda prompt, output: output == '5', evaluation_version='synthetic-stages-v1',
        constraints=sera.Constraints(quality_floor=.99)) as result:
        assert result.report['status'] == 'ready'
        assert len(result.checkpoints) == 3
        assert result.checkpoints[-1]['configuration']['max_num_batched_tokens'] == expected_tokens
        for checkpoint in result.checkpoints[1:]:
            assert checkpoint['constraints']['min_output_tokens_per_second'] == pytest.approx(116.4)
        stage = json.loads((tmp_path/'stages/003-latency/result.json').read_text())
        last = stage['search_trials'][-1]['decision']
        assert last['selected'] == ('candidate' if throughput == 117 else 'baseline')
        if throughput == 110:
            assert 'throughput-requirement-failed' in last['constraint_failures']['candidate']
