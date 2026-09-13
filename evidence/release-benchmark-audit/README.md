# Offline release benchmark audit

This audit rechecked saved real outputs. It ran no GPU trials, provider calls, or network requests. It changed no model, prompt, output, or quality rule.

## What passed

The unchanged strict JSON grader reproduced every saved gate for eight trial records. These are 64 output checks on the same eight questions, not 64 distinct questions and not an HLE or SWE-bench score.

| Saved run | Strict tasks passed |
| --- | --- |
| Small Qwen BF16 baseline | 2/8 |
| Qwen72B FP8 fit trial | 8/8 |
| Qwen72B demo rehearsal | 8/8 |
| Qwen72B batch-token limit 4096 | 8/8 |
| Qwen72B batch-token limit 2048 | 8/8 |
| GLM BF16 | 0/8 |
| GLM FP8 weights | 0/8 |
| Small Qwen FP8 weights | 1/8 |

The four-load Qwen72B comparison was recomputed from saved request latency, token counts, and measurement-window durations. All saved reduced metrics matched exactly. Both configurations had 96 timed requests. Their model revision, input token IDs, tokenizer settings, generation settings, runtime versions, hardware record, and workload matched.

The candidate's aggregate throughput improved by **0.02382%**, below the required **5%**. The saved decision correctly kept the reference. This is one fixed comparison, not proof that agent search is better.

## What remains blocked

No measured grid or random replay ran. The evidence directory contains no frozen search manifest. Existing records are not a complete, predeclared Qwen3-0.6B candidate universe with the required outcome envelopes and identity bindings. The small-model baseline also fails its own 99% quality gate.

The pressure pilot remains **not established**: peak KV use was 93.66%, but it recorded zero preemptions. The Qwen72B two-configuration comparison cannot replace the specified small-model search benchmark. Complete owned-runtime collection cost and a frozen search-success rule are also missing for that benchmark.

The search harness tests use labeled synthetic fixtures to test grid/random replay, isolation, gates, and budgets. Those tests are software checks, not measured search results. This audit does not create a smaller universe after seeing results or relabel synthetic trials as measured.

## Repeat

From the repository root:

```bash
python -m benchmarks.release_audit --repo-root .
python -m pytest tests/test_search_benchmark.py tests/test_benchmark_cases.py tests/test_easy_cases.py tests/test_release_benchmark_audit.py -q
```

The audit prints JSON and does not overwrite evidence. [result.json](result.json) contains the per-case results, recomputed per-load metrics, exact input file SHA256 hashes, and replay blockers. Hashes bind the report to saved files; they do not independently prove GPU execution.

Validation at creation: **60 benchmark/audit tests passed**. An initial command named the nonexistent `tests/test_benchmarks.py`; it ran no tests. The corrected suite above passed.
