# Approved temporary Automatic battery comparison

The user approved a temporary switch from battery Low Power to Automatic, followed by restoration. This block replays the exact baseline and three candidate sources selected and implemented by the preceding 15-Luna/Astra swarm, in the original order. No new kernel or experiment order is invented. All previous calls and evidence remain recorded in the preceding phase.

The driver verifies each source hash and its prior correctness record, then obtains fresh correctness checks, baseline reports, paired controls, and a final held-out result. Astra reviews only fresh evidence. Low Power scores are not imported into eligibility; a difference between power modes is not an algorithmic gain. The four source hashes remain the same in both modes.

Limits and gates remain unchanged: six candidate maximum, 108 model-call maximum, 180-second agent-call timeout, 1,800-second overall maximum, three repeats, 5% separated ranges, frozen hill/compiler/FP32 tolerance/single thread, license retention, and final holdout. This replay needs only measured-result review calls. Four preflight tests pass; an initial Low Power or AC profile is rejected.

System Settings is used to apply the authorized change because noninteractive sudo requires a password. The host must restore battery Low Power after this process exits, including failure, then record and verify the restored mode. The driver does not modify system settings. Before and after captures reject a mid-block power-source or setting change.

Run once after the approved mode is visibly active:

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-automatic-2026-09-25/run.py
```

## Completed Automatic outcome

The exact-source replay completed with three Astra review calls and no new implementations. All four sources passed the 48-case correctness check. All 22 signed reports were independently verified. Source hashes and order match the preceding Low Power block; every timing report retained Battery Power and Automatic settings.

| Source | Scores (GFLOP/s) | Paired controls (GFLOP/s) |
| --- | --- | --- |
| libxsmm-reference-with-unused-panel32 | 1395.38, 1668.60, 1638.05 | Baseline |
| libxsmm-n512-sixteen-panel32-calls | 1339.67, 1630.17, 1410.96 | 1503.49, 1384.88, 1236.32 |
| libxsmm-n512-constant-shape-c-sme | 1488.55, 1207.13, 1270.95 | 1628.12, 1282.85, 1632.23 |
| libxsmm-full512-padded-272-byte-a-slices | 1252.91, 1252.91, 1377.19 | 1132.44, 1549.78, 1441.26 |

No candidate passed the fixed promotion gate. The first candidate reached 1,630.17 GFLOP/s in one report, but its median was 1,410.96 and its range overlapped controls. The imported baseline reached 1,668.60 in one validation report. Its held-out result was 1,153.52, below the 1,325.61 confirmation floor. Status: `final-performance-unconfirmed`; no winner; target unmet.

The user-approved temporary setting was restored to battery Low Power immediately after the process exited successfully. Both System Settings and `pmset` confirmed restoration; see `power-restoration.json`. AC remains Automatic.

The higher Automatic scores do not establish a kernel improvement or isolate a causal power-mode effect. These modes were measured in sequential blocks, not a randomized crossover. The same three source changes remain unpromoted in both modes. No AC results exist for these three exact sources yet.
