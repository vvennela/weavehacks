# Ten-run AC replay

Status: completed; no candidate promoted; ten-run goal not met. The current Mac is on AC Automatic. This block changes no power setting and does not consume permission for another temporary battery Automatic block.

Replay the exact four kernels from `cpu-libxsmm-editable-panel-2026-09-25` in their saved swarm-selected order. Use ten fresh baseline reports and ten alternating candidate/control pairs per candidate, then one held-out report for the selected source. Recheck deterministic 48-case correctness and record power before and after every official report. Preserve frozen hill, compiler, numerical tolerance, thread count, source hashes, and existing 5% separated-range promotion gate. Astra-high adjudicates fresh evidence through Codex ChatGPT login only. No new implementation or proposal call is required.

The user goal is to beat the imported baseline peak consistently over ten runs. The historical imported peak is 1668.5964359101147 GFLOP/s from Battery Automatic. Whether the user intends this historical peak or a fresh same-mode peak is awaiting adjudication. Collecting ten-run AC evidence supports either comparison without choosing between them. Report both. The internal legacy 1800 target is retained only to avoid changing an unresolved acceptance policy; its target_met flag does not decide the new goal. A retained baseline is never a Sera improvement.

Run caps stay six attempts, 108 model calls, 180 seconds per agent call, and 1800 seconds per block. An incomplete ten-run series cannot satisfy the user goal. No automatic retries or pooled power modes.

Validation before measurement: five replay/preflight tests plus 21 kernel-search tests passed. The preflight tests were first run without the driver and failed as expected.

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-ten-run-ac-2026-09-25/run.py
```

## Verified result

All 91 official report signatures verified: 10 baseline validations, 40 candidate validations, 40 unchanged paired controls, and one final report. All five exact sources passed 48 deterministic correctness cases. Power source and settings stayed unchanged. Four Astra-high review calls rejected all candidates; no implementation call was needed because this replay used the previously ranked swarm sources.

The fresh imported baseline scored 1153.53–1685.62 GFLOP/s (median1529.21). The saved historical peak for comparison was1668.60. Each validation score remains the frozen evaluator's best of three timed calls; ten reports do not mean ten individual timed calls.

| Candidate | Min / median / max GFLOP/s | Above saved peak | Above fresh AC peak | Paired wins |
| --- | --- | --- | --- | --- |
| libxsmm-n512-panel32-one-streaming-region | 1251.20 / 1493.03 / 1701.65 | 3/10 | 1/10 | 5/10 |
| libxsmm-full512-reserve-scratch-once | 1077.51 / 1389.38 / 1565.22 | 0/10 | 0/10 | 1/10 |
| libxsmm-full512-w32-k-loop-counters | 1050.63 / 1423.75 / 1667.73 | 0/10 | 0/10 | 4/10 |
| libxsmm-full512-fmopa-order-0132 | 1197.04 / 1459.39 / 1669.47 | 1/10 | 0/10 | 7/10 |

All candidate/control ranges overlap. No candidate passed the unchanged separated-range-plus-5% gate, and none met the ten-run goal under either peak definition. The final1495.81 GFLOP/s report confirms only the retained imported baseline, not any candidate gain. The candidate peak1701.65 is a measured sample, not a demonstrated consistent improvement.

`verify.py` independently rechecks source hashes, report signatures and identities, all score vectors, paired gates, unchanged power captures, and both peak comparisons. `verification.json` records those checks. The five preflight/replay tests and21 search tests passed after the run. A mock-only test failure caused by completed result files was corrected by supplying the fake advisor's observe method; no measured driver/source changed.

The next existing15-specialist board can use the already verified optional full512 transpose primitives. Each proposed wrapper must include all input conversion/allocation costs inside timed gemm. Prior panel, scratch, counter, and issue-order experiments remain historical failures, not new proposals.
