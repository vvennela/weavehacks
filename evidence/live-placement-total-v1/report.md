# Sera automatic two-model placement

Status: closed
Stop reason: no-legal-plans
Selected plan: ce12ce3d0586bf045759ce2e4e69b265cfc76e73c0fa6021a018f298d6c28a23
Objective: memory
Joint search trials: 1
Joint restoration trials: 0
Quality and latency limits remain mandatory for both models.
Latency objective is the worst service p95. Memory is sampled device peak.
Throughput is both services' output tokens divided by the sum of shared load-window durations.
Capacity evidence: measured quantized placement versus an estimated BF16 fit rejection.
No measured memory-savings claim without a measured matching BF16 pair; no global-optimality claim.
Provider certificate proves existing schema formatting, not placement reasoning quality.
Total-device accounting: service allocations are configured vLLM budgets, not separately verified hard caps.
Weave: https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09bce-654d-71f2-aaf4-3accd0872b4e
