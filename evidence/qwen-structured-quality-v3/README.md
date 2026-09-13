# Qwen structured-output pilot: 7/8, rejected

Source revision: `ae81606c0978de404755e777249a254660a154dc`.
Pinned Qwen3-0.6B, BF16 weights and KV, same eight questions and system prompt, 64 output tokens, temperature 0, seed 0, and 0.99 quality floor.

Native JSON decoding produced valid JSON on all eight requests. Seven answers passed the unchanged strict grader. The filtering answer was `[{"id":"a"},{"id":"b"}]`; the required answer was `["a"]`. This is a semantic error, not a formatting or grading failure. The configuration is not quality-valid and cannot be the benchmark's passing baseline.

All generated token arrays were nonempty and all completions stopped normally. An independent audit reproduced the grades and confirmed the dataset, prompt, schema, and profile hashes. No output was repaired and no question or gate was changed. The earlier 2/8 BF16 result remains a separate, unstructured-decoding run, not a performance reference for this new profile.

## Diagnostic latency

Eight serial requests, one pass, no warmup or retries:

- Median: 112.60 ms.
- First request: 1,068.26 ms.
- Filtering request: 59,213.57 ms. This is also the maximum and nearest-rank p95 of these eight samples.
- Other requests: 85.43–129.08 ms.
- Startup: 151.12 seconds, separate from request latency.

The long filtering request remains in the raw record. Its cause is not established. Request latency can include first-use structured-decoding work; this is not the normal repeated performance protocol and supports no speedup claim.

The repaired CUDA include order allowed vLLM startup and generation. Cleanup passed and GPU memory returned to 0 MiB. Both earlier startup failures remain preserved in v1 and v2. No joint-placement or live-search claim follows from this pilot.
