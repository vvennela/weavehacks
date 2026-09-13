# Sera single-model result

Status: closed
Selection: candidate
Reason: candidate-meets-constraints-baseline-does-not

Objective: {'priority': 'throughput', 'min_improvement_fraction': 0.05}
Measured frontier: ['candidate']
Task scores use the supplied versioned evaluator; see each trial's gate and constraints.
This is one comparison, not a statistically established speedup.

Baseline: infeasible; requests=unavailable; p95=unavailable ms; throughput=unavailable output tokens/s; peak memory=unavailable MiB; output tokens=unavailable; startup=unavailable s.
Candidate: collected; requests=24; p95=573.1047949993808 ms; throughput=13.662783308506244 output tokens/s; peak memory=88449 MiB; output tokens=165; startup=71.07374969100056 s.
Task score: 1.0000; required >= 0.99; pass=True.
Hard limits: {'quality_floor': 0.99, 'p95_latency_ms': None, 'max_memory_mib': None}; failures: {'baseline': ['estimated-memory-does-not-fit'], 'candidate': []}.

Workload: {'prompt_count': 8, 'concurrency': 1, 'warmup_requests': 8, 'measured_requests': 24, 'quality_requests': 8}
Generation: {'temperature': 0, 'top_p': 1, 'top_k': -1, 'seed': 0, 'max_tokens': 64, 'enable_thinking': False}
Record: /marimo/sera-evidence/large-fit-v1/result.json
