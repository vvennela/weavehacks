# BF16 versus FP8 KV: first task-quality comparison

Both runs completed all 24 tasks, returned identical rendered prompt token IDs, and released GPU memory to zero. No request errors or output-limit truncations occurred. These are original microtasks, not official HLE, DeepSWE, or SWE-bench results.

Frozen suite: `sera-task-v1`, SHA256 `eb33e22a1375f62ee031605653447ff7b904a3d9a3965bf5e81ca33a24fc9b22`.

## Primary results

| Measure | BF16 baseline | FP8 KV cache |
| --- | ---: | ---: |
| Strict task passes | 3/24 (12.5%) | 1/24 (4.2%) |
| Valid required JSON | 3/24 | 1/24 |
| Coding passes | 2/12 | 1/12 |
| Reasoning passes | 0/6 | 0/6 |
| Extraction passes | 1/6 | 0/6 |
| Median request latency | 128.9 ms | 130.0 ms |
| p95 request latency | 421.3 ms | 219.1 ms |
| Maximum request latency | 54,626.5 ms | 301.1 ms |
| Generated tokens | 400 | 358 |
| GPU memory after close | 0 MiB | 0 MiB |

One case passed under both settings. FP8 lost two baseline passes: the inclusive-range repair and record-field extraction. There were no gains. Both lost passes involve output format/structure, so they do not by themselves establish worse reasoning. Mean position-wise token agreement was 0.7717; it is diagnostic, not the task-quality score.

## Formatting is a major confounder

The frozen contract requires exactly `{"answer": ...}` without Markdown. BF16 had 21 format failures and FP8 had 23. We did not loosen the grader after inspecting outputs.

A separate post-hoc inspection found four additional correctly typed answers inside a single outer JSON code fence in each run: `code-02-default`, `code-05-stable-sort`, `reason-01-remainder`, and `extract-02-status-filter`. Ignoring only that fence would produce 7/24 and 5/24, respectively. These are diagnostics under a different rule, not replacement primary scores or a new acceptance policy. Malformed JSON, extra fields, and incorrect values were not repaired.

There are clear task errors as well. Both configurations return 385 for 2 seconds plus 350 milliseconds (expected 2350), and both return the original five-element list instead of the requested three-element slice. This model/configuration is not yet a strong quality reference for the selected workload.

## Timing limits

The BF16 first measured request took 54.626 seconds after two warmups. Server logs show a running request during the delay but do not establish its cause. It is retained in every reported statistic. With 24 samples, nearest-rank p95 is the second-slowest sample and does not show that maximum; read both.

Median latency is effectively tied. Do not claim an FP8 speedup from p95 or aggregate token throughput: there is one pass, the BF16 outlier is unresolved, and output lengths differ. A timing follow-up must repeat the entire frozen suite for both configurations and report each pass separately. Server metrics include warmups; task timing uses the 24 saved request samples only.

The task run uses chat templating with thinking explicitly disabled, a 128-token cap, temperature 0, seed 0, concurrency 1, and the same pinned Qwen revision. Server flags differ only in KV precision and local port. Both use a 0.90 memory fraction; no reduced allocated-memory footprint is claimed. The collector uses a 15-second graceful shutdown setting, and neither task run required its forced-shutdown fallback.

## Evidence and reproduction

- `comparison.json`: strict scores, paired outcomes, token agreement, and timing.
- `../tasks-v1-bf16/`: raw BF16 responses, prompt/output tokens, server log, and metrics.
- `../tasks-v1-fp8-kv/`: the corresponding FP8 KV evidence.
- `../../benchmarks/`: cases, deterministic grader, and fixed protocol.
- `../../experiments/run_task_benchmark.py`: live collection function used through marimo-pair; it does not execute model-generated code.

Recompute locally from the repository root without a GPU:

```bash
python3 -m experiments.compare_task_vectors evidence/tasks-v1-bf16/result.json evidence/tasks-v1-fp8-kv/result.json
```

No Sera configuration is promoted by this pilot. The next product decision is whether answer correctness and JSON-format compliance should be separate gates. The existing specification's token-agreement acceptance rule has not been silently replaced.
