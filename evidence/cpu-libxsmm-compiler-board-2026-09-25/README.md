# Compiler-informed swarm and current-power replay

Status: measurements complete; final coordinator review failed. No candidate is promoted, and no held-out report exists.

The run used the saved full512 NN baseline (`67da75dd729b153a2129f8b1a71dd77b4d01609a94b6d2909ae69d99974fbdae`) and fresh measurements on Battery Power with the saved low-power settings. Prior AC scores were not imported. The fixed evaluator, FP32 arithmetic, compiler flags, tolerance, 10 reports per source, 10 paired controls per candidate, and separated-ranges-plus-5% promotion gate remained unchanged.

The run made 73 Codex model calls and 5 implementation attempts within the 108-call, six-candidate, 180-second-per-call, 1800-second overall caps. It recorded seven trial entries: the fresh baseline, five scored candidates, and one candidate rejected before scoring. All five scored candidates failed the promotion gate. The baseline ranged from 1001.78 to 1113.46 GFLOP/s. Candidate and paired-control ranges were:

| Candidate | Candidate GFLOP/s | Paired control GFLOP/s | Promotion gate |
| --- | ---: | ---: | --- |
| TB with timed SME A transpose | 625.54–1070.00 | 984.33–1106.19 | Failed |
| TB with timed NEON A transpose | 600.02–962.86 | 800.80–1093.42 | Failed |
| Four-step K-loop unroll | 792.92–1102.40 | 822.89–1083.13 | Failed |
| Padded 288-byte A slices | 841.93–1094.35 | 810.78–1088.99 | Failed |
| TA with timed SME B transpose | 588.94–785.19 | 795.27–1105.81 | Failed |

Both 15-specialist ballots matched their saved deterministic ranking: round 1 selected `a_transpose`, `assembly_audit`, then `cache_conflict_layout`; round 2 selected `n512_fast_path`, then `a_transpose`. See `verification.json` for report hashes, signature checks, exact score counts, board checks, and trial source hashes.

The final Astra review did not complete. Its saved input was 1,108,459 characters, 59,883 over the 1,048,576-character limit. The later prompt-repair verification records that prompts were compacted without rewriting failed-phase records. The failed run therefore has no final review decision or held-out confirmation. Keep the unchanged NN baseline; the legacy 1800-GFLOP/s flag is not evidence that the objective was met.

Run `PYTHONPATH=. /tmp/sera-audit-venv/bin/python evidence/cpu-libxsmm-compiler-board-2026-09-25/verify.py` to verify saved evidence only. It calls `hills verify` for each recorded report and does not run measurements.
