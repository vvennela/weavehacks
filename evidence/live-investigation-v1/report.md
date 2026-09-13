# Sera single-model result

Status: closed
Selection: baseline
Reason: no-valid-selected-proposal

Objective: {'priority': 'latency', 'min_improvement_fraction': 0.05}
Measured frontier: ['baseline', 'trial-1']
Task scores use the supplied versioned evaluator; see each trial's gate and constraints.
This bounded search is not a statistically established advantage over other search methods.

Baseline: collected; requests=96; p95=773.5430580000866 ms; throughput=26.135631945182787 output tokens/s; peak memory=88687 MiB; output tokens=660; startup=72.06961458599994 s.
  concurrency=1; requests=24; p95=575.3087319999395 ms; throughput=13.635762626039286 output tokens/s.
  concurrency=2; requests=24; p95=651.117763000002 ms; throughput=23.62997718026722 output tokens/s.
  concurrency=4; requests=24; p95=728.7052029998904 ms; throughput=41.4463768814336 output tokens/s.
  concurrency=8; requests=24; p95=773.5430580000866 ms; throughput=75.38914457744524 output tokens/s.
trial-1: collected; requests=96; p95=773.4389649999684 ms; throughput=26.11297753514722 output tokens/s; peak memory=88561 MiB; output tokens=660; startup=60.0561732770002 s.
  concurrency=1; requests=24; p95=575.3022430001238 ms; throughput=13.609757288592968 output tokens/s.
  concurrency=2; requests=24; p95=651.3438479998968 ms; throughput=23.635428483381194 output tokens/s.
  concurrency=4; requests=24; p95=729.8443689999203 ms; throughput=41.41712658593016 output tokens/s.
  concurrency=8; requests=24; p95=773.4389649999684 ms; throughput=75.47240107237788 output tokens/s.

Selection latency is the worst per-load p95; percentiles are not pooled. Aggregate throughput divides all output tokens by the sum of measured load durations.
Hard limits: {'quality_floor': 0.99, 'p95_latency_ms': None, 'max_memory_mib': None}; failures: {}.

Investigation trials: 1/2; stop: no-valid-selected-proposal.
Each round records proposals, arbitration, measurements, gates, and prediction review.
This bounded investigation is not proof of a search advantage.

Workload: {'prompt_count': 8, 'concurrency': [1, 2, 4, 8], 'warmup_requests_per_load': 8, 'measured_requests_per_load': 24, 'quality_requests': 8, 'quality_concurrency': 1, 'latency_reduction': 'worst-per-load-percentile', 'throughput_reduction': 'total-tokens-over-total-measured-window-seconds'}
Generation: {'temperature': 0, 'top_p': 1, 'top_k': -1, 'seed': 0, 'max_tokens': 64, 'enable_thinking': False}
Record: /marimo/sera-evidence/live-investigation-v1/result.json

## Agent investigation

Agents propose experiments. Deterministic checks decide which results are eligible.
Trial order and access to history do not prove a causal search advantage.

### Round 1

Specialist batching: accepted.
History supplied: none.
Proposal trial-001: trial; max_num_batched_tokens = 2048.
Parent trial: baseline.
Reason: Reducing the maximum number of batched tokens from 4096 to 2048 may lower GPU memory pressure and reduce queueing delays, potentially improving the 95th percentile latency.
Prediction: p95_latency_ms will decrease relative to baseline
Would refute it: p95_latency_ms does not improve by at least 5% compared to baseline
Cited metrics: input_tokens, output_tokens, p95_latency_ms, request_wall_seconds.
Arbitration ID: batching:trial-001.

Arbiter chose: batching:trial-001. Reason: The proposal aims to reduce the 95th‑percentile latency by halving the maximum number of batched tokens, which directly addresses the latency objective (5% improvement). It does not affect the quality floor (baseline quality is 1.0). With a moderate confidence of 0.5 and a low expected cost (1 trial), and two trials remaining, the proposal offers a reasonable trade‑off between potential latency gain and risk, making it the best candidate to test next.

Trial trial-1: collected.
Scheduled by: arbiter.
Quality gate: passed; score=1.0; floor=0.99.
p95: 773.4389649999684 ms; throughput: 26.11297753514722 output tokens/s; peak memory: 88561 MiB.
Gate selection: baseline; reason: p95-improvement-below-five-percent.
Constraint failures: {'baseline': [], 'candidate': []}.
Prediction review: refuted. The candidate trial achieved a marginal 0.013% reduction in p95_latency_ms (from 773.543058 ms to 773.438965 ms), far below the 5% improvement threshold required by the falsification condition. Therefore the prediction that p95_latency_ms would decrease relative to baseline was refuted.

### Round 2

Specialist batching: accepted.
History supplied: trial-1.
Proposal trial-002: trial; max_num_batched_tokens = 1024.
Parent trial: baseline.
Reason: Reducing the maximum number of batched tokens from 2048 to 1024 may further lower GPU memory pressure and queueing delays, potentially improving the 95th‑percentile latency.
Prediction: p95_latency_ms will decrease relative to baseline
Would refute it: p95_latency_ms does not improve by at least 5% compared to baseline
Cited metrics: input_tokens, output_tokens, p95_latency_ms, request_wall_seconds.
Arbitration ID: batching:trial-002.

Arbiter chose: none. Reason: The only legal proposal (batching:trial-002) proposes further reducing max_num_batched_tokens to 1024. The prior trial with 2048 tokens already failed to meet the 5% latency improvement target, and there is no evidence that a smaller batch size would yield a meaningful gain. Confidence is low (0.4) and the expected benefit is uncertain, so the proposal is not selected for execution.

Final selection: baseline.
Stop reason: no-valid-selected-proposal.
Trials used: 1/2.
Runner status: closed; closed=True.
Raw evidence: result.json — search.rounds, search_trials, and agent_calls.
