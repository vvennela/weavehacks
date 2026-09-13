# Collect a frozen latency comparison

This is a separate benchmark command, not a new limit on normal Sera search.

Eight candidate options per investigator do not mean 24 distinct features. Their options overlap. Sera has eight typed control families and a 20-technique reference catalog; some catalog entries cannot run. Section 19 allows at most 12 distinct candidate configurations per profile, plus the named baseline.

## What works

1. Freeze full configurations and source records before measuring candidates.
2. Start the baseline. Grade its raw answers with the existing strict JSON task grader.
3. Stop if the baseline fails the frozen task floor. Do not collect a misleading oracle.
4. Measure each candidate once, including failed starts. Save raw runtime and request records.
5. Recompute p95 from saved request timings and task scores from saved answers. Keep per-load p95, worst-load p95, startup time, total collection time, sampled GPU memory, generation errors, and failed configurations.
6. Replay grid search and 20 fixed random seeds. Optional agent replays use the production three-investigator, peer-review, and arbiter selection function. No GPU runs occur during replay.

No live benchmark collection or provider replay was run to validate this new command. Tests use explicit synthetic fixtures. The existing large-model demo results are not a Qwen0.6B benchmark universe.

## Freeze a plan

Use the same reviewed workload and task floor throughout collection. First establish a quality-valid Qwen/Qwen3-0.6B pilot and, for section 20, the claimed pressure. If pressure is absent, report the scenario as not established. Do not change questions or lower the floor after seeing candidate results.

The input JSON plan contains:

| Field | Content |
| --- | --- |
| `model_id` | `Qwen/Qwen3-0.6B` |
| `model_revision`, `tokenizer_revision` | The pinned `MODEL_REVISION` in `sera.config` |
| `profile_name` | A stable, meaningful profile name |
| `baseline` | Complete `RuntimeConfig().model_dump()`; only declared memory fraction may differ |
| `candidates` | 2–12 distinct complete configurations, frozen before collecting outcomes |
| `budget` | Benchmark search budget, 1–8 and strictly below candidate count |
| `evidence_kind` | `measured` for actual collection; `test-fixture` only in injected unit tests |
| `records` | The complete identity source records below |
| `compatibility` | Optional precision-mode → SHA256 of a passed, same-hardware compatibility check |
| `random_seeds` | Optional, defaults to 0–19; exactly 20 distinct integers |
| `max_proposals` | Optional, defaults to 32; bounds repeated/invalid replay proposals |

`records` must have exactly these eight fields:

- `workload`: `{"cases": <unchanged strict task cases>, "system_prompt": <frozen text>}`. Each case has a unique `id`, nonempty `prompt`, `expected`, and `max_tokens: 64`. Extra case metadata is retained and hashed.
- `input_token_ids`: exact rendered token lists from the pinned pilot, in case order. The collector checks every successful trial against them.
- `profile`: `{"concurrency": [1, 2, 4, 8], "gpu_memory_utilization": 0.9}` or the reviewed profile. Every candidate must support the declared load.
- `generation`: `sera.runtime.GENERATION` plus `enable_thinking: false`.
- `quality_gate`: `{"version": "sera-task-v1", "floor": 0.99}` or the explicitly approved floor. This is task correctness, not token agreement. Changing it requires a new predeclared experiment.
- `measurement`: the exact `benchmarks.collection.MEASUREMENT` dictionary. It pins request counts, warmup, reduction, and timing scope.
- `hardware`: exact `uuid`, `name`, `total_mib`, `compute_capability`, and `driver` fields from the pilot GPU snapshot. Do not include transient memory use.
- `runtime`: exact installed versions of `vllm`, `torch`, `transformers`, and `flashinfer-python`.

Allowed frozen candidate changes are FP8 precision (with checked compatibility), batch tokens, sequence count, prefix caching, chunked prefill, and eager/graph execution. Context and memory fraction stay fixed within this benchmark profile. Full configurations are sorted lexicographically, not by measured performance. Runtime schema checks still apply.

Precision compatibility hashes are references, not automatic proof: retain and review the passed source check on this exact runtime/GPU. Combined FP8 weights and KV require a combined check. The agent replay adapter currently accepts only single-setting candidates representable by the production proposal schema; weight changes and combined candidates can be collected and replayed by grid/random, but fail agent preflight rather than silently disappearing.

```bash
python -m benchmarks.run_search freeze --plan benchmark-plan.json --output-file frozen-bundle.json
```

This command makes no GPU or provider calls. It hashes all source records, configurations, and the complete bundle. It refuses to replace an existing file.

## Collect on the GPU

```bash
python -m benchmarks.run_search collect --bundle frozen-bundle.json --output-dir evidence/search-collection-v1
```

This is the command that launches GPU servers. It requires the pinned Linux runtime and idle GPU. It saves the frozen bundle before starting. It stops after a bad baseline, identity mismatch, or failed cleanup. Ordinary candidate startup/task failures remain outcomes; they are not dropped. The output directory must be new. Interrupted collections are preserved and incomplete; this command does not resume them automatically.

Each candidate has a raw `*-source.json`, plus the runner's logs and request artifacts when startup reached that stage. `outcomes.json` contains hash-bound normalized records. `summary.json` and `measurements.md` give an honest partial or complete table. Failures before a trustworthy record exists stay missing and block oracle claims.

The measurement uses repeated prompts after per-load warmup. Prefix caching gains apply to that workload, not cold or unseen prompts. Startup is reported separately; total collection time already includes startup. A failed start has no ready timestamp: its reported startup interval ends when `start()` raises, before outer cleanup; the runtime can also clean up internally before raising. The raw record labels that timing scope. GPU memory is sampled whole-device allocation, not model-weight size. Queue/TTFT/preemption telemetry is a cumulative after-load snapshot, not a measured-window average or in-flight KV peak.

## Replay without more GPU trials

```bash
python -m benchmarks.run_search replay --collection evidence/search-collection-v1 --output-dir evidence/search-replay-v1
```

This command checks the frozen bundle, full universe, valid baseline, and raw source hashes. It recomputes normalized outcomes before any callback runs. It then saves fixed grid, all 20 random runs, and their distribution. Without agent flags it makes no provider calls.

For the same production three-investigator selection, add a currently certified provider:

```bash
python -m benchmarks.run_search replay \
  --collection evidence/search-collection-v1 \
  --output-dir evidence/search-agent-replay-v1 \
  --agent-provider codex-relay --agent-model gpt-5.6-luna \
  --project vvennela-n-a/wandb_agent_default_project \
  --provider-check evidence/provider-luna-expanded-v1/result.json \
  --relay-dir /tmp/sera-search-replay
```

Keep a matching local controller connected for `codex-relay`. Alternatively use `--agent-provider wandb`, omit `--relay-dir`, and supply the exact model/project's current passing provider check. The command does not create or rerun a provider check.

Each method has fresh client state. The variants are:

- `full-evidence`: three independent concurrent investigators, optional cached-metric inspections, peer review, one arbiter selection.
- `no-history`: the same selection, but prior outcomes, metric history, and proposal logs are removed before prompts and inspection reads. Baseline and remaining-candidate mask stay available.
- `round-robin`: one of the same three investigators each round, its initial and refinement calls, no peer board and no arbiter.

These are cached metric inspections, **not Weave trace reads**. The `load_metrics` query supplies per-load p95 records; `quality_outputs` supplies scored task-gate summaries, not output text. `latency_outliers` returns no request records because raw request outliers are not imported. Source IDs start with `cached:` and refer to hash-bound local trial artifacts, not Weave calls. The production prompt projection preserves those records, selected history, and the frozen quality floor. No callback receives unseen outcomes or the oracle. Policies are trusted local code, not a security sandbox. Exact no-telemetry ablation remains unavailable because the existing proposal contract requires a valid metric citation.

Saved policy settings precede provider calls. Final audit files contain each round's prompts, decisions, inspections, and provider records. Each full decision permits at most 13 provider requests, each using the client's existing bounded retry/timeout behavior. The frozen proposal limit bounds the total replay. It does not cap normal live Sera search.

## What this does not prove

The table answers which collected configurations were faster and passed the task gate. A full comparison also measures trials to within 5% of the complete universe's best valid latency, plus terminal latency, failures, regret, and provider-call time.

`benchmark_claim` remains `not-assessed`. Section 19.4 still needs an exact, predeclared random-search and ablation passing rule. Do not choose that rule after seeing the scores. No global optimum, production-wide speedup, or agent intelligence claim follows from the table alone.
