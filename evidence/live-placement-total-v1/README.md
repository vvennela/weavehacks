# Two-model placement: passed and independently audited

The specified Qwen3-0.6B and GLM-4-9B pair ran together within the declared
**24 GiB total-device budget**. Both kept the unchanged eight tasks, **99% quality
floor**, zero generation errors, and **at most 10% p95 slowdown**. Both returned
runners answered a fresh task correctly, then closed. Device memory returned to
**0 MiB**, with no remaining owned process groups or GPU process rows.

| Service | Precision | Isolated p95 | Joint p95 | Slowdown | Joint limit |
| --- | --- | --- | --- | --- | --- |
| Qwen3-0.6B | BF16 weights/KV | 136.49 ms | 138.78 ms | 1.67% | 150.14 ms |
| GLM-4-9B | FP8 weights, BF16 KV | 170.85 ms | 177.93 ms | 4.15% | 187.93 ms |

Each model passed **8/8 serial task checks and 96/96 timed task checks** across
concurrency 1/2/4/8. Both measurement windows overlap at every load. The recorded
joint p95 values are the worst per-load p95, not a pooled average.

Sampled total device peak: **19,904 MiB (19.44 GiB)**, below 24 GiB. Qwen and GLM
startup took 45.05 s and 65.06 s, respectively; these are separate from request
latency. No further optimization or trial was needed to pass.

## What Sera did

Luna selected the sole eligible plan from four frozen plans. Three alternatives
were rejected by deterministic memory estimates before GPU execution. The
selected plan had passing, exactly bound isolated references. The executor then
measured both live services together and enforced every gate before returning
either runner. Search stopped because no untested legal plan remained.

The source audit matches **272 raw request outputs** to the saved Weave trace,
including all warmups, timed requests, and serial quality checks. It also checks
the actual arbiter request/response, gate events, trace ownership, and completion
of all **279 trace calls**. The two post-return probes and final cleanup are saved
external records; they are not presented as children of the ended trace root.

[Open the joint placement trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09bce-654d-71f2-aaf4-3accd0872b4e).

## Scope and limits

- The physical GPU has 97,887 MiB. The deliberate 24 GiB budget represents smaller
  memory capacity, **not another card's speed or bandwidth**.
- Accounting verifies sampled **total device memory**. The 3 GiB Qwen and 17 GiB
  GLM allocations are configured vLLM budgets, not separately verified hard caps.
  Sampling can miss short peaks.
- The matching all-BF16 plan fails its declared allocation estimate. It was not
  measured. This supports the fixed-allocation quantized configuration comparison,
  not a claim that every possible BF16 allocation fails 24 GiB, nor measured BF16
  memory savings.
- This was one eligible placement plan and one arbiter choice. It is not a
  multi-round placement swarm or proof of global optimality.
- Both services used the same requested-output-type schemas as their references.
  Previous failed quality profiles remain unchanged.

## Repeat the audit

```bash
PYTHONPATH=. python evidence/live-placement-total-v1/audit.py
```

The audit regrades raw serial and timed outputs, recomputes every load's latency,
checks exact model/configuration/schema/token/reference binding, recomputes
overlap, checks the unchanged 10% limits, verifies both probes and cleanup, and
matches saved Weave outputs. `audit.json` records source hashes and all verdicts.
Two negative checks substitute corrupted records in memory only: a wrong task
answer is rejected by regrading, and an altered p95 is rejected by raw-request
reduction. Neither check edits the evidence files.
It makes no GPU, provider, or network calls. It verifies artifact consistency,
not independent proof of execution. Original measurements are never rewritten.
