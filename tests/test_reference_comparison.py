from copy import deepcopy
from pathlib import Path
import json

import pytest

import sera
from sera.config import LARGE_MODEL_ID, LARGE_MODEL_REVISION
from sera import pipeline


@pytest.mark.parametrize('candidate_latency,selected', [(50.0, 'candidate'), (200.0, 'baseline')])
def test_large_comparison_preserves_model_precision_loads_and_returned_runner(tmp_path, monkeypatch,
                                                                           candidate_latency, selected):
    reference = json.loads(Path('evidence/large-fit-v1/result.json').read_text())['candidate_trial']
    runners = []
    measured_loads = []

    class Runner:
        def __init__(self, *, artifact_dir, configuration, model_id, revision):
            assert model_id == LARGE_MODEL_ID and revision == LARGE_MODEL_REVISION
            assert configuration.quantization == 'fp8_per_tensor'
            self.configuration = configuration
            self.artifact_dir = artifact_dir
            self.record = {'configuration': configuration.model_dump(), 'model_id': model_id,
                           'revision': revision, 'sampled_peak_memory_mib': 88449}
            self.ready = False
            runners.append(self)

        def start(self):
            self.ready = True

        def close(self):
            self.ready = False

        def _require_ready(self):
            assert self.ready

    def collect(model, prompts, trial_id, *, workload, baseline=False):
        measured_loads.append(workload.concurrency)
        trial = deepcopy(reference)
        trial.update(trial_id=trial_id, runtime=model.record)
        trial['self_check'] = deepcopy(trial['quality'])
        trial['reduced']['p95_latency_ms'] = 100.0 if baseline else candidate_latency
        return trial

    monkeypatch.setattr(pipeline, 'SeraModel', Runner)
    monkeypatch.setattr(pipeline, 'collect_trial', collect)
    with sera.optimize(models=[LARGE_MODEL_ID], prompts=['test'] * 8,
                       output_dir=tmp_path/'comparison',
                       baseline_configuration=sera.RuntimeConfig(quantization='fp8_per_tensor'),
                       evaluation=lambda prompt, output: True, evaluation_version='fixture-v1',
                       constraints=sera.Constraints(quality_floor=.99),
                       workload=sera.Workload(concurrency=[1, 2, 4, 8])) as result:
        assert result.report['decision']['selected'] == selected
        assert measured_loads == [[1, 2, 4, 8], [1, 2, 4, 8]]
        assert result.report['baseline_name'] == 'sera-fp8-weight-reference-v1'
        assert result.models[0].ready
        assert sum(runner.ready for runner in runners) == 1
        expected_batch = 2048 if selected == 'candidate' else 4096
        assert result.models[0].configuration.max_num_batched_tokens == expected_batch
    assert not any(runner.ready for runner in runners)


def test_unchecked_large_weight_and_cache_combination_is_rejected_before_execution(tmp_path):
    with pytest.raises(ValueError, match='Combined FP8'):
        sera.optimize(models=[LARGE_MODEL_ID], prompts=['test'], output_dir=tmp_path/'rejected',
                      baseline_configuration=sera.RuntimeConfig(quantization='fp8_per_tensor'),
                      candidate=sera.Candidate(name='unverified', reason='unsupported combination',
                          config=sera.RuntimeConfig(quantization='fp8_per_tensor', kv_cache_dtype='fp8')),
                      evaluation=lambda prompt, output: True, evaluation_version='fixture-v1',
                      constraints=sera.Constraints(quality_floor=.99))
    assert not (tmp_path/'rejected').exists()
