# Approved Qwen72B batching comparison

Outcome: keep the 4096-token FP8 reference. Both configurations passed all eight unchanged strict-JSON tasks and all 96 timed requests (24 at each load). The candidate changed only the batch-token limit to 2048. FP8 weights, BF16 KV, model revision, prompts, generation settings, quality floor, and service memory fraction stayed fixed.

The declared objective was aggregate output throughput, with a 5% minimum improvement. The measured gain was **0.0238%**, below that threshold. Worst-load p95 changed by **0.0506%**. These differences do not establish a performance win.

| Concurrent requests | Reference p95 (ms) | Candidate p95 (ms) | Reference output tokens/s | Candidate output tokens/s |
| --- | --- | --- | --- | --- |
| 1 | 573.54 | 573.25 | 13.66 | 13.67 |
| 2 | 649.55 | 649.33 | 23.71 | 23.71 |
| 4 | 729.21 | 728.00 | 41.54 | 41.53 |
| 8 | 772.28 | 771.89 | 75.68 | 75.66 |

Selection uses the worst per-load p95, never pooled latency percentiles. Aggregate throughput is total output tokens divided by the sum of measured durations: 26.1996 versus 26.2058 tokens/s. Each configuration produced 660 output tokens across the timed requests. The higher per-load throughput at concurrency eight is load scaling within this workload, not an improvement from changing the batch limit.

Sampled peak total GPU memory was 88,687 MiB for the reference and 88,561 MiB for the candidate. The reference was reloaded, returned a correct fresh answer, and closed with GPU memory at 0 MiB. The final W&B agent selected the reference and marked the proposed improvement refuted. No recommendation-error repair was needed.

This is a controlled comparison with fixed plans followed by a real agent review, not adaptive search or evidence that Sera beats grid search. No questions, thresholds, or configurations were retuned after the result. Startup is separate from request latency. GLM preparation overlapped reference startup, not the declared model workloads; this is not an isolated startup-cost comparison.

Implementation: `792331bbc64a4d9a6c288390e5d04e356001ce2c`. The raw result contains each load's requests, quality outputs, agent evidence/responses, runtime records, and the selected runner. Logs and raw metrics are preserved alongside it. [Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09901-2d4c-7ee2-adbf-831c6c0130ac).
