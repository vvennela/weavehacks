# Proposed extension: one-level FP32 Strassen

Status: approved by the user on 2026-09-25: “Allow one-level Strassen alongside current methods.” The running classical block retains its saved plan. No benchmark rule, numerical tolerance, power setting, or budget was changed.

Recommendation: allow the existing 15-specialist board to consider one-level Strassen alongside classical GEMM. The board would still rank experiments and Astra would implement its choices. This adds an algorithm family; it does not select a candidate or promise a speedup.

Split each 512-square input into four 256-square blocks. Compute seven block products instead of the conventional eight, using FP32 throughout:

```
P1 = (A11 + A22) (B11 + B22)
P2 = (A21 + A22) B11
P3 = A11 (B12 - B22)
P4 = A22 (B21 - B11)
P5 = (A11 + A12) B22
P6 = (A21 - A11) (B11 + B12)
P7 = (A12 - A22) (B21 + B22)

C11 = P1 + P4 - P5 + P7
C12 = P3 + P5
C21 = P2 + P4
C22 = P1 - P2 + P3 + P6
```

The subproducts require 117,440,512 scalar multiply-accumulate terms instead of 134,217,728: 12.5% fewer. Standard recombination adds 18 block additions/subtractions (1,179,648 scalar operations). Memory traffic, allocation, calls and rounding effects can erase the savings. This is an arithmetic count, not a measured runtime prediction. The algorithm and its weaker numerical stability are described in [Higham's primary analysis](https://nhigham.com/wp-content/uploads/2023/08/high90s.pdf), sections 2 and 4.

Approved implementation boundary:

- Only the n=512 path may use one decomposition level. Other sizes and allocation failure retain the existing correct path.
- All block extraction, sums, subproducts, scratch allocation, recombination and cleanup stay inside timed gemm. No persistent buffers, result caching, external library, mixed precision, or benchmark changes.
- The current generic SME fallback can compute 256-square subproducts. The prepared optimized LIBXSMM helpers cannot: their exported shapes are 512 or 512-by-32. If the board needs a 256-square primitive, prepare it from the same pinned LIBXSMM generator, with the same license, ABI, byte and correctness checks as existing imports. Do not pretend the current helpers support that shape.
- Preserve tolerance 0.002. Check existing deterministic cases plus cancellation and scale-sensitive public cases before official timing. A mathematically valid identity can still fail FP32 accuracy.
- Preserve the same source/power separation, ten paired report repetitions, frozen official hill and existing promotion gate. Use the existing per-block and per-call caps. No deeper recursion or Winograd schedule is included in this proposed first extension.

Alternative: keep research limited to the current classical GEMM packing, transpose, cache and instruction-scheduling families. They remain available; the previous failures do not prove their search space is exhausted.

Approval was requested and received because AGENTS.md says: “The user adjudicates decisions” and reserves “product or research direction” changes for the user. Luna supplied the breadth analysis; the primary agent checked the arithmetic and prepared this bounded proposal. No performance evidence for Strassen on this workload exists yet.
