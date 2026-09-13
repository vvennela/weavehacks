from pathlib import Path
import threading
import time

import pytest

from sera.config import RuntimeConfig, Workload
from sera.measurement import collect_trial, reduce_loads
from sera.pipeline import render_summary


@pytest.mark.parametrize('loads', [[], [0], [True], [2, 1], [1, 1], [9]])
def test_workload_rejects_invalid_or_ambiguous_loads(loads):
    with pytest.raises(ValueError):
        Workload(concurrency=loads)


def test_sweep_uses_worst_load_latency_without_pooling_percentiles():
    loads = [
        {'reduced': {'request_count': 2, 'successful_requests': 2, 'generation_errors': 0,
                     'p50_latency_ms': 10, 'p95_latency_ms': 20, 'p99_latency_ms': 20,
                     'request_wall_seconds': 2, 'output_tokens': 20, 'input_tokens': 40}},
        {'reduced': {'request_count': 2, 'successful_requests': 2, 'generation_errors': 0,
                     'p50_latency_ms': 50, 'p95_latency_ms': 100, 'p99_latency_ms': 100,
                     'request_wall_seconds': 1, 'output_tokens': 30, 'input_tokens': 40}},
    ]
    reduced = reduce_loads(loads)
    assert reduced['p95_latency_ms'] == 100
    assert reduced['request_count'] == 4
    assert reduced['output_tokens_per_second'] == pytest.approx(50 / 3)
    assert reduced['p99_reliable'] is False


def test_sweep_runs_concurrent_requests_but_quality_stays_serial(tmp_path):
    class Response:
        def to_dict(self):
            return {'text': 'ok', 'token_ids': [1], 'prompt_token_ids': [2],
                    'finish_reason': 'stop', 'latency_ms': 10,
                    'usage': {'completion_tokens': 1, 'prompt_tokens': 1}}

    class Model:
        artifact_dir = tmp_path
        configuration = RuntimeConfig()
        record = {}

        def __init__(self):
            self.lock = threading.Lock()
            self.active = 0
            self.peak = 0

        def prepare(self, prompt):
            return {}, [2]

        def _generate_prepared(self, payload, tokens):
            with self.lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            time.sleep(.005)
            with self.lock:
                self.active -= 1
            return Response()

        def metrics_snapshot(self):
            return {'raw': '', 'reduced': {}}

    model = Model()
    result = collect_trial(model, ['a', 'b'], 'baseline', baseline=True,
                           workload=Workload(concurrency=[1, 2]))
    assert result['status'] == 'collected'
    assert model.peak == 2
    assert [load['concurrency'] for load in result['loads']] == [1, 2]
    assert [len(load['requests']) for load in result['loads']] == [6, 6]
    assert len(result['quality']) == len(result['self_check']) == 2
    assert result['reduced']['request_count'] == 12
    assert result['workload']['quality_concurrency'] == 1


def test_sweep_rejects_load_above_service_sequence_limit_before_generation(tmp_path):
    class Model:
        artifact_dir = tmp_path
        configuration = RuntimeConfig(max_num_seqs=1)

    with pytest.raises(ValueError):
        collect_trial(Model(), ['a'], 'candidate', workload=Workload(concurrency=[2]))
    assert not list(Path(tmp_path).iterdir())


def test_summary_shows_each_load_instead_of_only_a_pooled_number(tmp_path):
    report = {'status': 'closed', 'baseline': {'status': 'collected', 'loads': [
        {'concurrency': 4, 'reduced': {'request_count': 24, 'p95_latency_ms': 600.0,
                                     'output_tokens_per_second': 40.0}}]}}
    summary = render_summary(report, tmp_path)
    assert 'concurrency=4' in summary
    assert 'p95=600.0 ms' in summary
    assert 'worst per-load' in summary
