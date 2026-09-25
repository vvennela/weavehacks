# LIBXSMM AC and battery comparison inventory

Snapshot: 2026-09-25T06:45:34.591969+00:00 UTC. This inventory covers the completed battery block and three distinct evidence phases. Each score vector remains in the report order recorded by the Hill; repeats are not combined into a cross-phase statistic.

The frozen Hill identity is tree `76db49356748c18dccac376bed489268b047b60a`, n=512, tolerance 0.002, on arm64 with Apple clang version 21.0.0 (clang-2100.1.1.101). AC and battery measurements are separate power phases. Do not pool their scores or interpret their absolute difference as a candidate speedup.

## Evidence phases

- **AC reference:** [`evidence/cpu-libxsmm-reference-2026-09-24/baseline-run/search/result.json`](../cpu-libxsmm-reference-2026-09-24/baseline-run/search/result.json) measured unchanged source `7e9ab1076777a40cb0ad30527e381b221d4024cd99f370708971fb652b31810e` at [1541.2532704114913, 1333.2842863403828, 1328.0665951598835] GFLOP/s across three validations; its final holdout was 1533.190 GFLOP/s. Target 1800 was not met. The four signed reports were independently verified in [`baseline-verification.json`](../cpu-libxsmm-reference-2026-09-24/baseline-verification.json).
- **Separate AC swarm baseline:** [`evidence/cpu-libxsmm-swarm-2026-09-24/search/result.json`](../cpu-libxsmm-swarm-2026-09-24/search/result.json) repeated the same source hash at [1643.4756775419414, 1276.74414125079, 1176.058920286144] GFLOP/s. The Astra implementation timed out before producing a candidate source or candidate score. This is a separate baseline phase, not a replicate to pool with the AC reference phase.
- **Battery swarm:** [`evidence/cpu-libxsmm-measure-prepared-2026-09-24/search/result.json`](../cpu-libxsmm-measure-prepared-2026-09-24/search/result.json) completed with status `final-performance-unconfirmed`. The 22 report signatures, source hashes, public correctness records, and unchanged battery/settings captures are recorded as verified in [`verification.json`](../cpu-libxsmm-measure-prepared-2026-09-24/verification.json). The final result is 801.300 GFLOP/s, status `final-performance-unconfirmed`, target false, and no winner selected.

## Battery candidate and paired-control records

| Source hash | Candidate validation scores (GFLOP/s) | Paired unchanged controls (GFLOP/s) | Review | Promotion |
|---|---:|---:|---|---|
| `bf47e981d23289bfc6faba38d6ac5a3c8362db81f2b61e0215dd441135878685` | [730.6016211251696, 778.1662624286882, 756.8683079169249] | [795.0698209044307, 1015.3586799322641, 847.4679057889266] | reject | no |
| `8b01ee298ba0f0d49915cec8e0730ff168af64562bb9d6f717f7adbaaba5ff3a` | [765.6808535378168, 1018.8927819450573, 954.298077756665] | [824.6864888803946, 868.4898760325931, 801.8983294144035] | revise | no |
| `ec83ff3b94f2983c17a1f7fd69aea377ed143b5993635a8770818124d4fcdd91` | [1087.5141231535335, 1047.5529938845925, 1091.2009939850639] | [947.5574885566502, 1040.1128771679143, 873.31584564557] | revise | no |

These are within-battery paired records only. All three candidates remained ineligible and unpromoted. The last two bounded attempts abstained and have no source hash or score.

## Source-by-power coverage

| Exact source SHA-256 | AC reference | AC swarm baseline-only phase | Battery phase |
|---|---|---|---|
| `7e9ab1076777a40cb0ad30527e381b221d4024cd99f370708971fb652b31810e` | measured, 3 validations + final | measured, separate 3 validations | measured, 3 validations + 9 controls + final |
| `bf47e981d23289bfc6faba38d6ac5a3c8362db81f2b61e0215dd441135878685` | unmeasured | unmeasured | measured, 3 validations + paired controls |
| `8b01ee298ba0f0d49915cec8e0730ff168af64562bb9d6f717f7adbaaba5ff3a` | unmeasured | unmeasured | measured, 3 validations + paired controls |
| `ec83ff3b94f2983c17a1f7fd69aea377ed143b5993635a8770818124d4fcdd91` | unmeasured | unmeasured | measured, 3 validations + paired controls |

There are no AC candidate cells in this evidence set, and no battery final holdout with a confirmed winner. The machine reached the 1800 GFLOP/s target in none of the recorded final outcomes. See [`report.json`](report.json) for exact report paths, source hashes, and the phase-level data.
