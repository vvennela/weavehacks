"""Read the vLLM 0.26 Prometheus surface without inventing missing values."""

import math

from prometheus_client.parser import text_string_to_metric_families


def parse_vllm_metrics(text: str, model_name: str | None = None) -> dict:
    samples = [sample for family in text_string_to_metric_families(text)
               for sample in family.samples
               if model_name is None or sample.labels.get("model_name") == model_name]

    def total(name, reasons=None):
        values = [sample.value for sample in samples if sample.name == f"vllm:{name}"
                  and (reasons is None or sample.labels.get("finished_reason") in reasons)]
        if not values or any(not math.isfinite(value) or value < 0 for value in values):
            return None
        return sum(values)

    def mean_ms(name):
        value, count = total(name + "_sum"), total(name + "_count")
        return value / count * 1000 if value is not None and count else None

    cache = total("kv_cache_usage_perc")
    return {
        "completed_requests": total("request_success_total", {"stop", "length"}),
        "request_errors": total("request_success_total", {"abort", "error", "repetition"}),
        "preemptions": total("num_preemptions_total"),
        "running_requests": total("num_requests_running"),
        "waiting_requests": total("num_requests_waiting"),
        "kv_cache_percent": cache * 100 if cache is not None else None,
        "mean_ttft_ms": mean_ms("time_to_first_token_seconds"),
        "mean_queue_ms": mean_ms("request_queue_time_seconds"),
    }
