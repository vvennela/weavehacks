# LIBXSMM timing evidence review

This review uses public signed `kernel-opt` reports, their saved before/after host observations, and the phase verification records. It does not use private evaluator inputs or rerun measurements.

## Finding

The evidence does not identify a compute bottleneck. It shows substantial timing variation for the same source under unchanged benchmark settings, while recording no per-kernel counters or stage timings. This is consistent with run-to-run noise or changing runtime state, but the records do not establish which one caused it. They cannot distinguish a compute limit from a memory, packing, scheduling, or thermal limit.

Each official report contains three raw durations and scores the fastest (`seconds_best_of_3`). Those timings are only about 0.16–0.50 ms. The report prints decimal values to nanosecond places, but gives no calibrated timer resolution or accuracy. The observed spread among the three measurements is often tens to hundreds of microseconds, far larger than the last printed decimal places. The fastest-of-three score therefore hides much of the short-run spread and is not a stable estimate of typical call time.

## Same-source evidence

All three phases used the frozen `kernel-opt` tree `76db49356748c18dccac376bed489268b047b60a`, n=512, tolerance 0.002, Apple clang 21 with `-O3 -march=native -ffast-math -shared -fPIC -lm`, and an arm64 Darwin report environment. The reference source SHA-256 is `7e9ab1076777a40cb0ad30527e381b221d4024cd99f370708971fb652b31810e`. The two AC baseline blocks and the battery baseline map to the same Hill submission hash, so their baseline results are for the same source.

| Phase | Power captured before and after | Same-source baseline GFLOP/s, in report order | Fastest-of-three durations |
|---|---|---|---|
| AC reference | AC Power | 1541.3, 1333.3, 1328.1 | 174.2–202.1 µs |
| Separate AC swarm baseline | AC Power | 1643.5, 1276.7, 1176.1 | 163.3–228.3 µs |
| Battery swarm baseline | Battery Power | 1020.5, 1077.3, 1056.0 | 249.2–263.0 µs |

These phase vectors are kept separate. In particular, the AC blocks are separate runs, and the battery phase occurred later. Their absolute differences do not isolate a causal power-source effect. The power metadata does show normal OS mode differences: `powermode 0` on AC and `powermode 1` on battery. Each host capture reports no recorded thermal or performance warning. No capture reports clock frequency, core affinity, P/E core identity, active processes, or CPU utilization.

The within-report raw timing arrays also vary. Across the AC baselines, individual timings range from 163.3 to 335.0 µs. Across the battery baseline and its paired unchanged controls, individual timings range from 249.2 to 414.8 µs. In the battery block, the unchanged source's initial validation scores were 1020.5–1077.3 GFLOP/s, while its nine paired-control scores ranged from 795.1 to 1040.1 GFLOP/s. The candidate score changes must be judged against those contemporaneous controls, not against AC scores or an earlier battery baseline.

## Candidate evidence limits

Battery candidate sources were measured only in the battery block; none has an AC candidate measurement. The two-step-unroll source (`ec83ff3b94f2983c17a1f7fd69aea377ed143b5993635a8770818124d4fcdd91`) scored 1087.5, 1047.6, and 1091.2 GFLOP/s against paired controls 947.6, 1040.1, and 873.3. The corresponding pair changes are +14.8%, +0.7%, and +24.9%. That single near-equal pair and the large control spread do not establish a repeatable gain or explain its cause. The search marked it ineligible and unpromoted; the final result was `final-performance-unconfirmed`, target false, with no winner.

The baseline phase verification records report valid signatures and matching sources; the battery verification records all 22 signed reports, matching sources, passing public correctness, and unchanged power/settings before and after each report. These checks establish report integrity and power-state consistency. They do not establish stable clocks, quiet system load, or a specific bottleneck.

## Next admissible diagnostic

Within the frozen scorer, collect several additional independent **unchanged-source baseline** reports in one steady, recorded power state, each using the existing three-timing Hill report. Capture the existing host observations around each report and keep the reports as separate samples. This would measure report-to-report dispersion for one exact source under that state before another candidate is judged. Do not change the Hill, power settings, compiler flags, thread count, or promotion threshold; do not pool AC and battery samples. If the baseline distribution remains broad, treat small candidate deltas as unresolved and repeat the fixed paired-control protocol. This diagnostic can quantify variability; it still cannot name a hardware bottleneck without new approved instrumentation.

## Evidence paths

- AC reference: `evidence/cpu-libxsmm-reference-2026-09-24/baseline-run/search/` and `baseline-verification.json`.
- Separate AC swarm baseline: `evidence/cpu-libxsmm-swarm-2026-09-24/search/` and `verification.json`.
- Battery swarm: `evidence/cpu-libxsmm-measure-prepared-2026-09-24/search/` and `verification.json`.

## Current energy-mode observation (2026-09-25)

A later, current Foundation check using `NSProcessInfo.processInfo.isLowPowerModeEnabled` returned `true`. The current `pmset -g custom` snapshot reports `powermode 1` for Battery Power and `powermode 0` for AC Power, matching the saved settings in the current panel-swarm controls. This is a present-day observation; the historical AC and battery reports captured `pmset` state but did not record the Foundation flag. Do not project this result backward onto those runs or attribute their scores to Low Power Mode.

Apple documents that energy modes can be configured independently for battery and adapter power, and that Low Power Mode reduces energy use. Its guide describes the user-facing modes, but does not define the numeric `pmset powermode` values as a mapping to those modes. The measurements therefore distinguish two facts: the host was on AC or battery, and the OS had a configured/runtime energy mode. Neither fact alone identifies the active clock or a performance ceiling. [Apple Support: About Power Modes on your Mac](https://support.apple.com/en-ie/101613)
