# Next source-grounded specialist board

This bounded Sera run retains the imported LIBXSMM baseline with its optional unused panel helper. Fifteen GPT-6 Luna specialists jointly propose and rank experiments; GPT-6 Astra-high implements the selected order and reviews measured outcomes. Three independent Luna reviews add concrete source anchors, feasibility checks, and a history inventory. They do not choose the order or establish performance.

The driver carries actual trial results and failed/skipped attempts from five preceding phases. Low Power and Automatic results stay in separate phase records and are historical context only. Every candidate must pass fresh correctness and paired controls on the initial power source/settings. No system setting changes are authorized by this driver.

Unchanged contract: full single-thread FP32 row-major C=A@B, n=512 timing, frozen kernel-opt hill and compiler flags, tolerance 0.002, all packing/allocation timed, no external runtime libraries or caching, full LIBXSMM notice. Three repeated candidate/control reports, 5% separated-range promotion, one held-out final, target strictly above 1,800 GFLOP/s. Limits remain six attempts, 108 model calls, 180 seconds per agent call, and 1,800 seconds overall. Fresh directories prevent accidental restart or evidence overwrite.

The two context tests passed after an initial failing test. A read-only preflight loaded all five existing phases, including the interrupted phase, without dropping failed attempts or combining scores. No new kernel measurements are claimed by this preparation.

Run once after the three review artifacts are present:

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-next-board-2026-09-25/run.py
```

## Completed Low Power outcome

Sera completed two rounds of 15 specialist recommendations and 15 full-board ballots, using 73 model calls and six implementation attempts. Five distinct kernels passed 48 deterministic correctness cases each. The 64 KiB packed-A implementation timed out at the unchanged 180-second call limit and produced no candidate. No measured source passed promotion.

| Candidate | GFLOP/s | Paired controls GFLOP/s |
| --- | --- | --- |
| libxsmm-full512-row-half-first-traversal | 1031.79, 1071.42, 1095.84 | 1105.43, 1070.18, 1082.03 |
| libxsmm-full512-packed-b-column-panels | 877.12, 942.57, 738.47 | 1096.40, 802.80, 1088.62 |
| libxsmm-full512-column-panel-first-traversal | 637.61, 621.62, 642.83 | 1071.60, 1073.39, 1076.61 |
| libxsmm-full512-distance4-bounded-prefetch | 736.36, 764.50, 754.39 | 1087.33, 1071.24, 872.13 |
| libxsmm-k-loop-joint-two-stream-end-tests | 1048.75, 949.93, 1106.00 | 1020.83, 1064.16, 839.08 |

The unchanged baseline scored 1,078.23, 1,013.60, and 826.70 GFLOP/s; its final held-out report was 1,026.19. Status is completed with the unchanged baseline retained. This is not an optimization gain, and the 1,800 target remains unmet. All 34 report signatures, source hashes, unchanged power/settings captures, and promotion decisions were independently checked. Both 15-ballot rankings were recomputed and matched execution order. See `verification.json`.

The B-layout candidate allocates and fills a new 1 MiB packed-B buffer inside each timed n=512 call and frees it afterward; a read-only Luna source audit found no caching, external BLAS, threading, or benchmark-contract change. This added work must be paid before any locality benefit. The alternate column-first traversal and bounded prefetch variants lost in all three pairs. These results reject the tested variants; they do not isolate a hardware bottleneck.

Specialist advice still requires exact-source review. Root corrected an advisory that mistakenly called the previously measured two-register-bank pipeline new. Astra corrected another recommendation that used a 512-byte B stride where the supplied assembly uses 2,048. No claims of production readiness follow from a completed guarded run.

Next unresolved selected implementation: one 32-row packed-A buffer, 128-byte K stride, all sixteen column panels per row panel, one SME entry/exit. It remains unimplemented because of the call timeout. Existing 32-row helper calls are already measured and are not an equivalent implementation of this single-entry layout. New code must still be implemented by Sera and pass the unchanged gates. The proposed longer call timeout remains unapproved; this run retained 180 seconds.
