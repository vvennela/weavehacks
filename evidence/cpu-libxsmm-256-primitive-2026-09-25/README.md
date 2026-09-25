# Standalone 256-square LIBXSMM primitive

Prepared for the user-approved one-level FP32 Strassen research extension. This is an imported building block, not a selected Strassen implementation or a measured speedup.

The clean pinned LIBXSMM revision is 10490f10e79d4511f252c33279ef970a188cfab6. The offline exporter requests FP32 M=N=K=256, all leading dimensions256, alpha1, beta0, no transpose and no prefetch. It reports target appl_m4, 33,554,432 nominal FLOPs, a176-byte parameter structure, and pointer offsets32/80/128. No LIBXSMM runtime is linked into the standalone primitive.

The generated body is 2,500 bytes. Its editable assembly matches every exported byte, has no body relocations, external calls/address construction, x18 use, or out-of-body direct branch. Complete BSD notices are preserved. See export.json and verification.json for exact hashes and provenance.

Four deterministic correctness cases passed: random, identity, zero and asymmetric integer patterns, seed20260924. Checks cover full overwrite of nonzero C, guard regions, unchanged inputs, finite output, and tolerance0.002 against float64 products. These correctness-only tests do not score performance or establish Strassen-wrapper accuracy. Their first run failed because the probe did not exist; the completed implementation then passed all four.

For dense row-major P=X@Y, put Y in params[4], X in params[10], and P in params[16]; zero the other entries of const void*params[22]. Each dense block occupies256KiB. Parent512-stride quadrants are not valid direct operands or outputs. The future swarm-selected wrapper must form dense operands and recombine results inside timed gemm. See mapping-luna.md.

Reproduce using the pinned clean clone and static archive checked by prepare.py:

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python evidence/cpu-libxsmm-256-primitive-2026-09-25/prepare.py
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -m pytest -q evidence/cpu-libxsmm-256-primitive-2026-09-25/test_primitive.py
```

The role catalog now offers strassen_one_level as an alternate specialist. Astra still selects exactly15 roles. The new behavior test first rejected that unknown ID, then passed after the role was added; all25 catalog/advisory tests passed. No running classical block was changed to use the new role.
