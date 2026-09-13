# Saved failure replay: trace checks pass, reasoning fails

This is a **coached replay with zero new GPU trials**, recorded from commit `4471c98`.
It is not a successful autonomous diagnosis or search demonstration.

[Open the Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09a63-0465-7324-8010-1db65f99d9cb).
The independent offline audit is in [verification.json](verification.json).

## What the evidence proves

- 368 persisted calls, including 24 provider responses and 11 completed inspection operations across all six investigator/round pairs.
- All calls belong to this replay trace and completed without a trace exception. Provider content and returned reasoning match the saved responses exactly.
- All 282 republished request/metric payloads match their original live source calls after removing the explicit replay tag. Both diagnosis payloads match the revealed records. Source file hashes, cited output hashes, shared findings, and overlapping investigator phases check out.
- The startup log records `cutlass_gemm_caller.cuh:62, Error Internal` at lines 404 and 539. Full-log and raw-line hashes match. This identifies the observed signature, not its root cause or an out-of-memory failure.

Cache hits retain persisted-source provenance; 11 inspection operations do not mean 11 separate network fetches.

## What failed

All six refined proposals returned the same incorrect explanation: batching 2048 would truncate “2265 input tokens per request.” The number 2,265 is the total across 24 requests, averaging 94.375 tokens per request. Actual prompts contain 85–109 tokens. The original batch-2048 trial already completed all eight tasks correctly. The claimed truncation and quality risk are not supported.

Round-one scheduling and memory investigators initially proposed batch 2048. The output-quality investigator initially abstained with the false truncation argument; all three refined responses then repeated it. This shows agreement on an error, not validated reasoning.

A separate provider transport audit found zero mismatches across 24 saved requests and responses. The six refinements have distinct provider response IDs, request hashes, and returned-reasoning hashes, but identical final content. The new truncation claim first appears in output-quality's initial response (`agent_calls[10]`), then enters shared finding 2. It was not present in that request, although the older tokens-per-request error was. These records show the model responses propagated the error; the controller did not copy one response into six calls.

Initial inspection responses from memory-context and output-quality acknowledged CUTLASS and absent startup measurements. Output-quality's initial provider reasoning also acknowledged the unknown root cause. None of the initial or refined proposal reasons preserved that diagnosis. No refined reason explains the later measured objective miss, although two round-two raw reasoning records mention trial 2's minimal improvement.

One optional inspection failed: round-one output-quality requested the unavailable tool `trial_diagnosis`. The controller rejected it with `ValueError`; one valid read had already completed. That investigator was marked degraded. A trace without exceptions does not mean every investigation action succeeded.

The replay's mechanical result is **false**: no round-one candidate survived refinement. Round-two abstention passed its recorded check, but zero remaining budget and no legal candidate already required abstention.

## Measurement and scope limits

The failed startup has no measured quality or latency. Missing-output gate zeros are not 0/8 model accuracy. The saved batch trial passed 8/8 tasks; p95 latency was 773.763191 ms versus the 774.183015 ms baseline. Its 0.054228% gain missed the unchanged 5% requirement. These are historical measurements, not results of a replay recommendation.

The replay explicitly taught the CUTLASS/no-quality interpretation and disclosed the later objective-miss category before revealing trial-2 metrics. Round one offered only batch 2048. There was no new candidate execution, reviewer call, or returned-runner test. The leakage fix `4211643` was merged after recording; this evidence was not rerun. Treat it as a coached diagnostic regression that exposed a factual reasoning failure.
