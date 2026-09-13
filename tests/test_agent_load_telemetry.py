"""Keep actual vLLM snapshots visible without treating them as load-window metrics."""

from copy import deepcopy

import pytest

from sera.config import MODEL_ID, MODEL_REVISION, RuntimeConfig
from sera.investigation import round_evidence
from sera.metrics import parse_vllm_metrics
from sera.pipeline import agent_evidence


# Exact samples from live-investigation-v1/baseline/
# metrics-concurrency-1-after-measurement.prom. The original record is not rewritten.
LIVE_AFTER_SAMPLES = '''vllm:num_preemptions_total{engine="0",model_name="sera-model"} 0.0
vllm:time_to_first_token_seconds_count{engine="0",model_name="sera-model"} 32.0
vllm:time_to_first_token_seconds_sum{engine="0",model_name="sera-model"} 4.371091365814209
vllm:request_queue_time_seconds_count{engine="0",model_name="sera-model"} 32.0
vllm:request_queue_time_seconds_sum{engine="0",model_name="sera-model"} 0.00019441500057837402
'''


def trial_record():
    after = parse_vllm_metrics(LIVE_AFTER_SAMPLES, 'sera-model')
    other_after = dict(after, mean_ttft_ms=250.0, mean_queue_ms=2.0, preemptions=3.0)
    output = {'prompt_index': 0, 'text': 'answer', 'token_ids': [1], 'prompt_token_ids': [2]}
    config = RuntimeConfig()
    return {'trial_id': 'baseline', 'status': 'collected', 'config_hash': config.config_hash,
            'runtime': {'configuration': config.model_dump(), 'model_id': MODEL_ID,
                        'revision': MODEL_REVISION, 'sampled_peak_memory_mib': 2000},
            'quality': [output], 'self_check': [deepcopy(output)],
            'reduced': {'p95_latency_ms': 773.543, 'output_tokens_per_second': 26.135,
                        'p95_ttft_ms': None, 'p95_queue_ms': None,
                        'p95_time_per_output_token_ms': None},
            'metrics': {'concurrency-1-after-measurement': after,
                        'concurrency-2-after-measurement': other_after},
            'loads': [{'concurrency': 1, 'metrics': {'after-measurement': after}},
                      {'concurrency': 2, 'metrics': {'after-measurement': other_after}}]}


def test_parsed_load_snapshots_reach_agent_with_explicit_cumulative_names():
    trial = trial_record()
    original = deepcopy(trial)
    evidence = agent_evidence(trial)
    metrics = evidence['metrics']
    assert metrics['concurrency_1_cumulative_snapshot_mean_ttft_ms'] == pytest.approx(136.59660518169403)
    assert metrics['concurrency_1_cumulative_snapshot_mean_queue_ms'] == pytest.approx(0.006075468768074188)
    assert metrics['concurrency_1_cumulative_snapshot_preemptions'] == 0.0
    assert metrics['concurrency_2_cumulative_snapshot_mean_ttft_ms'] == 250.0
    assert metrics['concurrency_2_cumulative_snapshot_mean_queue_ms'] == 2.0
    assert metrics['concurrency_2_cumulative_snapshot_preemptions'] == 3.0
    # There is no invented aggregate or replacement of measured client metrics.
    assert metrics['mean_ttft_ms'] is None
    assert metrics['mean_queue_ms'] is None
    assert metrics['preemptions'] is None
    for key, value in trial['reduced'].items():
        assert metrics[key] == value
    assert trial == original
    assert any('cumulative' in note and 'warmup' in note and 'earlier loads' in note
               for note in evidence['limitations'])


def test_later_trial_history_carries_same_load_fields_without_changing_baseline():
    baseline = trial_record()
    initial = agent_evidence(baseline)
    initial_copy = deepcopy(initial)
    candidate = trial_record()
    candidate['trial_id'] = 'trial-1'
    candidate['loads'][0]['metrics']['after-measurement']['mean_ttft_ms'] = 150.0
    history = round_evidence(initial, {'rounds': []}, [candidate], remaining=1)
    metrics = history['metrics']
    assert metrics['trial_1_concurrency_1_cumulative_snapshot_mean_ttft_ms'] == 150.0
    assert metrics['trial_1_concurrency_1_cumulative_snapshot_preemptions'] == 0.0
    assert metrics['trial_1_concurrency_2_cumulative_snapshot_mean_queue_ms'] == 2.0
    assert metrics['trial_1_p95_latency_ms'] == candidate['reduced']['p95_latency_ms']
    assert metrics['trial_1_p95_ttft_ms'] is None
    assert metrics['concurrency_1_cumulative_snapshot_mean_ttft_ms'] == initial['metrics'][
        'concurrency_1_cumulative_snapshot_mean_ttft_ms']
    assert initial == initial_copy


def test_missing_load_snapshot_stays_none_and_zero_remains_available():
    trial = trial_record()
    trial['loads'][0]['metrics']['after-measurement']['mean_queue_ms'] = 0.0
    trial['loads'][1]['metrics'] = {'after-measurement': {'unavailable': 'fixture scrape failure'}}
    metrics = agent_evidence(trial)['metrics']
    assert metrics['concurrency_1_cumulative_snapshot_mean_queue_ms'] == 0.0
    assert metrics['concurrency_1_cumulative_snapshot_preemptions'] == 0.0
    for name in ('mean_ttft_ms', 'mean_queue_ms', 'preemptions'):
        assert metrics[f'concurrency_2_cumulative_snapshot_{name}'] is None


def test_legacy_unprefixed_snapshot_aliases_still_work():
    trial = trial_record()
    snapshot = trial['loads'][0]['metrics']['after-measurement']
    trial.pop('loads')
    trial['metrics'] = {'after-measurement': snapshot}
    metrics = agent_evidence(trial)['metrics']
    for name in ('mean_ttft_ms', 'mean_queue_ms', 'preemptions'):
        assert metrics[name] == snapshot[name]
    assert metrics['p95_ttft_ms'] is None
    assert not any(key.startswith('concurrency_') for key in metrics)
