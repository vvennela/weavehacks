# First AC swarm experiment run

Target: exceed 1,800 GFLOP/s under the unchanged frozen single-thread FP32 hill. **Target not met; no candidate was promoted.** The held-out score for the unchanged original kernel was **1,579.41 GFLOP/s**.

The run used fresh AC baseline and paired-control measurements. No battery score was imported as AC comparison evidence. Every evaluation recorded AC status and checked unchanged power settings before and after. The fixed three-repeat, separated-ranges-plus-5% gate remained in force. Astra reviewed each measured candidate and returned reject/revise; none was adopted.

| Candidate | GFLOP/s repeats | Unchanged controls | Astra |
|---|---|---|---|
| existing-sme | 1270.20, 1445.79, 1536.85 |  | baseline |
| sme_fp32_tiles | 47.93, 49.60, 47.70 | 1510.19, 1226.66, 1145.32 | reject |
| compiler_codegen | 1583.69, 1389.36, 1383.09 | 1491.65, 1322.89, 893.42 | revise |
| address_generation | 1403.89, 1302.83, 1524.85 | 1528.82, 1007.11, 1444.17 | revise |
| register_reuse | 811.70, 1483.07, 1393.56 | 1597.04, 1017.60, 1505.25 | revise |
| cache_blocking | 1002.41, 1561.42, 1462.86 | 1074.46, 1446.12, 1343.29 | revise |

The sixth selected experiment was not timed. Astra abstained because its requested selector order already existed in the baseline; the alternate interpretation repeated `register_reuse`. Exact reasoning is in `agent/state.json`.

All six scored sources (baseline plus five candidates) passed the 48-case public correctness check. All 34 signed hill reports were independently reverified; see `verification.json`. This verifies source correctness on those cases and report integrity, not production readiness or a performance gain.

## Swarm behavior and provenance

The first batch reused exactly the preserved plan board and 14 valid rankings from `../cpu-swarm-plan-2026-09-24/`. Its fifteenth ranking had one duplicated and one missing experiment ID. That specialist supplied one corrected ranking against the unchanged board; the original failed artifact was retained. This run imported planning data only, then generated new AC performance evidence. `controls.json` records both the plan hash and implementation hashes.

First batch: `sme_fp32_tiles`, `compiler_codegen`, `address_generation`. After receiving measured outcomes, the swarm selected `register_reuse`, `cache_blocking`, and `za_four_tile_reuse`. Astra replaced `loop_order` and `sme_fp32_tiles` in the advisory roster with `cache_conflict_layout` and `za_four_tile_reuse` before the second planning batch. All 15 specialists ranked each board. Astra implemented that joint order and reviewed measured results.

There were 74 Codex calls including the original plan and one ranking repair, within the 108-call ceiling. Logged models are Luna for specialist advice/rankings and Astra-high for roster selection, implementation and measured review. No API-key or alternate-provider fallback was used.

## Limits and next evidence

Unchanged controls ranged from 893.42 to 1,597.04 GFLOP/s. AC did not eliminate timing variation, so overlapping ranges were not accepted as improvements. The first loop-interchange candidate added repeated partial-C spills/reloads and was far slower; the signed comparisons preserve that negative result.

`hardware-probe.c` and `hardware-probe.json` establish that this M4 Pro has 16 FP32 lanes per streaming vector (512 bits). This diagnostic is not a timing result and was obtained after the second batch was selected; it was not retroactively inserted into the saved agent prompts.

The search completed normally. Native C execution remains trusted local research, not a security sandbox. This run demonstrates joint proposal ranking, dynamic specialist replacement, implementation, correctness checks, official measurements and Astra adjudication; it does not establish the requested optimization competence at 1,800 GFLOP/s.
