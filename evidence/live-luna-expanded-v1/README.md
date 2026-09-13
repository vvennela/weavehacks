# Expanded Luna run: measured gain, interrupted confirmation

The three Luna investigators received eight legal candidate options each, inspected evidence, shared findings, and sent proposals to the arbiter. The first round included different ideas: prefix caching and graph execution. The arbiter chose caching.

| Measured configuration | Task score | Worst-load p95 |
| --- | --- | --- |
| FP8-weight deployment, BF16 KV | 8/8 | 770.60 ms |
| Prefix caching enabled | 8/8 | 625.34 ms |
| Batch-token limit 2048, caching disabled | 8/8 | 773.40 ms |

Caching reduced measured p95 by **18.85%**, exceeding the unchanged 5% target. The traffic repeats eight prompts after warmup. This is a warm/reused-input result, not a speedup claim for arbitrary unseen inputs. The smaller batch budget did not improve latency.

The generator refreshed its menu and offered a caching-plus-batching combination after both components passed task quality. No combination trial ran. Both local controllers exited with a relay connection/validation error. Later Luna requests timed out, so round three produced no valid proposal. The exact connection failure cause is not established. The run stopped at `no-valid-selected-proposal`, not a measured plateau.

Sera returned the accepted caching configuration, passed a fresh request, closed the runner, and recorded zero remaining GPU memory. The independent audit recomputes all three task scores and candidate gates, binds all 33 completed live responses to their local Luna CLI records, and checks all 18 specialist prompt shortlists. There were 16 timed-out attempts. The strict full-loop audit fails because the confirmation was not executed and two investigators skipped optional reads in round two.

[Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09af0-cf43-7bcf-899c-0fb6c230e46d): 517 exported calls. See `independent-audit.json`, `verification.json`, and the raw controller records in `../live-luna-expanded-controller-v1`.

GPU source: `c7c8ae1b6bcca5d0ed73640ecc12fd0dfbe98d7c`. The original controller used `c10c9fe2be796150263821aba873014d9043651a`. A later controller fix retries read-only connection failures; it does not change this saved run or its acceptance rules.
