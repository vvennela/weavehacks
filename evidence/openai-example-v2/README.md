# Full direct-API dry run: passed

Run source: `f4d8fa60c6b821ac9400b6c2cacfb048d3b21338`.
Date: 2026-09-13. Total elapsed time: **838.164 seconds (13:58)**, including the
provider check. This is a real GPU run, not a scripted agent or simulator.

Three Astra investigators called OpenAI through LiteLLM from Molab. There was no
local Codex relay controller. The provider passed all 34 fixed compatibility
cases on the first attempt. The prior [failed check](../openai-example-v1/README.md)
remains saved; its missing specialist-role schema description was fixed without
relaxing validation.

The run called `ExampleRun.optimize()`, which calls `sera.optimize(mode='swarm')`.
It used Qwen2.5-72B, FP8 weights, BF16 KV cache, eight unchanged strict-JSON tasks,
concurrency 1/2/4/8, a 99% quality floor, and a 5% progress threshold. There was no
total candidate-trial cap. It started from the explicitly configured FP8
baseline, not a new fit-first quantization search.

| Configuration | Worst-load p95 | Task score | Startup | Sampled GPU peak |
| --- | --- | --- | --- | --- |
| Reference | 771.05 ms | 8/8 | 71.08 s | 88,687 MiB |
| Prefix caching | 624.79 ms | 8/8 | 65.07 s | See audit |
| Graph execution only | 764.07 ms | 8/8 | 77.08 s | See audit |
| Prefix caching + graph execution | **618.59 ms** | **8/8** | 80.08 s | 88,347 MiB |

Every configuration completed 96 timed requests with zero generation errors.
The winner reduced p95 by **19.7729%** relative to this run's reference. This is
request latency, not startup time or Weave logging-span duration. Model weights
were already cached. The gain applies to warmed, repeated short prompts, not
arbitrary traffic, general model quality, or unseen inputs.

## The loop

Each of three rounds ran three investigator instances in parallel. They chose
read-only Weave queries, proposed experiments, shared findings, and refined
their proposals. The arbiter selected one GPU candidate per round:

1. Prefix caching passed quality and improved p95 by 18.97%.
2. Graph execution alone passed quality, but did not beat prefix caching.
3. The confirmation round combined both measured, quality-passing changes.
   It improved the current winner by about 0.99%, below the 5% progress rule.

Sera stopped with `objective-plateau-confirmed` and selected `trial-3`. This is
the declared stopping policy, not statistical proof of a plateau or global
optimality. It does not establish that three agents beat one agent or grid search.

A fresh request through the returned runner passed in 437.64 ms. It repeated a
known task; it was not a held-out quality test. Cleanup returned GPU use to zero.
The launcher and final evidence audit both exited with code 0. The runner is
closed; this recording does not leave a model service running.

## Weave verification

[Completed trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09c11-ca49-7d43-94cf-e56c54f98ac4):
**746 completed calls, zero call exceptions**. The trace includes 42 typed agent
responses and 552 recorded model requests. These are not GPU trial counts.

The audit checked each investigator's completed read, its Weave source, and all
eight distinct cited record hashes against current cloud records. The agents
read load metrics and slow model requests, including inputs and outputs. The
quality evaluator is local deterministic code; Weave supplies recorded evidence,
not a replacement quality judge.

- [Audit summary and full agent proposals](audit-summary.json)
- [Measured investigator phase timestamps and proposal changes](replay-timings.json)
- [Launch script](run.py)
- [Audit script](audit.py)

The full 32 MB optimizer record remains at
`/marimo/sera-evidence/openai-example-v2/swarm-59bf8318c3fa/result.json`.
The compact audit records its SHA-256, the invocation, provider-certificate hash,
all measured results, proposal/arbiter records, and verified Weave read hashes.
Secrets were supplied only through the runtime environment. The exported audit
was checked for the active OpenAI and W&B keys before saving it in the repository.

The source suite passed **1,582 tests, one optional skip**. This is narrow live
acceptance on the tested Molab GPU, not general production certification.
