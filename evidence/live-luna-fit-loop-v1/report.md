# Sera single-model result

Status: closed
Selection: baseline
Reason: budget-exhausted

Objective: {'priority': 'latency', 'min_improvement_fraction': 0.05}
Measured frontier: ['baseline', 'trial-2']
Task scores use the supplied versioned evaluator; see each trial's gate and constraints.
This bounded search is not a statistically established advantage over other search methods.

Baseline: collected; requests=96; p95=770.9771380000348 ms; throughput=26.278378948934115 output tokens/s; peak memory=88687 MiB; output tokens=660; startup=212.21348705699984 s.
  concurrency=1; requests=24; p95=571.9535749999523 ms; throughput=13.726094450889558 output tokens/s.
  concurrency=2; requests=24; p95=649.1010509998887 ms; throughput=23.739418303021882 output tokens/s.
  concurrency=4; requests=24; p95=726.033101999974 ms; throughput=41.60467794486244 output tokens/s.
  concurrency=8; requests=24; p95=770.9771380000348 ms; throughput=75.74228225014024 output tokens/s.
trial-2: collected; requests=96; p95=769.1628219999984 ms; throughput=26.264900938030195 output tokens/s; peak memory=88561 MiB; output tokens=660; startup=63.058758160000025 s.
  concurrency=1; requests=24; p95=571.5217970000595 ms; throughput=13.7042394989553 output tokens/s.
  concurrency=2; requests=24; p95=648.3346520001305 ms; throughput=23.73888378695453 output tokens/s.
  concurrency=4; requests=24; p95=725.6761560001905 ms; throughput=41.64239122418661 output tokens/s.
  concurrency=8; requests=24; p95=769.1628219999984 ms; throughput=75.84139700670136 output tokens/s.

Selection latency is the worst per-load p95; percentiles are not pooled. Aggregate throughput divides all output tokens by the sum of measured load durations.
Hard limits: {'quality_floor': 0.99, 'p95_latency_ms': None, 'max_memory_mib': None}; failures: {}.

Investigation trials: 2/2; stop: budget-exhausted.
Each round records proposals, arbitration, measurements, gates, and prediction review.
This bounded investigation is not proof of a search advantage.

Workload: {'prompt_count': 8, 'concurrency': [1, 2, 4, 8], 'warmup_requests_per_load': 8, 'measured_requests_per_load': 24, 'quality_requests': 8}
Generation: {'temperature': 0, 'top_p': 1, 'top_k': -1, 'seed': 0, 'max_tokens': 64, 'enable_thinking': False}
Record: /marimo/sera-evidence/live-luna-fit-loop-v1/result.json

## Agent investigation

Agents propose experiments. Deterministic checks decide which results are eligible.
Trial order and access to history do not prove a causal search advantage.
Independent investigators inspect traces and exchange findings before arbitration.

### Deployment stage

Original BF16 baseline: infeasible (estimate only; not a measured BF16 run).
Fit reason: Estimated BF16 runtime exceeds the service memory budget.
Estimated BF16 runtime bytes: 160444792832.
Quantization specialist status: accepted.
Quantization specialist recommends: weight-fp8. Reason: FP8 weight quantization reduces estimated weight memory from 145.4 GB to 75.2 GB and estimated peak memory from 160.4 GB to 90.2 GB, making the plan estimated to fit while retaining BF16 KV storage and an explicit workspace estimate. This trades reduced weight precision and potential quality risk for deployment feasibility; latency and task quality remain unmeasured, so no speedup or quality-floor claim is made.
Deployment arbiter chose: weight-fp8. Reason: Weight FP8 is the only legal plan estimated to fit, reducing estimated peak memory to 90.2 GB versus 160.4 GB for the infeasible BF16 baseline. This trades reduced weight precision for deployment feasibility; quality and latency remain unmeasured, and no speedup can be measured because the BF16 baseline cannot run. A real trial is useful to verify feasibility and assess quality and latency against the stated gates.
Trial candidate: collected.
Scheduled by: not recorded.
Quality gate: passed; score=1.0; floor=0.99.
p95: 770.9771380000348 ms; throughput: 26.278378948934115 output tokens/s; peak memory: 88687 MiB.
Gate selection: candidate; reason: candidate-meets-constraints-baseline-does-not.
Constraint failures: {'baseline': ['estimated-memory-does-not-fit'], 'candidate': []}.
Prediction review: confirmed. The deployment-feasibility prediction was confirmed: the candidate completed collection with 96/96 successful requests, no generation errors, task quality 1.0 meeting the 0.99 floor, and no candidate constraint failures. Recorded evidence: status, decision, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. Baseline was not measured and no speedup claim is supported; do not retry this configuration in the bounded search.
Observed experiment result: accepted.
latency: baseline=not recorded; candidate=770.9771380000348; gain=not recorded; required=0.05. Gain and required gain are fractions, not percentages.
Root cause: not-established. The observed outcome does not establish a model, kernel, memory-pressure, or scheduling cause. A startup error category is not the underlying server-log cause.
Saved evidence: status, decision, reduced, runtime/sampled_peak_memory_mib, task_quality/per_prompt.
Next proposal constraint: Do not retry the same tested configuration in this bounded search.
Next proposal constraint: Preserve the fixed quality floor and all workload constraints.
Next proposal constraint: Use the recorded constraints and measurements to justify the next action, or abstain.
Deployment outcome: feasible; selected=candidate.
Deployment prediction review: confirmed. The deployment-feasibility prediction was confirmed: the candidate completed collection with 96/96 successful requests, no generation errors, task quality 1.0 meeting the 0.99 floor, and no candidate constraint failures. Recorded evidence: status, decision, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. Baseline was not measured and no speedup claim is supported; do not retry this configuration in the bounded search.
Deployment trials included in budget: 1.
No BF16 speedup comparison is available: the BF16 baseline was not measured.
The measured deployment becomes the reference for later investigation. Deployment advice is a separate stage; see the round records for proposal competition.

### Round 1

Swarm investigators: scheduling, memory_context, output_quality.
Initial investigation overlap: recorded.
Peer-review overlap: recorded.
Shared findings board: ff5b8f4694ecd3f21ab1735f30f3166dc8656992f39ebef330d4074673f6bca7; entries=3.
Investigator roles are analysis perspectives, not additional hardware capabilities. GPU trials remain sequential.

Investigator scheduling: accepted.
Inspection latency_outliers: complete; source=weave; calls=01a09ab6-b8e6-76b4-881a-6b030798a556, 01a09ab6-b8d2-72fd-b1f2-4b7eb13a7570, 01a09ab6-b8d0-73d7-aec3-979134819e9b.
Inspection load_metrics: complete; source=weave; calls=01a09ab6-b8e6-76b4-881a-6b030798a556, 01a09ab6-b8db-7676-a3a1-73d35c27c632, 01a09ab6-b8db-7676-a3a1-73d35c27c632, 01a09ab6-b8db-7676-a3a1-73d35c27c632, 01a09ab6-b8db-7676-a3a1-73d35c27c632.
Initial proposal: max_num_batched_tokens=2048. No execution failure was observed: the recorded candidate outcome was collected with generation_errors=0 and quality passed, according to diagnosis call 01a09ab6-b8e6-76b4-881a-6b030798a556; the load call 01a09ab6-b8db-7676-a3a1-73d35c27c632 recorded successful_requests=24 for each concurrency. The underlying scheduling or memory cause remains unknown; runtime/sampled_peak_memory_mib and cumulative queue/TTFT snapshots do not establish causality. I reject abstention because 2048 is a legal supported change and remains untested in the bounded search, while preserving the fixed quality floor and workload constraints.

Investigator memory_context: accepted.
Inspection latency_outliers: complete; source=weave; calls=01a09ab6-b8e6-76b4-881a-6b030798a556, 01a09ab6-b8d2-72fd-b1f2-4b7eb13a7570, 01a09ab6-b8d0-73d7-aec3-979134819e9b.
Inspection load_metrics: complete; source=weave; calls=01a09ab6-b8e6-76b4-881a-6b030798a556, 01a09ab6-b8db-7676-a3a1-73d35c27c632, 01a09ab6-b8db-7676-a3a1-73d35c27c632, 01a09ab6-b8db-7676-a3a1-73d35c27c632, 01a09ab6-b8db-7676-a3a1-73d35c27c632.
Initial proposal: max_num_batched_tokens=2048. No observed trial failure is present: the prior diagnosis recorded an accepted outcome with generation_errors 0 and verified quality at read call 01a09ab6-b8e6-76b4-881a-6b030798a556. Baseline p95_latency_ms was 770.9771380000348 ms, with 96 successful_requests and 0 trace_failed_task_count; read call 01a09ab6-b8db-7676-a3a1-73d35c27c632 reports the candidate load rows, but it does not establish the cause of any latency difference. I reject inferring a memory cause because runtime/sampled_peak_memory_mib is only an evidence path, not a measured causal result. The legal untested 2048 max_num_batched_tokens setting is therefore a low-confidence latency hypothesis for the single remaining trial, subject to the fixed quality and workload constraints.

Investigator output_quality: accepted.
Inspection latency_outliers: complete; source=weave; calls=01a09ab6-b8e6-76b4-881a-6b030798a556, 01a09ab6-b8d2-72fd-b1f2-4b7eb13a7570, 01a09ab6-b8d0-73d7-aec3-979134819e9b.
Inspection load_metrics: complete; source=weave; calls=01a09ab6-b8e6-76b4-881a-6b030798a556, 01a09ab6-b8db-7676-a3a1-73d35c27c632, 01a09ab6-b8db-7676-a3a1-73d35c27c632, 01a09ab6-b8db-7676-a3a1-73d35c27c632, 01a09ab6-b8db-7676-a3a1-73d35c27c632.
Initial proposal: keep-baseline. Observed outcome: the inspected candidate was collected and accepted, with generation_errors 0 and verified quality; no failed trial is present. Read call 01a09ab6-b8e6-76b4-881a-6b030798a556 records status collected and decision accepted, while 01a09ab6-b8db-7676-a3a1-73d35c27c632 records successful load results. The cause of the candidate's latency is unknown; the evidence does not establish a model, kernel, memory-pressure, or scheduling cause, and runtime/sampled_peak_memory_mib is not provided for the baseline metrics. Since the request does not authorize a GPU trial and the exact untested supported value cannot be established from the supplied records, abstain and retain baseline, preserving task_quality/per_prompt and the fixed quality floor.

Participation investigator: active; legal candidates=2; Read-only investigation of the same legal candidate pool..
Participation investigator: active; legal candidates=2; Read-only investigation of the same legal candidate pool..
Participation investigator: active; legal candidates=2; Read-only investigation of the same legal candidate pool..
Inactive roles were not called. Active means a legal untested setting was available.

Specialist batching: accepted.
History supplied: none.
Proposal proposal-scheduling-2048: trial; max_num_batched_tokens = 2048.
Parent trial: baseline.
Reason: Observed failure: none was established. The prior candidate was collected and accepted with generation_errors=0 and verified quality mean=1.0 at read call 01a09ab6-b8e6-76b4-881a-6b030798a556; its load measurements are recorded at read call 01a09ab6-b8db-7676-a3a1-73d35c27c632. The underlying performance cause is unknown, and the diagnosis explicitly states that no model, kernel, memory-pressure, or scheduling cause was established. Independently of peer suggestions, 2048 is the legal untested batching setting most directly aligned with the latency objective. The baseline has p95_latency_ms=770.9771380000348, successful_requests=96, generation_errors=0, and trace_failed_task_count=0; the fixed evidence paths are status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. This supports one bounded trial but does not authorize claiming improvement before measurement.
Prediction: p95_latency_ms is predicted to decrease by at least 5% from the baseline 770.9771380000348 ms, while successful_requests remains equal to request_count and generation_errors remains zero. This is a hypothesis, not a measured gain; candidate load evidence is from read call 01a09ab6-b8db-7676-a3a1-73d35c27c632 and fixed path runtime/sampled_peak_memory_mib.
Would refute it: Refute if p95_latency_ms is not at least 5% below 770.9771380000348 ms, or if successful_requests falls below request_count, generation_errors becomes nonzero, trace_failed_task_count rises, or verified quality falls below 0.99. Check read call 01a09ab6-b8e6-76b4-881a-6b030798a556 and fixed paths status, decision, reduced, and task_quality/per_prompt.
Cited metrics: p95_latency_ms, p50_latency_ms, successful_requests, generation_errors, request_count, sampled_peak_memory_mib, trace_failed_task_count.
Cited value: p95_latency_ms=770.9771380000348.
Cited value: p50_latency_ms=702.5923290000264.
Cited value: successful_requests=96.
Cited value: generation_errors=0.
Cited value: request_count=96.
Cited value: sampled_peak_memory_mib=88687.
Cited value: trace_failed_task_count=0.
Arbitration ID: scheduling:proposal-scheduling-2048.

Specialist batching: accepted.
History supplied: none.
Proposal proposal-max-batched-tokens-2048: trial; max_num_batched_tokens = 2048.
Parent trial: baseline.
Reason: No observed trial failure is present: diagnosis call 01a09ab6-b8e6-76b4-881a-6b030798a556 recorded the candidate as collected and accepted, with generation_errors=0 and verified quality passed; its evidence paths include status, decision, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. The unknown cause of any startup error category is therefore not a basis for causal claims. Load call 01a09ab6-b8db-7676-a3a1-73d35c27c632 measured successful_requests=24 for each concurrency and generation_errors=0, with p95_latency_ms reaching 770.9771380000348 ms at concurrency 8. I reject the output_quality abstention because one legal untested setting remains and the scheduling and memory_context suggestions independently identify 2048; this proposal is only a bounded measurement recommendation, not trial authorization.
Prediction: p95_latency_ms may decrease from the measured baseline of 770.9771380000348 ms; no gain is established before measurement.
Would refute it: Refute if measured p95_latency_ms is not at least 5% below baseline, or if successful_requests falls below request_count, generation_errors becomes nonzero, or verified quality falls below 0.99.
Cited metrics: p95_latency_ms, successful_requests, generation_errors, request_count, sampled_peak_memory_mib.
Cited value: p95_latency_ms=770.9771380000348.
Cited value: successful_requests=96.
Cited value: generation_errors=0.
Cited value: request_count=96.
Cited value: sampled_peak_memory_mib=88687.
Arbitration ID: memory_context:proposal-max-batched-tokens-2048.

Specialist batching: accepted.
History supplied: none.
Proposal proposal-2048-batched-tokens: trial; max_num_batched_tokens = 2048.
Parent trial: baseline.
Reason: Observed failure: none is present. Diagnosis read call 01a09ab6-b8e6-76b4-881a-6b030798a556 records the candidate as collected and accepted with generation_errors=0 and verified quality, while load read call 01a09ab6-b8db-7676-a3a1-73d35c27c632 records successful_requests=24 for each concurrency and p95_latency_ms values through concurrency 8; fixed paths include status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. The cause of any latency difference is unknown. Independently of peer suggestions, 2048 is a legal supported untested batching setting and the remaining trial can test whether it improves p95_latency_ms while preserving quality and reliability. The inspected candidate outcome does not establish a causal gain for this setting.
Prediction: p95_latency_ms may decrease by at least 5% versus the measured baseline value of 770.9771380000348 ms; no gain is established before measurement.
Would refute it: Refute the prediction if measured p95_latency_ms is not at least 5% below 770.9771380000348 ms, or if successful_requests is below request_count, generation_errors is nonzero, trace_failed_task_count rises, or verified quality falls below 0.99. These checks should be recorded in the corresponding load and quality read calls.
Cited metrics: p95_latency_ms, p50_latency_ms, successful_requests, generation_errors, request_count, trace_failed_task_count.
Cited value: p95_latency_ms=770.9771380000348.
Cited value: p50_latency_ms=702.5923290000264.
Cited value: successful_requests=96.
Cited value: generation_errors=0.
Cited value: request_count=96.
Cited value: trace_failed_task_count=0.
Arbitration ID: output_quality:proposal-2048-batched-tokens.

Arbiter chose: scheduling:proposal-scheduling-2048. Reason: No observed failure was established: the measured baseline had 96/96 successful requests, zero generation errors, and verified quality mean 1.0 at source call 01a09ab6-b8e6-76b4-881a-6b030798a556, with p95 latency 770.9771380000348 ms. The cause of latency is unknown; the evidence does not establish a model, kernel, memory-pressure, or scheduling cause. I accept the peers' shared proposal to test max_num_batched_tokens=2048 as a legal, untested latency hypothesis within the one-trial budget, while rejecting any implication that its gain is already measured. Quality and latency gates must be evaluated after execution.
Trials executed in this round: trial-2.

Trial trial-2: collected.
Scheduled by: arbiter.
Quality gate: passed; score=1.0; floor=0.99.
p95: 769.1628219999984 ms; throughput: 26.264900938030195 output tokens/s; peak memory: 88561 MiB.
Gate selection: baseline; reason: p95-improvement-below-five-percent.
Constraint failures: {'baseline': [], 'candidate': []}.
Prediction review: refuted. The proposal's latency prediction was refuted: the measured p95 improvement was 0.235%, below the required 5% (769.162822 ms versus 770.977138 ms). Reliability and quality constraints passed, with 96/96 successful requests, zero generation errors, and quality mean 1.0. Evidence is recorded in read calls 01a09ab6-b8db-7676-a3a1-73d35c27c632 and 01a09ab6-b8e6-76b4-881a-6b030798a556 and paths status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. Do not retry this tested configuration; use a different setting or abstain.
Observed experiment result: objective-not-improved.
latency: baseline=770.9771380000348; candidate=769.1628219999984; gain=0.002353268223676252; required=0.05. Gain and required gain are fractions, not percentages.
Root cause: not-established. The observed outcome does not establish a model, kernel, memory-pressure, or scheduling cause. A startup error category is not the underlying server-log cause.
Saved evidence: status, decision, reduced, runtime/sampled_peak_memory_mib, task_quality/per_prompt.
Next proposal constraint: Do not retry the same tested configuration in this bounded search.
Next proposal constraint: Preserve the fixed quality floor and all workload constraints.
Next proposal constraint: Use the measured gain and required gain to justify a different setting, or abstain.

Final selection: baseline.
Stop reason: budget-exhausted.
Trials used: 2/2.
Runner status: closed; closed=True.
Raw evidence: result.json — search.rounds, search_trials, and agent_calls.

