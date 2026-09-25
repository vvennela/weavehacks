# LIBXSMM-reference swarm run — interrupted before candidate

The unchanged LIBXSMM-derived baseline completed three official validation measurements: **1,643.48, 1,276.74, and 1,176.06 GFLOP/s**. All three signed reports verify. The saved baseline also passed the recorded 48-case public correctness check. There is no final held-out report.

The swarm used 32 model calls: one Astra-high roster selection, 15 Luna proposal calls, 15 Luna ranking calls, and one Astra-high implementation call. All advice and rankings were received. The original selected order is preserved as `k_loop_schedule`, `address_generation`, `sme_fp32_tiles`. The first Astra-high implementation call timed out after about 180 seconds. No candidate source was produced or scored; the 1,800 GFLOP/s target has no result for this run.

The pending order remains in `agent/state.json`. A later machine preflight found battery power and stopped before any continuation or candidate measurement. Do not treat the baseline scores as candidate or optimization scores. No source was promoted and no final target decision was made.
