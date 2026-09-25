# Sera CPU specialist experiment — 2026-09-24

**The 1,780 GFLOP/s target was not met. No candidate passed the promotion rule.**

This is a real `import sera` run at implementation commit `d7b8e5f`, not the earlier Codex subagent named Sera. Six Codex ChatGPT-authenticated GPT-6 Astra calls ran in two batches of three; this run started before the user requested that all 15 specialists use Luna. It does not validate that later 15-Luna design.

The selected roles were SME tiles, register tiling, packing layout, then SME tiles again, memory traffic, and instruction scheduling. The second SME call received its earlier measured outcome through scoped memory. All six sources passed public seeded odd-size/guard checks and the unchanged hill. None cleared the conservative separated-range 5% promotion rule.

## Measurements

All numbers below are signed hill report scores in GFLOP/s. The hill retains its fixed best-of-three timing rule; each table range spans three separate reports, not a best-of-repeats selection.

| Source | Validation range | Median | Paired unchanged control range | Promoted |
| --- | ---: | ---: | ---: | --- |
| existing-sme | 620.24–1059.26 | 1037.26 | Initial baseline | False |
| sme-panel-pack-fused-unroll4 | 851.61–1101.84 | 1014.24 | 842.70–1060.14 | False |
| sme-2x2-two-step-register-pipeline | 739.75–1029.31 | 978.35 | 879.04–1035.77 | False |
| sme-row-panel-pack | 901.42–1014.24 | 920.22 | 822.68–1060.31 | False |
| sme-fused-transpose-1x4-tiles | 591.54–977.76 | 858.77 | 782.42–1082.04 | False |
| sme-full-transpose-padded-stride | 992.52–1045.68 | 1016.64 | 818.50–1050.63 | False |
| sme-full-tile-staggered-unroll4 | 732.10–1028.16 | 900.29 | 991.45–1037.60 | False |

Final held-out check of the unchanged baseline: **623.97 GFLOP/s**, correctness passed. This is not evidence of an optimization gain.

## Comparability and limits

- Frozen hill tree: `76db49356748c18dccac376bed489268b047b60a`; M4 Pro / MacBook-Pro-8.local; n=512; float32; tolerance 0.002; one thread; no external libraries.
- Compiler: Apple clang 21.0.0 with unchanged `-O3 -march=native -ffast-math -shared -fPIC -lm`. Packing, allocation, and call overhead remain timed.
- Private seeds and evaluator source were not read or modified by the agents. Forty signed reports were saved: 3 baseline + 6×6 interleaved candidate/control + 1 final. All signatures were independently reverified.
- Seven sources (baseline plus six candidates) passed the public deterministic validator: 15 sizes × 3 input kinds each. This does not prove every possible shape or native-code safety.
- The initial baseline ranged from 620.24 to 1,059.26 GFLOP/s, a 42.3% range relative to its median. Observations during the run show battery power and substantial unrelated CPU activity. The environment was too variable for a narrow performance claim.
- Do not compare these measurements directly to the previous task’s 1,449 result or a published kernel result with different timing/power conditions.
- The existing acceptance policy was used. Proposed changes such as rejecting an unstable baseline before agent calls, stricter final gain confirmation, and expanded swarm policy await user adjudication. Signed reports are left unchanged.

## Files

- [Search result](search/result.json), [controls and implementation hashes](controls.json), [host observations](host-observation.json).
- [Specialist dispatch and memory](agent/state.json), [journal](journal.md).
- `search/trial-*/source/kernel.c` contains every source; nearby JSON contains signed scores and public correctness checks.

## Earlier integration attempts

`../cpu-kernel-codex-2026-09-24-v2/` contains the earlier six-candidate single-proposer run: no promotion, unchanged final 955.85 GFLOP/s. Code was being developed during that integration attempt, so it is not a frozen package release certificate.
`../cpu-kernel-codex-2026-09-24/` records an interrupted setup attempt: Hills waited on unrelated iCloud-backed Git files before scoring. The adapter was then changed to submit a source-only temporary directory. No failed run was relabeled as success.
