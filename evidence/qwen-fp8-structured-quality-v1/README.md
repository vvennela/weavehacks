# Qwen FP8 structured-output quality pilot

**Result: task gate failed.** The pinned Qwen3-0.6B model passed 7/8 original tasks (87.5%), below the unchanged 99% floor. All eight outputs were valid JSON, had nonempty generated token lists, and finished normally. Independent strict regrading matched every saved grade; no output was repaired.

The filter task failed semantically: the model returned `{"answer": [{"id": "a"}, {"id": "b"}]}` instead of `{"answer": ["a"]}`. Native JSON decoding fixed the format, not this wrong answer. The BF16 structured pilot failed the same task; this record does not establish a new FP8-specific quality loss.

## Profile and measurements

The dataset, questions, system prompt, answer-independent response schema, generation settings, context limits, load, and quality floor match `qwen-structured-quality-v3`. Only weight quantization changes to `fp8_per_tensor`; KV remains `auto` (BF16). The saved profile hash is valid and differs because the configuration changed.

- Model revision: `c1899de289a04d12100db370d81485cdf75e47ca`.
- Requests: eight, serial, one pass, no warmup or retries.
- Median request latency: **109.04 ms**.
- Maximum and eight-sample nearest-rank p95: **714.25 ms**. This first-request value is retained.
- Filter-task latency: **318.82 ms**.
- Startup: **43.04 s**, separate from request latency.
- Cleanup passed; GPU memory returned to **0 MiB**.

These are diagnostic request timings, not a controlled performance comparison. They include possible first-use decoding work and exclude model startup and prompt tokenization. The difference from the BF16 pilot does not establish a speedup. This failed task gate does not authorize placement or replacing the strict benchmark baseline.

## Evidence

The [raw result](result.json) contains the unchanged cases, full completion exchanges, token IDs, per-case grades, runtime identity, and cleanup record. SHA256 at audit: `23c9fd836bf74e939af0b7a2973cf6b59ad9e62fea05be892b3c94ce8f3119f0`.

The independent audit was read-only. It made no model calls, changed no thresholds, and ran no new GPU trials.
