# Preparation for the 1,800 GFLOP/s goal

This is setup evidence, not a performance result. No candidate or baseline was timed in this step.

- `35d21e1`: Sera CPU proposer and specialist team default to GPT-6 Luna through Codex ChatGPT login; the example targets 1,800 GFLOP/s.
- `7d6c0ab`: the low-level kernel search also defaults to 1,800 GFLOP/s. A regression test proves that 1,790 no longer meets the default target.
- Relevant tests: 58 passed (`test_kernel_search`, `test_kernel_tools`, `test_kernel_specialists`, `test_cpu_kernel_validation`, `test_public_api`). These tests cover model dispatch and search behavior, not achieved CPU throughput.
- The requested 15-agent configuration remains pending the user's roster adjudication. Current routing still activates at most three specialists. No 15-Luna performance experiment has run.
- Current host power/process/thermal observations are in `host-observation.json`. The host was on battery. Power condition is pending user adjudication; it must be recorded separately from earlier runs if it changes.

The preceding specialist evidence remains unchanged in `../cpu-specialists-codex-2026-09-24/`. That run used six GPT-6 Astra calls, found no accepted improvement, and did not reach either 1,780 or 1,800 GFLOP/s. It does not validate the requested Luna swarm.

GPT-6 Luna reviewed model dispatch and measurement readiness during this step. The review confirmed the former model-default gap and the host-variability problem. The model-default gap is fixed; timing variation has not been fixed or hidden. The original hill, correctness tolerance, thread limit, compiler flags, score convention, and promotion rule remain unchanged.

## Kernel review for user adjudication

Luna proposed a larger eight-tile FP32 SME microkernel, a constant-shape FP32 fast path, and a mixed-precision path with FP32 accumulation. The primary agent checked the larger tile claim before presenting it as a viable option: Apple clang rejected tile selector 4 for `svmopa_za32_f32_m` with valid range [0, 3]. See `tile-selector-check.json`. The eight independent FP32 tiles proposed by Luna are unavailable through this operation; this suggestion is rejected as stated.

Two untested options remain with the user for adjudication:

1. An FP32 `n == 512` fast path with fixed loop bounds and a general-size fallback.
2. A mixed-precision SME path with FP32 accumulation, subject to instruction support and the unchanged 0.002 correctness tolerance. Conversion cost must remain inside the timed call. Accuracy and throughput are unproven.

Neither option has been implemented, timed, or accepted. No target success is claimed.
