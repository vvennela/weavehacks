# Astra: earlier two-trial comparison

This saved real run used Astra for all investigator roles, separately from Luna. Astra selected Qwen72B online FP8 deployment. The deployed model passed the eight fixed tasks. The three investigators then abstained from a batching experiment, and Sera returned the working FP8 reference. The returned request and cleanup passed.

[Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09abb-31b5-750a-9c6e-68d32cd4a03e)

This is not a completed optimization-experiment comparison or a plateau run: no post-deployment candidate ran. The stricter all-investigator-inspection audit also fails because output_quality explicitly declined a remote read, citing the already supplied passing quality results. Scheduling and memory_context each performed two reads. Do not label the trace as satisfying an all-three-read requirement.

The run contains 172 completed Weave calls with no recorded call exception. `weave-calls-normalized.json` exports typed responses from their actual fields. Local Codex controller records are in `../live-astra-controller-v2`. No BF16 performance comparison, speedup, or multi-GPU claim is established.
