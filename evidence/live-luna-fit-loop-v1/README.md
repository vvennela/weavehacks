# Luna: earlier two-trial comparison

This is a saved real Qwen72B GPU run, not the later uncapped plateau run.

Luna selected online FP8 weights, then three Luna investigators read Weave evidence and compared findings. The arbiter selected a batch-token limit of 2048. Both configurations passed all eight fixed tasks and all 96 measured requests. Worst-load p95 changed from 770.977138 to 769.162822 ms: 0.235%, below the required 5%. The reviewer rejected the improvement claim, and Sera returned the FP8 reference with batch tokens 4096. Its returned request passed, and cleanup released the GPU.

The run used both allowed trials: deployment and one batching experiment. It contains one post-deployment search round, not an uncapped or multi-round plateau search.

[Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09ab2-8a98-7815-b4b1-77fcb3bc61f0)

`verification.json` records the passing structural audit of 318 calls and 17 agent requests. `weave-calls-normalized.json` exports actual typed response fields; the original dump preserves the earlier export-format error. Controller records are in `../live-luna-controller-v2`.

Reasoning is not fully verified: one initial investigator denied evidence that was supplied, and the final review cited baseline records beside candidate measurements. Peer review corrected the initial action, and the measured selection was correct. These limits remain visible; this is not proof of reliable diagnosis, a speedup, or search superiority.
