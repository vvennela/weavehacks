# One-level Strassen and classical-method swarm

Status: measurement block complete; the unchanged baseline failed held-out confirmation. No candidate was promoted, and the optimization goal is not met.

The search used the pinned full512 NN source with the unused LIBXSMM256 primitive (`8bb0113e377808a841819354296fa0ef02ff49e4188d57a091afc6463fc0ca18`). It made 71 Codex calls and 6 implementation attempts. Three changed kernels were measured, each with ten validations and ten alternating paired controls, on Battery Power with the original low-power settings. All packing and workspace remained inside the timed call. The verifier checked 71 signed reports, all source hashes, power boundaries, ballots, rankings, and the saved correctness records.

Each measured source passed the 48 standard correctness cases and four extra cancellation/scale stress cases at tolerance 0.002. This verifies only these recorded cases and does not prove accuracy for all inputs.

| Candidate | Validation GFLOP/s | Paired-control GFLOP/s | Candidate pair wins | Gate |
| --- | ---: | ---: | ---: | --- |
| One-level Strassen, three buffers | 432.96–567.57 | 776.29–1091.57 | 0/10 | Failed |
| Full512 `subs`/`b.ne` loop control | 819.86–1108.66 | 763.69–1110.96 | 7/10 | Failed |
| Strassen with NEON packing | 454.69–559.53 | 785.00–1086.97 | 0/10 | Failed |

None passed the fixed gate `min(candidate) > 1.05 × max(paired control)`. The classical loop-control candidate won 7/10 pairs, but its ranges overlap and it was not promoted. Both Strassen candidates lost all ten pairs; these results do not establish a cause beyond the measured complete implementations.

The fresh baseline ranged from 905.47 to 1102.21 GFLOP/s, with a 1067.08 median. The final unchanged-baseline holdout scored 848.695 GFLOP/s, below the required 860.199 GFLOP/s floor. The result is `final-performance-unconfirmed`; there is no winner and no target success.

Keep power-mode comparisons separate. This phase measured Battery Power only. Saved historical peaks are 1668.596 GFLOP/s on Battery Automatic, 1685.623 GFLOP/s for the prior AC initial baseline, and 1687.393 GFLOP/s for the prior AC unchanged control. None is pooled with this phase's battery measurements. The 1800-GFLOP/s field remains a legacy target flag, not the goal definition.

Both 15-specialist ballots and the selected attempt order are checked in `verification.json`. The record includes report hashes, source hashes, correctness evidence, power observations, candidate ranges, and final holdout status. Re-run `PYTHONPATH=. /tmp/sera-audit-venv/bin/python evidence/cpu-libxsmm-strassen-swarm-2026-09-25/verify.py` to verify saved evidence only; it does not run a benchmark.

Preparation and driver tests plus the relevant core suite passed73 tests. The extra
checks use seed20260924, cancellation perturbations.03125/.0625, and signed powers
of two with exponent ranges±8/±12 plus small mantissa perturbations. Input preservation,
finite output, output guards and full overwrite are checked. `preparation.json`
records exact imported NN/TA/TB/TT/n256 compiled bytes; `source-audit-luna.md` records
Luna's Strassen source audit and the root follow-up checks. The saved limits remain
six implementation attempts,108 calls,180seconds per call and1800seconds per block.
No deeper recursion, Winograd schedule, external runtime or power-setting change was used.
