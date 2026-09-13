# Three Astra investigators: saved-evidence diagnostic

Date: 2026-09-13. Model requested for all three workers: `gpt-6-astra`.

Result: all three investigators reached evidence-supported conclusions on the
central failure, token arithmetic, quality, latency, and budget checks. This is a
non-blind diagnostic, not a controlled model comparison or a production Sera run.

## Execution

Three independent Codex subagents started with no inherited conversation:

- `/root/astra_scheduling_trial`
- `/root/astra_memory_trial`
- `/root/astra_quality_trial`

Each performed two task turns. First, they inspected saved baseline measurements
and the failed context-256 startup, then proposed a legal next action. The only
permitted change was batch tokens 4096 to 2048, with one remaining trial, the
same eight tasks, a 99% quality floor, and a 5% latency-improvement target.

Second, the controller supplied summaries of peer findings and authorized reads
of the saved batch-2048 outcome. Each investigator checked the revealed files,
reviewed peer claims, evaluated its prediction, and selected a final action with
zero trials remaining. This was a historical result reveal, not execution of an
experiment proposed by these agents.

No GPU trials, W&B inference requests, or new Weave traces were created for this
diagnostic. Workers used local saved measurements and logs. Their task calls and
answers are in the Codex conversation; this file is the controller's summary,
not a verbatim transcript or exported provider-call audit.

## Test contamination

The controller mistakenly authorized `invocation.json`, which contains prior
agent narratives and future-stage references. All three workers reported seeing
that content. The controller then prohibited further use of that file and
required conclusions to cite raw measurements. All six final panels disclosed
the contamination. The run cannot establish blind prediction or a fair
improvement over the previous provider. There was no replacement run.

## Findings

| Check | Scheduling | Memory/context | Output quality |
| --- | --- | --- | --- |
| Identify startup CUTLASS error without asserting root cause | Correct | Correct | Correct |
| Distinguish 2,265 total tokens from 94.375 tokens/request | Correct | Correct | Correct |
| Do not invent measured quality or latency for failed startup | Correct | Correct | Correct |
| Do not treat allocated memory or idle gauges as proven pressure | Correct | Correct | Correct |
| Separate task correctness from output agreement | Correct | Correct | Correct |
| Separate quality pass from latency-objective failure | Correct | Correct | Correct |
| Stop and keep baseline when budget is zero | Correct | Correct | Correct |

These are manual checks of the returned explanations against raw files, not an
automatic semantic score or a claim that every statement was exhaustively audited.

All three initially recommended the legal batch-2048 trial as an empirical check,
not a promised optimization. All predicted no qualifying 5% gain. The quality
investigator also predicted 8/8 task correctness. After reading the historical
outcome, all three retained the baseline and prohibited further trials.

The controller independently recomputed:

- Input lengths: 85, 88, 92, 96, 101, 95, 109, 89 tokens; mean 94.375.
- Each load: 2,265 input tokens / 24 successful requests = 94.375.
- Baseline worst-load p95: 774.183014999835 ms.
- Candidate worst-load p95: 773.7631910003984 ms.
- Required candidate p95: at most 735.4738642498432 ms.
- Relative improvement: 0.054228004399802014%, below 5%.
- Both sets of eight parsed task answers match: 5, 9, 3, 10, 3, 4, ["a"], "CAT".

## Useful differences and remaining errors

The memory investigator found additional evidence: reported KV capacity stayed
at 46,144 tokens when context fell to 256. The later batch trial reported 47,840
tokens and only 126 MiB less sampled peak GPU memory. This does not establish a
pressure-relief mechanism or its cause.

Scheduling and quality did not independently verify the baseline cache capacity
during peer review. That metric was available in their authorized sources:
`baseline/metrics-concurrency-1-after-measurement.prom`, line 517,
`vllm:cache_config_info{kv_cache_size_tokens="46144", ...}`. They marked the claim
unverified rather than fabricating a citation. Evidence discovery is still
incomplete, even though the final actions were correct.

The quality investigator also noted that the candidate's `self_check` is empty;
matching measured outputs is not a separate candidate self-check execution.

## Source identity

Paths below are relative to `evidence/live-swarm-investigation-v1/`.

| File | SHA256 |
| --- | --- |
| baseline/trial.json | 2a3a87c985358e7c39c43352e0cbf34c02a4515d62d99679902428a0d47ee68d |
| trial-1/runtime.json | 876714756f2d717633af015d3e2220a12803eeea9a757551128f4e376a69e099 |
| trial-1/server.log | 0ecab48aa5f47a86284b294135bf33bf523e13da139a06cac3aea0ba5901f065 |
| trial-2/trial.json | baa941280641ce27d4a36e141bba86c437c3ac25b48746bdec86d12cadc21e06 |
| trial-2/runtime.json | c47dcb0f3ea75209936ca5eed103805036185f1b594d5b030d1aa6945afb273a |
| invocation.json (contamination source) | 69a20c06f9f04c1c91aa129bc9803c1b1a25b37573c3641a0aec0a0a2dc35b45 |

## What this does not establish

This does not prove search superiority, useful agent disagreement, reliable
structured provider responses, autonomous Sera integration, Weave tool access,
production cost/latency, or success on unseen failures. It also does not validate
the separate compact-prompt implementation currently in progress.

W&B's current [serverless model catalog](https://docs.wandb.ai/inference/models)
lists `openai/gpt-oss-120b` and `openai/gpt-oss-20b`, but not Astra. A W&B-hosted
investigator comparison therefore requires a different model; that comparison
was not performed here. Astra in Codex and W&B Serverless Inference are separate
execution paths.
