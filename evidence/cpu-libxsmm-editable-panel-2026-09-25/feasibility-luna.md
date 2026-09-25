# Feasibility: one SME entry around all 32-row panels

## Conclusion

Yes. The generated `M=512, N=32, K=512` helper already contains the complete 32-row output-panel computation. Its compact `Lpanel32_330` output-tile loop covers all 512 columns for that one 32-row A panel. A new outer loop around **packing plus that existing tile loop** can repeat the panel 16 times while leaving `smstart`, stack setup, ABI prologue, `smstop`, and epilogue outside. This removes repeated helper entry/exit work; it does not remove repeated packing or GEMM work. This is a feasibility finding, not a speed claim or experiment selection.

## Verified helper facts

The source of the evidence is the embedded helper in `cpu-libxsmm-generator-2026-09-25/panel_primitive.c`, cross-checked against `disassembly.txt`, `export.json`, and `assembly-audit.json`.

- The helper is `_sera_libxsmm_panel32`, callable through the 176-byte LIBXSMM parameter block. It loads B, A, and C pointers from offsets `0x20`, `0x50`, and `0x80` respectively. Export metadata records descriptor `(M,N,K)=(512,32,512)`, `lda=ldb=ldc=512`, beta zero, and a 1,536-byte/384-instruction body. In editable assembly, the relevant labels are `Lpanel32_70` (packing), `Lpanel32_330` (output-tile loop), and `Lpanel32_368` (K loop).
- It has one `smstart` at offset `0x5c` and one `smstop` at `0x5cc`.
- It reserves 64 KiB scratch at offset `0x64` (`sub sp,sp,#0x10000`) and sets `x3` to its base. The pack loop starts at `0x70`: its 32 iterations load 32 vectors from the A-panel pointer (`x1`, advancing by `0x800` per vector) and ZA-transpose/store 16,384 FP32 values into that 64 KiB panel. Each iteration subtracts `0x10000` from `x1` at `0x1c0` and adds `0x40` at `0x318`, for a net `+0x40` per iteration. The loop therefore advances `x1` by `0x800` total. At `0x324`, it subtracts `0x800` (2 KiB) to restore `x1` to the panel start; at `0x328` it restores `sp` from `x20`.
- The compute/tile loop starts at `0x330` (`Lpanel32_330`). It initializes `x6=512`; each body computes one 32-column block with a 512-iteration K loop (`x8=512` at `0x364`, body `0x368..0x38c`, label `Lpanel32_368`), then writes the tile and advances B/C traversal by 128 bytes. The `sub x6,#32; cbnz` at `0x5c4..0x5c8` runs 16 tile iterations. The last tile iteration leaves the loop; it does not perform another panel’s packing.
- In the current wrapper, each call sets `x0` to the unchanged B base, `x1` to `A + r*512`, and `x2` to `C + r*512`, where `r=0,32,...,480`. That pointer mapping is recorded in the generator review and exercised by panel correctness tests.
- The body has no relocations or external calls; all direct branches are internal. Its raw `.long` representation was checked byte-for-byte against the exported primitive. The full BSD license is retained.

## Minimal structural edit, if the board requests it

First make a host-side, editable assembly rendering of the existing helper. Before changing behavior, assemble that rendering and require its code bytes to equal the existing 1,536-byte body, with the same branch targets and no relocations. Keep the saved-register prologue/epilogue and streaming entry/exit byte-identical in this preparation check. This is mechanical source preparation; current Sera agents cannot regenerate the LIBXSMM kernel themselves.

Then, for the one-entry variant, the outer panel loop belongs around the pack block beginning at `0x70` and the tile block beginning at `0x330`. Keep one 64 KiB scratch allocation and one SME streaming region for the entire function. The high-level control flow is:

```text
save original B, A, C pointers in registers preserved across the body
smstart
allocate scratch once; retain scratch base
for panel = 0..15:
    x0 = B_base
    x1 = A_base + panel * 0x10000
    x2 = C_base + panel * 0x10000
    x3 = scratch_base
    sp = scratch_base       # pack's existing [sp] stores use this as cursor
    pack this A panel (existing 32-iteration loop)
    sp = scratch_base       # keep the reserved panel live for compute
    run the existing 16-tile / 512-K compute loop
    # restore loop inputs before next panel
sp = saved stack top
smstop
restore stack and callee-saved registers; return
```

`0x10000` is exactly 32 rows × 512 FP32 values × 4 bytes. A and C panel starts advance by that amount. B always resets to the same base; the existing compute loop advances it across the 512 output columns. The packed A panel is reused across all 16 column tiles within one panel, then overwritten for the next disjoint row panel. Panels cover output rows `[0,512)` exactly once. Preserve the existing beta-zero output writes, K order, four-FMOPA sequence, and general-size fallback in `gemm`.

The existing helper's `sp` is both pack-store cursor and allocation pointer: packing advances it by 64 KiB back to `x20`. Therefore a correct outer loop must explicitly reset the pack cursor to a separately retained scratch base at each panel, then reset `sp` to that base after packing so the region stays reserved during compute. After the sixteenth panel, restore `sp` to the saved stack top before the epilogue. Do not preserve the current end-of-pack `mov sp,x20` as the between-pack-and-compute action; that would free the scratch while it is consumed. The existing output-tile loop also mutates x0/x2 and advances x3 between its 16 tiles; reset all three from saved bases at the next panel boundary. Do not rely on the post-panel register values.

Suitable saved pointer/loop registers must be chosen by auditing the whole body, not by assuming a register is unused from a short disassembly excerpt. The current prologue saves x20/x21, x22/x23, x26/x27, and x28/x29. The edit must preserve the AAPCS64 callee-saved contract and retain 16-byte stack alignment at all C ABI boundaries. No calls may be inserted inside the SME region. Keep all 16 packs and all 16 tile traversals inside the timed `gemm` invocation.

## Feasibility limits and risks

This is smaller than rewriting the 32-row arithmetic kernel: it reuses the verified K loop, ZA layout, and C stores, adding only pointer preservation/reset and a 16-iteration outer branch. However, source conversion from raw words to editable assembly is preparation that must pass a byte-identical round trip. The modified body then needs a fresh full-GEMM correctness check covering all rows, output overwrite, unchanged inputs, the `n!=512` fallback, tails, and `n<=0`. A single SME entry avoids fifteen additional entries and exits compared with 16 calls, but its actual impact is unknown; no component timings or throughput results isolate that cost. Pack and compute work stay the same, and cache or thermal effects are not established.

## Evidence files

- `evidence/cpu-libxsmm-generator-2026-09-25/disassembly.txt`
- `evidence/cpu-libxsmm-generator-2026-09-25/panel_primitive.c`
- `evidence/cpu-libxsmm-generator-2026-09-25/export.json`
- `evidence/cpu-libxsmm-generator-2026-09-25/assembly-audit.json`
- `evidence/cpu-libxsmm-generator-2026-09-25/test_panel.py`
- `evidence/cpu-libxsmm-generator-2026-09-25/generator-review-luna.md`

## Correction note for earlier snapshots

An earlier copy of this note misstated the packing-pointer rewind. Exact disassembly offsets are: `0x1c0` subtracts `0x10000` from `x1` inside each pack iteration; `0x318` adds `0x40` once per iteration; after 32 iterations, `0x324` subtracts `0x800` (2 KiB), not 64 KiB. Thus the 32 packing iterations net to `+0x800` before the final rewind restores the panel base. The editable labels are `Lpanel32_70`, `Lpanel32_330`, and `Lpanel32_368`; `Llibxsmm_440` is a label from the separate full-size kernel and does not name this helper. This note corrects the saved feasibility document for future review; it does not claim that a live run which already captured an earlier copy was updated.
