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

Weave trace: https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09bc5-95bd-7363-ad57-e202dd411a62
Trace export: enabled
Qwen/Qwen3-0.6B: allocation=2684354560 bytes; memory fraction=0.015691562720279505; sampled service peak=unavailable MiB
zai-org/glm-4-9b-chat-hf: allocation=16106127360 bytes; memory fraction=0.1464545853892754; sampled service peak=unavailable MiB
Sampled device peak: unavailable MiB
