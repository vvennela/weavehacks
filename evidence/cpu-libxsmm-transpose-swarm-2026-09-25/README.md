# Swarm with optional full512 transpose primitives

Status: completed; no candidate promoted; ten-run goal not met. The current Mac is AC Automatic. No power-setting change is required or authorized by this driver.

The prepared source adds three exact, optional unused LIBXSMM primitives to the prior imported baseline. The original gemm body and NN instruction bytes remain unchanged. The new source is 108226 bytes and its compiled text is 20628 bytes; all four full512 generated bodies were found exactly once with their exported bytes. Binary layout is different, so the search measures a fresh baseline. The entire baseline passed48 deterministic correctness cases. Preparation selects no experiment and claims no speedup.

Astra-high chooses15 Luna specialists. The specialists receive complete source, exact transpose mappings, generator facts, and the prior unsuccessful trial inventory including the ten-run AC replay. They propose and jointly rank a batch; Astra implements the ranked queue and reviews results. Optional TA/TB/TT wrappers require all input conversion/allocation/cleanup inside timed gemm. The board can choose other distinct legal changes within the existing scope. All model calls use Codex with ChatGPT login only.

Ten validations per source and ten alternating fresh paired controls per candidate; existing 5% separated-range promotion and final held-out check retained. Current goal: beat imported baseline peak consistently over ten runs. Recent saved AC peak 1685.6230608449698; earlier Battery Automatic 1668.5964359101147. Compare both historical and fresh same-mode peaks without selecting the unresolved comparator policy. The internal 1800 setting is a legacy search stop check, not the goal definition. Never claim a retained baseline as a Sera improvement.

Caps unchanged:6implementation attempts,108model calls,180 seconds per call,1800seconds per block. Frozen hill, FP32 ABI, compiler flags, tolerance, thread count, licenses, and power profile remain fixed. Before/after power captures surround every report.

Preparation validation: 2 source-integrity tests, 1 driver integration test, and 46 existing search/advisory/board tests passed (49 total). Preparation tests first failed because the implementation did not exist. No timing was performed by preparation.

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-transpose-swarm-2026-09-25/run.py
```

## Result and audit

Three advisory rounds used83 Codex calls and four implementation attempts. The first two boards each contained15 Luna proposals and15 complete ranking ballots; both selected orders were independently recomputed. The third board had15 abstentions and ended the search. This is a proposer stop, not evidence that all legal optimizations are exhausted.

- The first-ranked TB proposal specified an identity copy instead of a transpose. Astra abstained before creating a source.
- The second-ranked TB proposal had the correct mapping. Astra implemented a fresh1 MiB allocation, `sme_transpose(512,A,at)`, the importedTBcall, and free, with original NN allocation-failure fallback. Luna and root source reviews confirmed the mapping, timed work, sequential SME ownership, and unchanged general-size path.
- A160 KiB padded-scratch rewrite hit the existing180 second agent limit; it produced no candidate.
- The second board selected a store-order change already present in NN. Astra abstained and corrected the proposal's ZA tile dimensions.

The valid TB candidate passed48 deterministic cases but its ten scores were 1045.00–1556.15 GFLOP/s (median 1491.34), winning 3/10 paired comparisons. It beat neither the saved 1685.62peak nor fresh initial-baseline 1684.30peak in any run. Unchanged paired controls reached 1687.39. The full baseline remained selected; its final 1660.00score confirms only the baseline. All 31 official report signatures, source hashes, comparison identities, and before/after power captures verified. The 49 preparation/search/advisory tests passed after the block.

TA/TT full-call wrappers remain unmeasured. Lower rankings or later abstention do not constitute negative performance evidence for those paths. Some advisors conflated unmeasured paths with tested ones, and others requested machine output. Post-run `compiler-evidence.json`, both full compiled disassemblies and `timed-path-disassembly.txt` supply actual clang21 output under the frozen flags for the baseline and measuredTBsource. These are evidence for a future board, not a new candidate or timing result. Disassembler stub labels can be ambiguous; do not infer an external symbol solely from its nearest displayed label.
