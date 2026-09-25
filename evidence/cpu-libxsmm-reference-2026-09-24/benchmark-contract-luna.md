# LIBXSMM SME published benchmark: contract and comparability

## Finding

The published `1755.189780` and `1833.867522` GFLOP/s results are not the same workload as the local `kernel-opt` hill. The second published result is the faster one, but it computes **column-major** `C += A * B^T` with `beta=1`; the local hill calls a row-major full product `C = A * B` at `n=512`. The SME repository tells readers to clone LIBXSMM's default branch without recording its revision. The published README therefore does not pin the implementation that produced either score. Use the numbers as a useful reference point, not as an apples-to-apples baseline or evidence that a local kernel should reach the same score.

## What the published run says

The SME repository identifies the original machine as a 2024 11-inch iPad Pro Wi-Fi 1 TB with Apple's M4 SoC. Its README gives two `gemm_kernel` commands for 512-by-512-by-512 FP32 GEMM and reports:

| README case | Operation printed by README | Reported time | Reported rate |
|---|---|---:|---:|
| First command | `C = A x B` | 1.529381 s | 1755.189780 GFLOP/s |
| Second command | `C += A x B^T` | 1.463767 s | 1833.867522 GFLOP/s |

Both commands pass `alpha=1`, `beta=1`, no prefetch (`nopf`), no batch reduction (`nobr`), batch count 1, and 10000 repetitions. They differ at the `trans_b` argument: 0 for the first and 1 for the second. The current sample initializes C to zero for beta 1, so the first run starts as `C=0` and produces the first product on its first call; the measured loop still makes repeated beta-1 accumulation calls ([pinned source, C initialization](https://github.com/libxsmm/libxsmm/blob/10490f10e79d4511f252c33279ef970a188cfab6/samples/xgemm/gemm_kernel.c#L4320-L4334)). The second is unambiguously `C += A * B^T`.

The exact current source used for this inspection was LIBXSMM commit [`10490f10e79d4511f252c33279ef970a188cfab6`](https://github.com/libxsmm/libxsmm/tree/10490f10e79d4511f252c33279ef970a188cfab6), inspected read-only on 2026-09-24. In `samples/xgemm/gemm_kernel.c`, CLI parsing maps `argv[12]` to beta, `argv[16]` to `trans_b`, `argv[21]` to batch-reduction mode, `argv[22]` to batch count, and `argv[24]` to repetitions ([pinned source, argument parsing](https://github.com/libxsmm/libxsmm/blob/10490f10e79d4511f252c33279ef970a188cfab6/samples/xgemm/gemm_kernel.c#L3580-L3644)). The output format distinguishes `A x B` from `A x B^T` and prints `BR=1` ([pinned source, operation label](https://github.com/libxsmm/libxsmm/blob/10490f10e79d4511f252c33279ef970a188cfab6/samples/xgemm/gemm_kernel.c#L4038-L4058)). In this source, `nobr` maps to batch reduction type 0, while `br_count=1` is reported as `BR=1`; this is ordinary single GEMM, not a one-element batch-reduction benchmark.

The sample dispatches the JIT kernel before starting its timed loop. It runs correctness work before performance timing, then times the repeated kernel calls; the timer encloses the 10000 invocations, not process startup or JIT dispatch ([pinned source, dispatch and timer](https://github.com/libxsmm/libxsmm/blob/10490f10e79d4511f252c33279ef970a188cfab6/samples/xgemm/gemm_kernel.c#L2998-L3024), [pinned source, timed loop](https://github.com/libxsmm/libxsmm/blob/10490f10e79d4511f252c33279ef970a188cfab6/samples/xgemm/gemm_kernel.c#L3157-L3252)). Matrix allocations and initialization are in the caller, outside that timer. The reported JIT creation time (~71 and ~63 microseconds) is printed separately in the SME README. For these plain FP32 cases the command requests no VNNI conversion or batch packing. This is a kernel-throughput measurement; it does not include one-shot setup or a separate application-level pack/allocation cost. The transpose handling selected by the kernel remains part of the timed kernel execution.

The SME wrapper repository itself is pinned here at [`c9de42a561c9c3bf9e926748fb5113a075d1f096`](https://github.com/scalable-analyses/sme/tree/c9de42a561c9c3bf9e926748fb5113a075d1f096). That commit's README commands `git clone https://github.com/libxsmm/libxsmm.git` and does not pin a LIBXSMM SHA, submodule, or release. Therefore the published result cannot be attributed to the LIBXSMM inspection commit above. That current source is evidence for argument and timer semantics, not proof of the exact source revision used for the published measurement. A reproducible rerun must record the LIBXSMM commit, local diff, build options, compiler, OS, and machine.

## Comparison with the local hill

The active local contract is the `kernel-opt` hill in this repository: single-thread FP32, `n=512`, row-major `gemm(n, A, B, C)` computing the full product, with a strict target above 1800 GFLOP/s and a 0.002 correctness tolerance. Its current evidence reports Apple clang 21, `-O3 -march=native -ffast-math`, arm64/Darwin, and the signed machine label `MacBook-Pro-8.local`; the recorded local hardware profile identifies Apple M4 Pro. Its timing and acceptance protocol are the hill's own, including three validation repeats, paired unchanged controls, and a final held-out report ([local final report](search/final.json), [local search contract](../cpu-swarm-sme2-2026-09-24/search/result.json), [recorded hardware profile](../cpu-swarm-sme2-2026-09-24/agent/state.json)).

These differences matter:

- **Transpose and layout:** LIBXSMM's GEMM interface follows column-major BLAS layout conventions. The faster published command requests `trans_b=1`. The local ABI is row-major and requests non-transposed B. A row-major `C=A*B` can be represented by a column-major call as `C^T=B^T*A^T`, with operands/dimensions swapped, but this mapping does not make the README's `C += A*B^T` run identical to the local full-product call.
- **Beta:** both README commands pass beta 1. This is accumulation into C. The local hill verifies a complete output matrix for its function call; do not compare a score without matching C initialization and beta behavior.
- **Measurement boundary:** published timings cover repeated kernel execution after dispatch and setup. The local hill measures the submitted C function under its fixed harness. If implementation setup, allocation, data conversion, or packing is part of that function, it contributes to local timing. Do not compare kernel-only throughput with end-to-end local function latency as if the boundaries match.
- **Machine:** the README result is from an M4 iPad Pro. The local machine is a MacBook Pro with an M4 Pro. They are different SoCs and systems; equal product names or ISA support do not establish equal sustained clocks, cooling, memory behavior, or performance.
- **Repetition and warm-up:** `10000` is the timed repetition count in the command. The sample performs pre-timing correctness execution, but the README does not describe a separate long warm-up protocol. Do not report 10000 as 10000 warm-ups.

The README reports 1755.19 for its first command and 1833.87 for its second, but does not explain the difference causally. It is valid to say the transposed-B command is faster in the reported run. It is not valid to infer that transpose alone caused the gain: beta is 1 in both, but the repository does not pin the library source/build or provide repeated spread, and the README is not a paired local measurement. The LIBXSMM SME generator uses specialized SME code generation, but that implementation detail does not establish which design choice explains these aggregate rates.

## Primary sources

- SME repository README at the inspected wrapper commit: [README.rst](https://github.com/scalable-analyses/sme/blob/c9de42a561c9c3bf9e926748fb5113a075d1f096/README.rst#L4-L26), [reported results](https://github.com/scalable-analyses/sme/blob/c9de42a561c9c3bf9e926748fb5113a075d1f096/README.rst#L28-L85).
- LIBXSMM sample CLI, timer boundary, and reported operation label at the separately inspected upstream commit: [`samples/xgemm/gemm_kernel.c`](https://github.com/libxsmm/libxsmm/blob/10490f10e79d4511f252c33279ef970a188cfab6/samples/xgemm/gemm_kernel.c).
- LIBXSMM GEMM API and supported alpha/beta semantics: [LIBXSMM README, Matrix Multiplication](https://github.com/libxsmm/libxsmm#matrix-multiplication), [LIBXSMM MM documentation](https://github.com/libxsmm/libxsmm/blob/main/documentation/libxsmm_mm.md).
- Local measured contract and outcomes: [hill result](../cpu-swarm-sme2-2026-09-24/search/result.json), [final validation report](../cpu-swarm-sme2-2026-09-24/search/final.json), and [experiment summary](../cpu-swarm-sme2-2026-09-24/README.md).
