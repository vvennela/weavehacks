# SME techniques applied to the best Sera kernel

Status: completed; no candidate promoted. The run stopped at the candidate budget.

This phase replayed the saved best panel32 source `eb091b1e…` against a fresh
measurement of the imported reference `04fc3ff…`, then tested five additional changes
on the active panel32 path. It did not alter the inactive full512 assembly or test
Strassen or other algorithms. The Astra-high coordinator implemented five candidates
selected by the 15 Luna specialists. The phase recorded 73 model calls and five
implementation attempts across two ballot rounds. Both rounds had 15 received ballots;
the selected order was verified against the ranked ballots.

## Measured results

All results below are FP32 GFLOP/s, single-thread, under Battery Low Power
(saved battery `powermode 1`).
Each candidate has ten validations and ten alternating paired controls against the
current incumbent. No candidate passed the required gate
`min(candidate) > 1.05 × max(control)`, so the imported reference remained incumbent.

| Trial | Median | Range | Paired wins | Gate | Promoted |
|---|---:|---:|---:|---|---|
| Fresh imported reference baseline | 865.56 | 635.73–1079.86 | — | — | No |
| Replay: one SME region over panel32 | 925.95 | 747.82–1047.04 | 4/10 | Failed | No |
| Pointer adds after ZA1 | 1030.41 | 387.66–1075.18 | 9/10 | Failed | No |
| Load next operands before branch | 885.99 | 595.42–1035.77 | 5/10 | Failed | No |
| SUBS/B.NE K-loop control | 929.00 | 750.78–1033.27 | 5/10 | Failed | No |
| FMOPA order 0,2,1,3 | 967.20 | 551.01–1063.64 | 3/10 | Failed | No |
| Distance-1 guarded B prefetch | 917.98 | 690.21–956.28 | 4/10 | Failed | No |

The 9/10 pointer-add candidate still failed because its worst run did not clear the
maximum paired-control score plus 5%. Pair wins and medians alone do not meet the fixed
gate. Every source passed all 48 frozen correctness cases at tolerance 0.002; that is
48 cases per source, or 336 source-case checks across the seven measured sources.

The selected source remained the imported reference. Its final held-out score was
916.553 GFLOP/s, below the legacy 1800 GFLOP/s target. `target_met` is false. The
verification script checked all 131 signed reports and all 393 raw timing samples,
source and report identity, unchanged power provenance, correctness records, ranking,
and the final selection. Verification passed; no performance run was started by the
verifier.

## Scope and interpretation

The local compute-only calibration is separate from these GEMM measurements. It used
register-only operands and ran under Battery Low Power; its different workload means
its result cannot replace this phase's GEMM baseline. The published ~2008 GFLOP/s
single-core result is from a base M4 compute microbenchmark, not an M4 Pro GEMM limit.
No result here establishes a 2000 GFLOP/s M4 Pro peak or causal benefit from an
individual change.

Evidence: [`verification.json`](verification.json), the frozen signed reports under
`search/`, and [the hardware-specific reference note](../../docs/sera-sme-throughput-references-2026-09-25.md).
