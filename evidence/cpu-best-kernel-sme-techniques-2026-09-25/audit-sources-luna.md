# Static audit of measured panel-loop source changes

Scope: source-only comparison of trials 002 through 006 with trial 001.
No compiler, native kernel, test, or benchmark was run for this review.

The reviewed changes are confined to the inner loop of the existing
`_sera_libxsmm_panel32` assembly. The C `gemm` dispatch is unchanged: `n ==
512` calls this helper with the same parameter slots; other sizes use the
existing fallback. The product still performs the same four FP32 FMOPAs per
K-step into ZA tiles 0–3, with unchanged predicates and operands.

| Trial | Source change | Static correctness assessment |
| --- | --- | --- |
| 002 | Moves the `x0`/`x3` pointer increments between the first pair and second pair of FMOPAs. | Both vector pairs were loaded before the increments. The remaining FMOPAs consume the same `z` registers. Each ZA tile still receives its FP32 updates in the original K order; only address-update placement changes. |
| 003 | Software-pipelines operand loads: preload K=0, run 511 loop iterations that compute the current pair then load the next pair, and issue a final four-FMOPA tail. | Counter 511 plus the tail covers K=0…511 once. Each load precedes the FMOPAs that consume those vectors. Pointers advance once for each of the 512 K positions, then rewind by 512×2048 bytes (`x0`, 1 MiB) and 512×128 bytes (`x3`, 64 KiB), matching the existing panel strides. The last load is K=511; the resulting one-past pointers are not dereferenced before rewind. Per-tile accumulation order is unchanged. |
| 004 | Replaces `sub x8,#1; cbnz x8,label` with `subs x8,#1; b.ne label`. | Both branch while the decremented counter is nonzero and exit at zero. No operand, pointer, or FP operation changes. |

The modified GPRs (`x0`, `x3`, `x8`) are caller-saved. The helper's save/restore
of the callee-saved GPRs and `d8`–`d15`, its parameter ABI, SME entry/exit, and
stack/scratch setup are unchanged. No ABI change is apparent in these diffs.

This inspection supports source-level equivalence of the loop bounds and FP
update order; it does not prove assembled instruction scheduling, dynamic
memory safety, or a speedup. Compilation, existing public correctness checks,
and official paired measurements remain the evidence for those claims. In
particular, no timing claim follows from moving pointer arithmetic or
software-pipelining loads.

## Trials 005 and 006

Trial 005 reorders the four independent tile updates from trial 001's ZA order
0,1,2,3 to 0,2,1,3. Each tile still receives exactly the same operand pair
once per K step, in the same K order. The cross-tile schedule does not change
the per-element FP32 accumulation order. Its `sub`/`cbnz` countdown is the
same as trial 001; no pointers or ABI state change.

Trial 006 restores trial 001's 0,1,2,3 tile order and adds a B prefetch in the
same loop. `x8` starts at 512 and decreases
once per K step; `x0` is the current B row and `x9` is its 2048-byte row
stride. The guard skips the prefetch when `x8 <= 1`. Thus it prefetches the
next row only while one exists: at `x8 == 2` it reaches row 511, and at
`x8 == 1` it does not form the out-of-range next-row hint. It leaves the
actual `ld1w`, pointer increments, FMOPAs, and per-tile math order unchanged.
Its countdown remains trial 001's `sub`/`cbnz`. The `cmp`/conditional branch
adds control flow; whether that guard and hint help is a timing question, not
a source-level conclusion.

Both changes remain in the n=512 helper path; general-size fallback and ABI
setup are untouched. This is source inspection only. It does not validate
hardware prefetch behavior or replace the required compiler, correctness, and
paired timing evidence.
