# Ten-run AC replay

Status: prepared. The current Mac is on AC Automatic. This block changes no power setting and does not consume permission for another temporary battery Automatic block.

Replay the exact four kernels from `cpu-libxsmm-editable-panel-2026-09-25` in their saved swarm-selected order. Use ten fresh baseline reports and ten alternating candidate/control pairs per candidate, then one held-out report for the selected source. Recheck deterministic 48-case correctness and record power before and after every official report. Preserve frozen hill, compiler, numerical tolerance, thread count, source hashes, and existing 5% separated-range promotion gate. Astra-high adjudicates fresh evidence through Codex ChatGPT login only. No new implementation or proposal call is required.

The user goal is to beat the imported baseline peak consistently over ten runs. The historical imported peak is 1668.5964359101147 GFLOP/s from Battery Automatic. Whether the user intends this historical peak or a fresh same-mode peak is awaiting adjudication. Collecting ten-run AC evidence supports either comparison without choosing between them. Report both. The internal legacy 1800 target is retained only to avoid changing an unresolved acceptance policy; its target_met flag does not decide the new goal. A retained baseline is never a Sera improvement.

Run caps stay six attempts, 108 model calls, 180 seconds per agent call, and 1800 seconds per block. An incomplete ten-run series cannot satisfy the user goal. No automatic retries or pooled power modes.

Validation before measurement: five replay/preflight tests plus 21 kernel-search tests passed. The preflight tests were first run without the driver and failed as expected.

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-ten-run-ac-2026-09-25/run.py
```
