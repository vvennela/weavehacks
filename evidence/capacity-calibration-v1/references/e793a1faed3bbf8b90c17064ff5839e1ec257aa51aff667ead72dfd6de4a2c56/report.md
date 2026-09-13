# Sera two-model placement

Status: rejected
Outcome: not-attempted
Reason: estimated-memory-does-not-fit

Memory budget constrained to represent a smaller card; execution uses the measured physical GPU.
This represents memory capacity, not another card's speed or bandwidth.
Physical bytes: 102641958912
Declared bytes: 25769803776
Memory peaks are sampled, not continuous allocation enforcement.
This executor tests one explicit plan; see the search report for agent selection. No global-optimality claim.
No quantization-enabled placement claim without an unchanged-budget unquantized comparison.

Weave trace: https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09bc5-7e3e-7d1c-b8f4-324372769635
Trace export: enabled
Qwen/Qwen3-0.6B: allocation=3221225472 bytes; memory fraction=0.02092208362703934; sampled service peak=unavailable MiB
zai-org/glm-4-9b-chat-hf: allocation=18253611008 bytes; memory fraction=0.16737666901631473; sampled service peak=unavailable MiB
Sampled device peak: unavailable MiB
