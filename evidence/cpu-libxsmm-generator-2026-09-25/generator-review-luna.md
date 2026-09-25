# Pinned LIBXSMM SME generator: legal layout and blocking controls

**Source facts.** This review uses LIBXSMM commit [`10490f10e79d4511f252c33279ef970a188cfab6`](https://github.com/libxsmm/libxsmm/tree/10490f10e79d4511f252c33279ef970a188cfab6). The offline exporter in [`export_kernel.c`](../cpu-libxsmm-reference-2026-09-24/export_kernel.c) dispatches an FP32 `(M,N,K)=(512,512,512)` kernel with `BETA_0` and no prefetch, then exports the generated code bytes. Runtime LIBXSMM is not needed for a generated kernel.

At M4, `generator_gemm.c` selects the SME GEMM path only for FP32 and a restricted flag set: XGEMM ABI, optional `TRANS_A`, `TRANS_B`, and batch-reduce-stride; it strips `BETA_0` before checking that set ([source](https://github.com/libxsmm/libxsmm/blob/10490f10e79d4511f252c33279ef970a188cfab6/src/generator_gemm.c#L1284-L1299)). `generator_gemm_common_aarch64.c` hard-codes macro blocking at N=64 and M=32 ([source](https://github.com/libxsmm/libxsmm/blob/10490f10e79d4511f252c33279ef970a188cfab6/src/generator_gemm_common_aarch64.c#L2306-L2321)). There is no public descriptor field or SME-specific environment variable for choosing those block sizes. `LIBXSMM_TARGET` and `libxsmm_set_target_arch` select the code-generation architecture, not blocking.

`TRANS_A` and `TRANS_B` are legal descriptor choices, and `generator_gemm_sme.c` contains A/B transpose-to-stack paths. For example, no `TRANS_B` invokes `transpose_b_to_stack` in the 17–32 N remainder path; setting `TRANS_B` skips that step there ([source](https://github.com/libxsmm/libxsmm/blob/10490f10e79d4511f252c33279ef970a188cfab6/src/generator_gemm_sme.c#L1308-L1334)). A flag flip alone changes the mathematical operation. It is legal for this fixed workload only if the supplied operand storage and leading dimensions are changed to match the flag while preserving beta=0 output.

## Concrete generator-supported decomposition

The SME generator has a direct N=32 path: with N=32, its `n_rest` falls in `17..32`, then it uses M blocks of 32, calls the same SME outer-product kernel, and handles beta-zero C initialization/store ([source](https://github.com/libxsmm/libxsmm/blob/10490f10e79d4511f252c33279ef970a188cfab6/src/generator_gemm_sme.c#L1308-L1428)). This enables an offline-generated `(512,32,512)` primitive without editing LIBXSMM or introducing a runtime library. A wrapper can cover the original row-major output in 16 disjoint row bands, with call index `r=0,32,...,480`:

- `A_arg = B`, interpreted column-major as `Bᵀ` (`m=512,k=512`);
- `B_arg = A + r*512`, interpreted column-major as the 512x32 panel from 32 row-major rows of A;
- `C_arg = C + r*512`, the matching 32 output rows; keep `lda=ldb=ldc=512`.

This is the identity `Cᵀ=BᵀAᵀ` with the same FP32 values and beta=0 semantics. The generator will still pack its non-transposed B operand to stack once per primitive call. Compared with one 512x512 call, this trades sixteen function/SME entries for a narrower generated kernel and per-call panel packing. Whether that helps is an untested hypothesis; include every pack and call in timing and verify panel boundaries/correctness.

## What can change, and what cannot

1. **Descriptor/layout choices:** export `TRANS_A` or `TRANS_B` variants only with matching packed input and leading dimensions. The M4 generator accepts these variants, but direct use of the current row-major pointers with toggled flags is incorrect. A prepacked operand plus `TRANS_B` may bypass the generator's internal B transpose in relevant paths; this is a data-layout experiment, not a free flag optimization.
2. **Public blocking route:** export smaller N shapes such as N=32 and loop over disjoint output panels in the wrapper. The source has a dedicated 17–32 branch, but the wrapper adds calls and cannot claim a gain in advance.
3. **Internal blocking:** to change the fixed 32/64 macro-block constants while keeping a single full-shape dispatch requires an offline LIBXSMM source modification and regeneration. It must update the paired M/N remainder logic and pack/store traversal, not only `setup_blocking_sme`. Do not expect `LIBXSMM_TARGET` or a leading-dimension choice to select new block sizes.

The adapter remains specialized to the fixed n=512 call and must preserve the existing general-size fallback. This note reports generator capabilities and algebraic legality only; it contains no benchmark result or performance promise.
