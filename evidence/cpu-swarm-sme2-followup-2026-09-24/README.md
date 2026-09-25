# SME2-guided AC follow-up

This phase completed three candidate attempts against the unchanged baseline under the fixed, single-thread FP32 n=512 `kernel-opt` hill. All **22** signed Hill reports independently passed `hills verify --json`: three baseline validation reports, nine candidate validation reports, nine paired-control reports, and one final report. All report records are official and passed; they share the same hill tree. AC power and unchanged power settings were recorded around all 22 evaluations, with no recorded thermal or performance warning.

Each candidate passed the public correctness validator's 48 deterministic cases (16 dimensions × three input kinds). None passed the performance promotion gate. Astra-high reviewed all three results and returned `revise`; no candidate was adopted.

| Candidate | Validation GFLOP/s | Paired controls GFLOP/s | Astra-high review |
|---|---|---|---|
| `sme_fp32_schedule` | 1,508.06; 978.95; 1,596.24 | 1,308.11; 1,549.78; 1,007.89 | Revise: mixed results and large repeat variation; no stable gain or causal finding. |
| `tail_alignment` | 1,464.20; 1,440.30; 1,533.92 | 1,440.30; 1,039.77; 1,013.60 | Revise: gains coincided with much lower controls; repeat variation prevents a stable gain. |
| `loop_order` | 1,468.87; 1,573.63; 1,546.80 | 1,559.54; 1,237.50; 1,555.78 | Revise: two losses and one gain against the lowest control; no stable improvement. |

The unchanged baseline scored **1,389.66, 933.69, and 878.32 GFLOP/s** in validation, then **1,575.94 GFLOP/s** on the final report. The approved target is strictly greater than 1,800 GFLOP/s; it was not met. The selected source remains the baseline. These results do not establish a speedup, causal effect, or end-to-end model gain.

The saved state records **37 Codex calls**: 15 Luna proposal calls, 15 Luna ranking calls, one Astra-high roster selection, three Astra-high implementation calls, and three Astra-high measured reviews. All 15 roles submitted advice and rankings. Candidate results and reviews are preserved in `search/result.json` and `agent/state.json`.

This phase is closed. The next research direction is to start from a proven LIBXSMM reference implementation, as requested, rather than continue unguided SME2 source edits. This is a future phase, not evidence in this folder. All measurements here used the frozen hill and existing correctness checks; native execution remains trusted local research, not a production sandbox.
