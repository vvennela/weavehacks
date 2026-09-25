# Prepared Automatic replay — awaiting user decision

Do not run or change energy settings until the user authorizes a second temporary Automatic battery block. The earlier one-block authorization was used and Low Power was restored.

This prepared replay uses the exact baseline and four candidate sources from `cpu-libxsmm-editable-panel-2026-09-25` in their saved15-specialist implementation order. It checks source hashes and obtains fresh48-case correctness, three baseline scores, three paired candidate/control scores per candidate, and a final held-out report. No new kernel proposals or ranking changes are made. The source changes are: one-entry64KiB panel layout, one-time128KiB scratch allocation,32-bit K-loop counters, and reversed ZA2/ZA3 issue order. None passed promotion under Low Power.

The existing driver is reused with the prior-phase path and candidate-count text updated. All fixed scoring/FP32/thread/compiler/promotion rules and per-block caps remain unchanged. Astra-high reviews fresh evidence only. The host must restore Low Power after the process exits, including failure, and verify restoration through System Settings and command captures. The driver checks Automatic Battery Power before and after each score and does not modify settings itself.

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-editable-panel-automatic-2026-09-25/run.py
```
