# Large-model deployment: passed

Sera rejected the estimated BF16 plan, asked the W&B agent to choose an estimated-feasible plan, loaded the original pinned Qwen2.5-72B weights with online FP8, and returned a working runner after task acceptance. The test ran on the supplied RTX PRO 6000 Blackwell using implementation commit `14b47b00a985d9d7c3434f8c3e7ef1cd66a12c63`.

| Check | Result |
| --- | --- |
| Original BF16 weight files | 135.43 GiB; cannot fit in 95.59 GiB physical VRAM |
| BF16 runtime estimate | 149.43 GiB; not executed |
| FP8 runtime estimate | 84.05 GiB; eligible for one trial |
| vLLM reported loaded weights | 70.15 GiB |
| Sampled peak total GPU memory | 88,449 MiB / 86.38 GiB |
| Strict task quality | 8/8 correct, including required JSON format; floor unchanged at 0.99 |
| Timed requests | 24/24 successful, concurrency 1 |
| Median / p95 request latency | 511.80 / 573.10 ms |
| Output throughput | 13.66 tokens/s for this short-answer workload |
| Server startup, weights already downloaded | 71.07 s; excluded from request latency |
| Fresh request after runner return | Correct: `{"answer": 5}`; 463.42 ms |
| Cleanup | Passed; GPU memory returned to 0 MiB |

The original download and file validation completed before startup. Its 37 shards are cached in Molab, not committed to Git. KV remained BF16. Model loading and online quantization took 21.11 seconds within the full 71.07-second server startup. Downloads are a separate preparation cost; model loading is still a per-start cost.

The 0.90 service fraction is not a hard total-process memory cap: the observed peak was 0.34 GiB above the planner's 86.03 GiB service budget, but below physical VRAM. This run specified a quality floor, not a separate `max_memory_mib` constraint. Do not claim that the memory estimate was exact or that a strict 86.03 GiB cap passed.

## Agent review issue

The initial agent selected `weight-fp8`. After measurement, it selected `candidate` but labeled the throughput prediction `not-tested` because BF16 measurements were unavailable. That explanation was correct. The fit-first validator rejected this response because it expected the deployment prediction, not a speedup prediction. The raw response and `agent_final_error` remain unchanged in `result.json`. The deterministic deployment decision and returned runner passed independently.

The implementation now states the deployment-feasibility prediction explicitly. The [separate saved-evidence agent review](../large-fit-review-v2/README.md) passed on its first response without rerunning the GPU workload; it does not replace this original record.

## Limits

This proves one agent-directed feasible deployment, not best-plan selection, a speedup, broad model quality, concurrency scaling, or multi-GPU placement. The workload is the same eight easy strict-JSON tasks used in the preceding verified check. No questions, answer keys, thresholds, or output formatting rules changed after seeing results. The runner was closed after the fresh request; use the demo command's interactive mode to keep a new runner open.

[Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a098f0-3057-7eaf-a3c3-a26867d7e8f8). Raw requests, token IDs, agent responses, metrics, runtime details, and server logs are saved alongside this file.
