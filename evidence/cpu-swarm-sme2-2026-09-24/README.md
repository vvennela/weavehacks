# SME2-guided AC kernel experiment

This block completed three of six implementation attempts under the fixed, single-thread FP32 n=512 `kernel-opt` hill. It made 35 of the 108 allowed model calls: 15 Luna proposal calls, 15 Luna ranking calls, one Astra-high roster-selection call, three Astra-high implementation attempts, and one Astra-high review. All 15 roles submitted proposals and valid rankings.

The first attempt produced one new candidate, `compiler_codegen`. The other two attempts abstained because `vector_access` and `n512_fast_path` repeated the same source. The candidate passed the public 48-case correctness check, but every paired load was slower than every unchanged control:

| Repeat | Candidate GFLOP/s | Unchanged control GFLOP/s |
|---:|---:|---:|
| 1 | 891.07 | 1,528.09 |
| 2 | 1,048.92 | 1,464.86 |
| 3 | 899.78 | 1,570.95 |

Astra-high rejected the candidate because it was ineligible under the fixed separated-ranges-plus-5% rule. The measured regression is clear; these results do not establish its cause. No candidate was accepted or promoted.

The unchanged baseline validation scores were 1,362.33, 998.06, and 1,546.06 GFLOP/s. Its final held-out report was 1,526.65 GFLOP/s. The approved target is strictly greater than 1,800 GFLOP/s; it was not met. All **10** signed Hill reports (three baseline validation, three candidate validation, three paired controls, and one final report) passed independent `hills verify --json` checks. AC power and unchanged power settings were recorded before and after every evaluation; no thermal or performance warning was recorded. See `verification.json` for each report and result.

The search stopped after three of six implementation attempts because of a control-flow error. That error was fixed later in commit `9c232eb`; the root agent reports 51 tests passed for that fix. A fresh phase is expected to use the remaining three attempts and 73 model calls. That fix and future phase are not measurements in this evidence bundle.

This is local trusted research, not a native-code sandbox or production deployment. Passing the finite correctness suite does not prove correctness for every dimension. No accepted speedup or end-to-end model gain is established.
