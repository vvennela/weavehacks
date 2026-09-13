# Corrected failure replay v2: reasoning failed

This is a no-GPU diagnostic replay from source `679cfa4`, not a successful autonomous search. It uses real provider calls and remote Weave inspections of copied, previously measured GPU records.

[Saved result](result.json) · [Audit and file hashes](verification.json) · [Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09a6d-0185-7238-98bd-7e43a144b336)

## What passed

All six investigator phases completed at least one inspection. The 374 saved trace calls include eight actual inspection operations and 28 provider attempts. All 28 transmitted message lists and decoded user evidence match the saved requests; provider content, reasoning, and role also match. Twenty-five attempts have parsed output; three have empty content.

Both rounds pass the offline checks for scoped source call IDs, payload hashes, inspection projections, shared findings, and overlapping initial/refinement work. All 282 copied model-request/metric payloads match their original source records. These checks establish trace consistency, not reasoning quality.

The corrected per-prompt summary was present for all six phases: eight prompts, 85–109 tokens, mean 94.375. Load evidence identifies 2,265 total input tokens across 24 successful requests, not tokens per request.

## What failed

All six refined proposals still claim about 2,265 tokens per request. Round-one accepted batching proposals and the arbiter also claim that a 2,048 batch-token limit shrinks KV allocation and relieves pressure. The records do not establish that claim. A batch-token limit is not a prompt-truncation limit.

The arbiter selected the legal batch-2,048 proposal in round one. In round two, all three investigators proposed FP8 KV despite no supported changes and zero remaining budget. Validation rejected them. This is not correct abstention, so the recorded mechanical check fails too.

The FP8 KV reasons guess that automatic KV precision means fp16 and assert quality preservation from prompt length. Neither claim is supported. None of the twelve initial/refined proposal reasons states the observed CUTLASS startup signature.

Two optional inspection requests were invalid: scheduling requested `task_quality` in round one; memory/context requested `trial_diagnosis` in round two. Each still had a successful allowed inspection, but these phases are marked degraded.

## What the historical evidence means

Trial one failed during startup with a CUTLASS internal-error signature. It has no measured quality or latency. Missing-output gate zeros are not 0/8 model accuracy, and the signature does not establish an out-of-memory failure or a root cause.

Historical trial two passed 8/8 tasks. Its p95 latency was 773.763 ms against 774.183 ms for baseline: a 0.054228% gain, below the required 5%. It is an objective miss, not a quality failure or a demonstrated search win.

## Limits

The earlier future-outcome sentence is removed. Trial-two records are revealed in round two. Startup interpretation remains explicitly coached, so this is not blind failure diagnosis. The replay forces a zero-budget second round and reveals historical trial two independently of the current recommendation.

No new GPU trial, prediction-review call, or returned-runner probe ran here. The original [live run](../live-swarm-investigation-v1/README.md) remains separate. This replay proves corrected evidence delivery and safe rejection of unavailable actions; it does not prove reliable reasoning or completion of the swarm demo.
