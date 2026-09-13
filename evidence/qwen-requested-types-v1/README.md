# Requested-type quality pilot: 8/8, verified

Pinned Qwen3-0.6B passed all eight original tasks at the unchanged **99% quality
floor**. The independent audit regraded the raw completion text with the original
strict grader. It verified the dataset, prompts, schema, profile, request hashes,
model revision, generation settings, and zero-memory cleanup.

This is the new `sera-easy-requested-types-v1` decoding profile. Six requests
require an integer, one an array of strings, and one a string. The schema builder
reads only the requested type in the task prompt; string ID types come from the
input records. It never reads the answer key or rationale, solves the filter,
enumerates allowed IDs, or restricts array length.

The filtering response was exactly `{"answer": ["a"]}`. The other seven raw
answers also passed unchanged. All generated token lists were nonempty and every
completion stopped normally. The server log records eight successful completion
requests: one pass, no warmup or retries.

Weights and KV remain BF16. Model revision:
`c1899de289a04d12100db370d81485cdf75e47ca`.
Temperature 0, seed 0, and the 64-token output limit remain unchanged.

## Diagnostic latency

- Median of eight requests: **95.46 ms**.
- Nearest-rank p95 / maximum: **690.90 ms**, the first request.
- Filtering request: **99.08 ms**.
- Startup: **46.06 s**, separate from request latency.

Latency can include first-use grammar work. This one-pass quality pilot is not
the repeated-load performance protocol and establishes no speedup.

The earlier untyped and broad-schema failures remain separate, unchanged results.
This pass does not establish joint placement or quality at a smaller memory
allocation. Any placement proof must use the same typed schemas and pass its own
isolated and joint measurements.

## Reproduce the audit

```bash
PYTHONPATH=. python evidence/qwen-requested-types-v1/audit.py \
  --source-dir evidence/qwen-requested-types-v1
```

`audit.json` records every raw answer, recomputed grade, diagnostic latency, and
source/code SHA256. The audit makes no GPU or provider calls and never edits the
original result or logs. It verifies saved-artifact consistency, not independent
proof of GPU execution.
