import pytest

from sera import Constraints
from sera.config import LARGE_MODEL_ID, LARGE_MODEL_REVISION, RuntimeConfig
from sera.fit import fit_review_evidence, plan_fit
from sera.measurement import measured_frontier, select_candidate
from sera.runtime import SeraModel


def test_large_model_bf16_is_rejected_before_loading_but_fp8_is_a_fit_candidate():
    plan = plan_fit(gpu_memory_mib=97887)
    assert plan['model_id'] == LARGE_MODEL_ID
    assert plan['revision'] == LARGE_MODEL_REVISION
    baseline, fp8 = plan['plans']
    assert baseline['weights_bytes'] > 97887 * 1024**2
    assert not baseline['estimated_fit']
    assert fp8['estimated_fit']
    assert fp8['configuration']['quantization'] == 'fp8_per_tensor'
    assert fp8['measurement_status'] == 'not-measured'
    assert plan['download_bytes'] == 72706203648 * 2


def test_smaller_gpu_rejects_both_plans_without_starting_a_model():
    assert not any(p['estimated_fit'] for p in plan_fit(gpu_memory_mib=24576)['plans'])


@pytest.mark.parametrize('memory', [0, -1, True, '97887'])
def test_fit_requires_valid_hardware_memory(memory):
    with pytest.raises(ValueError):
        plan_fit(gpu_memory_mib=memory)


def test_fit_runtime_requires_the_pinned_model_revision(tmp_path):
    with pytest.raises(ValueError):
        SeraModel(artifact_dir=tmp_path/'wrong', model_id=LARGE_MODEL_ID, revision='main')
    runner = SeraModel(artifact_dir=tmp_path/'correct', model_id=LARGE_MODEL_ID,
                       revision=LARGE_MODEL_REVISION,
                       configuration=RuntimeConfig(quantization='fp8_per_tensor'))
    assert runner.model_id == LARGE_MODEL_ID


def test_glm_runner_requires_its_pinned_revision(tmp_path):
    from sera.config import GLM_MODEL_ID, GLM_MODEL_REVISION
    with pytest.raises(ValueError):
        SeraModel(artifact_dir=tmp_path/'wrong-glm', model_id=GLM_MODEL_ID, revision='main')
    runner = SeraModel(artifact_dir=tmp_path/'glm', model_id=GLM_MODEL_ID, revision=GLM_MODEL_REVISION)
    assert runner.model_id == GLM_MODEL_ID


def test_verified_candidate_needs_no_output_reference_from_an_infeasible_baseline():
    baseline = {'trial_id': 'baseline', 'status': 'infeasible'}
    candidate = {'trial_id': 'candidate', 'status': 'collected', 'input_token_ids': [[1]],
                 'task_quality': {'valid_outputs': True, 'mean': 1.0},
                 'runtime': {'sampled_peak_memory_mib': 80000},
                 'reduced': {'p95_latency_ms': 100.0, 'output_tokens_per_second': 50.0}}
    constraints = Constraints(quality_floor=.99)
    decision = select_candidate(baseline, candidate, constraints=constraints)
    assert decision['selected'] == 'candidate'
    assert decision['outcome'] == 'feasible'
    assert decision['p95_improvement_fraction'] is None
    assert measured_frontier(baseline, candidate, constraints=constraints) == [candidate]


@pytest.mark.parametrize('selected,status', [('candidate', 'collected'), (None, 'startup-failed')])
def test_fit_review_assesses_deployment_not_an_unmeasured_speedup(selected, status):
    decision = {'selected': selected, 'outcome': 'feasible' if selected else 'no-safe-configuration'}
    trial = {'status': status, 'runtime': {'sampled_peak_memory_mib': 88449},
             'task_quality': {'mean': 1.0 if selected else 0.0, 'passed': bool(selected)},
             'reduced': {'p95_latency_ms': 573.0} if selected else None}
    feedback = fit_review_evidence({'plan_id': 'weight-fp8'}, trial, decision)
    assert feedback['prediction']['kind'] == 'deployment-feasibility'
    assert feedback['candidate_tested'] is True
    assert feedback['candidate_status'] == status
    assert feedback['candidate_task_quality'] == trial['task_quality']
    assert feedback['candidate_peak_memory_mib'] == 88449
    assert feedback['baseline_measured'] is False
    assert feedback['speedup_claim_allowed'] is False
    assert feedback['eligible_trial_ids'] == [selected or 'no-safe-configuration']
