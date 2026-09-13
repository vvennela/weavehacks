# Luna: complete expanding-search loop, with a controller reconnection

Sera completed four GPU trials across three swarm rounds without a total trial cap. Three Luna investigators worked in parallel in each round, read Weave evidence, shared findings, and sent refined proposals to an arbiter. The arbiter chose experiments; no person selected the settings.

| Measured configuration | Tasks | Worst-load p95 | Startup |
| --- | --- | --- | --- |
| FP8 weights, BF16 KV reference | 8/8 | 769.48 ms | 65 s |
| Prefix caching | 8/8 | 625.37 ms | 64 s |
| Batch tokens 2048, caching off | 8/8 | 770.49 ms | 62 s |
| Prefix caching + batch tokens 2048 | 8/8 | 625.56 ms | 63 s |

The winner is **prefix caching alone**, with **18.73% lower p95** than this run's measured reference. The batch-only candidate did not improve latency. Its combination with caching also did not improve the incumbent. This was the measured confirmation after a no-progress round, so Sera stopped with `objective-plateau-confirmed`. It restored the caching winner, passed a fresh request through the returned runner, closed it, and recorded zero remaining GPU memory.

The same eight strict tasks, 99% quality floor, 5% progress threshold, and concurrency 1/2/4/8 were used throughout. Each of the 18 initial/refinement specialist prompts contained eight distinct legal options. Eight is an option-list limit, not a GPU trial cap. A combination was eligible because both component trials passed task quality; the batch-only component did not have to improve latency to be considered in a newly measured combination.

## Connection interruption and limits

The local controller exited after three unsuccessful read-only connection attempts. The GPU process stayed active. The operator restarted the same controller command against the same relay and output directory; no GPU trial was restarted. See [the restart record](../live-luna-expanded-controller-v2/controller-restart.json). The agents continued the same search and selected the confirmation candidate themselves.

One invalid-output response and one timed-out attempt were rejected, followed by successful responses. This run proves automatic experiment selection, feedback, validation, and stopping **with a manually restored transport connection**. It does not prove unattended recovery from a long outage. The earlier interrupted run remains in `../live-luna-expanded-v1`; it was not overwritten.

Latency uses repeated prompts after per-load warmup; startup is measured separately. The gain does not apply to unseen or cold traffic without another measurement. Eight tasks are not broad model-quality evidence. The stopping rule is not statistical proof of a plateau, global optimality, or a search advantage over simpler methods. BF16 weights did not fit; there is no measured BF16 speedup comparison.

## Verification and trace

[Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09b20-b22e-7adb-8fb2-e7a4b6e4ca17): **664 exported calls and 45 completed typed agent responses**. These are not GPU trial counts.

`verification.json` passes with no issues: three concurrent investigators, scoped reads in every round, shared findings, actual measured feedback, combination selection, confirmation stopping, returned-runner probe, and cleanup. `independent-audit.json` recomputes all task scores and candidate gates, verifies the measured combination parents and runtime flags, binds the 45 completed responses to saved Luna CLI calls, and checks all 18 eight-option shortlists. These checks do not certify the truth of every agent explanation.

GPU source: `c7c8ae1b6bcca5d0ed73640ecc12fd0dfbe98d7c`. Controller source at initial launch: `d4d55b0e1a90b47500adafde7ad26e36c5795fe8`; its code was unchanged at reconnection. The original 34-case `provider-luna-expanded-v1` certificate was reused because the schema did not change. Raw controller calls and launch records are in `../live-luna-expanded-controller-v2`.
