# Approved temporary Automatic battery comparison

The user approved a temporary switch from battery Low Power to Automatic, followed by restoration. This block replays the exact baseline and three candidate sources selected and implemented by the preceding 15-Luna/Astra swarm, in the original order. No new kernel or experiment order is invented. All previous calls and evidence remain recorded in the preceding phase.

The driver verifies each source hash and its prior correctness record, then obtains fresh correctness checks, baseline reports, paired controls, and a final held-out result. Astra reviews only fresh evidence. Low Power scores are not imported into eligibility; a difference between power modes is not an algorithmic gain. The four source hashes remain the same in both modes.

Limits and gates remain unchanged: six candidate maximum, 108 model-call maximum, 180-second agent-call timeout, 1,800-second overall maximum, three repeats, 5% separated ranges, frozen hill/compiler/FP32 tolerance/single thread, license retention, and final holdout. This replay needs only measured-result review calls. Four preflight tests pass; an initial Low Power or AC profile is rejected.

System Settings is used to apply the authorized change because noninteractive sudo requires a password. The host must restore battery Low Power after this process exits, including failure, then record and verify the restored mode. The driver does not modify system settings. Before and after captures reject a mid-block power-source or setting change.

Run once after the approved mode is visibly active:

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-automatic-2026-09-25/run.py
```
