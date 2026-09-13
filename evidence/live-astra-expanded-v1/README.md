# Astra: complete expanding-search loop

Sera completed four GPU trials across three swarm rounds, without a total trial cap. Three independent Astra investigators inspected Weave records in parallel, proposed experiments, shared findings, and sent refined proposals to an arbiter. Each received eight legal options per phase.

| Measured configuration | Task score | Worst-load p95 | Startup |
| --- | --- | --- | --- |
| FP8 weights, BF16 KV reference | 8/8 | 770.49 ms | 66 s |
| Prefix caching | 8/8 | 625.34 ms | 63 s |
| Graph execution, caching off | 8/8 | 764.91 ms | 191 s |
| Prefix caching + graph execution | 8/8 | 619.85 ms | 79 s |

The winner reduced p95 by **19.55%** against the measured reference. Startup is excluded from request latency. The workload repeats eight prompts after per-load warmup, at concurrency 1, 2, 4, and 8. This result applies to that reuse pattern; it is not an unseen-input or broad model-quality benchmark.

## What the agents did

1. An advisor and arbiter selected online FP8 weights after the BF16 fit estimate failed. Sera loaded the model and checked its answers.
2. The first swarm round considered caching and graph execution. The arbiter selected caching; it passed quality and reduced p95 by 18.84%.
3. The next round used those measurements and selected graph execution as an isolated change. It worked and preserved quality, but its 0.72% reference-relative gain was below the 5% target and slower than caching.
4. With two independently quality-passing changes, the generator offered their combination. The last round also considered prefill scheduling and memory allocation. The arbiter selected the combination, naming both actual component trials.
5. The combination was measured again and became the fastest accepted configuration. It added only 0.88% over the caching winner, below the 5% per-round progress threshold. That completed the no-progress-plus-one confirmation rule, so Sera stopped.
6. Sera returned the combination, passed a fresh request through the returned runner, then closed it and recorded zero remaining GPU memory.

The 99% task-quality floor and 5% improvement target were unchanged. This is a measured stopping-policy result, not statistical proof of a plateau or global optimality. It does not prove a swarm beats one agent or a fixed search order.

## Verification

[Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09b0c-d1ac-74ea-a68c-06a4872829c4): **662 exported calls, 45 completed typed agent responses**. These are not GPU trial counts.

`verification.json` passes with no issues: three concurrent investigators, shared findings, trace provenance, actual trial feedback, the confirmation stop, and returned-runner checks. `independent-audit.json` also recomputes all four task scores and candidate gates, checks the combination's measured parents and launch flags, binds all 45 live responses to completed Astra CLI calls, and checks all 18 eight-option prompt shortlists. No agent attempts timed out.

Raw local Codex records are in `../live-astra-expanded-controller-v1`. GPU source: `c7c8ae1b6bcca5d0ed73640ecc12fd0dfbe98d7c`. The local controller was restarted at `5b872a546bd09f65f1de28e21995a06f60ec17eb` before this GPU run; that change adds bounded read-only connection retries. The earlier 34-case provider certificate remains unchanged.
