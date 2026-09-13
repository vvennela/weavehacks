# Sera completion checkpoint

Updated 2026-09-13. **Single-model swarm and constrained two-model placement demonstrated; full specification not complete.**
This file separates implementation from measured acceptance. It does not mark
unproven features complete because their tests pass.

Latest check: the final installed-wheel joint repeat failed GLM's latency gate
(192.68 ms versus the fixed 187.93 ms ceiling). Both models passed task quality,
memory stayed below 24 GiB, and cleanup returned the GPU to zero usage. The older
passing joint run below remains valid historical evidence, not a guarantee that
the latest repeat passed. The cause of the timing difference is not established.

The blank [Example run notebook](notebooks/Example%20run.ipynb) and hosted-provider
adapters are pushed. Source `f4d8fa6` passes 1,582 tests with one optional skip.
The [full OpenAI/LiteLLM dry run](evidence/openai-example-v2/README.md) passed:
34/34 provider cases, three autonomous search rounds, quality passing on all four
measured configurations, 19.77% lower p95, a fresh returned-runner request, and
zero GPU memory after cleanup. All 746 Weave calls completed without exceptions;
eight distinct records read by the investigators match their cloud-output hashes.
The first [failed provider check](evidence/openai-example-v1/README.md) is preserved.
No API keys are stored in the notebook.

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

The final source suite passes **1,512 tests**, with one optional marimo skip
(`uv run --frozen --extra dev pytest -q`, 62.22 s) on `befda96`, in a fresh frozen
development environment. The previously stale lock file now includes the current
package and its dependencies. Clean installation checks are separate from live GPU acceptance.

[Ordered stages](docs/staged-optimization.md) are implemented and tested through
the real pipeline with synthetic GPU/provider boundaries. For
`stages=['latency', 'quantization'], k=3.0`, a 2% memory gain with 1% latency
regression is accepted; 4% latency regression and quality failures are rejected.
`k` is the allowed regression in earlier objectives, not a minimum gain. Each
stage remeasures the previous winner, freezes its evidence, and preserves the
earlier limits. These tests do not establish a live staged speedup.

The [README quick check](README.md#quick-test-does-the-loop-work) passes 45 offline
checks and includes a repeatable script that saves a synthetic loop report. It
requires no GPU or API key and makes no real inference-performance claim.

## Requested steps 1–6

| Step | Verified result | Still missing |
| --- | --- | --- |
| 1. Search comparison | Live search found the near-oracle winner in 1 trial versus fixed grid's 3; random replay median is 2. Saved outcomes and provider ablations are audited. | Full section 19.4 acceptance. This is a three-candidate exploratory comparison; all ablations tie. No measured swarm-coordination advantage. |
| 2. Two-model allocation | Luna selected the eligible plan. Both models passed simultaneous quality, latency, and overlap gates; two returned runners passed fresh requests and closed cleanly. | Only one plan was eligible, so this does not establish placement-search advantage. Per-service hard caps remain unverified under approved total-device accounting. |
| 3. Free GPU capacity | Qwen72B FP8 fits where its BF16 weights exceed the physical card. The Qwen0.6B + GLM9B FP8 pair now passes together within a declared 24 GiB budget, peaking at 19,904 MiB. | The matching BF16 placement rejection is an estimate, not measured savings or proof that every BF16 allocation fails. Real 2/4/8-GPU validation is excluded by user agreement, not completed. |
| 4. Recovery | Single-model SQLite checkpoints, exclusive ownership, interrupted-trial handling, and safe resume are merged. Offline process-kill tests pass. | Live unattended outage recovery and long-running reliability tests are deferred. Placement resume is not implemented; the single-model resume constraints remain explicit. |
| 5. Pressure scenarios | Both frozen pilots ran, their raw counters were audited, and cleanup passed. | Neither scenario met its acceptance thresholds. No cache-pressure or reversed-pressure optimization claim. |
| 6. Release | Clean base/swarm wheel checks pass. The previous source joint run returned usable runners and cleaned up. | The final installed-wheel repeat failed GLM latency. No generic production certification, live outage test, or soak test. Partner presentation rehearsal remains separate. |

Evidence: [benchmark and pressure audit](evidence/final-benchmark-audit-v1/README.md),
[live grid comparison](evidence/live-grid-comparison-v1/README.md),
[capacity calibration](evidence/capacity-calibration-v1/README.md),
[passing joint placement](evidence/live-placement-total-v1/README.md),
[SQLite recovery](docs/optimizer-recovery.md),
[latest clean package checks](evidence/stable-release-package-v2/README.md).

The final tested wheel is built from source `befda96`; SHA-256:
`e5e3a0856385e4da8523f5d9f4aa294a86bf490dbc99bf1dcd2c1144e653334d`.
Both clean installations and all 68 packaged source-file comparisons pass.
Two independent builds have identical bytes; 23 package audit commands pass.

## Passing joint placement

The approved 24 GiB demonstration budget is explicitly smaller than the physical
97,887 MiB card. It represents memory capacity, not a smaller card's compute
speed or bandwidth. The user approved total-device accounting because Molab
cannot attribute NVIDIA memory to the two separate service processes.

Both models pass all eight task checks and all 96 timed requests at concurrency
1/2/4/8, first alone and then together. The 99% quality floor, zero-error rule,
and maximum 10% latency slowdown remain unchanged:

| Model | Configured allocation | Isolated p95 | Joint p95 | Slowdown | Joint ceiling |
| --- | --- | --- | --- | --- | --- |
| Qwen3-0.6B, BF16 | 3 GiB | 136.49 ms | 138.78 ms | 1.67% | 150.14 ms |
| GLM-4-9B, FP8 weights/BF16 KV | 17 GiB | 170.85 ms | 177.93 ms | 4.15% | 187.93 ms |

The joint sampled device peak is **19,904 MiB**, leaving **4,672 MiB** within the
24 GiB demonstration budget. Both returned runners pass a fresh request for the
first unchanged task. Cleanup leaves zero GPU memory, no owned process groups,
and no GPU compute-process rows. The runners are now closed; no active model
service is promised.

Luna selected the only eligible plan after deterministic fit and reference
checks. The smaller 2.5 + 15 GiB pair and matching BF16 alternatives remain saved
as estimated rejections. This proves selection and measured acceptance, not a
multi-plan placement search advantage. The isolated calibration audit matches
272 request outputs against Weave records. The joint run has its own
[Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09bce-654d-71f2-aaf4-3accd0872b4e).

Total-device mode samples the full GPU memory, checks the declared budget, owns
the local process groups, and requires complete idle-device cleanup. The service
allocations are configured vLLM budgets, **not separately verified hard caps**.
The sandbox can expose GPU memory under PID 1; Sera does not invent per-service
memory values or claim ownership of that aggregate PID.

The task schemas specify response types, not correct answers. Fresh probes show
that returned runners work; they do not establish quality on unseen tasks. A
new prompt through a structured runner requires an explicit response format.

## What runs where

| Component | Location | Authentication |
| --- | --- | --- |
| Repository, tests, Codex relay controller | Local Mac | Existing Git and Codex login |
| Sera optimizer, validator, Qwen/GLM and vLLM | Molab Linux GPU | Notebook pairing token |
| Earlier Luna/Astra investigator inference | Hosted OpenAI models, called by local controller | Existing Codex login; not local model inference |
| Latest Astra investigator inference | OpenAI API through LiteLLM, called from Molab | Runtime OpenAI API key; no Codex controller |
| Traces and trace reads | W&B Weave cloud | `WANDB_API_KEY` in Molab |
| W&B serverless model inference | Optional investigator route | W&B key; not the Qwen/GLM GPU runner |
| ARIA | Optional W&B browser review; not integrated into execution | Signed-in UI review passed; authenticated headless route unverified |

No secret values are saved here. A Weave key does not provide control over a
hosted model's GPU configuration. The current Codex investigator route requires
the local controller to remain connected to Molab.

## Release and claim boundaries

- Supported paths: the single-model live API and measured constrained joint
  placement, with saved real recordings. Returned rehearsal runners are closed.
- Hardware acceptance is narrow: pinned models on the tested single RTX PRO 6000
  Blackwell/Molab/vLLM setup. It does not cover arbitrary models or deployments.
- Strict full benchmark acceptance and pressure demonstrations remain unproven.
  Live outage and soak tests are deferred. Do not call the entire specification done.
- The sampled memory limits do not guarantee that very short peaks were captured.
- Startup/download time is separate from measured request latency.
- The partner's demo and website files were not changed in this work.
- ARIA remains optional. The [browser review](docs/aria-browser-review.md) verified
  a signed-in review and separate headless login-page navigation. It did not
  verify authenticated headless advice extraction or orchestration. It cannot
  replace the working Sera loop or bypass its validator.
