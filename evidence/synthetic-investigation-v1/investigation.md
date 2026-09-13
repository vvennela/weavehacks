## Agent investigation

SYNTHETIC offline rehearsal. Agents, outputs, timing, and memory are fixtures.
No LM or GPU calls ran. This is not measured model performance.

Agents propose experiments. Deterministic checks decide which results are eligible.
Trial order and access to history do not prove a causal search advantage.

### Round 1

Specialist quantization: accepted.
History supplied: none.
Proposal quantization-1: trial; kv_cache_dtype = fp8.
Parent trial: baseline.
Reason: Test the declared cache-precision experiment
Prediction: Reduce p95 by at least 5% while preserving task correctness
Would refute it: Quality fails or p95 improves by less than 5%
Cited metrics: p95_latency_ms.
Arbitration ID: quantization:quantization-1.

Specialist batching: abstained.
History supplied: none.
Proposal batching-1: keep-baseline; no setting change.
Parent trial: baseline.
Reason: Wait for the cache experiment
Prediction: No change until the cache result is available
Would refute it: Quality fails or p95 improves by less than 5%
Cited metrics: p95_latency_ms.

Arbiter chose: quantization:quantization-1. Reason: Choose the only active proposal in this scripted rehearsal

Trial trial-1: collected.
Scheduled by: arbiter.
Quality gate: failed; score=0.0; floor=0.99.
p95: 10.0 ms; throughput: 100.0 output tokens/s; peak memory: 2000 MiB.
Gate selection: baseline; reason: candidate-constraints-failed.
Constraint failures: {'baseline': [], 'candidate': ['task-quality-failed']}.
Prediction review: refuted. The deterministic task and performance gates rejected this trial

### Round 2

Specialist batching: accepted.
History supplied: trial-1.
Proposal batching-2: trial; max_num_batched_tokens = 2048.
Parent trial: baseline.
Reason: The earlier cache trial was fast but failed quality; test batching with baseline precision
Prediction: Reduce p95 by at least 5% while preserving task correctness
Would refute it: Quality fails or p95 improves by less than 5%
Cited metrics: trial_1_p95_latency_ms.
Arbitration ID: batching:batching-2.

Arbiter chose: batching:batching-2. Reason: Choose the only active proposal in this scripted rehearsal

Trial trial-2: collected.
Scheduled by: arbiter.
Quality gate: passed; score=1.0; floor=0.99.
p95: 80.0 ms; throughput: 100.0 output tokens/s; peak memory: 2000 MiB.
Gate selection: candidate; reason: quality-passed-and-p95-improved-at-least-five-percent.
Constraint failures: {'baseline': [], 'candidate': []}.
Prediction review: confirmed. The deterministic task and performance gates passed

Final selection: trial-2.
Stop reason: budget-exhausted.
Trials used: 2/2.
Runner status: closed; closed=True.
Raw evidence: result.json — search.rounds, search_trials, and agent_calls.

Synthetic fresh-runner probe passed: True.
Synthetic fresh response: {"answer": 15}
