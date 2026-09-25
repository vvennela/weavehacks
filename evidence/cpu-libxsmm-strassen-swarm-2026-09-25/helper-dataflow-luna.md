# LIBXSMM helper dataflow facts for the Strassen board

Source inspected: `baseline/kernel.c`, SHA256 `8bb0113e377808a841819354296fa0ef02ff49e4188d57a091afc6463fc0ca18`. The active `gemm` wrapper is at lines 773–785. The 512 assembly starts at line 43; its labels are `Llibxsmm_64`, `_78`, `_440`, `_478`, and `_70c`. The added 256 body starts at line 3140 (`_sera_libxsmm_256`); corresponding labels are `Lgemm256_64`, `_78`, `_440`, `_478`, and `_70c`. Preparation records confirm the 256 body matches the imported helper and is unused by baseline `gemm`.

## Active full512 NN path

For `n == 512`, `gemm` sets `parameters[4]=B`, `[10]=A`, `[16]=C` and calls `sera_libxsmm_512`; other slots are zero. Assembly loads those pointers into x0, x1, x2 respectively (lines 58–61). There is no C-side input packing in this active path.

The assembly packs A from x1 into a 128 KiB stack scratch panel. `Llibxsmm_64` reserves `0x20 << 12` bytes (line 75) for a 64-row band. In each `Llibxsmm_78` iteration, paired groups of 32 vector loads read A with a 2048-byte row stride, move through ZA, then store 8 × 256-byte groups for each half into the scratch (lines 85–320). The 32 K-panel iterations cover 512 K values in 16-float chunks. x3/x26 identify the packed panel; the compute path reads it while B remains directly addressed from x0. After a band, x1 advances by 128 KiB (64 rows); x7 decreases by 64 until all eight row bands are covered.

`Llibxsmm_440` processes 32-column panels: x6 begins at 512 and decreases by 32. Each panel runs two K=512 loops, `Llibxsmm_478` and `Llibxsmm_70c`. Each loop reads B at a 2048-byte K-row stride, packed A at a 256-byte stride, performs four FP32 FMOPA operations per K step, and writes a 32×32 output tile. The second tile uses x3+128 bytes and C+65,536 bytes, i.e. the next 32 rows. Together the two tiles cover a 64×32 portion of C. The outer counters cover 8 row bands ×16 column panels. These are source-level traversal facts, not timing explanations.

## Added dense 256 helper

The 256 helper is a fixed FP32 256³ beta-zero body. For row-major `P=X@Y`, the verified mapping is `[4]=Y`, `[10]=X`, `[16]=P`; other parameter slots are zero. The ABI has fixed 256 leading dimensions; it has no argument for a parent matrix's 512 stride. Therefore a Strassen wrapper cannot pass a 256 quadrant view from A or B directly. It must form dense 256×256 operands for each product and provide dense storage for the helper's beta-zero product, then scatter/recombine that result into the 512-stride C quadrants.

The helper itself **does repack its x1 operand**. x1 is loaded from slot `[10]` (lines 3155–58); `Lgemm256_78` reads that dense operand with 1024-byte row stride and packs a 64-row ×256-K panel into 64 KiB of stack scratch (lines 3170–3417). It iterates 16 K panels of 16 floats. During compute, x0 (slot `[4]`) is read directly with 1024-byte K-row stride; x3 reads the packed x1 panel. `Lgemm256_440` walks 32-column panels, and `Lgemm256_478`/`_70c` each run K=256 and write two 32×32 tiles for a 64×32 output band. Four 64-row bands and eight 32-column panels cover the dense output. Thus caller-side dense operand formation is required, but adding a second explicit transpose/pack of X would duplicate work the helper already performs. This does not remove the need to materialize X and Y from strided parent quadrants.

The helper reserves 64 KiB by subtracting `0x10 << 12` from SP and uses x3/x26 as scratch bases. Like the 512 body, it restores SP before its compute loops while retaining the scratch address in a register. A wrapper must treat helper stack use as internal, keep its own workspaces valid across each call, and preserve the ABI and complete BSD notice. No performance effect is established by these facts.

## Constraints for code review

- Do not treat the n256 helper as a direct strided-quadrant GEMM or as a caller-provided packed-panel API.
- Dense X, dense Y, and dense beta-zero product buffers may be reused sequentially only after their contents are no longer needed; every allocation, formation, helper call, and recombination stays inside timed `gemm`.
- The helper packs only its x1/input-at-slot-10 operand; slot-4 input is consumed directly. It does not pack both operands.
- The full512 path already performs its own A-panel packing and the observed 64×32 macroblock traversal. Proposals that merely add these same operations repeat existing behavior.
- Stack scratch sizes and traversal follow from the listed instructions. They establish neither a correctness failure nor a speed cause; only fresh correctness and paired measurements can establish those outcomes.
