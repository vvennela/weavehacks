# LIBXSMM experiment history for the next board

This inventory distinguishes **actual source hashes** from proposal text, abstentions, and timeouts. Every candidate below is unpromoted. The exact low-power-to-Automatic replay is a second measurement of the same four panel-swarm source hashes, not four new implementations.

## Implemented source changes

| Exact source SHA-256 | Actual change | Evidence and disposition |
|---|---|---|
| `7e9ab1076777a40cb0ad30527e381b221d4024cd99f370708971fb652b31810e` | Imported LIBXSMM full-512 SME kernel with row-major wrapper and general-size fallback. This is the original standalone reference, not a Sera optimization. | AC reference baseline, AC swarm baseline-only, battery reference, and next-continuation baseline; target not met. |
| `bf47e981d23289bfc6faba38d6ac5a3c8362db81f2b61e0215dd441135878685` | In both full-512 K loops, add one-step lookahead loads into z4–z7, copy them into z0–z3, and drain K=511. | Prepared-only phase passed correctness but was stopped before performance scoring. Later battery phase measured it and rejected it; no promotion. This is one change, not a separate experiment in each phase. |
| `8b01ee298ba0f0d49915cec8e0730ff168af64562bb9d6f717f7adbaaba5ff3a` | In both K loops, replace the 512-step decrement/branch with end pointers and pointer comparisons for the A/B streams. | Battery phase measured; mixed candidate/control repeats, revised and not promoted. |
| `ec83ff3b94f2983c17a1f7fd69aea377ed143b5993635a8770818124d4fcdd91` | In both K loops, load two K slices and issue eight ordered FMOPAs per loop body, with a one-step tail. | Battery phase measured; three paired gains varied widely, revised and not promoted. |
| `71c55f82b9955eefda8ca17f47e59fbe04c98919c7d30d110a6c540f38005bb8` | Move each K-loop counter decrement from after the FMOPA group to before it. | Next-continuation phase measured; revised and not promoted. |
| `13bc6a2ba0dc662d722b0ba8d09db1f2fc55ef77396b1056243d5fb154bf3cdc` | Move both K-loop pointer increments from before the FMOPA group to after it. | Next-continuation phase measured; revised and not promoted. |
| `a748475df6036ec229169ae103e91d567ca0854e45d885c5c8887c2e9580c36a` | Interleave the x0/x3 pointer increments within each four-FMOPA group: x0 after the first FMOPA, x3 after the third. | Next-continuation phase measured; revised and not promoted. |
| `e7b5eb8a9b290651137639917a3bdca342e9a1ed767d0ff8718449b03214c200` | Imported full-512 LIBXSMM body plus an additional generated 32-row panel primitive that the baseline wrapper does not call. | Panel-swarm baseline. This is a prepared/imported comparison source, not a Sera-discovered speedup and not hash `7e9ab1076777a40cb0ad30527e381b221d4024cd99f370708971fb652b31810e`. |
| `0b3b4431f6de2c249f799b21fa2e6731a4353a8cf303b8ec36d2e3b8b86b2051` | Replace one `sera_libxsmm_512` call in `gemm(n=512)` with sixteen calls to the supplied `sera_libxsmm_panel32`, one per 32-row output band. | Panel-swarm candidate, measured and unpromoted. Automatic replay reran the exact hash; it is not a new change. |
| `cadb05ebb2492c7eda03d5a5e2a71eca07ce0a5bcfd4e4a83053f708a3c598b7` | Route n=512 through a C SME implementation: retain the A transpose, accumulate fixed 32×32 tiles over K=512 in four ZA tiles, then store C. | Panel-swarm candidate, measured and unpromoted. Automatic replay reran the exact hash. |
| `0e428f343d60f7adb08f3627e633c382df52ec6417375aeeff58cc18c9916dca` | Keep the full-512 call but pad each packed-A K slice from 256 to 272 bytes; enlarge stack scratch and update consumer strides/rewinds. | Panel-swarm candidate, measured and unpromoted. Automatic replay reran the exact hash. |

The three panel-swarm candidates above retain the same order and hashes in `cpu-libxsmm-automatic-2026-09-25`; Automatic adds no source change. Their scores and paired controls are in each phase's `search/result.json`.

## Selected work that produced no candidate

- `cpu-libxsmm-swarm-2026-09-24`: the first selected K-loop schedule implementation timed out at 180 seconds. It produced no source. The same ranked experiment was later implemented as `bf47e981d23289bfc6faba38d6ac5a3c8362db81f2b61e0215dd441135878685` and performance-tested.
- `cpu-libxsmm-swarm-edits-2026-09-24`: a guarded-edit retry produced that same `bf47e981d23289bfc6faba38d6ac5a3c8362db81f2b61e0215dd441135878685` source and passed 48 correctness cases, but the AC preflight stopped the scorer because the host was on battery. It did not produce a second candidate or performance score.
- `cpu-libxsmm-next-2026-09-25`: the selected A-transpose implementation timed out at 180 seconds before producing a source. Its ranked queue was preserved for continuation.
- `cpu-libxsmm-next-continue-2026-09-25`: a second selected SME/tile implementation timed out and produced no source. The other tested K-loop sources are listed above.
- The battery phase's selected 64×32 cache-blocking proposal abstained because the full-512 reference already traverses 64 output rows as two 32-row tiles for each B panel. The selected predicated paired-LD1W post-index proposal abstained because that load form cannot update these two pointers.
- A selected scratch-lifetime proposal sought to reduce the full-512 128 KiB stack panel to 64 KiB while preserving the current consumer and traversal. The current code advances scratch by 256 bytes per K step and accesses through byte 130,943; a smaller allocation would overrun it. A valid reduced-buffer scheme needs coordinated packing, stride, rewind, and traversal changes outside that selected scope.
- The panel board's first selected panel32 idea was implemented once. Later panel-packing/cache-blocking attempts abstained as exact duplicates of the sixteen-call wrapper. A cache-layout proposal also abstained because its proposed 2,112-byte stride, 128 KiB-plus-8 KiB footprint, and 65,664-byte footprint were mutually inconsistent. The later measured `0e428f343d60f7adb08f3627e633c382df52ec6417375aeeff58cc18c9916dca` implementation used the corrected 272-byte stride; do not list that correction as untested.

Other specialist abstentions cite no distinct source-grounded proposal, existing full-kernel vector/tile behavior, or lack of compiler/disassembly evidence. These are recorded in the phase `agent/state.json` files; they are not failed measurements.

## Baseline and prompt corrections

1. Keep `7e9ab1076777a40cb0ad30527e381b221d4024cd99f370708971fb652b31810e` (the original exported LIBXSMM reference) separate from `e7b5eb8a9b290651137639917a3bdca342e9a1ed767d0ff8718449b03214c200` (that reference plus an unused generated panel helper). The latter was the panel-swarm replay baseline. `0b3b4431f6de2c249f799b21fa2e6731a4353a8cf303b8ec36d2e3b8b86b2051` is the first source here that changes the n=512 wrapper to call the helper sixteen times.
2. Do not describe the old 1,160–1,449 GFLOP/s result from the separate AutoLab `vvennela/kernel` hill as Sera package evidence. It came from another agent/task and another submission. The user-reported 1,780 GFLOP/s result belongs to that same AutoLab hill and is not Sera package evidence.
3. Claims that the 64×32 traversal, paired predicated LD1W, four ZA accumulator tiles, and panel32 primitive are wholly absent from the relevant baseline are misleading. Check the exact baseline hash and code block: some are already in the original kernel; panel32 was present but unused in `e7b5eb8a9b290651137639917a3bdca342e9a1ed767d0ff8718449b03214c200`.
4. Treat cross-phase scores as historical context only. Battery Low Power and Automatic blocks used the same four panel hashes, but no candidate was promoted in either. The sequential mode comparison does not identify a power-mode cause or a kernel speedup.

Use these exclusions as coverage context only. This review does not select a role, proposal, or experiment order for the next 15-Luna board.


## Primary records

- Original source: `evidence/cpu-libxsmm-reference-2026-09-24/editable/kernel.c` and `baseline-run/search/result.json`.
- K-loop history: `evidence/cpu-libxsmm-measure-prepared-2026-09-24/search/result.json`, `agent/state.json`, and `evidence/cpu-libxsmm-next-continue-2026-09-25/search/result.json`, `agent/state.json`.
- Prepared-only retry: `evidence/cpu-libxsmm-swarm-edits-2026-09-24/prepared/kernel.c` and `agent/state.json`.
- Panel baseline/candidates: `evidence/cpu-libxsmm-panel-swarm-2026-09-25/search/result.json` and `agent/state.json`; Automatic replay: `evidence/cpu-libxsmm-automatic-2026-09-25/search/result.json`.
