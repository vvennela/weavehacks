# Sera single-model result

Status: closed
Selection: baseline
Reason: specialists-abstained

Objective: {'priority': 'latency', 'min_improvement_fraction': 0.05}
Measured frontier: ['baseline']
Task scores use the supplied versioned evaluator; see each trial's gate and constraints.
This bounded search is not a statistically established advantage over other search methods.

Baseline: collected; requests=96; p95=770.0346799997533 ms; throughput=26.254544857281264 output tokens/s; peak memory=88687 MiB; output tokens=660; startup=65.06256347599992 s.
  concurrency=1; requests=24; p95=571.9661719999749 ms; throughput=13.692863936134257 output tokens/s.
  concurrency=2; requests=24; p95=648.1830070001706 ms; throughput=23.744805392815863 output tokens/s.
  concurrency=4; requests=24; p95=727.0046329999786 ms; throughput=41.63317724378138 output tokens/s.
  concurrency=8; requests=24; p95=770.0346799997533 ms; throughput=75.81470554951711 output tokens/s.

Selection latency is the worst per-load p95; percentiles are not pooled. Aggregate throughput divides all output tokens by the sum of measured load durations.
Hard limits: {'quality_floor': 0.99, 'p95_latency_ms': None, 'max_memory_mib': None}; failures: {}.

Investigation trials: 1/2; stop: specialists-abstained.
Each round records proposals, arbitration, measurements, gates, and prediction review.
This bounded investigation is not proof of a search advantage.

Workload: {'prompt_count': 8, 'concurrency': [1, 2, 4, 8], 'warmup_requests_per_load': 8, 'measured_requests_per_load': 24, 'quality_requests': 8}
Generation: {'temperature': 0, 'top_p': 1, 'top_k': -1, 'seed': 0, 'max_tokens': 64, 'enable_thinking': False}
Record: /marimo/sera-evidence/live-astra-fit-loop-v1/result.json

## Agent investigation

Agents propose experiments. Deterministic checks decide which results are eligible.
Trial order and access to history do not prove a causal search advantage.
Independent investigators inspect traces and exchange findings before arbitration.

### Deployment stage

Original BF16 baseline: infeasible (estimate only; not a measured BF16 run).
Fit reason: Estimated BF16 runtime exceeds the service memory budget.
Estimated BF16 runtime bytes: 160444792832.
Quantization specialist status: accepted.
Quantization specialist recommends: weight-fp8. Reason: Recommend weight-fp8 for deployment feasibility: estimated weights of 75,216,535,552 bytes plus BF16 KV of 10,737,418,240 bytes and workspace of 4,294,967,296 bytes total 90,248,921,088 bytes, leaving 2,128,841,932 bytes within the service budget. BF16 baseline exceeds the budget. FP8 linear weights reduce memory at the cost of precision; selected parameters and KV remain BF16. Workspace and loading feasibility remain unverified. No latency improvement or quality-floor compliance has been measured; the independent arbiter and deterministic gates must decide acceptance.
Deployment arbiter chose: weight-fp8. Reason: Use the remaining trial to test deployment feasibility: estimated peak memory is 90,248,921,088 bytes, leaving 2,128,841,932 bytes within the service budget. FP8 linear weights trade precision for fit while selected parameters and KV remain BF16. Loading, workspace requirements, and the 0.99 quality floor remain unverified. The BF16 baseline cannot run within budget, so speedup and the 5% improvement target cannot be measured against it; this recommendation does not approve any gate.
Trial candidate: collected.
Scheduled by: not recorded.
Quality gate: passed; score=1.0; floor=0.99.
p95: 770.0346799997533 ms; throughput: 26.254544857281264 output tokens/s; peak memory: 88687 MiB.
Gate selection: candidate; reason: candidate-meets-constraints-baseline-does-not.
Constraint failures: {'baseline': ['estimated-memory-does-not-fit'], 'candidate': []}.
Prediction review: confirmed. Deployment feasibility is confirmed: the candidate completed 96/96 requests with zero generation errors, passed quality at 1.0 against the 0.99 floor, and met all supplied constraints (decision, reduced, task_quality/per_prompt). Sampled peak memory was 88687 MiB (runtime/sampled_peak_memory_mib). The baseline was unmeasured and estimated not to fit, so no speedup or hardware-cause claim is supported. Retain the accepted candidate and abstain from retrying this configuration; any next proposal must preserve quality and workload constraints.
Observed experiment result: accepted.
latency: baseline=not recorded; candidate=770.0346799997533; gain=not recorded; required=0.05. Gain and required gain are fractions, not percentages.
Root cause: not-established. The observed outcome does not establish a model, kernel, memory-pressure, or scheduling cause. A startup error category is not the underlying server-log cause.
Saved evidence: status, decision, reduced, runtime/sampled_peak_memory_mib, task_quality/per_prompt.
Next proposal constraint: Do not retry the same tested configuration in this bounded search.
Next proposal constraint: Preserve the fixed quality floor and all workload constraints.
Next proposal constraint: Use the recorded constraints and measurements to justify the next action, or abstain.
Deployment outcome: feasible; selected=candidate.
Deployment prediction review: confirmed. Deployment feasibility is confirmed: the candidate completed 96/96 requests with zero generation errors, passed quality at 1.0 against the 0.99 floor, and met all supplied constraints (decision, reduced, task_quality/per_prompt). Sampled peak memory was 88687 MiB (runtime/sampled_peak_memory_mib). The baseline was unmeasured and estimated not to fit, so no speedup or hardware-cause claim is supported. Retain the accepted candidate and abstain from retrying this configuration; any next proposal must preserve quality and workload constraints.
Deployment trials included in budget: 1.
No BF16 speedup comparison is available: the BF16 baseline was not measured.
The measured deployment becomes the reference for later investigation. Deployment advice is a separate stage; see the round records for proposal competition.

### Round 1

Swarm investigators: scheduling, memory_context, output_quality.
Initial investigation overlap: recorded.
Peer-review overlap: recorded.
Shared findings board: 59ac599875b9af3ea453006b3212d60a2970432a49b478d7dbba7c6235cefe3e; entries=3.
Investigator roles are analysis perspectives, not additional hardware capabilities. GPU trials remain sequential.

Investigator scheduling: abstained.
Inspection load_metrics: complete; source=weave; calls=01a09abd-3192-7b8c-bc3c-6f509a2cd724, 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0, 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0, 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0, 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0.
Inspection latency_outliers: complete; source=weave; calls=01a09abd-3192-7b8c-bc3c-6f509a2cd724, 01a09abd-3177-7efc-8f14-c04f39e9511d, 01a09abd-3176-79f3-b895-3b1cf2105359.
Initial proposal: keep-baseline. No failure is observed: call 01a09abd-3192-7b8c-bc3c-6f509a2cd724 records accepted/collected at status and decision, with zero generation_errors at reduced and passing measured quality at task_quality/per_prompt. These observations establish no scheduling root cause. The baseline completed 96/96 requests; concurrency_8_cumulative_snapshot_mean_queue_ms is approximately 0.0074 and concurrency_8_cumulative_snapshot_preemptions is zero, though cumulative snapshots cannot establish causality. At baseline/prepared_prompt_tokens, the maximum prepared length is 109 tokens; eight such prompts fit within even the smallest supported budget, 1024. Consequently, neither 1024 nor 2048 has an evidenced mechanism for the required latency gain, supporting abstention. The unreliable p99 supplies no stronger justification.

Investigator memory_context: abstained.
Inspection load_metrics: complete; source=weave; calls=01a09abd-3192-7b8c-bc3c-6f509a2cd724, 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0, 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0, 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0, 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0.
Inspection latency_outliers: complete; source=weave; calls=01a09abd-3192-7b8c-bc3c-6f509a2cd724, 01a09abd-3177-7efc-8f14-c04f39e9511d, 01a09abd-3176-79f3-b895-3b1cf2105359.
Initial proposal: keep-baseline. No failure is observed: call 01a09abd-3192-7b8c-bc3c-6f509a2cd724 records an accepted, collected result at status and decision, with generation_errors=0 and passing measured quality at task_quality/per_prompt. The baseline completed 96/96 requests. A causal scheduling or memory bottleneck is not established. The 88687 MiB observation at runtime/sampled_peak_memory_mib does not establish KV pressure; concurrency_8_cumulative_snapshot_preemptions is zero and cumulative mean queue time is 0.007412273415496884 ms. These cumulative observations are limited evidence. The prepared prompt lengths already fit eight simultaneous prefills within the smaller supported 1024-token budget, so lowering max_num_batched_tokens from 4096 to 1024 or 2048 has no demonstrated workload constraint to relieve. Retain baseline rather than spend the remaining trial on an unsupported expectation of a 5% latency gain. No peer opinions were supplied.

Investigator output_quality: abstained.
Inspection not recorded: declined; source=not recorded; calls=not recorded.
Initial proposal: keep-baseline. No observed failure requires remediation: successful_requests is 96, generation_errors and trace_failed_task_count are zero, and measured_facts.baseline.quality records measured mean quality 1.0 with valid outputs. There are no previous trials or peer claims to assess. Inspection was declined; no successful reads, read call IDs, or fixed external evidence paths are supplied. The hypothesis is that reducing max_num_batched_tokens would rarely constrain this short-prompt workload and therefore offers little latency benefit. measured_facts.baseline.prepared_prompt_tokens supplies per-prompt lengths; aggregate input_tokens is not a context length. Near-zero concurrency_8_cumulative_snapshot_mean_queue_ms and zero concurrency_8_cumulative_snapshot_preemptions provide no evidence of scheduler pressure, although cumulative snapshots cannot establish causality. Preserve the verified baseline rather than spend the remaining trial on an unsupported improvement hypothesis.

Participation investigator: active; legal candidates=2; Read-only investigation of the same legal candidate pool..
Participation investigator: active; legal candidates=2; Read-only investigation of the same legal candidate pool..
Participation investigator: active; legal candidates=2; Read-only investigation of the same legal candidate pool..
Inactive roles were not called. Active means a legal untested setting was available.

Specialist batching: abstained.
History supplied: none.
Proposal scheduling-refine-abstain-01: keep-baseline; no setting change.
Parent trial: baseline.
Reason: No failure is observed: call 01a09abd-3192-7b8c-bc3c-6f509a2cd724 records accepted/collected at status and decision, zero generation_errors at reduced, and passing measured quality at task_quality/per_prompt. The supplied baseline has 96 successful_requests out of 96 request_count. No scheduling or memory cause is established. Independently reviewing the evidence, I accept the memory_context peer's prompt-budget argument: measured_facts.baseline.prepared_prompt_tokens places eight maximum-length prompts below both permitted budgets. I also accept output_quality's claim that no observed quality failure requires remediation. Near-zero concurrency_8_cumulative_snapshot_mean_queue_ms and zero concurrency_8_cumulative_snapshot_preemptions support abstention but, being cumulative snapshots, do not establish causality. Call 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0 at reduced/p95_latency_ms shows latency increasing with concurrency; that alone does not demonstrate token-budget contention. These measurements provide insufficient justification to spend the remaining trial on either smaller budget.
Prediction: Retaining baseline predicts no configuration-driven change. Neither supported max_num_batched_tokens value, 1024 or 2048, is expected to deliver the required 5% p95_latency_ms improvement over 770.0346799997533 ms (call 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0, reduced/p95_latency_ms at concurrency 8). measured_facts.baseline.prepared_prompt_tokens reports at most 109 tokens per prompt, so eight such prompts total 872 tokens, below both budgets. This is a hypothesis, not a measured comparison.
Would refute it: A controlled comparison demonstrating p95_latency_ms at or below 731.5329459997656 ms with either supported budget, preserving workload constraints and measured quality of at least 0.99, would refute the prediction. Compare latency against call 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0 at reduced/p95_latency_ms, and quality against call 01a09abd-3192-7b8c-bc3c-6f509a2cd724 at task_quality/per_prompt. No comparison or gate approval is claimed.
Cited metrics: p95_latency_ms, successful_requests, request_count, generation_errors, concurrency_8_cumulative_snapshot_mean_queue_ms, concurrency_8_cumulative_snapshot_preemptions, p99_reliable.
Cited value: p95_latency_ms=770.0346799997533.
Cited value: successful_requests=96.
Cited value: request_count=96.
Cited value: generation_errors=0.
Cited value: concurrency_8_cumulative_snapshot_mean_queue_ms=0.007412273415496884.
Cited value: concurrency_8_cumulative_snapshot_preemptions=0.0.
Cited value: p99_reliable=False.

Specialist batching: abstained.
History supplied: none.
Proposal memory-context-refine-abstain-01: keep-baseline; no setting change.
Parent trial: baseline.
Reason: No failure is observed: call 01a09abd-3192-7b8c-bc3c-6f509a2cd724 at status and decision records an accepted, collected result; reduced records generation_errors=0, and task_quality/per_prompt supports measured quality passing the floor. Available totals show 96 successful_requests out of 96 request_count. No memory or scheduling cause is established. Independently examining measured_facts.baseline.prepared_prompt_tokens shows both permitted budgets exceed the maximum aggregate prepared prefill for eight requests. The concurrency_8_cumulative_snapshot_mean_queue_ms of 0.007412273415496884 and zero concurrency_8_cumulative_snapshot_preemptions provide no positive evidence of scheduling pressure, although cumulative snapshots cannot establish causality. Call 01a09abd-3192-7b8c-bc3c-6f509a2cd724 at runtime/sampled_peak_memory_mib reports 88687 MiB; this supplies no comparative allocation evidence supporting a memory-saving claim. I accept the scheduling and output_quality peers' abstention rationale because these measurements independently support it, while treating their performance predictions as unverified hypotheses. With only one trial remaining and no supported mechanism for the required gain, retain baseline.
Prediction: Keeping baseline predicts no configuration-driven change. Neither supported max_num_batched_tokens value, 1024 or 2048, is expected to improve p95_latency_ms by 5%. Call 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0 at reduced/p95_latency_ms records 770.0346799997533 ms for concurrency 8. measured_facts.baseline.prepared_prompt_tokens gives a maximum of 109 tokens: eight such prompts total 872 tokens, below both budgets. This supports abstention, but does not prove that changing the budget has no runtime effect.
Would refute it: A controlled comparison showing either supported budget reproducibly achieves p95_latency_ms at or below 731.5329459997656 ms, while preserving workload constraints and measured quality of at least 0.99, would refute the prediction. Compare latency with call 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0 at reduced/p95_latency_ms and quality with call 01a09abd-3192-7b8c-bc3c-6f509a2cd724 at task_quality/per_prompt. No comparison is executed or gate approved here.
Cited metrics: p95_latency_ms, successful_requests, request_count, generation_errors, sampled_peak_memory_mib, concurrency_8_cumulative_snapshot_mean_queue_ms, concurrency_8_cumulative_snapshot_preemptions.
Cited value: p95_latency_ms=770.0346799997533.
Cited value: successful_requests=96.
Cited value: request_count=96.
Cited value: generation_errors=0.
Cited value: sampled_peak_memory_mib=88687.
Cited value: concurrency_8_cumulative_snapshot_mean_queue_ms=0.007412273415496884.
Cited value: concurrency_8_cumulative_snapshot_preemptions=0.0.

Specialist batching: abstained.
History supplied: none.
Proposal output-quality-refine-abstain-01: keep-baseline; no setting change.
Parent trial: baseline.
Reason: No failure is observed: call 01a09abd-3192-7b8c-bc3c-6f509a2cd724 records accepted/collected at decision and status, zero generation_errors at reduced, and passing measured quality at task_quality/per_prompt. Available metrics report 96 successful_requests out of 96 and trace_failed_task_count=0; measured_facts.baseline.quality reports mean=1.0 across eight scored prompts. The latency cause remains unestablished. Independently evaluating the peers, I accept their abstention rationale because measured_facts.baseline.prepared_prompt_tokens places the entire eight-prompt prefill below either supported budget, and there is no measured quality defect to address. This does not prove identical scheduling or latency. The individual JSON outputs alone would not establish task correctness, and p99_reliable=false limits tail conclusions. Keeping the verified baseline is better supported than spending the remaining trial on an unsupported improvement hypothesis.
Prediction: Retaining baseline predicts no configuration-driven change. Neither supported max_num_batched_tokens value has demonstrated a route to the required 5% improvement over p95_latency_ms=770.0346799997533, recorded by call 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0 at reduced/p95_latency_ms. measured_facts.baseline.prepared_prompt_tokens gives a maximum of 109 tokens; eight such prompts total 872, below both supported budgets. This supports abstention, not a measured equivalence claim.
Would refute it: A controlled comparison showing either supported budget reproducibly achieves p95_latency_ms at or below 731.5329459997656 while preserving workload constraints and measured quality of at least 0.99 would refute the prediction. Compare latency with call 01a09abd-3185-79bc-8c4e-d36fe0bc8aa0 at reduced/p95_latency_ms and quality with measured_facts.baseline.quality and call 01a09abd-3192-7b8c-bc3c-6f509a2cd724 at task_quality/per_prompt.
Cited metrics: request_count, successful_requests, generation_errors, trace_failed_task_count, p95_latency_ms, p99_reliable.
Cited value: request_count=96.
Cited value: successful_requests=96.
Cited value: generation_errors=0.
Cited value: trace_failed_task_count=0.
Cited value: p95_latency_ms=770.0346799997533.
Cited value: p99_reliable=False.

Arbiter choice: not recorded.
Trials executed in this round: none.

Final selection: baseline.
Stop reason: specialists-abstained.
Trials used: 1/2.
Runner status: closed; closed=True.
Raw evidence: result.json — search.rounds, search_trials, and agent_calls.

