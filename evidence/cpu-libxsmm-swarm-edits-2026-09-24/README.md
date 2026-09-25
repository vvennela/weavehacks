# Prepared LIBXSMM software-pipeline experiment

Status: candidate generated and correctness-checked; performance not measured.

The prior swarm selected `k_loop_schedule`, `address_generation`, then `sme_fp32_tiles`. Its first full-file implementation call timed out. This continuation retained all 15 rankings, verified the board hash and aggregated order, and retained the 32 spent model calls and one spent implementation attempt. It retries the same selected experiment using guarded source edits; it imports no performance measurements for promotion.

The AC preflight stopped the measurement invocation because the Mac reported battery power. `ac-preflight-failure.log` preserves the failure. A separate `--prepare-only` invocation generated and checked code without calling the performance evaluator. Battery/host state is recorded; the AC profile describes the required measurement environment, not the code-preparation power source.

## Prepared change

`prepared/kernel.c` changes only the reference's two n=512 compute loops. It loads the first operands, then overlaps one-step lookahead loads into z4–z7 with computation on the current operands in z0–z3. Each iteration copies the next operands into the current registers; a final drain performs the last four MOPAs without loading past K=511. The additional register-copy work may offset any latency benefit. This is an unproven performance hypothesis.

The original license, packing, stores, ABI wrapper, and general fallback remain intact. The provenance comment originates from the unmodified reference; this candidate changes its generated instructions and is not byte-identical to the 2,500-byte reference. The guarded response and full candidate are retained separately.

Public validation passes all 48 fixed-seed cases with maximum relative error 1.0017720606112918e-6 (limit .002). No GFLOP/s result or promotion exists for this candidate. Source SHA-256: `bf47e981d23289bfc6faba38d6ac5a3c8362db81f2b61e0215dd441135878685`.

After preparation, the combined state records 33 model calls and two implementation attempts, including the earlier timeout. The original hard caps remain 108 calls and six attempts. The two remaining selected proposals retain their order. Fresh AC baseline/control measurements and Astra's measured review are still required.

The new `sera.kernel_edits` path requires a base hash from supplied measured history and one exact match for each old source span. Edits apply sequentially in memory. It rejects unknown/tampered bases and ambiguous edits; normal compilation, correctness, and performance checks still apply. The subsequent duplicate-source handling fix also skips no-op outputs without changing swarm order. Current relevant suite: 108 passed.
