# Code-generation review

This is a static comparison of the recorded compiler output for trial 001
(`ec4b0603…`) and trial 003 (`c905f585…`), built with Apple clang 21 and the
same `-O3 -march=native -ffast-math -shared -fPIC -lm` flags. It is not a
performance measurement.

Trial 001's ordinary C pack/combine loops are already vectorized. Its saved
`gemm` assembly contains `ldp`/`stp` Q-register transfers and `fadd.4s` /
`fsub.4s` operations in the n=512 path. Trial 003 changes only that helper to
explicit 4-float NEON loads, stores, adds, and subtracts (`vld1q_f32`,
`vst1q_f32`, `vaddq_f32`, `vsubq_f32` in the source). The resulting machine
code still uses Q-register vector operations. Thus the difference is not
“scalar C versus SIMD”; it is compiler-generated versus explicitly written
SIMD for these loops.

Recorded compiled text falls from 37,820 to 29,012 bytes (8,808 bytes, about
23.3%). The extracted `gemm` assembly falls from 3,464 to 1,302 lines. This is
a real static-code-size change, but line count and text size do not establish
runtime speed or identify the cause of the candidate's measured result.

Both outputs have the same static direct-call counts: 5 `malloc`, 6 `free`, 6
`memcpy`, 1 `bzero`, and 7 `sera_libxsmm_256` call sites in the extracted
function. Three `memcpy` call sites precede the n!=512 fallback branch in
each file, so copy operations remain represented as libc calls in the
specialized path. These are *static call-site* counts, not dynamic invocation
counts: some sites sit in loops, and the function also contains allocation
failure and general-size paths. Do not infer per-call copy cost from these
counts. The source places the work inside `gemm`, so it remains included in
official timing.

The saved codegen record says the complete compiled text differs and records
source, assembly, and disassembly hashes. No new score, dynamic profile,
instruction count, or component-cost estimate follows from this inspection.
Use the existing paired measurements for performance conclusions; any
follow-up should measure the same frozen source and contract.
