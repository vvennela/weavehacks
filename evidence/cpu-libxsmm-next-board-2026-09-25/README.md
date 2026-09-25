# Next source-grounded specialist board

This bounded Sera run retains the imported LIBXSMM baseline with its optional unused panel helper. Fifteen GPT-6 Luna specialists jointly propose and rank experiments; GPT-6 Astra-high implements the selected order and reviews measured outcomes. Three independent Luna reviews add concrete source anchors, feasibility checks, and a history inventory. They do not choose the order or establish performance.

The driver carries actual trial results and failed/skipped attempts from five preceding phases. Low Power and Automatic results stay in separate phase records and are historical context only. Every candidate must pass fresh correctness and paired controls on the initial power source/settings. No system setting changes are authorized by this driver.

Unchanged contract: full single-thread FP32 row-major C=A@B, n=512 timing, frozen kernel-opt hill and compiler flags, tolerance 0.002, all packing/allocation timed, no external runtime libraries or caching, full LIBXSMM notice. Three repeated candidate/control reports, 5% separated-range promotion, one held-out final, target strictly above 1,800 GFLOP/s. Limits remain six attempts, 108 model calls, 180 seconds per agent call, and 1,800 seconds overall. Fresh directories prevent accidental restart or evidence overwrite.

The two context tests passed after an initial failing test. A read-only preflight loaded all five existing phases, including the interrupted phase, without dropping failed attempts or combining scores. No new kernel measurements are claimed by this preparation.

Run once after the three review artifacts are present:

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-next-board-2026-09-25/run.py
```
