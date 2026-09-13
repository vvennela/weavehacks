# Sera single-model result

Status: closed
Selection: baseline
Reason: objective-improvement-below-threshold

Objective: {'priority': 'throughput', 'min_improvement_fraction': 0.05}
Measured frontier: ['candidate']
Task scores use the supplied versioned evaluator; see each trial's gate and constraints.
This is one comparison, not a statistically established speedup.

Baseline: collected; requests=96; p95=772.2824129996297 ms; throughput=26.19957805281089 output tokens/s; peak memory=88687 MiB; output tokens=660; startup=78.06795278699974 s.
Candidate: collected; requests=96; p95=771.8916659996466 ms; throughput=26.205818712535798 output tokens/s; peak memory=88561 MiB; output tokens=660; startup=68.0683067760001 s.
Task score: 1.0000; required >= 0.99; pass=True.
Hard limits: {'quality_floor': 0.99, 'p95_latency_ms': None, 'max_memory_mib': None}; failures: {'baseline': [], 'candidate': []}.

Workload: {'prompt_count': 8, 'concurrency': [1, 2, 4, 8], 'warmup_requests_per_load': 8, 'measured_requests_per_load': 24, 'quality_requests': 8, 'quality_concurrency': 1, 'latency_reduction': 'worst-per-load-percentile', 'throughput_reduction': 'total-tokens-over-total-measured-window-seconds'}
Generation: {'temperature': 0, 'top_p': 1, 'top_k': -1, 'seed': 0, 'max_tokens': 64, 'enable_thinking': False}
Record: /marimo/sera-evidence/large-batch-comparison-v1/result.json
