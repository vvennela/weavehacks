# Approved BF16 cache-pressure pilot

Result: **not-established** under the predeclared criterion.

The user approved GPU memory fraction 0.025, eight concurrent requests with exactly 2,048 rendered input tokens, context limit 4,096, and at most eight sequences. The server budget is deliberately constrained to represent a smaller card; the physical card has 97,887 MiB. Synthetic padding creates the input length and is not a task-quality workload.

Two warm-ups preceded three waves of eight requests. Each request allowed 64 output tokens with normal EOS behavior. Metrics were sampled every 20 ms.

- Peak sampled KV use: 93.6594%.
- Measured preemptions: zero.
- Request errors: zero.
- Startup: 40.044 seconds.
- Cleanup passed; GPU memory returned to 0 MiB.

The criterion required at least 80% sampled KV use **and** at least one preemption, with zero errors and successful cleanup. High occupancy occurred; the preemption condition did not. There was no FP8 comparison and no automatic profile retuning. No quantization benefit is established.

The result records the exact profile, padded inputs, token IDs, requests, metric samples, runtime fingerprint, and cleanup. Raw before/peak/after metrics and server logs are preserved beside it.
