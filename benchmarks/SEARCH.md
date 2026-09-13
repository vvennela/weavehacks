# Saved-outcome search benchmark

`benchmarks.search` implements the replay mechanics in spec sections 19–20. It is a benchmark control, not Sera's public optimizer. It performs no GPU trials, network requests, model calls, or file writes. It does not change task cases, prompts, thresholds, or production selection.

## Freeze before collecting outcomes

Call `freeze_manifest(identity, baseline, candidates, budget=...)`, then save its returned JSON before measuring candidates. The manifest contains its own canonical SHA256 hash.

- Model: Qwen/Qwen3-0.6B only, with recorded model and tokenizer revision SHAs.
- Baseline: `sera-baseline-v1`. Only its memory fraction can change for a named workload profile.
- Universe: two to twelve distinct nonbaseline `RuntimeConfig` configurations. Changes are limited to supported precision fields and batching fields. Full configurations are sorted lexicographically by canonical JSON, not by scores or favorable names. Configuration hashes are candidate IDs.
- Budget: one to eight candidate trials, strictly smaller than the nonbaseline universe. The baseline costs zero search trials.
- All candidates keep the baseline's memory fraction and context limit. Illegal runtime configurations fail schema validation.
- Precision candidates require a `compatibility` map containing `kv-fp8` and/or `weights-fp8` with the hash of the passed hardware-check record. A combined candidate also requires `weights-and-kv-fp8`: separate successes do not establish that both settings work together. Verify each check actually passed on the same pinned runtime and GPU before supplying its hash.
- Freeze exactly twenty distinct random seeds; the default is integers 0 through 19.
- The proposal cap defaults to 32 and is also frozen. It bounds invalid or repeated choices without consuming GPU trials.

`identity` must contain exactly these fields:

```text
model_id, model_revision, tokenizer_revision, profile_name,
workload_hash, input_token_ids_hash, profile_hash, generation_hash,
quality_gate_hash, measurement_hash, hardware_hash, runtime_hash
```

Each `_hash` is the SHA256 of its complete canonical record, not a short label. Save those source records alongside the manifest. In particular, `profile_hash` must cover load and memory limits; `generation_hash` must cover all sampling and template settings; `quality_gate_hash` must cover evaluator version and floor; `measurement_hash` must cover warm-ups, passes, load, percentile method, and metric definitions. `input_token_ids_hash` prevents different rendered prompts from being joined as the same workload.

Do not refreeze a smaller universe after observing losing candidates. Missing outcomes mean the benchmark is incomplete, not that candidates can be dropped.

## Saved artifacts

Replay accepts the manifest and a list of outcome envelopes. Each envelope is:

```python
{"record": record, "artifact_hash": content_hash(record)}
```

Each record has these required fields:

```text
manifest_hash, identity, candidate_id, configuration, config_hash,
evidence_kind, source_evidence_hash, status,
feasibility_passed, reliability_passed, quality_passed,
p95_latency_ms, peak_memory_mib, startup_seconds, gpu_collection_seconds
```

`identity`, configuration, and hashes must exactly match the manifest. `source_evidence_hash` refers to the saved raw trial evidence from which the normalized outcome was derived. `evidence_kind` is `measured` for genuine collection or `test-fixture` for tests. They cannot be mixed. Hashes check identity and integrity; they do not prove that somebody actually ran a GPU trial. The caller must retain and audit source evidence. Never relabel synthetic values as measured.

Allowed statuses are `completed`, `startup-failed`, `request-failed`, `cleanup-failed`, and `infeasible`. Boolean gates must be actual booleans. The adapter must derive them from the frozen validators and recorded results, not ask an agent to approve them. Valid outcomes need positive finite p95 latency and peak memory. Failed outcomes can have null objective measurements. All outcomes need nonnegative timing measurements. Define `gpu_collection_seconds` as the complete owned runtime interval, including startup; `startup_seconds` is also reported separately and must not be added a second time.

An optional `telemetry` object accepts finite nonnegative numbers or null, for example queue time, KV use, or preemptions. Put only measurements for that record in it. Unknown fields are rejected to keep policy evidence narrow.

Exactly one artifact is required for the baseline and every frozen candidate, including failures. Missing or duplicate outcomes, hash mismatches, inconsistent workload/runtime identity, malformed gates, and absent valid metrics fail closed before a policy starts. This initial implementation also requires a quality-valid baseline. An invalid reference needs a separately specified protocol; it is not silently accepted.

Existing single-candidate result files are not automatically treated as complete search evidence. A collection adapter still needs to assemble and verify these envelopes from real trial records; do not invent missing values to make an import pass.

## Run policies

```python
from benchmarks.search import replay, run_comparison

grid_result = replay(manifest, artifacts)
comparison = run_comparison(
    manifest, artifacts,
    policies={"sera": sera_choice, "without-history": no_history_choice},
)
```

Each callback receives only a copied view:

- Baseline outcome and fixed identity.
- All legal configuration descriptions, without their outcomes.
- Outcomes selected by this policy so far.
- Remaining candidate IDs and trial budget.
- The proposal log, including rejected choices.

It returns one candidate ID. Selecting a new candidate reveals that cached outcome and consumes one trial, even if startup or quality failed. Out-of-universe and repeated proposals are recorded but consume no GPU trials. Repeats are not re-executed. Callback errors stop that policy and are recorded by exception type without arbitrary error text. Callbacks must set their own external-call timeouts; this in-process harness cannot safely preempt a blocked callback.

Each policy and each random seed starts with fresh observed history. Supply independent callback state for agent and ablation runs. The built-in random policy samples remaining candidates uniformly without replacement. Policies must not read the source artifact files or close over the full outcome table. The narrow callback view prevents accidental disclosure; it is not a sandbox against malicious Python introspection or outside file access. Agent prompts and tools must receive only that view. Do not send the completed benchmark report back into an unfinished policy run.

## Results and limits

Each replay reports the best quality-valid p95 latency and its peak-memory tie-breaker at trial counts zero through the used budget. The oracle is the best valid outcome in the complete frozen universe, including the baseline. It is computed for reporting after policy callbacks finish and is never in a policy view. The near-oracle threshold is latency no greater than 1.05 times oracle latency. A baseline already within that limit reaches it at trial zero.

Reports include trials to threshold (null if unreached), latency regret, invalid trials, quality failures, repeated proposals, collection/startup time, and policy-call time. No GPU trials occur during replay. The comparison returns all twenty random runs, their median terminal p95, their threshold-hit counts, and the hit fraction. Unreached thresholds remain right-censored; no fake trial count replaces them.

`performance_claim_allowed` is false for test fixtures. A true value only identifies consistent records labeled measured; it is not a passed benchmark claim or proof of provenance. Every report leaves `benchmark_claim` as `not-assessed`.

The spec leaves “beats the median random-search result at the same budget” and “outperforms an ablation” without an exact comparison rule. This harness reports terminal latency and trials to threshold but does not choose that rule after seeing results. The product owner must freeze the rule before making the section 19.4 claim. The near-oracle objective is p95 latency; this benchmark does not silently adopt the product's optional throughput or memory priority.

Real evidence still required:

1. A baseline pilot proving each section 20 pressure profile actually exists.
2. The frozen, compatible candidate configurations for each established profile.
3. Complete measured candidate outcomes with the same workload, gates, and hardware identity.
4. Agent and ablation callbacks, with saved prompts/responses and no access to unseen outcomes.
5. A preregistered success rule and the resulting grid, random distribution, and ablation comparisons.

Neither the unchanged eight easy tasks nor the original 24-case task pilot establishes queueing or KV pressure by itself. Their existing quality results cannot substitute for these measurements.

## Validation

```bash
.venv/bin/python -m pytest -q tests/test_search_benchmark.py
```

Tests use explicitly labeled synthetic fixtures solely to check mechanics. They cover frozen identity, missing/mismatched evidence, leakage through callback views, mutation isolation, budget accounting, failed trials, quality gates, oracle ties, and seeded reproducibility. They establish no model performance claim.

## W&B policy adapters: current bounded subset

`benchmarks.search_policies.WandbSearchPolicy` reuses `WandbAgent.request`, `Proposal`, `ArbiterDecision`, `validate_proposal`, and the existing provider-check gate without changing those contracts. Constructor validation is local; provider calls happen only when replay invokes the adapter. No live provider or GPU call was made to validate this implementation.

Available variants:

| Variant | Actual behavior |
| --- | --- |
| `full-evidence` | Each active quantization/batching specialist proposes once; the arbiter chooses at most one valid proposal. Baseline and selected outcome metrics/history are available. |
| `no-history` | Same specialist and arbiter calls, but all observed outcome history, flattened historical metrics, and past proposal logs are removed before every provider call. Baseline evidence and the remaining-candidate mask remain. |
| `round-robin` | Calls one active specialist, starting with quantization and rotating through batching. Skips inactive roles. Does not call the arbiter. |
| `no-reduced-telemetry` | The evidence projection removes all reduced metrics, but adapter creation is blocked by the current citation schema. No provider calls occur. |

The exact telemetry ablation is blocked because `Proposal.evidence_used` requires at least one citation, while `validate_proposal` only accepts names present in the supplied metrics. Removing every reduced metric leaves no valid citation. Keeping p95 or memory metrics and calling that “no reduced telemetry” would hide a contract change. A narrower “no auxiliary telemetry” comparison or a schema supporting nonmetric evidence needs an explicit, frozen definition first.

The expanded proposal schema supports FP8 KV plus bounded integer controls: `max_num_batched_tokens` (1–65,536), `max_num_seqs` (1–256), and `max_model_len` (65–4,096). Validation checks the actual parent configuration, the explicit per-run allowed values, and the frozen candidate hashes; booleans, no-op changes, and invalid combined settings are rejected. Live defaults remain limited to FP8 KV and batch tokens 2048: schema capability does not activate new GPU trials. The expanded provider-format check is pending; a new matching passed check is required before these adapters can use the expanded schema. Multi-value batching universes can now support more than one trial and a structural history ablation. The replay manifest still fixes context length across candidates, so context-varying universes remain blocked. The exact no-reduced-telemetry ablation also remains blocked by the metric-only citation contract described above. No real search win has been established. These adapters are not a substitute for the full section 19 Sera policy, its combination proposals, exploration rule, or a validated intelligence claim.

Before any live policy calls:

```python
from benchmarks.search import run_comparison
from benchmarks.search_policies import WandbSearchPolicy
from sera.agent import WandbAgent
from sera.storage import save_json

# manifest/artifacts must pass the frozen-universe checks described above.
# Use a fresh client per policy. The saved provider check must match current schemas.
policies = {
    name: WandbSearchPolicy(
        manifest,
        WandbAgent(project=project),
        provider_check=provider_check_path,
        variant=name,
        max_provider_requests=12,
    )
    for name in ('full-evidence', 'no-history', 'round-robin')
}

# Save policy settings/hashes before any call. This does not contact W&B.
for name, policy in policies.items():
    save_json(output_dir / f'{name}-policy.json', policy.export_audit())

try:
    comparison = run_comparison(manifest, artifacts, policies=policies)
    save_json(output_dir / 'comparison.json', comparison)
finally:
    for name, policy in policies.items():
        save_json(output_dir / f'{name}-policy.json', policy.export_audit())
```

Create `output_dir` before using this example. No credential values go in these artifacts. The audit records exact projected evidence, instructions, schema hashes, provider-model/project identity, raw provider call records and retry outcomes from the existing client, validation decisions, and selected candidate IDs. Audit records stay outside the next prompt; no-history never receives the adapter's earlier call log. The policy settings hash freezes the variant, specialist order, instructions, provider identity, schema identity, and call limit. Reusing one adapter for a second replay is not supported: create a fresh adapter and client so its call budget and round-robin state start clean.

Each adapter decision has at most one request per active specialist and, except round-robin, one arbiter request. Each request inherits the existing client's maximum two response attempts and timeout. The separate `max_provider_requests` cap bounds repeated invalid decisions across the whole policy run. Rejected provider responses, wrong roles, invalid citations, duplicate proposal IDs, unsupported configurations, and ineligible arbiter IDs never fall back silently to grid search. They return a rejected proposal to replay or stop when the call budget is exhausted. Valid abstention uses `StopSearch`: replay records a deliberate stop, not a GPU trial or a policy error.

All adapter tests use a local stub client. The provider-check function is replaced only inside tests; real adapter construction requires the actual matching saved check. The current tests establish schema wiring, evidence removal, bounded calls, and provenance logging—not provider reliability or useful search choices.
