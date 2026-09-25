# GPT-6 Luna integration review

The imported TA/TB/TT helpers use unique symbols and each owns ABI save/restore, stack scratch, and SME entry/exit. Declarations must precede candidate calls. Do not call them inside another streaming region. Preserve the original NN gemm body in the prepared baseline and measure fresh controls because the source and binary layout change.

TA needs a freshly transposed B buffer, TB a freshly transposed A buffer, TT both. Each is1MiB at512square. Parameter slots4/10 carry those mapped operands, slot16 remains original C. Allocation, input conversion, helper call, free and all stores stay inside timed gemm. On allocation failure, free partial buffers and use unchanged NN; preserve non512 fallback, beta0, full overwrite and unchanged inputs. Prepared-input probe checks do not establish full-call wrapper performance.

Exclude aliases of the measured16-panel-call, one-entry32-row-panel, scratch-reservation, W32counter, FMOPA0132order, constant-shape-C and padded272B paths unless the source and hypothesis materially change. The latest ten-run AC phase failed to show a consistent gain for all four replayed candidates. New descriptor wrappers remain unmeasured and are options for the15-agent board, not chosen experiments. No kernel selection, edit or measurement was done by this review.
