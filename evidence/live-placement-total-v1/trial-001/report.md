# Sera two-model placement

Status: closed
Outcome: safe-placement
Reason: both-models-pass-measured-requirements

Memory budget constrained to represent a smaller card; execution uses the measured physical GPU.
This represents memory capacity, not another card's speed or bandwidth.
Physical bytes: 102641958912
Declared bytes: 25769803776
Memory peaks are sampled, not continuous allocation enforcement.
This executor tests one explicit plan; see the search report for agent selection. No global-optimality claim.
No quantization-enabled placement claim without an unchanged-budget unquantized comparison.
Total-device accounting: service allocations are configured vLLM budgets, not separately verified hard caps.
Qwen/Qwen3-0.6B: allocation=3221225472 bytes; memory fraction=0.02092208362703934; sampled service peak=unavailable MiB
zai-org/glm-4-9b-chat-hf: allocation=18253611008 bytes; memory fraction=0.16737666901631473; sampled service peak=unavailable MiB
Sampled device peak: 19904 MiB
Qwen/Qwen3-0.6B: passed=True; p95=138.7766269981512 ms
zai-org/glm-4-9b-chat-hf: passed=True; p95=177.9330960016523 ms
