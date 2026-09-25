# Continue the source-grounded LIBXSMM plan

This continuation preserves the failed phase's original six-attempt/108-call limits, its 32 spent calls and one spent attempt, and the pending scratch-lifetime then SME-scheduling order. It derives the remaining runtime from the original start timestamp plus 1,800 seconds; setup and recovery do not reset that deadline. An expired deadline stops before model setup. The timed-out experiment is not retried.

The validator checks spent budgets, limits, roster, board hash, all 15 ballots, Borda order, pending queue, and the prior timeout. Six tests pass. The baseline must match the original recorded source hash. All scores for eligibility are fresh; prior timings remain research context only. The existing correctness, license, power/settings, repeated-control, and final-holdout checks remain unchanged. This is a specific research continuation, not a general resume API.

The same code and test gates support AC and battery. Each block keeps its power mode fixed and all evidence separate. Fresh agent/search directories prevent overwrite of old reports.

Run: `PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-next-continue-2026-09-25/run.py`.

## Completed outcome

No candidate was promoted and the 1,800 GFLOP/s target was not met. The unchanged reference passed the final held-out check at **1081.13 GFLOP/s**. This is baseline confirmation, not a Sera-discovered speedup.

| Source | Validation GFLOP/s | Paired controls GFLOP/s | Promoted |
| --- | --- | --- | --- |
| libxsmm-aot-reference | 807.12, 1035.77, 1076.97 | Initial baseline | no |
| libxsmm-k-loop-counter-schedule | 1052.69, 1015.52, 855.91 | 866.50, 1093.05, 1087.15 | no |
| libxsmm-k-loop-consume-before-pointer-updates | 1090.83, 1103.35, 972.15 | 984.63, 1031.45, 1086.41 | no |
| libxsmm-k-loop-interleaved-pointer-updates | 998.67, 1067.69, 1066.28 | 1041.96, 997.44, 1062.58 | no |

The complete plan used 72 calls and six attempts, including two implementation timeouts and one abstention. The final store-grouping call timed out; the new timeout handler recorded the failure and allowed the held-out check to complete. The first packing implementation timed out in the prior phase. Neither timeout produced a measured candidate. The scratch proposal was skipped because its required unchanged strides and traversal conflicted with its smaller buffer.

All 22 signed reports were independently verified, with source hashes matching correctness records and unchanged battery power/settings before and after each score. All four measured sources passed 48 deterministic correctness cases. See [verification.json](verification.json) and [search/result.json](search/result.json). The earlier failed phase has three additional verified baseline reports; they remain separate from this block's eligibility.

## Exact source and power coverage

The reference has earlier AC measurements in the [preserved comparison inventory](../cpu-libxsmm-power-comparison-2026-09-24/report.md). The three new candidate sources below have battery measurements only; their AC cells remain unmeasured. No cross-power gain is claimed.

| Source SHA-256 | AC | This battery block |
| --- | --- | --- |
| `7e9ab1076777a40cb0ad30527e381b221d4024cd99f370708971fb652b31810e` | Earlier reference phases | Baseline, controls, and final |
| `71c55f82b9955eefda8ca17f47e59fbe04c98919c7d30d110a6c540f38005bb8` | Unmeasured | 3 validations with paired controls |
| `13bc6a2ba0dc662d722b0ba8d09db1f2fc55ef77396b1056243d5fb154bf3cdc` | Unmeasured | 3 validations with paired controls |
| `a748475df6036ec229169ae103e91d567ca0854e45d885c5c8887c2e9580c36a` | Unmeasured | 3 validations with paired controls |

Final validation: 86 relevant CPU, swarm, and continuation tests passed. The initial regression tests failed before the feedback and timeout fixes were implemented.
