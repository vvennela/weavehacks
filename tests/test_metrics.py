from pathlib import Path

import pytest

from sera.metrics import parse_vllm_metrics


FIXTURE = Path(__file__).parents[1] / "evidence/qwen-baseline-cuda-link/metrics.prom"


def test_parse_saved_vllm_metrics():
    metrics = parse_vllm_metrics(FIXTURE.read_text(), "sera-smoke")
    assert metrics["completed_requests"] == 3
    assert metrics["request_errors"] == 0
    assert metrics["preemptions"] == 0
    assert metrics["running_requests"] == 0
    assert metrics["waiting_requests"] == 0
    assert metrics["kv_cache_percent"] == 0
    assert metrics["mean_ttft_ms"] > 0
    assert metrics["mean_queue_ms"] >= 0


def test_missing_metrics_are_unavailable_not_zero():
    assert all(value is None for value in parse_vllm_metrics("# empty snapshot\n").values())
    assert all(value is None for value in parse_vllm_metrics(FIXTURE.read_text(), "absent-model").values())


def test_units_labels_and_zero_counts():
    text = '''vllm:kv_cache_usage_perc{model_name="chosen",engine="0"} 0.25
vllm:kv_cache_usage_perc{model_name="other",engine="0"} 0.9
vllm:request_queue_time_seconds_sum{model_name="chosen"} 0.012
vllm:request_queue_time_seconds_count{model_name="chosen"} 3
vllm:time_to_first_token_seconds_sum{model_name="chosen"} 0
vllm:time_to_first_token_seconds_count{model_name="chosen"} 0
'''
    result = parse_vllm_metrics(text, "chosen")
    assert result["kv_cache_percent"] == 25
    assert result["mean_queue_ms"] == pytest.approx(4)
    assert result["mean_ttft_ms"] is None


def test_nonfinite_metric_is_unavailable():
    assert parse_vllm_metrics('vllm:num_requests_running NaN\n')["running_requests"] is None
