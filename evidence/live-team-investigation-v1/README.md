# Trace-informed autonomous Sera rehearsal

Passed on 2026-09-13. Source: `27f877d34b9ef90b8ed4c1010503dbbd277ee562`.

Sera deployed Qwen2.5-72B with FP8 weights, measured the workload, generated tuning options, tested one agent-selected change, rejected its insufficient gain, and returned the measured reference. A new request passed after the runner was returned. All three runtime instances closed with `cleanup_pass: true`; the final GPU check was 0 MiB.

## What the agents did

1. A quantization advisor recommended FP8 weights because the BF16 weight estimate exceeded the card's physical memory. An independent arbiter approved the deployment trial.
2. The deployed model passed all eight fixed tasks. Sera retained the same live process as the measured reference; there was no reload at that handoff.
3. The automatic policy generated two single-setting options: context limit 256 and batch-token limit 2048. Neither was supplied as a hand-picked CLI candidate.
4. The batching specialist proposed batch tokens 2048. The arbiter approved it, and Sera measured it under the same four concurrency levels.
5. Quality passed, but the latency gain was only 0.0397357%, below the fixed 5% threshold. The reviewer marked the prediction refuted.
6. The next specialist received the measured history and abstained. Sera stopped at two of three allowed trials, restored the reference, tested the returned runner, and closed it.

The context-256 option was not tested. Quantization and batching acted in separate stages, not competing in one round. The parallelism role was inactive on this single-GPU runtime.

## Measurements

| Configuration | Task score | Timed requests | Worst per-load p95 | Output tokens/s | Sampled peak GPU memory |
| --- | --- | --- | --- | --- | --- |
| FP8 reference, batch tokens 4096 | 8/8 | 96/96 successful | 773.803563 ms | 26.099160 | 88,687 MiB |
| FP8 candidate, batch tokens 2048 | 8/8 | 96/96 successful | 773.496087 ms | 26.093338 | 88,561 MiB |

The quality floor stayed at 0.99. Both configurations used BF16 KV, context 4096, sequence limit 8, and concurrency levels 1, 2, 4, and 8. Throughput uses total output tokens divided by the combined measured windows. Startup and trace export are excluded from those windows. Startup took 64.06 seconds for the reference and 62.06 seconds for the candidate with model files already present.

The returned reference answered the first task again with `{"answer": 5}` in 495.62 ms. This was a new request through the returned runner, not a held-out question. The command closed that runner after the check; this saved result is not a currently running model.

## Weave evidence

[Open the complete trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09a0f-065b-7fcd-b076-d419fd5ae02d).

The post-run API audit found 297 completed calls with no exceptions, including 273 saved model requests, seven provider responses with returned reasoning, two batching-specialist calls, two arbiters, two reviewers, and one quantization advisor. Seven automatically traced provider calls and two metric records complete the child calls.

[weave-verification.json](weave-verification.json) records exact comparisons between persisted Weave outputs and the saved model requests, metrics, provider content/reasoning, and specialist evidence. All comparisons passed. [verify_weave.py](verify_weave.py) preserves the read-only audit used in Molab; it does not run inference.

Agents received bounded examples from the local request records also exported to Weave: up to four quality examples, prioritizing task failures, and two slow measured requests. They did not query a remote Weave or MCP server. All tasks passed in this live run; separate offline tests verify failed-answer selection and later-round feedback. Examples are selected evidence, not representative averages. Trace export span duration is logging time; request `latency_ms` is the measured inference time. Queue snapshots are cumulative and do not establish memory pressure.

## Reproduce on the supplied GPU

Install the matching Sera source in the notebook environment as well as checking out the repository. Molab puts installed packages before the checkout on its import path. The first launch used an older installed package and stopped before GPU work; [preflight-import-failure.log](preflight-import-failure.log) preserves that error. Updating the notebook's pinned package to the source commit above resolved it. The successful launch is in [console.log](console.log).

With the W&B key in `WANDB_API_KEY`, run from that checkout:

```bash
python -m experiments.run_investigation \
  --model Qwen/Qwen2.5-72B-Instruct \
  --fit-first --auto-space --budget 3 \
  --priority latency --concurrency 1 2 4 8 \
  --project vvennela-n-a/wandb_agent_default_project \
  --provider-check evidence/provider-v5/result.json \
  --output-dir sera-runs/new-team-rehearsal
```

This uses GPU time and requires a new output directory. The candidate budget includes deployment. Agent proposals can differ between runs; the command does not force a trial or a win. The saved passing provider certificate matches the unchanged response schemas. Later CLI hardening for malformed provider attempts is covered by offline tests, not an additional GPU rehearsal.

## Files and limits

[result.json](result.json) contains the full decisions, prompts, responses, measurements, automatic policy, and agent history. [report.md](report.md) is the generated readable report. [invocation.json](invocation.json) records successful completion, trace status, and runner cleanup. Per-runtime folders retain trial records, raw metric snapshots, runtime fingerprints, and server logs.

All 27 transferred runtime/result files were checked against [transfer-manifest.json](transfer-manifest.json). Server-log carriage returns were normalized to newlines during text transfer; both original-byte and normalized-text hashes are recorded. JSON and metric files match the remote bytes.

This proves the bounded single-model loop and its trace trail. It does not prove a speedup, optimal settings, search superiority, arbitrary-model support, two-model placement, or ARIA integration. The BF16 rejection is a fit estimate, not a measured BF16 performance comparison.
