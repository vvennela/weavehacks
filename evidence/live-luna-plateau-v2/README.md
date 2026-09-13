# Uncapped Luna loop: two swarm rounds and three GPU attempts

Source: `afcaa926d69aaa99f23d614843b083dcf8f1d49a`. The preceding early-stop run is preserved in `../live-luna-plateau-v1`. This retry clarifies proposal authority; it does not change the quality gate, candidate schema, or objective threshold.

## Result

| Attempt | Configuration change | Result |
| --- | --- | --- |
| Deployment (`candidate`) | Online FP8 weights; BF16 KV | All eight tasks pass; p95 770.991792 ms |
| First search (`trial-2`) | Batch-token limit 4096 → 2048 | All eight tasks pass; p95 770.248717 ms; 0.096% gain is below 5% |
| Confirmation (`trial-3`) | Context limit 4096 → 256, other settings from reference | Startup fails; no quality or latency measurement |

Both measured configurations completed 96 measured requests across concurrency 1, 2, 4, and 8. BF16 weights were estimated not to fit; there was no measured BF16 comparison. The eight tasks and 99% quality floor were unchanged.

Three parallel Luna investigators inspected scoped Weave evidence, proposed a setting, shared findings, and refined their proposals in each round. A separate arbiter selected each experiment. Round two received trial 2's measured feedback and a pending confirmation state. Each investigator chose the same configuration in a given round; no diversity or search-superiority claim follows.

The context experiment recorded a CUTLASS internal error during startup. Its underlying cause is not established. The final reviewer correctly marked the prediction `not-tested`. No third investigator round inspected this startup failure. Sera kept the original FP8 reference, answered the returned-runner check correctly, and closed. GPU memory was independently checked at 0 MiB after cleanup.

## What passes and what does not

`verification.json` passes the structural audit: three concurrent investigators, evidence reads, shared findings, feedback, uncapped launch, an attempted confirmation, returned runner, and trace consistency. There were **352 completed Weave calls**, no incomplete calls or trace exceptions, and **31 typed agent responses**. Handled trial failures can exist without a trace-call exception.

**Measured plateau confirmation fails.** The internal stop reason is `objective-plateau-confirmed`, because the policy counts the startup failure as a second round without qualifying progress. The verifier's `confirmation_trial_executed` means attempted, not successfully measured. Neither field proves a performance plateau. The recorded kernel failure is an observed error, not a root-cause diagnosis. Factual reasoning is not certified by the structural audit.

`independent-audit.json` binds all 31 recorded agent responses to completed local Luna CLI outputs, regrades both measured trials at 8/8, and recomputes all three deterministic gates. **Citation accuracy fails:** trial 2's final reviewer cites the deployment diagnosis, and trial 3's reviewer cites trial 2's diagnosis. Their outcome explanations are correct, but those source references are wrong. The deterministic gate does not depend on those citations. `measured-confirmation-audit.json` separately records the failed measured-confirmation check.

There was no qualifying speedup. The search has no total trial cap, but automatic candidate generation still creates a small pool once from the baseline: batch tokens 2048 and context 256 here. This is not an expanding search, global optimization, multi-GPU allocation, or proof that three agents outperform one.

## Plain-English rehearsal

“We started with a model too large for the GPU in its original format. An agent recommended compression, and Sera checked the resulting answers. Three investigators then read the evidence and recommended an experiment. It worked but was not meaningfully faster. They used that result to choose one more experiment. That experiment failed to start, so Sera kept the working model and checked another answer. The loop ran without us choosing the settings. We have proved the workflow, not a speedup.”

Open the [Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09acd-b8f9-7c5f-bbc2-7520c8f64163), then `report.md`, `investigation.md`, and `verification.json`. The runner is now closed; this recording is saved real GPU evidence, not an active endpoint.

## Repeat

`launch.json` saves the exact GPU command. It uses `--fit-first --swarm --until-plateau --auto-space --agent-provider codex-relay --agent-model gpt-5.6-luna`, with no `--budget`. Start a connected local controller first; `../live-luna-plateau-controller-v2/controller-launch.json` records its command with `--max-requests none`. Use fresh output and relay directories for both processes and a matching provider certificate. Authentication belongs in the environment, never in a committed command.

The GPU environment must match the saved runtime and have the pinned model files available. Luna ran through the local Codex login and relay, not W&B serverless inference. W&B provided tracing and evidence access. Rerunning starts real GPU and model-provider work; the absence of a trial cap does not mean unlimited candidate coverage or guaranteed progress.
