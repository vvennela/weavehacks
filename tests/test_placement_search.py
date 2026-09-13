"""Autonomous selection uses measured eligible plans; all GPU/provider calls are fake."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from sera.agent import ArbiterDecision
from sera.config import Budget, Objective
from sera.placement_config import validate_placement_plan
from test_placement import environment, inputs, MODEL_ID, GLM_MODEL_ID


class Agent:
    model, project, provider = 'fixture', 'test/project', 'fixture'
    def __init__(self, choices=None):
        self.history = []
        self.choices = iter(choices) if choices is not None else None
    def request(self, role, evidence, instruction):
        assert role == 'arbiter'
        index = next(self.choices) if self.choices is not None else 0
        choice = [] if index is None else [evidence['legal_proposal_ids'][index]]
        self.history.append(dict(evidence=deepcopy(evidence), instruction=instruction))
        return ArbiterDecision(ranked_proposal_ids=choice, reason='Select a supplied measured plan; joint performance remains untested.')


@pytest.fixture
def search_inputs(environment, monkeypatch, tmp_path):
    import sera.placement_search as search
    base = inputs(environment)
    plans, references, estimates = [], {}, {}
    for index in range(4):
        data = deepcopy(base['plan'])
        data['services'][0]['configuration']['max_num_batched_tokens'] = 4096 + 1024*index
        plan = validate_placement_plan(data)
        plans.append(plan)
        folder = tmp_path/f'reference-{index}'
        environment.measure_placement_references(**(base | dict(plan=plan, output_dir=folder)))
        references[plan.plan_hash] = folder/'result.json'
        estimates[plan.plan_hash] = base['memory_estimates']
    monkeypatch.setattr(search, 'require_provider_check', lambda path, agent:dict(schema_hash='checked-schema'))
    args = dict(plans=plans, workloads=base['workloads'], memory_estimates=estimates,
                isolated_references=references, agent=Agent(), provider_check='fixture',
                output_dir=tmp_path/'search')
    return search, args


def execution_stub(search, monkeypatch, latencies, *, failures=()):
    live = []
    starts = []
    values = iter(latencies)
    class Result:
        def __init__(self, plan, folder, value):
            self.plan_id = plan.plan_hash
            self.output_dir = Path(folder)
            self.closed = False
            self.models = [SimpleNamespace(model_id=MODEL_ID), SimpleNamespace(model_id=GLM_MODEL_ID)]
            gate = self.plan_id not in failures
            if not gate:
                self.models = []
            self.report = dict(status='ready' if gate else 'rejected',
                decision=dict(outcome='safe-placement' if gate else 'no-safe-placement', reason='fixture'),
                plan_hash=plan.plan_hash, shared_runtime=dict(sampled_peak_memory_mib=100, errors=[]),
                joint=dict(gates={m:dict(passed=gate) for m in (MODEL_ID, GLM_MODEL_ID)},
                           trials={m:dict(reduced=dict(p95_latency_ms=value, output_tokens=100),
                                         quality=[]) for m in (MODEL_ID, GLM_MODEL_ID)},
                           overlap=[dict(windows={MODEL_ID:dict(started=1., ended=2.),
                                                  GLM_MODEL_ID:dict(started=1., ended=2.)})]))
        def close(self):
            self.closed = True
            self.report['status'] = 'closed'
        def _save(self):
            pass
    def execute(**kwargs):
        assert all(result.closed or not result.models for result in live), 'old GPU pair must close first'
        result = Result(kwargs['plan'], kwargs['output_dir'], next(values))
        starts.append(kwargs['plan'].plan_hash)
        live.append(result)
        return result
    monkeypatch.setattr(search, 'place', execute)
    return starts, live


def test_plateau_allows_one_confirmation_then_restores_validated_best(search_inputs, monkeypatch):
    search, args = search_inputs
    starts, live = execution_stub(search, monkeypatch, [100., 110., 120., 100.])
    result = search.optimize_placement(**args)
    assert result.report['stop_reason'] == 'objective-plateau-confirmed'
    assert len(result.report['trials']) == 3
    assert starts == [args['plans'][0].plan_hash, args['plans'][1].plan_hash,
                      args['plans'][2].plan_hash, args['plans'][0].plan_hash]
    assert result.report['budget']['max_candidate_trials'] is None
    assert result.report['restoration']['status'] == 'ready'
    assert len(result.models) == 2
    assert args['agent'].history[1]['evidence']['history'][0]['objective_value'] == 100.
    result.close()
    assert all(pair.closed for pair in live)


def test_qualifying_progress_resets_confirmation_and_returns_current_best(search_inputs, monkeypatch):
    search, args = search_inputs
    starts, live = execution_stub(search, monkeypatch, [100., 110., 90., 80.])
    result = search.optimize_placement(**args)
    assert result.report['stop_reason'] == 'no-legal-plans'
    assert len(starts) == 4
    assert result.report['selected_plan_id'] == args['plans'][3].plan_hash
    assert 'restoration' not in result.report
    assert len(result.models) == 2
    result.close()


def test_explicit_budget_counts_failed_joint_trials(search_inputs, monkeypatch):
    search, args = search_inputs
    first = args['plans'][0].plan_hash
    starts, _ = execution_stub(search, monkeypatch, [100., 100.], failures={first})
    result = search.optimize_placement(**args, budget=Budget(max_candidate_trials=2))
    assert len(starts) == 2
    assert result.report['stop_reason'] == 'explicit-trial-budget'
    assert result.report['selected_plan_id'] == args['plans'][1].plan_hash
    result.close()


def test_agent_abstention_starts_no_gpu_plan(search_inputs, monkeypatch):
    search, args = search_inputs
    args['agent'] = Agent(choices=[None])
    monkeypatch.setattr(search, 'place', lambda **_:pytest.fail('Abstention must not start a GPU'))
    result = search.optimize_placement(**args)
    assert result.models == []
    assert result.report['stop_reason'] == 'agent-abstained'


def test_unknown_agent_plan_id_is_rejected_before_gpu(search_inputs, monkeypatch):
    search, args = search_inputs
    args['agent'].request = lambda *args:ArbiterDecision(ranked_proposal_ids=['invented'], reason='invalid')
    monkeypatch.setattr(search, 'place', lambda **_:pytest.fail('Unknown plan must not start'))
    result = search.optimize_placement(**args)
    assert result.report['stop_reason'] == 'invalid-agent-decision'
    assert result.models == []


def test_reference_quality_is_recomputed_before_plan_reaches_agent(search_inputs, monkeypatch):
    import json
    search, args = search_inputs
    bad_id = args['plans'][0].plan_hash
    path = args['isolated_references'][bad_id]
    record = json.loads(path.read_text())
    record['isolated'][MODEL_ID]['quality'][0]['text'] = 'wrong'
    path.write_text(json.dumps(record))
    args['agent'] = Agent(choices=[None])
    result = search.optimize_placement(**args)
    assert bad_id not in args['agent'].history[0]['evidence']['legal_proposal_ids']
    assert result.report['rejected'][0]['plan_id'] == bad_id


def test_measured_search_with_real_executor_has_distinct_trial_trace_ids(search_inputs):
    search, args = search_inputs
    result = search.optimize_placement(**args)
    assert result.report['stop_reason'] == 'objective-plateau-confirmed'
    ids = [trial['report']['joint']['trials'][GLM_MODEL_ID]['trial_id'] for trial in result.report['trials']]
    assert ids == ['trial-001/joint', 'trial-002/joint', 'trial-003/joint']
    assert result.report['restoration']['joint']['trials'][GLM_MODEL_ID]['trial_id'] == 'return-validation/joint'
    assert all('/search/references/' in trial['report']['isolated_reference']['path'] for trial in result.report['trials'])
    assert len(result.models) == 2
    result.close()


def test_failed_restoration_cannot_return_an_old_passing_record(search_inputs, monkeypatch):
    search, args = search_inputs
    _, live = execution_stub(search, monkeypatch, [100., 110., 120., None])
    result = search.optimize_placement(**args)
    assert result.models == []
    assert result.report['status'] == 'no-safe-placement'
    assert result.report['return_failure'] == 'restoration-requirements-failed'
    assert all(pair.closed for pair in live)


def test_marginal_improvement_does_not_reset_plateau_but_best_measured_pair_is_kept(search_inputs, monkeypatch):
    search, args = search_inputs
    starts, _ = execution_stub(search, monkeypatch, [100., 98., 97.])
    result = search.optimize_placement(**args)
    assert len(starts) == 3
    assert result.report['stop_reason'] == 'objective-plateau-confirmed'
    assert result.report['selected_plan_id'] == args['plans'][2].plan_hash
    assert [trial['qualifying_progress'] for trial in result.report['trials']] == [True, False, False]
    result.close()


def test_provider_certificate_failure_starts_no_joint_or_agent_call(search_inputs, monkeypatch):
    search, args = search_inputs
    def reject(*args):
        raise ValueError('certificate mismatch')
    monkeypatch.setattr(search, 'require_provider_check', reject)
    monkeypatch.setattr(search, 'place', lambda **_:pytest.fail('must not start'))
    with pytest.raises(ValueError, match='certificate'):
        search.optimize_placement(**args)
    assert not args['agent'].history


def test_changed_quality_contract_cannot_enter_candidate_universe(search_inputs):
    search, args = search_inputs
    changed = args['plans'][1].model_dump()
    changed['services'][0]['constraints']['quality_floor'] = .5
    replacement = validate_placement_plan(changed)
    old = args['plans'][1].plan_hash
    args['plans'][1] = replacement
    args['memory_estimates'][replacement.plan_hash] = args['memory_estimates'].pop(old)
    args['isolated_references'][replacement.plan_hash] = args['isolated_references'].pop(old)
    with pytest.raises(ValueError, match='requirements'):
        search.optimize_placement(**args)
    assert not args['agent'].history


def test_estimated_infeasible_bf16_plan_is_visible_to_agent_but_not_executable(search_inputs, monkeypatch):
    search, args = search_inputs
    baseline = args['plans'][0]
    quantized_data = baseline.model_dump()
    quantized_data['services'][1]['configuration']['quantization'] = 'fp8_per_tensor'
    quantized = validate_placement_plan(quantized_data)
    # Use the real isolated-only executor for a valid synthetic quantized reference.
    from sera.placement import measure_placement_references
    reference_folder = Path(args['output_dir']).parent/'quantized-reference'
    estimates = args['memory_estimates'][baseline.plan_hash]
    measure_placement_references(plan=quantized, workloads=args['workloads'], memory_estimates=estimates,
                                 output_dir=reference_folder)
    huge = {model:value for model,value in estimates.items()}
    huge[GLM_MODEL_ID] = huge[GLM_MODEL_ID].model_copy(update={'weights_bytes':600*1024**2})
    args.update(plans=[baseline, quantized],
        memory_estimates={baseline.plan_hash:huge, quantized.plan_hash:estimates},
        isolated_references={baseline.plan_hash:None, quantized.plan_hash:reference_folder/'result.json'})
    starts, _ = execution_stub(search, monkeypatch, [100.])
    result = search.optimize_placement(**args)
    evidence = args['agent'].history[0]['evidence']
    assert evidence['legal_proposal_ids'] == [quantized.plan_hash]
    rejected = evidence['rejected_plans'][0]
    assert rejected['plan_id'] == baseline.plan_hash
    assert rejected['reason'] == 'estimated-memory-does-not-fit'
    assert rejected['measurement_status'] == 'not-measured'
    assert rejected['fit_check'][GLM_MODEL_ID]['required_bytes'] > rejected['fit_check'][GLM_MODEL_ID]['allocation_bytes']
    assert starts == [quantized.plan_hash]
    proof = result.report['capacity_evidence']
    assert proof['established'] is True
    assert proof['unquantized_failure_basis'] == 'deterministic-estimate-not-measured'
    assert proof['measured_memory_savings_bytes'] is None
    assert result.report['quantization_enabled_placement'] is True
    result.close()
