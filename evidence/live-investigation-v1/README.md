# Real agent investigation: completed, reference retained

Source revision: `ae81606c0978de404755e777249a254660a154dc`.
[Open the Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a099cb-eb93-7ae1-aa16-b453793a3058).

Sera completed two decision rounds and one candidate GPU trial on pinned Qwen2.5-72B. FP8 weights and BF16 KV stayed fixed. The declared candidate batch-token limits were 2,048 and 1,024, against the 4,096 reference. The budget allowed at most two trials; it did not require spending both.

## What happened

1. The batching specialist proposed 2,048 and predicted at least a 5% p95 improvement as its success condition. The arbiter selected it.
2. Sera measured the same eight questions at concurrency 1, 2, 4, and 8. Both configurations passed all eight strict quality checks and all 96 timed requests.
3. Worst-load p95 changed from 773.543058 to 773.438965 ms: only a 0.0134567% improvement. Throughput fell from 26.135632 to 26.112978 output tokens/s. The deterministic gate retained the reference, and the agent review marked the prediction refuted.
4. Round two received that result and review. The specialist proposed 1,024, but the arbiter declined it because the previous trial offered no meaningful gain. No 1,024 GPU trial ran.
5. Sera restored the 4,096 reference. A new request returned `{"answer": 5}` in 492.52 ms. This repeated the first task; it was not a held-out question. All three owned runtimes cleaned up and returned GPU memory to 0 MiB. The command exited 0.

There were five real agent calls, each completed in one attempt. Independent review reproduced all quality grades and metric reductions, verified the identical model/hardware/workload identities, and checked that the later arbiter received the earlier failure evidence.

## What this proves

A real propose → arbitrate → measure → gate → review → use feedback loop works and returns a usable runner. It can stop without spending its full budget.

It does not prove a speedup, better search than grid/random, pressure relief, or two-model placement. Only the batching specialist was active. Queueing and memory-pressure explanations were hypotheses, not established causes. The second specialist's prose described a 2,048-to-1,024 change, while its typed parent remained the 4,096 baseline; no invalid execution followed because the arbiter declined the trial.

A post-run audit found an evidence-assembly bug: the agent input omitted available queue/first-token/preemption snapshots from this multi-load run. The raw per-load `.prom` files and parsed snapshots are preserved, but the lookup expected the older single-load key. The client-side latency/throughput calculations and quality gates are unaffected. This record does not claim that the agents used all available telemetry. A separate code fix forwards load-specific cumulative snapshot fields; it does not retroactively change these agent messages or establish a new live result.

The original report uses the generic stop label `no-valid-selected-proposal`. Its recorded arbiter response shows a valid decline, not a provider or runtime error. A later reporting-only fix distinguishes `arbiter-declined`; this saved evidence is unchanged.

## Show this to a nontechnical partner

“The agent suggested a setting. Sera tried it and found almost no improvement. It kept the working setting. On the next round, the decision agent used that result to reject another weak experiment. The result is a model we can use, plus an audit trail—not a made-up speedup.”

Open `report.md` to follow both rounds. `result.json` contains raw requests, gates, agent messages, and trial history. `invocation.json` records the declared scope and successful returned-runner check. The Molab summary reads these saved files and does not restart a GPU job when rerun.
