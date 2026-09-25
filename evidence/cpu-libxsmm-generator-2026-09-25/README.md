# Optional LIBXSMM 32-row primitive

The user-approved search starts from LIBXSMM's SME method. Prior attempts to write a smaller-panel kernel as a long assembly edit timed out or imposed inconsistent pointer/stride constraints. This preparation makes an existing pinned-generator capability available to the Sera swarm. It does not select a performance experiment or claim a speedup.

The pinned LIBXSMM `10490f10e79d4511f252c33279ef970a188cfab6` generator exports an FP32 beta-zero NN `(M,N,K)=(512,32,512)` kernel with `lda=ldb=ldc=512`. Its 1,536 bytes are embedded in `panel_primitive.c`; there is no runtime LIBXSMM dependency. It uses a 64 KiB packed operand panel. The complete BSD notice is retained.

`panel_probe.c` only exposes the primitive's ABI for correctness checks. It computes a 32-by-512 row-major product from a 32-by-512 A panel and full 512-by-512 B. Twelve deterministic tests cover random/identity/zero inputs at four row offsets, nonzero output overwrite, exact outside-output guards, and unchanged inputs. All passed. The body reassembles byte-for-byte, has no body relocations, external calls/address materialization, or x18 use, and all direct branch targets remain inside it. See `assembly-audit.json`, `disassembly.txt`, and `relocations.txt`.

`baseline/kernel.c` retains the original `gemm` body and 512-square generated kernel, and adds the optional unused primitive with a forward declaration. That larger source is a new build identity and requires fresh baseline scores. Its final form passed all 48 deterministic public GEMM correctness cases; `baseline-correctness-final.json` and `baseline-provenance.json` bind the exact source hash. The earlier correctness report predates the added forward declaration and is not the authoritative current-source record.

The swarm can select an experiment using this primitive by changing the 512-only wrapper. The algebraic mapping is documented in the Luna generator review. Astra must implement the wrapper, and Sera must check full-product correctness and paired performance. All sixteen calls, SME entries/exits, and internal packing would remain inside the timed call. The current baseline still calls the original full-size kernel exactly once. The fixed hill, compiler, threads, tolerance, and promotion gates remain unchanged.

## Reproduction

Build the pinned LIBXSMM clone as in the earlier reference. Compile `export_panel.c` against its headers and static library, then run the exporter with `panel-32.bin` as its output path. `export.json` records the descriptor, ABI offsets, code size, and binary hash. `panel_primitive.c` embeds each little-endian four-byte word as `.long` with the pinned ABI; `panel_probe.c` adds a correctness-only wrapper. Disassemble a compiled probe object with Apple LLVM `llvm-objdump -d --mattr=+sme,+sme2` and inspect text-section relocations with `-r`.

Run the primitive checks:

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -m pytest -q evidence/cpu-libxsmm-generator-2026-09-25/test_panel.py
```

No performance was measured during preparation. The [generator review](generator-review-luna.md), [layout review](layout-review-luna.md), and [measurement review](measurement-review-luna.md) are research context. They are not proof of speed or production readiness.
