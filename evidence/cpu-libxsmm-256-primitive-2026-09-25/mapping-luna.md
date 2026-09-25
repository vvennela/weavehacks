# GPT-6 Luna audit: 256-square helper for one-level Strassen

The approved seven-product equations and four recombinations are algebraically valid. Signs and FP32 rounding need explicit checks in any implemented candidate. This note does not choose a schedule for the specialist board.

The helper descriptor must be M=N=K=256, lda=ldb=ldc=256, FP32 inputs/output/compute, alpha1, beta0, no transpose and no prefetch. Export from the pinned LIBXSMM revision, with fresh source and binary hashes. Check the actual exported parameter structure size and A/B/C offsets; existing 512 metadata alone is insufficient.

For a dense row-major product P=X@Y, pass Y as column-major A, X as column-major B, and P as output. This computes P-transpose through column-major views and yields row-major P in memory. A quadrant inside a 512-square matrix has stride512 and cannot be passed directly to a helper whose leading dimension is256. Form or copy both operands into dense 256-square workspaces. The beta0 result also needs dense storage: a C quadrant has stride512 and is not a valid direct destination.

A feasible bounded-workspace option uses three 256-square FP32 arrays: left operand, right operand, and product (768 KiB total). Form each pair of operands, call the helper, then accumulate the product with the appropriate signs into the strided C quadrants. Reuse these buffers across seven products and initialize output before accumulation. Other schedules remain the board's choice. All copies, sums, allocation, helper calls, recombination, and cleanup remain in timed gemm. No persistent state or precomputed input is allowed.

The existing full512 and 512-by-32 primitives cannot substitute for a separately generated 256 helper. Do not patch shape metadata or truncate their machine code. Primitive correctness is distinct from correctness and speed of a complete Strassen wrapper.
