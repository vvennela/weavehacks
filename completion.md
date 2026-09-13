# Sera completion checkpoint

Updated 2026-09-13. **Core single-model loop demonstrated; full specification not complete.**
This file separates implementation from measured acceptance. It does not mark
unproven features complete because their tests pass.

## What works

The autonomous loop has real Luna and Astra recordings: three investigators read
evidence, share findings, propose experiments to an arbiter, receive measured
feedback, and stop under the progress rule. Deterministic code controls legality,
quality, selection, and cleanup. There is no fixed total trial cap in those runs.

The [Astra recording](evidence/live-astra-expanded-v1/README.md) completed three
rounds and four GPU trials. All eight tasks passed; worst-load p95 improved
19.55% on the repeated-prompt workload. It returned a usable runner and closed
cleanly. The [Luna repeat](evidence/live-luna-expanded-v2/README.md) also completed,
with an 18.73% gain on that workload; it required one controller reconnection.
Neither result proves general reasoning reliability or globally optimal settings.

The combined source suite passes **1,334 tests**, with one optional marimo skip
(`uv run --frozen --extra dev pytest -q`, 46.89 s). The final ownership-diagnostic
change also passes the 50-test focused placement suite.

The [README quick check](README.md#quick-test-does-the-loop-work) passes 45 offline
checks and includes a repeatable script that saves a synthetic loop report. It
requires no GPU or API key and makes no real inference-performance claim.

## Requested steps 1–6

| Step | Verified result | Still missing |
| --- | --- | --- |
| 1. Search comparison | Live search found the near-oracle winner in 1 trial versus fixed grid's 3; random replay median is 2. Saved outcomes and provider ablations are audited. | Full section 19.4 acceptance. This is a three-candidate exploratory comparison; all ablations tie. No measured swarm-coordination advantage. |
| 2. Two-model allocation | Automatic selection, reference binding, joint executor, output schemas, latency gates, and tracing are merged. Qwen at 3 GiB and GLM at 17 GiB pass isolated calibration. | Passing joint run, automatic live selection, two returned runners, and a verified capacity claim. Molab hides per-service GPU identity. |
| 3. Free GPU capacity | Online FP8 makes pinned Qwen72B fit where its BF16 weights exceed the physical card. The new two-model calibration passes each service's smaller allocation alone. | Do not present isolated results as simultaneous sharing. Real 2/4/8-GPU validation is excluded by user agreement, not completed. |
| 4. Recovery | SQLite checkpoints, exclusive ownership, interrupted-trial handling, and safe resume are merged. Offline process-kill tests pass. | Real unattended GPU/controller outage recovery. The supported resume constraints are explicit. |
| 5. Pressure scenarios | Both frozen pilots ran, their raw counters were audited, and cleanup passed. | Neither scenario met its acceptance thresholds. No cache-pressure or reversed-pressure optimization claim. |
| 6. Release | Combined source tests and clean base/swarm package checks pass. Raw evidence, scripts, and reports are saved. | Final combined installed-package GPU rehearsal and partner's presentation rehearsal. Existing clean-install checks do not prove those. |

Evidence: [benchmark and pressure audit](evidence/final-benchmark-audit-v1/README.md),
[live grid comparison](evidence/live-grid-comparison-v1/README.md),
[capacity calibration](evidence/capacity-calibration-v1/README.md),
[SQLite recovery](docs/optimizer-recovery.md),
[latest clean package checks](evidence/final-package-release-v2/README.md).

The final tested wheel is built from source `9fb0851`; SHA-256:
`27d3abc04afe55423538f93aa41104e6085ffe1b49cdd7a86534daed1b4f348f`.
Both clean installations and all 66 packaged source-file comparisons pass.

## Immediate decision: joint GPU accounting

The approved 24 GiB demonstration budget is explicitly smaller than the physical
97,887 MiB card. Both models pass all eight task checks and all 96 timed requests
at concurrency 1/2/4/8 under their isolated allocations:

| Model | Isolated peak | Isolated p95 | Required joint p95 ceiling |
| --- | --- | --- | --- |
| Qwen3-0.6B, BF16 | 2,803 MiB | 136.49 ms | 150.14 ms |
| GLM-4-9B, FP8 weights/BF16 KV | 17,105 MiB | 170.85 ms | 187.93 ms |

The smaller 2.5 + 15 GiB pair fails the declared Qwen memory estimate before
startup. Matching BF16 alternatives are also saved as estimated rejections.
No unsafe configuration was loaded. Both measured services closed to zero GPU
memory. The audit matches 272 request outputs against actual Weave records.

During GLM execution, the API PID was 58350 and the engine PID was 58452, but
both NVIDIA tools reported GPU memory under PID 1. The gVisor sandbox exposes no
usable translation. This blocks **separate service hard-cap verification**, not
isolated task quality. Sera now reports this cause explicitly and does not
falsely certify cleanup of unresolved memory.

Joint testing is paused pending the user's choice: retain separate hard caps
and require a compatible accounting environment, or explicitly approve a Molab
mode that enforces the total 24 GiB device limit without claiming separately
verified service caps. No such contract change is applied yet.

## What runs where

| Component | Location | Authentication |
| --- | --- | --- |
| Repository, tests, Codex relay controller | Local Mac | Existing Git and Codex login |
| Sera optimizer, validator, Qwen/GLM and vLLM | Molab Linux GPU | Notebook pairing token |
| Luna/Astra investigator inference | Hosted OpenAI models, called by local controller | Existing Codex login; not local model inference |
| Traces and trace reads | W&B Weave cloud | `WANDB_API_KEY` in Molab |
| W&B serverless model inference | Optional investigator route | W&B key; not the Qwen/GLM GPU runner |
| ARIA | W&B application; not integrated | Account access still needs verification |

No secret values are saved here. A Weave key does not provide control over a
hosted model's GPU configuration. The current Codex investigator route requires
the local controller to remain connected to Molab.

## Release and claim boundaries

- Supported fallback: single-model live API plus saved real swarm recordings.
  No currently open model service is promised; the calibration runners are closed.
- Joint sharing, strict full benchmark acceptance, pressure demonstrations, and
  real outage recovery remain unproven. Do not call the entire specification done.
- The sampled memory limits do not guarantee that very short peaks were captured.
- Startup/download time is separate from measured request latency.
- The partner's demo and website files were not changed in this work.
- ARIA remains optional. The [updated access review](docs/aria-programmatic-review.md)
  documents a UI-configured event trigger, not a verified typed request/response
  integration. It cannot replace the working Sera loop or bypass its validator.
