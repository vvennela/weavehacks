# Layout option for the next specialist board

The latest completed continuation did not measure an A/B data-layout change. It measured three K-loop schedule variants; none met the promotion gate. The `a_transpose` implementation timed out, and the selected `scratch_lifetime` attempt abstained because “shrink scratch to 64 KiB” conflicted with keeping the current 128 KiB consumer strides and 64-row traversal. That is a useful constraint: a smaller buffer only works if packing, consumer stride, tile coverage, and traversal change together. See the [continuation summary](../cpu-libxsmm-next-continue-2026-09-25/README.md), [saved swarm state](../cpu-libxsmm-next-continue-2026-09-25/agent/state.json), and [measured trials](../cpu-libxsmm-next-continue-2026-09-25/search/result.json).

One bounded layout experiment for specialists to assess is a **32-row A panel path for n=512**, implemented in C/SME and selected only by the existing `n==512` dispatch. It avoids rewriting the long embedded LIBXSMM loop body. The current fast path allocates 128 KiB of stack scratch per 64-row band (`kernel.c`, `Llibxsmm_64`, lines 69–75) and consumes its packed A data with a 256-byte per-K pointer step (`Llibxsmm_478`/`Llibxsmm_70c`, lines 318–345 and 482–509). The general fallback already has a ZA transpose helper and four-tile SME GEMM structure (`sme_transpose` and `sme_gemm`, lines 681–751), but it materializes a full 512-by-512 transpose.

The proposed experiment would replace the 512-only dispatch with a row-panel loop that packs one 32-row A block into a reusable 64 KiB scratch panel, then computes all 16 output-column tiles before reusing that panel:

```text
for r0 in 0, 32, ..., 480:
    pack[k, r] = A[r0 + r, k]        # k=0..511, r=0..31; 16,384 FP32 values
    for j0 in 0, 32, ..., 480:
        zero one 32x32 ZA output tile
        for k in 0..511, increasing:
            load A panel values pack[k, 0..31]
            load contiguous B row values B[k, j0..j0+31]
            apply the same four FP32 FMOPA updates
        store C[r0..r0+31, j0..j0+31]
```

This defines the data layout and loop order together. The packed address is `pack[k*32 + r]`; the input is `A[(r0+r)*512 + k]`; B remains in its current row-major form, so each 32-value B slice is contiguous; and C is written at `C[(r0+r)*512 + (j0+c)]`. A K iteration must load the 32 A values and 32 B values for the same `k`, update all four ZA tiles in the existing accumulation order, and advance K exactly once. Every output tile has one writer, starts from zero, and stores 32 rows by 32 columns. The row panels cover `[0,512)` without overlap or gaps. Keep the current ABI and `n!=512` fallback unchanged.

The scratch buffer is allocated once inside `gemm`, reused for all sixteen row panels, and freed before return. If allocation fails, dispatch to the unchanged LIBXSMM 512 kernel. Packing, compute, fallback handling, and cleanup all remain in the timed call. Do not keep the old 256-byte consumer stride or two-half traversal while shrinking the panel: this panel is dense K-major with a 128-byte K step, and the new 32-row loop owns one row half at a time.

The hypothesis is narrower scratch and explicit reuse of each packed A panel across every output-column tile. The main risk is that 32-row panels may reload B more often than the current 64-row blocking; the full packing and allocation cost also counts. Current evidence gives no speedup or cache-causality claim. Specialists should decide whether this trade-off merits a candidate, and whether the existing transpose helper can be adapted safely to produce the 32-row panel or whether a simpler pack is safer. Preserve the fixed FP32 arithmetic, full-call timing, tail/general fallback behavior, tolerance, and existing repeated paired-control gates.
