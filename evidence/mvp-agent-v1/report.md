# Sera single-model result

Status: closed
Selection: baseline
Reason: candidate-quality-failed

Task quality was not verified. The gate checks token agreement, not correct answers.
This is one comparison, not a statistically established speedup.

Baseline: collected; requests=24; p95=577.3394000007102 ms; output tokens=903; startup=39.041297497000414 s.
Candidate: collected; requests=24; p95=556.920128999991 ms; output tokens=918; startup=40.04143956500047 s.
Token agreement: 0.7246; required >= 0.99; pass=False.

Workload: {'prompt_count': 8, 'concurrency': 1, 'warmup_requests': 8, 'measured_requests': 24, 'quality_requests': 8}
Generation: {'temperature': 0, 'top_p': 1, 'top_k': -1, 'seed': 0, 'max_tokens': 64, 'enable_thinking': False}
Record: /marimo/sera-evidence/mvp-agent-v1/result.json
