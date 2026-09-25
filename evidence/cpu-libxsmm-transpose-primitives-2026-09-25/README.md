# Optional full-size LIBXSMM transpose primitives

These are imported, offline-generated capabilities for future Sera-selected experiments. No kernel candidate or experiment was selected during preparation, no baseline was replaced, no performance was measured, and no power setting changed. The pending Automatic replay remains unstarted.

The clean pinned LIBXSMM revision is10490f10e79d4511f252c33279ef970a188cfab6. The exporter requests FP32 full512×512×512, beta0, no prefetch, lda=ldb=ldc512. A fresh ordinary NN export matched all2,500 bytes of the existing reference. The three additional descriptors exported successfully:

| Primitive | Flags | Bytes | Required row-major input preparation |
| --- | --- | --- | --- |
| `sera_libxsmm_ta` | TRANS_A | 3,216 | Form a contiguous transpose of original B; pass it as parameter4; original A as parameter10 |
| `sera_libxsmm_tb` | TRANS_B | 1,520 | Original B as parameter4; form a contiguous transpose of original A as parameter10 |
| `sera_libxsmm_tt` | TRANS_A and TRANS_B | 2,236 | Transposed original B as parameter4; transposed original A as parameter10 |

Parameter16 remains the original row-major C output. All mappings implement Cᵀ=BᵀAᵀ through the column-major ABI. See the independent Luna [mapping](mapping-luna.md) and [generator-path](generator-paths-luna.md) reviews. A transpose flag is not a valid drop-in replacement with the old pointers.

Each editable assembly primitive reassembles to its exact exported bytes. Audits found no body relocations, external calls/address construction, x18 use, or direct branches outside the helper. Complete BSD notices are included in each C source. The signed hill is not involved in this preparation; `verification.json` records mechanical checks and provenance, not a signed throughput result.

Nine deterministic correctness-only tests passed: random, identity, and zero cases for each variant, seed20260924,512×512FP32, nonzero output overwrite, output guards, unchanged inputs, finite output, and tolerance0.002 against float64 products. `probe.c` accepts already prepared buffers only for these tests. That test setup is not a legal performance wrapper: a future Sera candidate must allocate, transpose/pack, call the primitive, and free inside timed `gemm`, retaining the general-size fallback. No caller-side/precomputed transpose or input caching may be used for scoring.

## Reproduction

Build the pinned clean clone with the previously recorded `make -j2 BLAS=0 STATIC=1`. Compile `export.c` against its include directory and static libxsmm.a. Invoke the exporter as `export nn|ta|tb|tt output.bin`; preserve the printed ABI metadata and annotate it with the descriptor, pinned revision, and binary hash as in the saved JSON files. Compare NN output with `../cpu-libxsmm-reference-2026-09-24/kernel-512.bin`.

`prepare.py` reads those saved binaries/metadata, imports the tested mechanical translator from the preceding editable-panel preparation, embeds the complete notices, and independently compiles and checks each editable text section. It writes the correctness-only probe and verification manifest. Run:

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python evidence/cpu-libxsmm-transpose-primitives-2026-09-25/prepare.py
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -m pytest -q evidence/cpu-libxsmm-transpose-primitives-2026-09-25/test_primitives.py
```

The primitives are available for a later15-Luna board to rank. Preparing them does not show that their required full-call conversions are faster than the current reference.
