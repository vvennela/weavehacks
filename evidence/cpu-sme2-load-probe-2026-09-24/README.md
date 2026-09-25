# SME2 compiler and correctness probes

The M4 Pro reports SME2 support and 16 FP32 lanes per streaming vector. `probe.c` loads two pairs of FP32 vectors, updates four ZA tiles, and stores one row from each tile. Apple clang 21 emits two multi-vector load instructions for these four operand vectors. Eight fixed-seed input cases produced the exact expected values, with output guards intact.

`indirect-store.c` performs the same operation but reads each output row into an SVE register before storing it. Its eight fixed-seed cases also match exactly with guards intact. The generated assembly confirms ZA-to-vector transfers followed by vector stores.

Both sources compile with the frozen optimization flags and a function-level SME2 target attribute. These are instruction and correctness probes, not GEMM benchmarks. No speedup has been measured. Full kernel candidates must pass the existing public and signed hill checks, including general shapes and n=512.

Artifacts include source, generated assembly, and correctness summaries. Seed: 20260924. The probe validates full-vector accesses only; a candidate must retain safe tail handling.
