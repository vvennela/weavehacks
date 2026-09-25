# Next LIBXSMM swarm block

Goal: exceed 1,800 GFLOP/s under the frozen single-thread FP32 n=512 hill. This is a new bounded search after the prior six-attempt plan finished. Prior evidence and spent budgets remain recorded in the earlier phase. This block uses the same limits: six implementation attempts, 108 Codex model calls, and 1,800 seconds. It starts with a fresh unchanged LIBXSMM baseline and does not import prior timings for eligibility.

The previous block passed correctness for three K-loop variants but promoted none. Two later proposals were skipped because one already existed and the other required an unsupported load form. The new task includes those dispositions and source-grounded Luna reviews. Sera now shares skipped-proposal reasons across all specialist roles in later rounds. Fifteen Luna specialists still propose and rank each batch; Astra-high still selects roles, implements the ranked batch, and reviews measured candidates.

Both AC and battery measurements are retained separately by exact source. The current block accepts the initial power source, requires it and power settings to remain unchanged around every score, and establishes its own baseline and paired controls. License, compiler flags, numerical tolerance, correctness checks, promotion gate, and held-out evaluation remain unchanged.

Preparation validation: 73 CPU-path tests passed after the disposition-feedback fix; 14 example/continuation tests passed after enabling both power modes in the standard runner. The driver parses as Python. Independent Luna review precedes execution. No performance claim follows from these checks.

Run once in this fresh directory:

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-next-2026-09-25/run.py
```

Execution status and exact source hashes are in `controls.json`, `agent/state.json`, and `search/result.json` when created. Signed reports and before/after power observations accompany each trial. The source reviews are unverified research advice; the evaluator decides correctness and speed.

## Terminal outcome

The first implementation call exceeded its unchanged 180-second limit. The process exited with failure before any candidate source or score. All three fresh baseline reports were verified: 1105.62, 1044.67, and 936.95 GFLOP/s. There is no candidate result or final holdout. The saved plan retains 32 spent model calls, one spent implementation attempt, and the remaining swarm-ranked queue. Continuation must preserve those budgets and order.
