# Astra: old-menu abstention run

This run used the old, two-choice search pool at source `afcaa926d69aaa99f23d614843b083dcf8f1d49a`. It does not test the expanded candidate generator.

Sera estimated the BF16 Qwen72B reference would not fit. Its advisor and arbiter selected online FP8 weights with BF16 KV. The deployment ran all eight tasks successfully. Three Astra investigators inspected Weave evidence, shared findings, and independently declined the two remaining settings: batch tokens 2048 or context 256. Neither option offered a strong hypothesis for this short-input workload.

Sera returned the measured baseline. A fresh request passed, and the runner closed and released the GPU. There was one swarm decision round, no post-deployment optimization trial, and no measured latency improvement. This is a valid abstention outcome, not proof of the requested multi-iteration search loop. The strict two-round audit in `verification.json` fails for that reason.

[Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09ad9-f17a-7ebb-b9df-9a5dec21a1ab): 175 exported calls. Raw local Codex records are in `../live-astra-plateau-controller-v1`.

Bookkeeping note: the first two completed Astra request directories were initially saved under the Luna controller output folder. Their request and invocation records identify Astra. Only those two new directories were moved into the Astra folder; the original launch record and corrected restart record are preserved. No completed Luna records were overwritten.
