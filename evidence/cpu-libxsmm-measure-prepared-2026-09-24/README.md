# AC-only measurement continuation

This script is prepared but has not run a performance measurement. It consumes the correctness-tested `libxsmm-k-loop-software-pipeline` candidate from the previous preparation phase once, then continues the original pending order: `address_generation`, `sme_fp32_tiles`.

Before execution it checks the board hash, all 15 rankings, aggregated order, spent budgets, candidate hash, correctness evidence, retained license, and exact replay of the saved edits against the reference. The existing 33 model calls and two implementation attempts remain spent. The hard caps remain 108 calls and six attempts: one prepared candidate awaits measurement, and four new implementation attempts remain available.

The script imports no old timing results into promotion eligibility. It will run a fresh reference baseline, repeated paired controls, Astra's measured reviews, and the final held-out check under the unchanged hill. AC is required before model/evaluator setup and around each score. Power settings must remain unchanged. Candidate sources must retain the LIBXSMM license notice before they reach correctness or timing checks.

This is a specific audited research continuation, not a general production resume API. It requires a fresh `agent/` and `search/` output directory; it does not overwrite a partially measured run.

Check the saved plan without generation or scoring:

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python evidence/cpu-libxsmm-measure-prepared-2026-09-24/run.py --check-only
```

Run measurements after AC is restored:

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-measure-prepared-2026-09-24/run.py
```

Validation: six checkpoint/preflight tests pass. The check-only invocation confirms the prepared source hash and reports battery power. No performance result or target claim is attached to this continuation yet.

## Updated power authorization

The user subsequently authorized benchmarking on battery with a fresh baseline. The driver now accepts either AC or battery and requires the same power source and settings throughout the block. Prior AC scores remain separate from eligibility. Seven checkpoint/power-policy tests pass. The earlier AC-only preflight and review above describe the previous policy.
