# Two real swarm iterations: safe recovery, investigation gap

[Open the completed Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09a31-ec01-7c30-86cd-c51337b414a9). Source: `61aad6c9e8b08aea4de595963f3aabe3400ef00e`.

This run used Qwen2.5-72B with FP8 weights and BF16 KV on the RTX PRO 6000. It kept the same eight strict JSON tasks, 99% quality floor, 5% latency-improvement requirement, and concurrency levels 1, 2, 4, and 8. The budget allowed two candidate trials, plus the baseline.

| Stage | What happened |
| --- | --- |
| Baseline | Passed 8/8 tasks; worst-load p95 774.183015 ms. |
| Round 1 | Three investigators read Weave. Initial proposals differed, then all refined to context 256. vLLM failed during startup with a CUTLASS internal error. No task-quality or latency measurement exists for this candidate. |
| Round 2 | The agents received the failure record but all declined fresh inspections. Two repeated proposals were rejected. The arbiter selected batch tokens 2048; it passed 8/8 tasks with p95 773.763191 ms. |
| Return | The 0.054228% latency gain was below 5%. Sera restored the baseline, passed a repeated known-question probe, and closed. GPU memory returned to 0 MiB. |

## What this proves

Three independent investigators produced competing initial settings, shared findings, and refined their proposals. The controller attempted one candidate per round, rejected illegal repeats, kept its gates, recovered from a failed start, and returned a usable reference. Both allocated candidate trials were counted, including the failed start.

It does **not** prove useful failure-driven investigation. In round two the agents skipped Weave reads. Several explanations misread 2,265 input tokens per load as tokens per request; actual prompts contain 85–109 tokens. Their claims about context limits relieving KV pressure were not established. The first reviewer correctly said the latency prediction was not tested, but the old controller rejected that review. These defects remain in the original record.

Later code requires a successful failure inspection before a new proposal, accepts “not tested” for an unmeasured performance prediction, exposes exact safe startup-error evidence, and labels per-request token counts. Those fixes were not running during this recording.

## Specific startup failure

The original [server log](trial-1/server.log) reports `cutlass_gemm_caller` with `Error Internal` at `cutlass_gemm_caller.cuh:62`. The raw log's LF-delimited lines are 404 and 539. Its SHA256 is `0ecab48aa5f47a86284b294135bf33bf523e13da139a06cac3aea0ba5901f065`. This identifies the observed failing operation, not the underlying cause of that kernel error. There is no evidence here that FP8 is universally broken, that the model answered incorrectly, or that this was an out-of-memory error.

## Evidence

The original result, invocation, report, server logs, metrics, and complete Weave call dump are preserved. All 33 transferred files matched their original byte hashes. `weave-verification.json` is the first audit and is intentionally preserved: it reports real missing inspections and also exposed audit bugs involving Weave call-reference serialization and failed starts without metrics. Corrected audits must be saved separately.

Use this plain-English explanation: “The agents proposed a change that crashed during loading. Sera recovered, tested a different change, found no useful speedup, and returned the working model. The run also exposed that our agents could skip investigating a failure; we fixed that rule instead of presenting the skipped investigation as success.”
