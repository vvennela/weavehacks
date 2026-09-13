# Approved joint run: total-device accounting

User approved total-device accounting for Molab on 2026-09-13 after the isolated
calibrations. The physical GPU has 97,887 MiB; the declared device budget is
24 GiB. Service allocations are configured vLLM budgets, not separately verified
hard caps. GPU memory sampling can miss short peaks.

The four plans and their model/runtime settings are unchanged from
`evidence/capacity-calibration-v1/manifest.json`. This manifest adds only the
explicit accounting mode and the saved isolated reference paths. The Qwen
3 GiB + GLM 17 GiB quantized plan has passing isolated evidence. The smaller pair
and both BF16 counterfactuals remain estimate-rejected, not measured failures.

Luna acts as placement frontier reader and arbiter. It receives all rejected-plan
arithmetic but can choose only an eligible plan or abstain. This is not another
three-investigator single-model search, nor proof of a broader placement search.
The objective is memory; no fixed total trial cap is imposed. The frozen finite
menu can end the search when no untested eligible plan remains.

Unchanged gates: all eight tasks, 99% quality floor, zero generation errors,
concurrency 1/2/4/8, and joint p95 at most 10% above each matching isolated p95.
The limits are Qwen 150.14391369841178 ms and GLM 187.93426960219224 ms.
Startup and preparation time remain separate from request latency.

Both workloads must overlap in the joint trial. Return both runners only after
both pass; probe the first unchanged task on each, then close both. Verify owned
local process groups have exited and the total device returns to its pre-launch
memory range with no remaining GPU process rows. Never kill an unknown process.

A passing FP8 pair versus estimated BF16 rejection supports the fixed-budget
configuration comparison only. It does not show that every possible BF16
allocation fails the 24 GiB total limit or that a smaller physical card has the
same speed. No measured BF16 memory savings or latency will be invented.
