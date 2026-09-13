# Sera single-model result

Status: closed
Selection: baseline
Reason: budget-exhausted

Objective: {'priority': 'latency', 'min_improvement_fraction': 0.05}
Measured frontier: ['trial-2']
Task scores use the supplied versioned evaluator; see each trial's gate and constraints.
This bounded search is not a statistically established advantage over other search methods.

Baseline: collected; requests=96; p95=774.183014999835 ms; throughput=26.091243601820057 output tokens/s; peak memory=88687 MiB; output tokens=660; startup=64.0627345870007 s.
  concurrency=1; requests=24; p95=575.68412099954 ms; throughput=13.601762172027842 output tokens/s.
  concurrency=2; requests=24; p95=652.3806710001736 ms; throughput=23.594660990329107 output tokens/s.
  concurrency=4; requests=24; p95=728.8488650001455 ms; throughput=41.41931005542926 output tokens/s.
  concurrency=8; requests=24; p95=774.183014999835 ms; throughput=75.40081855019488 output tokens/s.
trial-1: startup-failed; requests=unavailable; p95=unavailable ms; throughput=unavailable output tokens/s; peak memory=88383 MiB; output tokens=unavailable; startup=unavailable s.
trial-2: collected; requests=96; p95=773.7631910003984 ms; throughput=26.1012576453115 output tokens/s; peak memory=88561 MiB; output tokens=660; startup=61.05702809799914 s.
  concurrency=1; requests=24; p95=576.2143770007242 ms; throughput=13.605418018630278 output tokens/s.
  concurrency=2; requests=24; p95=652.0657500004745 ms; throughput=23.618969944223775 output tokens/s.
  concurrency=4; requests=24; p95=729.0415770003165 ms; throughput=41.3958773019511 output tokens/s.
  concurrency=8; requests=24; p95=773.7631910003984 ms; throughput=75.45264325352132 output tokens/s.

Selection latency is the worst per-load p95; percentiles are not pooled. Aggregate throughput divides all output tokens by the sum of measured load durations.
Hard limits: {'quality_floor': 0.99, 'p95_latency_ms': None, 'max_memory_mib': None}; failures: {}.

Investigation trials: 2/2; stop: budget-exhausted.
Each round records proposals, arbitration, measurements, gates, and prediction review.
This bounded investigation is not proof of a search advantage.

Workload: {'prompt_count': 8, 'concurrency': [1, 2, 4, 8], 'warmup_requests_per_load': 8, 'measured_requests_per_load': 24, 'quality_requests': 8, 'quality_concurrency': 1, 'latency_reduction': 'worst-per-load-percentile', 'throughput_reduction': 'total-tokens-over-total-measured-window-seconds'}
Generation: {'temperature': 0, 'top_p': 1, 'top_k': -1, 'seed': 0, 'max_tokens': 64, 'enable_thinking': False}
Record: /marimo/sera-evidence/live-swarm-investigation-v1/result.json

## Agent investigation

Agents propose experiments. Deterministic checks decide which results are eligible.
Trial order and access to history do not prove a causal search advantage.
Independent investigators inspect traces and exchange findings before arbitration.

### Round 1

Swarm investigators: scheduling, memory_context, output_quality.
Initial investigation overlap: recorded.
Peer-review overlap: recorded.
Shared findings board: 79b3824ba56ff52c0ec8edbcf9b91d7dbfdbb78a410205e7bf0af3bafc191582; entries=3.
Investigator roles are analysis perspectives, not additional hardware capabilities. GPU trials remain sequential.

Investigator scheduling: accepted.
Inspection latency_outliers: complete; source=weave; calls=01a09a33-a9ef-7e58-8400-d1166667928b, 01a09a33-a9ed-70b7-945b-91d17956e6cd.
Inspection not recorded: declined; source=not recorded; calls=not recorded.
Initial proposal: max_model_len=256. Baseline shows high memory usage (≈88 GiB) and a 5 % latency target. The model’s max_model_len is 4096, far exceeding the token length of the current workload. Reducing max_model_len to 256 is expected to lower memory pressure, improve throughput, and reduce tail latency. If the trial fails to meet the 5 % latency improvement, the change will be considered ineffective.

Investigator memory_context: accepted.
Inspection latency_outliers: complete; source=weave; calls=01a09a33-a9ef-7e58-8400-d1166667928b, 01a09a33-a9ed-70b7-945b-91d17956e6cd.
Inspection load_metrics: complete; source=weave; calls=01a09a33-aa04-7eaf-ac8a-8fcbae158650, 01a09a33-aa04-7eaf-ac8a-8fcbae158650, 01a09a33-aa04-7eaf-ac8a-8fcbae158650, 01a09a33-aa04-7eaf-ac8a-8fcbae158650.
Initial proposal: max_num_batched_tokens=2048. The baseline trial shows a p95 latency of 774 ms, exceeding the 5 % improvement target (≤ 735 ms). Load‑metrics indicate that at concurrency 8 the system experiences high latency (p95 = 774 ms) while memory usage is high (≈ 88 GiB). Reducing max_num_batched_tokens from 4096 to 2048 is expected to lower peak memory pressure, decrease queueing and TTFT, and thus reduce the tail latency. If the new p95 latency remains above 735 ms, the prediction is refuted.

Investigator output_quality: accepted.
Inspection latency_outliers: complete; source=weave; calls=01a09a33-a9ef-7e58-8400-d1166667928b, 01a09a33-a9ed-70b7-945b-91d17956e6cd.
Inspection not recorded: declined; source=not recorded; calls=not recorded.
Initial proposal: max_model_len=256. The baseline p95 latency is 774 ms, exceeding the 5 % improvement target. Reducing the maximum model length from 4096 to 256 tokens lowers the KV cache size and overall memory footprint, which is expected to reduce GPU pressure and improve throughput. The tasks in the current workload are short and do not require long context, so the quality floor should remain satisfied. If the p95 latency does not drop below 735.3 ms, the change will be considered ineffective.

Participation investigator: active; legal candidates=2; Read-only investigation of the same legal candidate pool..
Participation investigator: active; legal candidates=2; Read-only investigation of the same legal candidate pool..
Participation investigator: active; legal candidates=2; Read-only investigation of the same legal candidate pool..
Inactive roles were not called. Active means a legal untested setting was available.

Specialist batching: accepted.
History supplied: none.
Proposal proposal-2: trial; max_model_len = 256.
Parent trial: baseline.
Reason: The baseline p95 latency is 774 ms, exceeding the 5% improvement target (≈735.3 ms). Reducing the maximum model length from 4096 to 256 tokens lowers the KV cache size and overall memory footprint, which is expected to reduce GPU pressure and improve throughput. The current workload consists of short prompts that do not require long context, so the quality floor should remain satisfied. If the p95 latency does not drop below 735.3 ms, the change will be considered ineffective.
Prediction: p95_latency_ms will decrease below 735.3 ms
Would refute it: p95_latency_ms >= 735.3 ms after the trial
Cited metrics: p95_latency_ms, p99_latency_ms, p50_latency_ms, request_wall_seconds, request_count, successful_requests, input_tokens, output_tokens, input_tokens_per_second, output_tokens_per_second, sampled_peak_memory_mib, concurrency_8_cumulative_snapshot_mean_queue_ms, concurrency_8_cumulative_snapshot_mean_ttft_ms.
Cited value: p95_latency_ms=774.183014999835.
Cited value: p99_latency_ms=836.0755710000376.
Cited value: p50_latency_ms=705.4281220007397.
Cited value: request_wall_seconds=25.295842929999708.
Cited value: request_count=96.
Cited value: successful_requests=96.
Cited value: input_tokens=9060.
Cited value: output_tokens=660.
Cited value: input_tokens_per_second=358.1616167158935.
Cited value: output_tokens_per_second=26.091243601820057.
Cited value: sampled_peak_memory_mib=88687.
Cited value: concurrency_8_cumulative_snapshot_mean_queue_ms=0.006877492211287972.
Cited value: concurrency_8_cumulative_snapshot_mean_ttft_ms=192.8349807858467.
Arbitration ID: scheduling:proposal-2.

Specialist batching: accepted.
History supplied: none.
Proposal proposal-2: trial; max_model_len = 256.
Parent trial: baseline.
Reason: The baseline p95 latency is 774 ms, exceeding the 5 % improvement target. The current workload consists of short prompts that do not require a 4096‑token context, so reducing max_model_len to 256 tokens will shrink the KV cache and overall memory footprint, alleviating GPU pressure and improving throughput. This change is expected to lower the tail latency below 735.3 ms while maintaining the quality floor. If the new p95 latency does not drop below 735.3 ms, the change will be considered ineffective.
Prediction: p95_latency_ms will decrease below 735.3 ms
Would refute it: p95_latency_ms >= 735.3 ms after the trial
Cited metrics: p95_latency_ms, p99_latency_ms, p50_latency_ms, request_wall_seconds, request_count, successful_requests, input_tokens, output_tokens, input_tokens_per_second, output_tokens_per_second, sampled_peak_memory_mib, concurrency_8_cumulative_snapshot_mean_queue_ms, concurrency_8_cumulative_snapshot_mean_ttft_ms.
Cited value: p95_latency_ms=774.183014999835.
Cited value: p99_latency_ms=836.0755710000376.
Cited value: p50_latency_ms=705.4281220007397.
Cited value: request_wall_seconds=25.295842929999708.
Cited value: request_count=96.
Cited value: successful_requests=96.
Cited value: input_tokens=9060.
Cited value: output_tokens=660.
Cited value: input_tokens_per_second=358.1616167158935.
Cited value: output_tokens_per_second=26.091243601820057.
Cited value: sampled_peak_memory_mib=88687.
Cited value: concurrency_8_cumulative_snapshot_mean_queue_ms=0.006877492211287972.
Cited value: concurrency_8_cumulative_snapshot_mean_ttft_ms=192.8349807858467.
Arbitration ID: memory_context:proposal-2.

Specialist batching: accepted.
History supplied: none.
Proposal trial-max_model_len-256: trial; max_model_len = 256.
Parent trial: baseline.
Reason: Baseline p95 latency is 774 ms, exceeding the 5 % improvement target. The workload uses only ~2265 input tokens per request, far below the current max_model_len of 4096, so reducing max_model_len to 256 will shrink the KV cache and overall memory footprint, lowering GPU pressure and improving throughput. The quality floor should remain satisfied. If the new p95 latency does not drop below 735.3 ms, the change will be considered ineffective.
Prediction: p95_latency_ms decreases below 735.3 ms
Would refute it: p95_latency_ms >= 735.3 ms after the trial
Cited metrics: p95_latency_ms, p99_latency_ms, p50_latency_ms, request_wall_seconds, request_count, successful_requests, input_tokens, output_tokens, input_tokens_per_second, output_tokens_per_second, sampled_peak_memory_mib, concurrency_8_cumulative_snapshot_mean_queue_ms, concurrency_8_cumulative_snapshot_mean_ttft_ms.
Cited value: p95_latency_ms=774.183014999835.
Cited value: p99_latency_ms=836.0755710000376.
Cited value: p50_latency_ms=705.4281220007397.
Cited value: request_wall_seconds=25.295842929999708.
Cited value: request_count=96.
Cited value: successful_requests=96.
Cited value: input_tokens=9060.
Cited value: output_tokens=660.
Cited value: input_tokens_per_second=358.1616167158935.
Cited value: output_tokens_per_second=26.091243601820057.
Cited value: sampled_peak_memory_mib=88687.
Cited value: concurrency_8_cumulative_snapshot_mean_queue_ms=0.006877492211287972.
Cited value: concurrency_8_cumulative_snapshot_mean_ttft_ms=192.8349807858467.
Arbitration ID: output_quality:trial-max_model_len-256.

Arbiter chose: output_quality:trial-max_model_len-256. Reason: Baseline p95 latency is 774 ms, exceeding the 5 % improvement target (≈735.3 ms). The workload uses only ~2265 input tokens per request, far below the current max_model_len of 4096, so reducing max_model_len to 256 will shrink the KV cache and overall memory footprint, alleviating GPU pressure and improving throughput. This change is expected to lower the tail latency below 735.3 ms while maintaining the quality floor. If the new p95 latency does not drop below 735.3 ms, the change will be considered ineffective.
Trials executed in this round: trial-1.

Trial trial-1: startup-failed.
Scheduled by: arbiter.
Quality gate: failed; score=0.0; floor=0.99.
p95: not recorded ms; throughput: not recorded output tokens/s; peak memory: 88383 MiB.
Gate selection: baseline; reason: candidate-constraints-failed.
Constraint failures: {'baseline': [], 'candidate': ['measurement-failed', 'task-quality-failed', 'input-token-mismatch', 'objective-metric-unavailable']}.
Prediction review: ValueError.
Trial error: RuntimeError.
Observed experiment result: startup-failed.
latency: baseline=774.183014999835; candidate=not recorded; gain=not recorded; required=0.05. Gain and required gain are fractions, not percentages.
Root cause: not-established. The observed outcome does not establish a model, kernel, memory-pressure, or scheduling cause. A startup error category is not the underlying server-log cause.
Saved evidence: status, decision, failure_stage, error, runtime/sampled_peak_memory_mib, task_quality/per_prompt.
Next proposal constraint: Do not retry the same tested configuration in this bounded search.
Next proposal constraint: Preserve the fixed quality floor and all workload constraints.
Next proposal constraint: Inspect the persisted failure record; absent requests are not a quality or speed result.

### Round 2

Swarm investigators: scheduling, memory_context, output_quality.
Initial investigation overlap: recorded.
Peer-review overlap: recorded.
Shared findings board: 464c4f6ad5c1d7e012c53ee7e9c8c152e566cffa9dbcfb84c2766f646c99778f; entries=3.
Investigator roles are analysis perspectives, not additional hardware capabilities. GPU trials remain sequential.

Investigator scheduling: rejected.
Inspection not recorded: declined; source=not recorded; calls=not recorded.
Initial proposal: max_num_batched_tokens=2048. Baseline p95 latency is 774 ms, exceeding the 5% improvement target. Load‑metrics show high latency at concurrency 8 and high memory usage (~88 GiB). Reducing max_num_batched_tokens from 4096 to 2048 is expected to lower peak memory pressure, reduce queueing and TTFT, and thus lower the tail latency. If the new p95 latency remains above 735 ms, the prediction is refuted.

Investigator memory_context: accepted.
Inspection not recorded: declined; source=not recorded; calls=not recorded.
Initial proposal: max_num_batched_tokens=2048. Baseline p95 latency is 774.183 ms, exceeding the 5 % improvement target (≤ 735 ms). Load‑metrics show that at concurrency 8 the system experiences high latency (p95 = 774 ms) while memory usage is high (~88 GiB). Reducing max_num_batched_tokens from 4096 to 2048 is expected to lower peak memory pressure, decrease queueing and TTFT, and thus reduce the tail latency. If the new p95 latency remains above 735 ms, the prediction is refuted.

Investigator output_quality: accepted.
Inspection not recorded: declined; source=not recorded; calls=not recorded.
Initial proposal: max_model_len=256. Baseline p95 latency is 774 ms, exceeding the 5 % improvement target (≈735.3 ms). The workload uses only ~2265 input tokens per request, far below the current max_model_len of 4096, so reducing max_model_len to 256 tokens will shrink the KV cache and overall memory footprint, lowering GPU pressure and improving throughput. The short prompts should keep the quality floor satisfied. If the new p95 latency does not drop below 735.3 ms, the change will be considered ineffective.

Participation investigator: active; legal candidates=1; Read-only investigation of the same legal candidate pool..
Participation investigator: active; legal candidates=1; Read-only investigation of the same legal candidate pool..
Participation investigator: active; legal candidates=1; Read-only investigation of the same legal candidate pool..
Inactive roles were not called. Active means a legal untested setting was available.

Specialist batching: rejected.
History supplied: trial-1.
Proposal proposal-4: trial; max_model_len = 256.
Parent trial: baseline.
Reason: Baseline p95 latency is 774.183 ms, exceeding the 5 % improvement target (≤ 735.3 ms). The workload uses only ~2265 input tokens per request, far below the current max_model_len of 4096, so reducing max_model_len to 256 tokens will shrink the KV cache and overall memory footprint, lowering GPU pressure and improving throughput. The short prompts should keep the quality floor satisfied. If the new p95 latency does not drop below 735.3 ms, the change will be considered ineffective.
Prediction: p95_latency_ms decreases below 735.3 ms
Would refute it: p95_latency_ms >= 735.3 ms after the trial
Cited metrics: p95_latency_ms, p99_latency_ms, p50_latency_ms, request_wall_seconds, request_count, successful_requests, input_tokens, output_tokens, input_tokens_per_second, output_tokens_per_second, sampled_peak_memory_mib, concurrency_8_cumulative_snapshot_mean_queue_ms, concurrency_8_cumulative_snapshot_mean_ttft_ms.
Cited value: p95_latency_ms=774.183014999835.
Cited value: p99_latency_ms=836.0755710000376.
Cited value: p50_latency_ms=705.4281220007397.
Cited value: request_wall_seconds=25.295842929999708.
Cited value: request_count=96.
Cited value: successful_requests=96.
Cited value: input_tokens=9060.
Cited value: output_tokens=660.
Cited value: input_tokens_per_second=358.1616167158935.
Cited value: output_tokens_per_second=26.091243601820057.
Cited value: sampled_peak_memory_mib=88687.
Cited value: concurrency_8_cumulative_snapshot_mean_queue_ms=0.006877492211287972.
Cited value: concurrency_8_cumulative_snapshot_mean_ttft_ms=192.8349807858467.
Prior feedback: trial-1: quality=failed; prediction=not recorded.
Validation error: ValueError.

Specialist batching: accepted.
History supplied: trial-1.
Proposal proposal-4: trial; max_num_batched_tokens = 2048.
Parent trial: baseline.
Reason: Baseline p95 latency is 774.183 ms, exceeding the 5 % improvement target (≤ 735 ms). Load‑metrics show that at concurrency 8 the system experiences high latency (p95 = 774 ms) while memory usage is high (~88 GiB). Reducing max_num_batched_tokens from 4096 to 2048 is expected to lower peak memory pressure, decrease queueing and TTFT, and thus reduce the tail latency. If the new p95 latency remains above 735 ms, the prediction is refuted.
Prediction: p95_latency_ms decreases below 735 ms
Would refute it: p95_latency_ms > 735 ms
Cited metrics: p95_latency_ms, concurrency_8_cumulative_snapshot_mean_ttft_ms, concurrency_8_cumulative_snapshot_mean_queue_ms, sampled_peak_memory_mib, request_wall_seconds.
Cited value: p95_latency_ms=774.183014999835.
Cited value: concurrency_8_cumulative_snapshot_mean_ttft_ms=192.8349807858467.
Cited value: concurrency_8_cumulative_snapshot_mean_queue_ms=0.006877492211287972.
Cited value: sampled_peak_memory_mib=88687.
Cited value: request_wall_seconds=25.295842929999708.
Prior feedback: trial-1: quality=failed; prediction=not recorded.
Arbitration ID: memory_context:proposal-4.

Specialist batching: accepted.
History supplied: trial-1.
Proposal proposal-4: trial; max_num_batched_tokens = 2048.
Parent trial: baseline.
Reason: Baseline p95 latency is 774 ms, exceeding the 5 % improvement target (≤ 735 ms). Load‑metrics show high latency at concurrency 8 and high memory usage (~88 GiB). Reducing max_num_batched_tokens from 4096 to 2048 is expected to lower peak memory pressure, reduce queueing and TTFT, and thus lower the tail latency. If the new p95 latency remains above 735 ms, the prediction is refuted.
Prediction: p95_latency_ms decreases below 735 ms
Would refute it: p95_latency_ms > 735 ms
Cited metrics: p95_latency_ms, concurrency_8_cumulative_snapshot_mean_ttft_ms, concurrency_8_cumulative_snapshot_mean_queue_ms, sampled_peak_memory_mib, request_wall_seconds.
Cited value: p95_latency_ms=774.183014999835.
Cited value: concurrency_8_cumulative_snapshot_mean_ttft_ms=192.8349807858467.
Cited value: concurrency_8_cumulative_snapshot_mean_queue_ms=0.006877492211287972.
Cited value: sampled_peak_memory_mib=88687.
Cited value: request_wall_seconds=25.295842929999708.
Prior feedback: trial-1: quality=failed; prediction=not recorded.
Arbitration ID: output_quality:proposal-4.

Arbiter chose: memory_context:proposal-4. Reason: Baseline p95 latency (774 ms) exceeds the 5 % improvement target (≤ 735 ms). Load‑metrics indicate high memory usage (~88 GiB) and elevated latency at concurrency 8. Reducing max_num_batched_tokens from 4096 to 2048 is expected to lower peak memory pressure, decrease queueing and TTFT, and thus bring p95 latency below the target while maintaining the quality floor.
Trials executed in this round: trial-2.

Trial trial-2: collected.
Scheduled by: arbiter.
Quality gate: passed; score=1.0; floor=0.99.
p95: 773.7631910003984 ms; throughput: 26.1012576453115 output tokens/s; peak memory: 88561 MiB.
Gate selection: baseline; reason: p95-improvement-below-five-percent.
Constraint failures: {'baseline': [], 'candidate': []}.
Prediction review: refuted. The candidate trial (trial-2) executed with max_num_batched_tokens=2048 produced a p95_latency_ms of 773.7631910003984 ms, which is still above the predicted threshold of 735 ms. Therefore the prediction that the p95 latency would drop below 735 ms was refuted. The baseline trial was selected because it is the only eligible_trial_id available.
Observed experiment result: objective-not-improved.
latency: baseline=774.183014999835; candidate=773.7631910003984; gain=0.0005422800439980201; required=0.05. Gain and required gain are fractions, not percentages.
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

