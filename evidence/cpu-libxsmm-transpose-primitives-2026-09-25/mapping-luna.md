# Full-size LIBXSMM transpose-descriptor mappings

This records legal storage mappings for offline-generated full-size beta-zero primitives. It does not select or measure a candidate.

## Fixed dimensions and parameter slots

The pinned exporter uses the LIBXSMM descriptor `(M,N,K)=(512,512,512)`, `BETA_0`, no prefetch, and the parameter block offsets `A=32`, `B=80`, `C=128` bytes (`params[4]`, `[10]`, and `[16]` on this 64-bit ABI). The offline exporter is [`export_kernel.c`](../cpu-libxsmm-reference-2026-09-24/export_kernel.c); its saved export metadata records those offsets. Transpose variants must add the matching `LIBXSMM_GEMM_FLAG_TRANS_A` and/or `LIBXSMM_GEMM_FLAG_TRANS_B` to `BETA_0` at dispatch.

The row-major contract is `C[i,j] = Σk A[i,k] * B[k,j]`. LIBXSMM computes column-major `C_col = op(A_arg) * op(B_arg)`. View output memory as `C_col = Cᵀ`, so the required operations are `op(A_arg)=Bᵀ` and `op(B_arg)=Aᵀ`, with call dimensions `(M,N,K)=(n,m,k)`. Here all dimensions are 512, but the leading dimensions below are stated from the logical physical storage shapes.

## Variants

All copied buffers contain FP32 values and are fully initialized before dispatch. Row-major input addresses below are `A_rm[i*k+j]` and `B_rm[i*n+j]`. The C pointer remains the original row-major `C`; interpreted column-major it is `Cᵀ`, with `ldc=n=512`. Because all dimensions are 512, every listed leading dimension is numerically 512.

| Dispatch transpose flags | `params[4]`: physical A_arg storage and LD | `params[10]`: physical B_arg storage and LD | Required op(A_arg), op(B_arg) |
|---|---|---|---|
| none (current) | `B_rm`, stored as column-major `Bᵀ` of shape `n×k`; `lda=n` | `A_rm`, stored as column-major `Aᵀ` of shape `k×m`; `ldb=k` | `Bᵀ`, `Aᵀ` |
| `TRANS_A` | `B_col_kn`, column-major logical `B` of shape `k×n`, with `B_col_kn[i + j*k] = B_rm[i*n+j]`; `lda=k` | `A_rm`, column-major logical `Aᵀ` of shape `k×m`; `ldb=k` | `Bᵀ`, `Aᵀ` |
| `TRANS_B` | `B_rm`, column-major logical `Bᵀ` of shape `n×k`; `lda=n` | `A_col_mk`, column-major logical `A` of shape `m×k`, with `A_col_mk[i + j*m] = A_rm[i*k+j]`; `ldb=m` | `Bᵀ`, `Aᵀ` |
| `TRANS_A & TRANS_B` | `B_col_kn` as above; `lda=k` | `A_col_mk` as above; `ldb=m` | `Bᵀ`, `Aᵀ` |

The output slot is `params[16]=C` in every row, with `ldc=n`. The beta-zero flag must remain set so each generated call overwrites its output. For this exact square case the transposed input buffers each occupy `512*512*sizeof(float)=1 MiB`.

## Timing and correctness requirements

The current no-transpose primitive passes the original input pointers directly. Each enabled transpose flag requires its corresponding full buffer: `TRANS_A` requires a `B_col_kn` copy; `TRANS_B` requires an `A_col_mk` copy; both require both buffers. These are physical transposes, not free pointer aliases. Build and fill every required buffer inside `gemm` so allocation and all copy work remain inside the measured call. Preserve original A and B inputs, keep beta zero, write all of C, and free temporary buffers before return. If allocation failure is handled, use the unchanged no-transpose implementation as fallback rather than dispatching with a mismatched buffer.

The current exporter passes all leading dimensions as 512 because the workload is square. For a future non-square use, recompute physical dimensions and LDs from the table; do not copy the numeric 512 mechanically. Validate each exported descriptor's transpose flags and ABI slots against a small deterministic reference before using it in the fixed hill.

## Source basis

- Pinned LIBXSMM revision: `10490f10e79d4511f252c33279ef970a188cfab6`.
- Existing exact no-transpose exporter: `evidence/cpu-libxsmm-reference-2026-09-24/export_kernel.c` and `export.json`.
- Generator eligibility and transpose-to-stack paths: [`generator-review-luna.md`](../cpu-libxsmm-generator-2026-09-25/generator-review-luna.md), including links to pinned `generator_gemm.c` and `generator_gemm_sme.c`.
- Algebraic identity: `Cᵀ=BᵀAᵀ`.
