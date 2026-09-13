# Sera single-model result

Status: closed
Selection: trial-1
Reason: objective-plateau-confirmed

Objective: {'priority': 'latency', 'min_improvement_fraction': 0.05}
Measured frontier: ['trial-1', 'trial-3']
Task scores use the supplied versioned evaluator; see each trial's gate and constraints.
This bounded search is not a statistically established advantage over other search methods.

Baseline: collected; requests=96; p95=770.6823209991853 ms; throughput=26.248872433001516 output tokens/s; peak memory=88687 MiB; output tokens=660; startup=68.07289270299952 s.
  concurrency=1; requests=24; p95=572.1306430023105 ms; throughput=13.688342728637384 output tokens/s.
  concurrency=2; requests=24; p95=648.2719099985843 ms; throughput=23.74068041658854 output tokens/s.
  concurrency=4; requests=24; p95=725.678558999789 ms; throughput=41.62605231661944 output tokens/s.
  concurrency=8; requests=24; p95=770.6823209991853 ms; throughput=75.82980486525912 output tokens/s.
trial-1: collected; requests=96; p95=625.7277270015038 ms; throughput=28.190020417833047 output tokens/s; peak memory=88431 MiB; output tokens=660; startup=67.07289243200285 s.
  concurrency=1; requests=24; p95=557.8476510017936 ms; throughput=14.110207615293128 output tokens/s.
  concurrency=2; requests=24; p95=617.4534900019353 ms; throughput=25.280347059886495 output tokens/s.
  concurrency=4; requests=24; p95=625.7277270015038 ms; throughput=47.29663854149279 output tokens/s.
  concurrency=8; requests=24; p95=618.179508997855 ms; throughput=96.86228198219551 output tokens/s.
trial-2: collected; requests=96; p95=770.4568759982067 ms; throughput=26.24203728156087 output tokens/s; peak memory=88561 MiB; output tokens=660; startup=68.07246891500108 s.
  concurrency=1; requests=24; p95=571.9249549983942 ms; throughput=13.686992375427042 output tokens/s.
  concurrency=2; requests=24; p95=647.7920239995001 ms; throughput=23.733315083397674 output tokens/s.
  concurrency=4; requests=24; p95=726.5452250030648 ms; throughput=41.61087088108115 output tokens/s.
  concurrency=8; requests=24; p95=770.4568759982067 ms; throughput=75.76862990666604 output tokens/s.
trial-3: collected; requests=96; p95=765.6131900002947 ms; throughput=26.390148274749848 output tokens/s; peak memory=88347 MiB; output tokens=660; startup=81.08243679700172 s.
  concurrency=1; requests=24; p95=570.7280129972787 ms; throughput=13.718448305122784 output tokens/s.
  concurrency=2; requests=24; p95=646.3642160015297 ms; throughput=23.93009989627078 output tokens/s.
  concurrency=4; requests=24; p95=718.3574529990437 ms; throughput=42.01690830368323 output tokens/s.
  concurrency=8; requests=24; p95=765.6131900002947 ms; throughput=76.40088135126675 output tokens/s.

Selection latency is the worst per-load p95; percentiles are not pooled. Aggregate throughput divides all output tokens by the sum of measured load durations.
Hard limits: {'quality_floor': 0.99, 'p95_latency_ms': None, 'max_memory_mib': None}; failures: {}.

Investigation trials: 3; no total trial cap; stop: objective-plateau-confirmed.
Each round records proposals, arbitration, measurements, gates, and prediction review.
This investigation is not proof of a search advantage.

Workload: {'prompt_count': 8, 'concurrency': [1, 2, 4, 8], 'warmup_requests_per_load': 8, 'measured_requests_per_load': 24, 'quality_requests': 8, 'quality_concurrency': 1, 'latency_reduction': 'worst-per-load-percentile', 'throughput_reduction': 'total-tokens-over-total-measured-window-seconds'}
Generation: {'temperature': 0, 'top_p': 1, 'top_k': -1, 'seed': 0, 'max_tokens': 64, 'enable_thinking': False}
Record: /marimo/sera-evidence/live-grid-comparison-v1/live/result.json

## Agent investigation

Agents propose experiments. Deterministic checks decide which results are eligible.
Trial order and access to history do not prove a causal search advantage.
Independent investigators inspect traces and exchange findings before arbitration.

### Round 1

Swarm investigators: scheduling, memory_context, output_quality.
Initial investigation overlap: recorded.
Peer-review overlap: recorded.
Shared findings board: 0f4af110b8533806de9cfcc9360d90b94d78842acbed1f630175270c2401f32c; entries=3.
Investigator roles are analysis perspectives, not additional hardware capabilities. GPU trials remain sequential.

Investigator scheduling: accepted.
Inspection latency_outliers: complete; source=weave; calls=01a09b99-9887-7509-8f15-42cdd4b82443, 01a09b99-9888-773e-9c38-9809c71fefac.
Inspection load_metrics: complete; source=weave; calls=01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c.
Initial proposal: enable_prefix_caching=True. No execution failure was observed: source call 01a09b99-989e-73fb-a0c7-984274c08e5c reports successful_requests 96 and generation_errors 0; the observed latency issue is high worst-case latency, with p95_latency_ms 770.682 ms and concurrency_8_cumulative_snapshot_mean_ttft_ms 191.122 ms. The cause is unknown, so this is a testable hypothesis rather than a claimed gain. Because fixed path input_token_ids contains short prepared prompts (85–109 tokens) and the workload explicitly uses repeated prompts after warmup, prefix reuse is the most targeted available-for-trial scheduling experiment. This changes the next setting by testing enable_prefix_caching=true while preserving the baseline context and batching limits.

Investigator memory_context: accepted.
Inspection latency_outliers: complete; source=weave; calls=01a09b99-9887-7509-8f15-42cdd4b82443, 01a09b99-9888-773e-9c38-9809c71fefac.
Inspection load_metrics: complete; source=weave; calls=01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c.
Initial proposal: enable_prefix_caching=True. No observed failure occurred: baseline completed 96 successful_requests with generation_errors 0, and sampled_peak_memory_mib was 88687, documented by inspection call 01a09b99-989e-73fb-a0c7-984274c08e5c and metrics paths metrics.successful_requests, metrics.generation_errors, and metrics.sampled_peak_memory_mib. Baseline latency was p95_latency_ms 770.6823, while concurrency_1_cumulative_snapshot_mean_ttft_ms was 136.56 and concurrency_8_cumulative_snapshot_mean_ttft_ms was 191.12. The fixed workload uses repeated prompts after warmup, with prepared prompt lengths from measured_facts.baseline.prepared_prompt_tokens sourced at input_token_ids; this supports testing prefix reuse, but does not prove a gain. Prefix caching is available and untested in supported_changes. The hypothesis is that reuse lowers TTFT; it is refuted by unchanged or worse latency, errors, or quality below the 0.99 floor.

Investigator output_quality: accepted.
Inspection latency_outliers: complete; source=weave; calls=01a09b99-9887-7509-8f15-42cdd4b82443, 01a09b99-9888-773e-9c38-9809c71fefac.
Inspection load_metrics: complete; source=weave; calls=01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c.
Initial proposal: enforce_eager=False. No failure was observed: source call 01a09b99-989e-73fb-a0c7-984274c08e5c recorded 96 successful requests and 0 generation errors, while fixed evidence path measured_facts.baseline.quality shows passed=true and mean=1.0. The observed latency remains highest at concurrency 8 (p95_latency_ms 770.6823209991853 ms; concurrency_8_cumulative_snapshot_mean_ttft_ms 191.12174771726131), with no preemptions. The unknown cause may include eager execution launch overhead; the available-for-trial graph-execution setting enforce_eager=false directly tests that hypothesis. The prepared prompt lengths at fixed path input_token_ids (mean 94.375 tokens) do not indicate a context-length issue. Peer findings are absent, so no peer claim is accepted or rejected. Evidence source call 01a09b99-989e-73fb-a0c7-984274c08e5c and fixed paths input_token_ids and measured_facts.baseline.quality support this next setting; source calls 01a09b99-9887-7509-8f15-42cdd4b82443 and 01a09b99-9888-773e-9c38-9809c71fefac show valid baseline outputs but do not establish causality.

Participation investigator: active; legal candidates=3; Read-only investigation of the same legal candidate pool..
Participation investigator: active; legal candidates=3; Read-only investigation of the same legal candidate pool..
Participation investigator: active; legal candidates=3; Read-only investigation of the same legal candidate pool..
Inactive roles were not called. Active means a legal untested setting was available.

Specialist batching: accepted.
History supplied: none.
Proposal sched-prefix-refine-01: trial; enable_prefix_caching = True.
Parent trial: baseline.
Reason: No execution failure was observed: source call 01a09b99-989e-73fb-a0c7-984274c08e5c reports successful_requests 96 and generation_errors 0. The observed issue is latency, with p95_latency_ms 770.6823209991853 ms and concurrency_8_cumulative_snapshot_mean_ttft_ms 191.12174771726131 ms; its cause is unknown. The fixed path measured_facts.baseline shows verified quality mean 1.0, so the next legal experiment should target repeated-prefill cost while preserving quality. I accept the scheduling and memory_context peer claims because they independently identify prefix reuse as relevant to this repeated-prompt workload; I reject output_quality's enforce_eager proposal for this round because prefix caching has more direct workload evidence and is available-for-trial. The evidence comes from source call 01a09b99-989e-73fb-a0c7-984274c08e5c, fixed path measured_facts.baseline, and the cited cumulative snapshots; this setting should be abandoned if the stated latency or quality conditions fail.
Prediction: For the repeated-prompt workload, enabling prefix caching is predicted to reduce p95_latency_ms and mean TTFT, especially concurrency_8_cumulative_snapshot_mean_ttft_ms; the magnitude is unknown before measurement.
Would refute it: Refute if quality falls below the fixed 0.99 floor, generation_errors becomes nonzero, successful_requests falls below 96, or p95_latency_ms fails to improve by at least 5% from 770.6823209991853 ms. Also refute the TTFT mechanism if concurrency_1_cumulative_snapshot_mean_ttft_ms and concurrency_8_cumulative_snapshot_mean_ttft_ms do not decrease. Check source call 01a09b99-989e-73fb-a0c7-984274c08e5c and fixed path measured_facts.baseline.quality.
Cited metrics: p95_latency_ms, concurrency_1_cumulative_snapshot_mean_ttft_ms, concurrency_8_cumulative_snapshot_mean_ttft_ms, generation_errors, successful_requests.
Cited value: p95_latency_ms=770.6823209991853.
Cited value: concurrency_1_cumulative_snapshot_mean_ttft_ms=136.55635714530945.
Cited value: concurrency_8_cumulative_snapshot_mean_ttft_ms=191.12174771726131.
Cited value: generation_errors=0.
Cited value: successful_requests=96.
Arbitration ID: scheduling:sched-prefix-refine-01.

Specialist batching: accepted.
History supplied: none.
Proposal sera-memory-context-prefix-caching-01: trial; enable_prefix_caching = True.
Parent trial: baseline.
Reason: Observed failure: none. Inspection call 01a09b99-989e-73fb-a0c7-984274c08e5c recorded successful_requests 96 and generation_errors 0, while the fixed path measured_facts.baseline records quality mean 1.0 and passed true; baseline sampled_peak_memory_mib was 88687. The unknown cause of the latency objective is therefore not an execution or quality failure. The baseline p95_latency_ms is 770.6823209991853 ms, and concurrency_1_cumulative_snapshot_mean_ttft_ms and concurrency_8_cumulative_snapshot_mean_ttft_ms are available for comparison. Because cache evaluation explicitly covers repeated prompts after warmup and prefix caching is an available untested control, test enable_prefix_caching=true; this independently supports the hypothesis that reuse can reduce prompt-processing latency without asserting a gain in advance.
Prediction: For the repeated-prompt workload, p95_latency_ms and concurrency_1_cumulative_snapshot_mean_ttft_ms and concurrency_8_cumulative_snapshot_mean_ttft_ms should decrease; generation_errors should remain 0 and successful_requests should remain 96. No measured gain is claimed before the trial.
Would refute it: Refuted if quality at measured_facts.baseline falls below the 0.99 floor, generation_errors becomes nonzero, successful_requests falls below 96, or p95_latency_ms fails to improve by at least 5% versus the baseline 770.6823209991853 ms.
Cited metrics: p95_latency_ms, concurrency_1_cumulative_snapshot_mean_ttft_ms, concurrency_8_cumulative_snapshot_mean_ttft_ms, generation_errors, successful_requests.
Cited value: p95_latency_ms=770.6823209991853.
Cited value: concurrency_1_cumulative_snapshot_mean_ttft_ms=136.55635714530945.
Cited value: concurrency_8_cumulative_snapshot_mean_ttft_ms=191.12174771726131.
Cited value: generation_errors=0.
Cited value: successful_requests=96.
Arbitration ID: memory_context:sera-memory-context-prefix-caching-01.

Specialist batching: accepted.
History supplied: none.
Proposal sera-output-quality-prefix-caching-001: trial; enable_prefix_caching = True.
Parent trial: baseline.
Reason: The observed issue is high worst-case latency, not an execution failure: read call 01a09b99-989e-73fb-a0c7-984274c08e5c recorded successful_requests=96 and generation_errors=0, while baseline p95_latency_ms was 770.6823209991853 and p99_reliable was false. The fixed evidence path measured_facts.baseline confirms verified quality mean 1.0 and passed=true, so the cause of the latency is unknown rather than demonstrated. Because the workload explicitly uses repeated prompts after warmup with prefix caching disabled, enabling prefix caching is a legal, untested latency experiment. I independently treat the scheduling and memory_context peer suggestions as corroborating hypotheses, not measurements; their shared recommendation is consistent with the workload but does not establish a gain.
Prediction: For the repeated-prompts-after-per-load-warmup workload, enabling prefix caching is predicted to reduce p95_latency_ms and mean TTFT, with the largest likely effect at concurrency 8; no measured gain is claimed before the trial. Quality should remain at or above the verified measured_facts.baseline quality floor of 0.99.
Would refute it: Refute this prediction if measured_facts.baseline quality is not preserved at the 0.99 floor, generation_errors becomes nonzero, successful_requests falls below 96, or p95_latency_ms fails to improve by at least 5% from 770.6823209991853 ms and both concurrency_1_cumulative_snapshot_mean_ttft_ms and concurrency_8_cumulative_snapshot_mean_ttft_ms do not decrease. Evidence must come from the new trial and the baseline inspection path measured_facts.baseline, with read call 01a09b99-989e-73fb-a0c7-984274c08e5c as the baseline reference.
Cited metrics: p95_latency_ms, concurrency_1_cumulative_snapshot_mean_ttft_ms, concurrency_8_cumulative_snapshot_mean_ttft_ms, generation_errors, successful_requests.
Cited value: p95_latency_ms=770.6823209991853.
Cited value: concurrency_1_cumulative_snapshot_mean_ttft_ms=136.55635714530945.
Cited value: concurrency_8_cumulative_snapshot_mean_ttft_ms=191.12174771726131.
Cited value: generation_errors=0.
Cited value: successful_requests=96.
Arbitration ID: output_quality:sera-output-quality-prefix-caching-001.

Arbiter chose: scheduling:sched-prefix-refine-01. Reason: Observed issue is high worst-case latency: p95_latency_ms was 770.6823209991853 with 96 successful_requests and 0 generation_errors, while verified quality was 1.0. The cause is unmeasured. I accept the peers' convergent hypothesis that enabling prefix caching may help this repeated-prompt workload, but reject any claim of a proven gain before testing. This legal, untested experiment fits the one-trial capacity; quality and the required 5% latency improvement must be evaluated after execution.
Trials executed in this round: trial-1.

Trial trial-1: collected.
Scheduled by: arbiter.
Quality gate: passed; score=1.0; floor=0.99.
p95: 625.7277270015038 ms; throughput: 28.190020417833047 output tokens/s; peak memory: 88431 MiB.
Gate selection: candidate; reason: quality-passed-and-p95-improved-at-least-five-percent.
Constraint failures: {'baseline': [], 'candidate': []}.
Prediction review: confirmed. The measured candidate confirmed the latency prediction: p95 latency improved from 770.6823209991853 ms to 625.7277270015038 ms, an 18.8086% improvement exceeding the required 5%. Quality passed at mean 1.0 with zero generation errors and 96 successful requests. Evidence is from source call 01a09b99-989e-73fb-a0c7-984274c08e5c and the recorded decision, status, runtime/sampled_peak_memory_mib, and task_quality/per_prompt paths. Do not retry this same tested configuration; preserve the quality floor and use these measurements to guide the next proposal.
Observed experiment result: accepted.
latency: baseline=770.6823209991853; candidate=625.7277270015038; gain=0.18808605056587868; required=0.05. Gain and required gain are fractions, not percentages.
Root cause: not-established. The observed outcome does not establish a model, kernel, memory-pressure, or scheduling cause. A startup error category is not the underlying server-log cause.
Saved evidence: status, decision, reduced, runtime/sampled_peak_memory_mib, task_quality/per_prompt.
Next proposal constraint: Do not retry the same tested configuration in this bounded search.
Next proposal constraint: Preserve the fixed quality floor and all workload constraints.
Next proposal constraint: Use the recorded constraints and measurements to justify the next action, or abstain.

### Round 2

Swarm investigators: scheduling, memory_context, output_quality.
Initial investigation overlap: recorded.
Peer-review overlap: recorded.
Shared findings board: fa01bdbdfd9677073272616a1450165f4cbb4ac8ad0aed1f36b87d0d0bd6a800; entries=3.
Investigator roles are analysis perspectives, not additional hardware capabilities. GPU trials remain sequential.

Investigator scheduling: accepted.
Inspection latency_outliers: complete; source=weave; calls=01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a, 01a09b99-9887-7509-8f15-42cdd4b82443, 01a09b99-9888-773e-9c38-9809c71fefac.
Inspection load_metrics: complete; source=weave; calls=01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b.
Initial proposal: max_num_batched_tokens=2048. No failed trial is observed: trial-1 was collected and accepted with quality passed and p95_latency_ms reduced from 770.6823209991853 to 625.7277270015038, supported by diagnosis call 01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a and paths status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. Its root cause remained unestablished, so I do not attribute the gain causally to prefix reuse. The baseline load record from call 01a09b99-989e-73fb-a0c7-984274c08e5c shows concurrency_8 cumulative mean TTFT of 191.12174771726131 ms, while trial-1's corresponding value was 147.1736840903759 ms; these cumulative snapshots are suggestive but not causal. The available-for-trial batch-budget control explicitly permits 2048, and it is untested in the supplied trial history. I therefore propose testing the smaller batch token budget for latency sensitivity under the fixed workload and quality constraints.

Investigator memory_context: accepted.
Inspection latency_outliers: complete; source=weave; calls=01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a, 01a09b99-9887-7509-8f15-42cdd4b82443, 01a09b99-9888-773e-9c38-9809c71fefac.
Inspection not recorded: declined; source=not recorded; calls=not recorded.
Initial proposal: enforce_eager=False. No observed trial failure is present: trial-1 was collected and accepted, with quality passing and p95 improving from 770.6823209991853 ms to 625.7277270015038 ms, as recorded by diagnosis call 01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a at evidence paths status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. Its root cause was explicitly not established. The baseline and trial-1 had zero generation errors and no preemptions, while sampled_peak_memory_mib was 88687 and trial_1_sampled_peak_memory_mib was 88431; therefore memory pressure is not demonstrated. Prefix caching is already tested and should not be retried. The remaining legal untested control enforce_eager=false is a fresh batching experiment: it may reduce execution overhead, reflected in p95_latency_ms and concurrency_8_cumulative_snapshot_mean_ttft_ms, without relying on the unsupported inference that a smaller context cap reduces reserved KV memory. The prediction is testable against the fixed quality and latency gates; the stated failure conditions would support keeping the baseline afterward.

Investigator output_quality: accepted.
Inspection latency_outliers: complete; source=weave; calls=01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a, 01a09b99-9887-7509-8f15-42cdd4b82443, 01a09b99-9888-773e-9c38-9809c71fefac.
Inspection load_metrics: complete; source=weave; calls=01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b.
Initial proposal: enforce_eager=False. No execution failure was observed: trial-1 was collected and accepted with 96 successful requests, 0 generation_errors, and p95 latency 625.7277270015038 ms versus the baseline 770.6823209991853 ms, while quality passed. This is documented by diagnosis call 01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a and paths status, decision, reduced, runtime/sampled_peak_memory_mib, task_quality/per_prompt. The underlying cause is unknown, so I do not attribute the gain causally. Prefix caching has already been tested; enforce_eager=false is an available, untested latency-focused setting and is independently justified by the available graph-execution technique. The next setting should test whether graph execution changes latency without violating quality or reliability constraints.

Participation investigator: active; legal candidates=2; Read-only investigation of the same legal candidate pool..
Participation investigator: active; legal candidates=2; Read-only investigation of the same legal candidate pool..
Participation investigator: active; legal candidates=2; Read-only investigation of the same legal candidate pool..
Inactive roles were not called. Active means a legal untested setting was available.

Specialist batching: accepted.
History supplied: trial-1.
Proposal proposal-scheduling-002: trial; max_num_batched_tokens = 2048.
Parent trial: baseline.
Reason: No trial failure was observed: diagnosis call 01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a records trial-1 as collected and accepted, with quality passed and trial_1_p95_latency_ms 625.7277270015038 versus baseline p95_latency_ms 770.6823209991853; load evidence is in call 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b. The underlying scheduling cause is not established, and the diagnosis evidence paths status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt do not prove causality. I reject peer recommendations to copy enforce_eager=false because that lever is not the scheduling technique active in this round; the available-for-trial scheduling technique and active value support max_num_batched_tokens=2048. This trial tests whether a smaller token budget changes tail latency, especially the concurrency_8_cumulative_snapshot_mean_ttft_ms, while preserving the verified quality result and request success.
Prediction: At the fixed workload and quality floor, p95_latency_ms may improve modestly or remain near baseline, with the clearest effect expected at concurrency 8; successful_requests should remain 96 and generation_errors 0. This is a prediction, not a measured gain.
Would refute it: Refute this hypothesis if the trial fails the 0.99 quality floor, generation_errors becomes nonzero, successful_requests falls below request_count, or p95_latency_ms is not improved by at least 5% versus the baseline 770.6823209991853 ms while concurrency_8_cumulative_snapshot_mean_ttft_ms materially worsens.
Cited metrics: p95_latency_ms, trial_1_p95_latency_ms, concurrency_8_cumulative_snapshot_mean_ttft_ms, trial_1_concurrency_8_cumulative_snapshot_mean_ttft_ms, successful_requests, generation_errors.
Cited value: p95_latency_ms=770.6823209991853.
Cited value: trial_1_p95_latency_ms=625.7277270015038.
Cited value: concurrency_8_cumulative_snapshot_mean_ttft_ms=191.12174771726131.
Cited value: trial_1_concurrency_8_cumulative_snapshot_mean_ttft_ms=147.1736840903759.
Cited value: successful_requests=96.
Cited value: generation_errors=0.
Prior feedback: trial-1: quality=passed; prediction=confirmed.
Arbitration ID: scheduling:proposal-scheduling-002.

Specialist batching: accepted.
History supplied: trial-1.
Proposal memory-context-refine-02: trial; enforce_eager = False.
Parent trial: baseline.
Reason: Observed failure: none. The prior trial was collected and accepted, with 96 successful requests, 0 generation_errors, and verified quality passing, according to diagnosis call 01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a at fixed evidence paths status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. Its measured p95_latency_ms was 625.7277270015038 versus baseline p95_latency_ms 770.6823209991853; sampled_peak_memory_mib was 88431 versus 88687, but the cause of that improvement is not established. Prepared prompts were short (85-109 tokens), and baseline concurrency snapshots show zero preemptions, so a memory-capacity change is not justified by observed pressure. I reject the scheduling peer's max_num_batched_tokens suggestion as insufficiently supported by direct memory-context evidence, while testing the independently available enforce_eager=false candidate because it may reduce execution overhead. Baseline load metrics came from call 01a09b99-989e-73fb-a0c7-984274c08e5c and the accepted trial load metrics from call 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b; these comparisons motivate a new test but do not establish causality.
Prediction: Test whether p95_latency_ms improves from the baseline value of 770.6823209991853 ms while successful_requests remains 96 and generation_errors remains 0; no memory improvement is asserted.
Would refute it: Refute if verified quality falls below 0.99, generation_errors becomes nonzero, successful_requests falls below request_count, or p95_latency_ms fails to improve by at least 5% versus baseline; also reject if sampled_peak_memory_mib materially worsens without latency benefit.
Cited metrics: p95_latency_ms, successful_requests, generation_errors, sampled_peak_memory_mib, trial_1_p95_latency_ms, trial_1_successful_requests, trial_1_generation_errors, trial_1_sampled_peak_memory_mib.
Cited value: p95_latency_ms=770.6823209991853.
Cited value: successful_requests=96.
Cited value: generation_errors=0.
Cited value: sampled_peak_memory_mib=88687.
Cited value: trial_1_p95_latency_ms=625.7277270015038.
Cited value: trial_1_successful_requests=96.
Cited value: trial_1_generation_errors=0.
Cited value: trial_1_sampled_peak_memory_mib=88431.
Prior feedback: trial-1: quality=passed; prediction=confirmed.
Arbitration ID: memory_context:memory-context-refine-02.

Specialist batching: accepted.
History supplied: trial-1.
Proposal proposal-enforce-eager-false-001: trial; enforce_eager = False.
Parent trial: baseline.
Reason: No execution failure was observed: trial-1 was collected with 96 successful_requests and 0 generation_errors, and its diagnosis at call 01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a records failure_kind=accepted with quality passed; the observed result was p95_latency_ms improving from 770.6823209991853 to 625.7277270015038. The same diagnosis states root cause is not established, so the cause remains unknown rather than proving prefix caching, graph execution, or memory pressure. The fixed evidence paths are status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. I reject copying the scheduling peer's max_num_batched_tokens choice because the current supported change list permits both options and its causal claim is unestablished; I accept the execution-latency direction from the graph-execution technique as a testable hypothesis. The trial-1 measurements show successful_requests=96, generation_errors=0, and concurrency_8_cumulative_snapshot_mean_ttft_ms decreasing from 191.12174771726131 to 147.1736840903759, supporting testing graph-enabled execution with enforce_eager=false while preserving the verified quality floor. This is a new untested setting, not a claimed measured gain.
Prediction: p95_latency_ms should improve by at least 5% versus the baseline 770.6823209991853 ms, while successful_requests remains 96 and generation_errors remains 0; concurrency_8_cumulative_snapshot_mean_ttft_ms should not materially worsen from the trial-1 value of 147.1736840903759 ms.
Would refute it: Refute if p95_latency_ms fails to improve by at least 5% versus baseline, verified quality falls below 0.99, successful_requests decreases, generation_errors becomes nonzero, or concurrency_8_cumulative_snapshot_mean_ttft_ms materially worsens versus 147.1736840903759 ms.
Cited metrics: p95_latency_ms, trial_1_p95_latency_ms, trial_1_successful_requests, trial_1_generation_errors, concurrency_8_cumulative_snapshot_mean_ttft_ms, trial_1_concurrency_8_cumulative_snapshot_mean_ttft_ms.
Cited value: p95_latency_ms=770.6823209991853.
Cited value: trial_1_p95_latency_ms=625.7277270015038.
Cited value: trial_1_successful_requests=96.
Cited value: trial_1_generation_errors=0.
Cited value: concurrency_8_cumulative_snapshot_mean_ttft_ms=191.12174771726131.
Cited value: trial_1_concurrency_8_cumulative_snapshot_mean_ttft_ms=147.1736840903759.
Prior feedback: trial-1: quality=passed; prediction=confirmed.
Arbitration ID: output_quality:proposal-enforce-eager-false-001.

Arbiter chose: scheduling:proposal-scheduling-002. Reason: Observed issue is baseline worst-load p95 latency of 770.6823209991853 ms, while quality passed at 1.0 and all 96 requests succeeded; the prior prefix-caching trial improved p95 to 625.7277270015038 ms (diagnosis 01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a), but it does not establish the cause of the latency. I accept scheduling's untested hypothesis that max_num_batched_tokens=2048 may further reduce high-concurrency latency, while rejecting any claim that this gain is already measured. The enforce_eager=false opinions are also untested and duplicated, so scheduling provides the distinct next experiment.
Trials executed in this round: trial-2.

Trial trial-2: collected.
Scheduled by: arbiter.
Quality gate: passed; score=1.0; floor=0.99.
p95: 770.4568759982067 ms; throughput: 26.24203728156087 output tokens/s; peak memory: 88561 MiB.
Gate selection: baseline; reason: p95-improvement-below-five-percent.
Constraint failures: {'baseline': [], 'candidate': []}.
Prediction review: confirmed. The tested candidate preserved the 0.99 quality floor, 96 successful requests, and zero generation errors, while p95 latency remained near baseline (770.4569 ms vs. 770.6823 ms). The broad prediction held, but the measured 0.029% improvement was below the required 5% threshold, so this does not justify selecting the candidate or claiming a meaningful gain. Evidence: diagnosis call 01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a and load call 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b. Do not retry this configuration in the bounded search.
Observed experiment result: objective-not-improved.
latency: baseline=770.6823209991853; candidate=770.4568759982067; gain=0.000292526498708786; required=0.05. Gain and required gain are fractions, not percentages.
Root cause: not-established. The observed outcome does not establish a model, kernel, memory-pressure, or scheduling cause. A startup error category is not the underlying server-log cause.
Saved evidence: status, decision, reduced, runtime/sampled_peak_memory_mib, task_quality/per_prompt.
Next proposal constraint: Do not retry the same tested configuration in this bounded search.
Next proposal constraint: Preserve the fixed quality floor and all workload constraints.
Next proposal constraint: Use the measured gain and required gain to justify a different setting, or abstain.

### Round 3

Swarm investigators: scheduling, memory_context, output_quality.
Initial investigation overlap: recorded.
Peer-review overlap: recorded.
Shared findings board: 5dfa340aaf66d9d44162725213c00ec94005dfb08004571f203b35b89a78b9c8; entries=3.
Investigator roles are analysis perspectives, not additional hardware capabilities. GPU trials remain sequential.

Investigator scheduling: accepted.
Inspection latency_outliers: complete; source=weave; calls=01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a, 01a09b9f-98a3-76ad-a04b-d9c704c64663, 01a09b9f-9832-7c4d-80ad-af78ab3f729b, 01a09b99-9887-7509-8f15-42cdd4b82443.
Inspection load_metrics: complete; source=weave; calls=01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a, 01a09b9f-98a3-76ad-a04b-d9c704c64663, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9f-9840-7694-8cc0-bdf81995838c, 01a09b9f-9840-7694-8cc0-bdf81995838c, 01a09b9f-9840-7694-8cc0-bdf81995838c, 01a09b9f-9840-7694-8cc0-bdf81995838c.
Initial proposal: enforce_eager=False. The observed trial-2 failure was objective-not-improved: p95_latency_ms was 770.4568759982067 versus baseline 770.6823209991853, below the required 5% improvement, with 96 successful_requests and 0 generation_errors; this is documented by diagnosis call 01a09b9f-98a3-76ad-a04b-d9c704c64663 at paths status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. Trial-1 was accepted and improved trial_1_p95_latency_ms to 625.7277270015038, but its diagnosis call 01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a states the root cause was not established. Therefore the cause remains unknown. The only currently available untested control is supported_changes enforce_eager=false, so test it against baseline. Baseline concurrency_8_cumulative_snapshot_mean_ttft_ms is 191.12174771726131, while trial-1 was 147.1736840903759 and trial-2 was 191.190779209136; these measurements motivate testing a distinct scheduling execution mode, without treating them as causal proof.

Investigator memory_context: rejected.
Inspection latency_outliers: complete; source=weave; calls=01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a, 01a09b9f-98a3-76ad-a04b-d9c704c64663, 01a09b9f-9832-7c4d-80ad-af78ab3f729b, 01a09b99-9887-7509-8f15-42cdd4b82443.
Inspection load_metrics: complete; source=weave; calls=01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a, 01a09b9f-98a3-76ad-a04b-d9c704c64663, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9f-9840-7694-8cc0-bdf81995838c, 01a09b9f-9840-7694-8cc0-bdf81995838c, 01a09b9f-9840-7694-8cc0-bdf81995838c, 01a09b9f-9840-7694-8cc0-bdf81995838c.
Initial proposal: enforce_eager=False. The observed prior objective failure was trial-2 being collected with quality passed but only 0.000292526498708786 improvement in p95_latency_ms, 770.4568759982067 versus baseline 770.6823209991853, documented by diagnosis call 01a09b9f-98a3-76ad-a04b-d9c704c64663 at evidence paths status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt; its cause is not established. Trial-1 was accepted with p95_latency_ms 625.7277270015038 and quality passed, from diagnosis call 01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a, but its prefix-caching effect is already tested and should not be retried. Memory changed little across baseline and trials (sampled_peak_memory_mib 88687, trial_1_sampled_peak_memory_mib 88431, trial_2_sampled_peak_memory_mib 88561), with zero generation errors, so memory pressure is not established as the cause. enforce_eager=false is the only declared supported untested change in this round; it tests a distinct execution-mode hypothesis within capacity. The prediction remains uncertain because cumulative measurements do not establish causality.

Investigator output_quality: accepted.
Inspection latency_outliers: complete; source=weave; calls=01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a, 01a09b9f-98a3-76ad-a04b-d9c704c64663, 01a09b9f-9832-7c4d-80ad-af78ab3f729b, 01a09b99-9887-7509-8f15-42cdd4b82443.
Inspection load_metrics: complete; source=weave; calls=01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a, 01a09b9f-98a3-76ad-a04b-d9c704c64663, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, 01a09b9f-9840-7694-8cc0-bdf81995838c, 01a09b9f-9840-7694-8cc0-bdf81995838c, 01a09b9f-9840-7694-8cc0-bdf81995838c, 01a09b9f-9840-7694-8cc0-bdf81995838c.
Initial proposal: enforce_eager=False. Observed outcome: trial-2 was collected with generation_errors 0 and verified quality, but its p95_latency_ms was 770.4568759982067 versus the baseline 770.6823209991853, an improvement of only 0.029%, below the required 5%; this is recorded by diagnosis call 01a09b9f-98a3-76ad-a04b-d9c704c64663 at paths status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. The cause of that objective miss is not established, so it is not evidence of a specific kernel, memory, or scheduling problem. Trial-1 independently showed that a different tested lever can improve p95_latency_ms to 625.7277270015038 with verified quality, while trial-2 rules out the already-tested max_num_batched_tokens=2048 setting as useful in this bounded search. enforce_eager=false is the only declared available-for-trial untested control and directly tests the graph-execution hypothesis; baseline and trial evidence show no generation errors and comparable sampled_peak_memory_mib (88687, 88431, 88561) at source call IDs 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a, and 01a09b9f-98a3-76ad-a04b-d9c704c64663. The experiment is useful because the hypothesis remains untested, not because a gain is assumed.

Participation investigator: active; legal candidates=1; Read-only investigation of the same legal candidate pool..
Participation investigator: active; legal candidates=1; Read-only investigation of the same legal candidate pool..
Participation investigator: active; legal candidates=1; Read-only investigation of the same legal candidate pool..
Inactive roles were not called. Active means a legal untested setting was available.

Specialist batching: accepted.
History supplied: trial-1, trial-2.
Proposal proposal-3-enforce-eager-false: trial; enforce_eager = False.
Parent trial: baseline.
Reason: Observed failure: trial-2 was collected successfully with verified quality and generation_errors 0, but its p95_latency_ms was 770.4568759982067 versus baseline 770.6823209991853, an improvement of only 0.000292526498708786, below the required 5%; this is documented by diagnosis call 01a09b9f-98a3-76ad-a04b-d9c704c64663 and evidence paths status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. The cause is not established. Trial-1 shows enable_prefix_caching improved p95_latency_ms to 625.7277270015038, while trial-2's max_num_batched_tokens change did not; the corresponding load evidence is in call IDs 01a09b99-989e-73fb-a0c7-984274c08e5c, 01a09b9c-60ca-7378-ba9b-bb8b4bcb144b, and 01a09b9f-9840-7694-8cc0-bdf81995838c. enforce_eager=false is the only supported, untested current-round control, so it provides a legal hypothesis test of execution scheduling without copying the already-tested settings.
Prediction: p95_latency_ms may improve versus the baseline 770.6823209991853 ms, potentially with lower concurrency_8_cumulative_snapshot_mean_ttft_ms, while generation_errors remains 0 and quality remains at or above the 0.99 floor; no measured gain is claimed before the trial.
Would refute it: Refute this prediction if the collected trial does not reduce p95_latency_ms by at least 5% versus baseline, if concurrency_8_cumulative_snapshot_mean_ttft_ms is not lower, if generation_errors becomes nonzero, quality fails its 0.99 floor, or execution fails.
Cited metrics: p95_latency_ms, trial_1_p95_latency_ms, trial_2_p95_latency_ms, concurrency_8_cumulative_snapshot_mean_ttft_ms, trial_2_concurrency_8_cumulative_snapshot_mean_ttft_ms, generation_errors, sampled_peak_memory_mib.
Cited value: p95_latency_ms=770.6823209991853.
Cited value: trial_1_p95_latency_ms=625.7277270015038.
Cited value: trial_2_p95_latency_ms=770.4568759982067.
Cited value: concurrency_8_cumulative_snapshot_mean_ttft_ms=191.12174771726131.
Cited value: trial_2_concurrency_8_cumulative_snapshot_mean_ttft_ms=191.19077920913696.
Cited value: generation_errors=0.
Cited value: sampled_peak_memory_mib=88687.
Prior feedback: trial-1: quality=passed; prediction=confirmed.
Prior feedback: trial-2: quality=passed; prediction=confirmed.
Arbitration ID: scheduling:proposal-3-enforce-eager-false.

Specialist batching: rejected.
History supplied: trial-1, trial-2.
Proposal proposal-3-enforce-eager-false: trial; enforce_eager = False.
Parent trial: trial-1.
Reason: The observed prior failure was trial-2 being collected with 96 successful_requests and 0 generation_errors but p95_latency_ms 770.4568759982067 ms versus baseline 770.6823209991853 ms, an improvement of only 0.000292526498708786, below the required 0.05; this is documented by diagnosis call 01a09b9f-98a3-76ad-a04b-d9c704c64663 at evidence paths status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. The cause is not established. Trial-1 showed a measured accepted p95_latency_ms of 625.7277270015038 ms with verified quality and 0 generation_errors, documented by call 01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a at the same fixed evidence paths. The peers unanimously suggest enforce_eager=false, but that suggestion is untrusted; independently, this is the only supported untested control in the supplied scope and tests whether eager execution contributes to the latency plateau while retaining trial-1 as the parent comparison.
Prediction: At verified quality, p95_latency_ms is predicted to fall by at least 5% versus the baseline 770.6823209991853 ms, with lower concurrency-8_cumulative_snapshot_mean_ttft_ms and generation_errors remaining 0; this is a hypothesis, not a measured gain.
Would refute it: Refute if the trial is collected but p95_latency_ms is not below 732.1482049492261 ms, concurrency_8_cumulative_snapshot_mean_ttft_ms is not lower than baseline, generation_errors becomes nonzero, quality falls below 0.99, or execution fails.
Cited metrics: p95_latency_ms, trial_1_p95_latency_ms, trial_2_p95_latency_ms, concurrency_8_cumulative_snapshot_mean_ttft_ms, generation_errors, successful_requests.
Cited value: p95_latency_ms=770.6823209991853.
Cited value: trial_1_p95_latency_ms=625.7277270015038.
Cited value: trial_2_p95_latency_ms=770.4568759982067.
Cited value: concurrency_8_cumulative_snapshot_mean_ttft_ms=191.12174771726131.
Cited value: generation_errors=0.
Cited value: successful_requests=96.
Prior feedback: trial-1: quality=passed; prediction=confirmed.
Prior feedback: trial-2: quality=passed; prediction=confirmed.
Validation error: ValueError.

Specialist batching: accepted.
History supplied: trial-1, trial-2.
Proposal proposal-3-enforce-eager-false: trial; enforce_eager = False.
Parent trial: baseline.
Reason: Observed failure: trial-2 was collected successfully with verified quality and 0 generation errors, but its p95_latency_ms was 770.4568759982067 ms versus the baseline p95_latency_ms of 770.6823209991853 ms, an improvement of only 0.000292526498708786, below the required 5%; this is recorded in diagnosis call 01a09b9f-98a3-76ad-a04b-d9c704c64663 at paths status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. The cause is not established. Trial-1 shows enable_prefix_caching achieved 625.7277270015038 ms with verified quality, while the independently tested max_num_batched_tokens change did not improve latency. The available-for-trial graph-execution technique permits enforce_eager=false, so this fresh trial tests whether graph execution reduces launch overhead while preserving quality; peer suggestions align with this setting, but the measured evidence does not yet establish its gain. Baseline and trial measurements are supported by call 01a09b99-989e-73fb-a0c7-984274c08e5c and trial-1 by call 01a09b9c-60fa-7ee5-a8a0-eca035c6ff8a, with fixed evidence paths status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt.
Prediction: p95_latency_ms will decrease by at least 5% from 770.6823209991853 ms while quality remains at or above 0.99, trial_2_generation_errors remains 0, and successful_requests remains 96; concurrency_8_cumulative_snapshot_mean_ttft_ms may also decrease.
Would refute it: Refute if the collected trial has p95_latency_ms at or above 732.1482049492261 ms, quality below 0.99, nonzero generation_errors, fewer than 96 successful_requests, execution failure, or materially higher sampled_peak_memory_mib.
Cited metrics: p95_latency_ms, trial_1_p95_latency_ms, trial_2_p95_latency_ms, concurrency_8_cumulative_snapshot_mean_ttft_ms, trial_2_generation_errors, successful_requests, sampled_peak_memory_mib.
Cited value: p95_latency_ms=770.6823209991853.
Cited value: trial_1_p95_latency_ms=625.7277270015038.
Cited value: trial_2_p95_latency_ms=770.4568759982067.
Cited value: concurrency_8_cumulative_snapshot_mean_ttft_ms=191.12174771726131.
Cited value: trial_2_generation_errors=0.
Cited value: successful_requests=96.
Cited value: sampled_peak_memory_mib=88687.
Prior feedback: trial-1: quality=passed; prediction=confirmed.
Prior feedback: trial-2: quality=passed; prediction=confirmed.
Arbitration ID: output_quality:proposal-3-enforce-eager-false.

Arbiter chose: scheduling:proposal-3-enforce-eager-false. Reason: Observed failure: trial-2 collected with verified quality 1.0 and zero generation errors, but p95_latency_ms was 770.4568759982067 versus the 770.6823209991853 baseline, far below the required 5% improvement; the cause remains not established. I reject any claim that enforce_eager is already beneficial because it is unmeasured. I accept the scheduling peer's proposal as a distinct, legal experiment because enforce_eager=false is supported and untested, and the pending confirmation round permits testing without presuming a gain; post-execution quality and latency gates must decide its result.
Trials executed in this round: trial-3.

Trial trial-3: collected.
Scheduled by: arbiter.
Quality gate: passed; score=1.0; floor=0.99.
p95: 765.6131900002947 ms; throughput: 26.390148274749848 output tokens/s; peak memory: 88347 MiB.
Gate selection: baseline; reason: p95-improvement-below-five-percent.
Constraint failures: {'baseline': [], 'candidate': []}.
Prediction review: refuted. Trial-3 was measured and collected, but its p95 latency improvement was 0.0065774585205464605, below the required 0.05; quality passed at 1.0 and generation_errors remained 0. The prediction was therefore refuted for objective-not-improved, with no causal hypothesis established. Diagnosis evidence is available via call 01a09b9f-98a3-76ad-a04b-d9c704c64663 and saved paths status, decision, reduced, runtime/sampled_peak_memory_mib, and task_quality/per_prompt. Do not retry the same tested configuration; use a materially different setting or abstain.
Observed experiment result: objective-not-improved.
latency: baseline=770.6823209991853; candidate=765.6131900002947; gain=0.0065774585205464605; required=0.05. Gain and required gain are fractions, not percentages.
Root cause: not-established. The observed outcome does not establish a model, kernel, memory-pressure, or scheduling cause. A startup error category is not the underlying server-log cause.
Saved evidence: status, decision, reduced, runtime/sampled_peak_memory_mib, task_quality/per_prompt.
Next proposal constraint: Do not retry the same tested configuration in this bounded search.
Next proposal constraint: Preserve the fixed quality floor and all workload constraints.
Next proposal constraint: Use the measured gain and required gain to justify a different setting, or abstain.

Stopping policy: objective plateau plus one confirmation round.
Pending confirmation round: False; consecutive rounds without qualifying progress: 2. 
Final selection: trial-1.
Stop reason: objective-plateau-confirmed.
Trials used: 3; no total trial cap.
Runner status: closed; closed=True.
Raw evidence: result.json — search.rounds, search_trials, and agent_calls.

