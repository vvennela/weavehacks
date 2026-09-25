# Continue the source-grounded LIBXSMM plan

This continuation preserves the failed phase's original six-attempt/108-call limits, its 32 spent calls and one spent attempt, and the pending scratch-lifetime then SME-scheduling order. It derives the remaining runtime from the original start timestamp plus 1,800 seconds; setup and recovery do not reset that deadline. An expired deadline stops before model setup. The timed-out experiment is not retried.

The validator checks spent budgets, limits, roster, board hash, all 15 ballots, Borda order, pending queue, and the prior timeout. Six tests pass. The baseline must match the original recorded source hash. All scores for eligibility are fresh; prior timings remain research context only. The existing correctness, license, power/settings, repeated-control, and final-holdout checks remain unchanged. This is a specific research continuation, not a general resume API.

The same code and test gates support AC and battery. Each block keeps its power mode fixed and all evidence separate. Fresh agent/search directories prevent overwrite of old reports.

Run: `PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-next-continue-2026-09-25/run.py`.
