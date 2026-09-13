# GLM structured-output pilot: 8/8, passed

Source revision: `ae81606c0978de404755e777249a254660a154dc`.
Pinned GLM-4-9B, BF16 weights and KV, the original eight questions and system prompt, 64 output tokens, temperature 0, seed 0, and 0.99 quality floor.

All eight raw answers were valid JSON and passed the unchanged strict grader, including the filtering answer `["a"]`. Every completion had nonempty output tokens and a normal stop. An independent audit reproduced all grades and confirmed the model revision, dataset, schema, and profile hashes. The decoding profile matches Qwen's structured-output pilot. No output was repaired and no task or threshold changed.

## Diagnostic latency

Eight serial requests, one pass, no warmup or retries:

- Median request latency: 141.05 ms.
- Maximum and nearest-rank p95: 1,360.60 ms, the first request.
- Startup: 100.08 seconds, separate from request latency.

These are diagnostic measurements, not the repeated performance protocol. They support no speedup or cross-model performance claim. Request timing can include first-use structured-decoding work.

Cleanup passed and GPU memory returned to 0 MiB. This proves isolated BF16 quality for this new decoding profile only. It does not prove FP8 quality or joint placement. Qwen0.6B remains at 7/8, so the specified pair is still ineligible for verified joint placement. Earlier GLM formatting failures remain preserved as separate results.
