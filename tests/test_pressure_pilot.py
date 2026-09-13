import pytest

from sera.metrics import measured_queue_time
from sera.pressure_pilot import pressure_verdict, PRESSURE_PROFILES


def metrics(total, count, model='sera-model'):
    return (f'vllm:request_queue_time_seconds_sum{{model_name="{model}"}} {total}\n'
            f'vllm:request_queue_time_seconds_count{{model_name="{model}"}} {count}\n')


def test_queue_uses_measured_delta_not_warmup_average():
    assert measured_queue_time(metrics(100, 2), metrics(100.48, 26), 'sera-model') == pytest.approx(20)


@pytest.mark.parametrize('before,after', [('', metrics(1, 24)), (metrics(2, 2), metrics(1, 26)),
                                        (metrics(1, 2), metrics(1, 2)),
                                        (metrics(1, 2), metrics(2, 1))])
def test_missing_or_reset_queue_counters_are_unavailable(before, after):
    assert measured_queue_time(before, after, 'sera-model') is None


def test_queue_does_not_include_other_services():
    before = metrics(0, 0) + metrics(100, 10, 'peer')
    after = metrics(.24, 24) + metrics(10000, 30, 'peer')
    assert measured_queue_time(before, after, 'sera-model') == pytest.approx(10)


def result(**changes):
    return dict(peak_kv_percent=90, measured_preemptions=1, measured_requests=24,
                request_errors=0, sampling_errors=0, measured_queue_ms=20,
                runtime={'cleanup_pass': True}, **changes)


def test_cache_requires_real_preemptions_and_all_requests():
    record = result()
    profile = PRESSURE_PROFILES['cache-v2']
    assert pressure_verdict(profile, record)
    for key, value in [('measured_preemptions', 0), ('measured_requests', 23),
                       ('sampling_errors', 1), ('peak_kv_percent', None)]:
        assert not pressure_verdict(profile, record | {key: value})
    assert not pressure_verdict(profile, record | {'runtime': {'cleanup_pass': False}})


def test_queue_requires_low_cache_no_preemptions_and_observed_queue():
    profile = PRESSURE_PROFILES['queue-v1']
    record = result() | {'peak_kv_percent': 30, 'measured_preemptions': 0}
    assert pressure_verdict(profile, record)
    for key, value in [('measured_queue_ms', None), ('measured_queue_ms', 9.9),
                       ('peak_kv_percent', 50), ('measured_preemptions', 1)]:
        assert not pressure_verdict(profile, record | {key: value})


def test_profiles_preserve_first_pilot_and_separate_reversal():
    assert PRESSURE_PROFILES['cache-v1']['input_tokens_per_request'] == 2048
    assert PRESSURE_PROFILES['cache-v2']['input_tokens_per_request'] == 2304
    assert PRESSURE_PROFILES['cache-v2']['gpu_memory_utilization'] == .025
    assert PRESSURE_PROFILES['queue-v1']['gpu_memory_utilization'] == .1
