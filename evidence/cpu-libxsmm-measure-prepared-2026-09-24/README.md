# LIBXSMM battery measurement continuation

The completed block retained the original 15-specialist rankings and spent budgets, measured the prepared software-pipeline candidate, then continued the pending pointer-end and two-step-unroll experiments. All three candidates passed 48 deterministic correctness cases. None passed the unchanged promotion gate: minimum candidate throughput must exceed maximum paired control throughput by 5%.

| Source | Validation GFLOP/s | Paired controls GFLOP/s | Astra review |
| --- | --- | --- | --- |
| Unchanged LIBXSMM reference | 1020.50, 1077.33, 1055.97 | Initial baseline | Retained |
| Software pipeline | 730.60, 778.17, 756.87 | 795.07, 1015.36, 847.47 | Reject |
| Pointer-end tests | 765.68, 1018.89, 954.30 | 824.69, 868.49, 801.90 | Revise; not promoted |
| Two-step K unroll | 1087.51, 1047.55, 1091.20 | 947.56, 1040.11, 873.32 | Revise; not promoted |

The unchanged reference's final held-out score was **801.30 GFLOP/s**, below its 969.48 confirmation floor. The result is `final-performance-unconfirmed`, with no winner returned and the 1,800 GFLOP/s target unmet. The low final result and control spread limit performance conclusions. No improvement is claimed.

All 22 signed reports were independently verified. Before/after observations confirm battery power and unchanged power settings for each score. Source hashes match the saved correctness records. See [verification.json](verification.json), [search/result.json](search/result.json), and the [AC/battery source comparison](../cpu-libxsmm-power-comparison-2026-09-24/report.md). AC results remain preserved separately. These new candidates do not yet have AC measurements.

## Budgets and continuation

The script checked the board hash, all 15 rankings, aggregated order, spent budgets, candidate hash, correctness evidence, retained license, and replay of the saved edits. It imported 33 model calls and two implementation attempts, but no old timing results for eligibility. The completed plan used 71 total model calls and six total implementation attempts, including the earlier timeout and prepared candidate. The second swarm batch selected two ideas: Astra abstained because one was already present in the reference and the other required an unsupported paired-load writeback form. No unmeasured proposal was credited as an improvement.

The hard caps remained 108 calls and six attempts. The frozen hill, numerical tolerance, compiler flags, one-thread limit, three repeats, paired controls, and final held-out check stayed unchanged. This is a specific audited research continuation, not a general production resume API. Output directories cannot be reused to overwrite a run.

## Power policy and checks

The user approved measurements on both AC and battery. Each block establishes fresh baselines and paired controls, keeps power source/settings unchanged, and retains both power modes separately for the same exact source. Missing source/power combinations remain unmeasured until that mode is available. Earlier AC-only preflight and review artifacts record the superseded policy.

Seven checkpoint and power-policy tests pass. Check the saved plan without generation or scoring:

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python evidence/cpu-libxsmm-measure-prepared-2026-09-24/run.py --check-only
```

The completed invocation was:

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-measure-prepared-2026-09-24/run.py
```
