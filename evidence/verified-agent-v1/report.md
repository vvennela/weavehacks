# Sera single-model result

Status: closed
Selection: None
Reason: no-trial-meets-constraints

Objective: {'priority': 'throughput', 'min_improvement_fraction': 0.05}
Measured frontier: []
Task scores use the supplied versioned evaluator; see each trial's gate and constraints.
This is one comparison, not a statistically established speedup.

Baseline: collected; requests=24; p95=159.3553350012371 ms; throughput=102.31818629667546 output tokens/s; peak memory=88305 MiB; output tokens=261; startup=41.038309364999805 s.
Hard limits: {'quality_floor': 0.99, 'p95_latency_ms': None, 'max_memory_mib': None}; failures: {'baseline': ['task-quality-failed'], 'candidate': ['measurement-failed', 'task-quality-failed', 'objective-metric-unavailable']}.

Workload: {'prompt_count': 8, 'concurrency': 1, 'warmup_requests': 8, 'measured_requests': 24, 'quality_requests': 8}
Generation: {'temperature': 0, 'top_p': 1, 'top_k': -1, 'seed': 0, 'max_tokens': 64, 'enable_thinking': False}
Record: /marimo/sera-evidence/verified-agent-v1/result.json
