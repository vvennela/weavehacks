# Swarm with optional full512 transpose primitives

Status: prepared. The current Mac is AC Automatic. No power-setting change is required or authorized by this driver.

The prepared source adds three exact, optional unused LIBXSMM primitives to the prior imported baseline. The original gemm body and NN instruction bytes remain unchanged. The new source is108226bytes and its compiled text is20628bytes; all four full512 generated bodies were found exactly once with their exported bytes. Binary layout is different, so the search measures a fresh baseline. The entire baseline passed48 deterministic correctness cases. Preparation selects no experiment and claims no speedup.

Astra-high chooses15Luna specialists. The specialists receive complete source, exact transpose mappings, generator facts, and the prior unsuccessful trial inventory including the ten-run AC replay. They propose and jointly rank a batch; Astra implements the ranked queue and reviews results. Optional TA/TB/TT wrappers require all input conversion/allocation/cleanup inside timed gemm. The board can choose other distinct legal changes within the existing scope. All model calls use Codex with ChatGPT login only.

Ten validations per source and ten alternating fresh paired controls per candidate; existing5% separated-range promotion and final held-out check retained. Current goal: beat imported baseline peak consistently over ten runs. Recent saved AC peak1685.6230608449698; earlier Battery Automatic1668.5964359101147. Compare both historical and fresh same-mode peaks without selecting the unresolved comparator policy. The internal1800 setting is a legacy search stop check, not the goal definition. Never claim a retained baseline as a Sera improvement.

Caps unchanged:6implementation attempts,108model calls,180seconds per call,1800seconds per block. Frozen hill, FP32 ABI, compiler flags, tolerance, thread count, licenses, and power profile remain fixed. Before/after power captures surround every report.

Preparation validation:2 source-integrity tests,1 driver integration test, and46 existing search/advisory/board tests passed (49total). Preparation tests first failed because the implementation did not exist. No timing was performed by preparation.

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-transpose-swarm-2026-09-25/run.py
```
