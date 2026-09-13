# Automatic placement on one GPU

This is an implemented, offline-tested path, not a passing live placement claim.
It adds agent selection and measured stopping to the shared-GPU executor. It does
not change the saved demo, the eight questions, or the quality floor.

## Pipeline

1. Freeze legal plans, workloads, byte budgets, and each model's quality/latency
   requirements. The approved rehearsal uses the specified Qwen3-0.6B/GLM-4-9B
   pair, a 0.99 floor, zero errors, and at most 10% joint p95 slowdown.
2. Call `measure_placement_references` for each plan. Both models run alone under
   their proposed allocations. A failure stops that plan before joint startup.
3. Call `optimize_placement` with plans and their saved references. It verifies the
   exact plan/workload/configuration/GPU/runtime identities, token IDs, request
   counts, timing windows, cleanup, and memory. It recomputes quality and p95 from
   saved outputs, rather than trusting a recorded pass flag. Invalid references
   are rejected before the agent sees a legal plan menu.
4. The certified provider receives measured isolated evidence, legal plan IDs,
   the objective, remaining budget, incumbent, and previous joint outcomes. The
   existing typed arbiter returns one plan ID or abstains. It cannot change a
   service allocation, quality floor, latency limit, or runtime setting.
5. Deterministic code tests the chosen pair concurrently and independently gates
   each model. Its next request includes failed quality outputs, memory evidence,
   and objective measurements. It never retests an already attempted plan during
   the search.
6. Stop under the specification's plateau rule, explicit budget, no remaining
   legal plan, agent abstention, invalid response, cancellation, or runtime safety
   failure. Return two usable runners only after the final pair passes again.

The memory budget represents a smaller card. This is not multi-GPU execution and
does not reproduce a smaller card's speed or bandwidth. A passing pair alone does
not prove quantization enabled placement; the unchanged-budget unquantized
comparison is still required for that claim.

## Objectives and stopping

- Default latency objective: lowest worst-service p95, then lower device memory.
- Memory objective: lower sampled device peak, with both task and latency gates
  still mandatory.
- Throughput objective: both services' output tokens divided by the sum of each
  shared load window's duration. Warmup and startup are not counted as throughput.
- A qualifying improvement uses the existing `Objective` threshold (5% by
  default). A round without qualifying progress starts a confirmation check. A
  second such round stops; qualifying progress resets the check. The best valid
  measured pair is retained even when its improvement is below 5%.
- Normal runs have no fixed total trial cap. The supplied plan menu is finite;
  exhausting it can stop before a confirmation. `Budget` adds an explicit cap.
- Failed joint attempts count. If an older winner must be returned, restoration
  is one additional, separately reported joint validation, not a hidden search
  trial. A failed restoration cannot return the old passing report as a runner.

The plan menu is supplied by the caller from eligible phase-one configurations.
This implementation does not invent new allocations, run a broad GLM search, or
calibrate memory limits during the final comparison.

## Python entry points

```python
from sera import Objective, optimize_placement

# Keys in both mappings are plan.plan_hash. Reference values are result.json paths
# from measure_placement_references; estimates contain the five byte components
# required by PlacementMemoryEstimate for each model.
with optimize_placement(
    plans=frozen_plans,
    workloads=per_model_workloads,
    memory_estimates=estimates_by_plan_hash,
    isolated_references=references_by_plan_hash,
    agent=checked_agent,
    provider_check=provider_certificate,
    objective=Objective(priority="memory"),
    output_dir="placement-search-001",
    weave_project="your-team/your-project",
) as result:
    if result.models:
        for model in result.models:
            print(model.generate("A representative task").text)
    else:
        print(result.report["stop_reason"])
```

The example explicitly prioritizes memory capacity. Omitting `objective` keeps
the specification's latency default. The function does not choose a provider or
API key. It uses the supplied agent and matching existing provider certificate.

References are copied and hash-bound in the search directory before selection.
Later edits to the source files cannot change an approved plan's evidence.
Hashes identify local artifacts, not who produced them: supply only measurements
from a trusted execution environment.

## Weave

Optional `weave_project` creates one `sera_optimize_placement` root. It contains
typed arbiter choices, available measured evidence, and both models' saved joint
requests and quality gates across iterations. Each trial and restoration has a
unique trial ID, including when a model's configuration stays unchanged. Raw
provider responses and provider-returned reasoning use the existing trace adapter.
No hidden reasoning is invented or requested.

Reused isolated measurements keep their source file hash and original Weave URL;
they are not mislabeled as new measurements in this root. Later caller requests
are outside the optimization root. `close()` records a linked cleanup event.

The existing provider certificate proves the reused response schema's formatting,
not placement reasoning quality. Actual plan IDs are checked locally on every
response. Trace or flush failures stay visible without rewriting measured task
scores. Inaccessible runners are closed if the trace wrapper cannot return them.

## Executable rehearsal

Run from the repository root. The manifest contains no guessed allocations.

```sh
python -m experiments.run_placement --manifest placement-manifest.json --phase check
python -m experiments.run_placement --manifest placement-manifest.json --phase references --output-dir placement-references-001
python -m experiments.run_placement --manifest placement-manifest.json --phase search --objective memory --output-dir placement-search-001
```

The manifest's schema is `sera-placement-rehearsal-v1`. It contains:

- `plans`: serialized `PlacementPlan` objects with the approved 0.10 slowdown
  fraction, unchanged 0.99 floor, and zero errors.
- `memory_estimates`: plan-hash to per-model five-component byte estimates.
- `concurrency`: the approved fixed load levels, such as `[1, 2, 4, 8]`.
- `isolated_references`: plan-hash to saved reference `result.json` path, required
  for `search`. The reference stage emits an index of these paths.
- `provider_check`: existing matching provider certificate path for `search`.
- `weave_project`: optional explicit trace project matching the agent project.

Relative paths resolve from the manifest directory. The search stage uses the
existing `SERA_AGENT_PROVIDER`, `SERA_AGENT_MODEL`, `SERA_PROJECT`, and relay/key
environment setup. Keys are never printed or stored in the manifest.

The CLI uses the unchanged eight-task strict JSON profile and hashes its dataset.
It does not silently adopt new structured decoding, thinking, output length, or
system prompts. An approved different decoding profile must be implemented and
hashed before it can become the live reference. `check` makes no GPU, provider,
or Weave call; success means the manifest is valid, not that either model passes.

The live search command also tests one post-return request per runner, grades it,
closes both services, and saves `rehearsal_passed`. This probe is the first unchanged
task, not a claim about unseen questions. A failed task or cleanup exits nonzero.

## Live blockers

The existing Qwen structured result is 7/8 and still fails the 0.99 requirement.
Nothing here relaxes or hides it. A quality-valid configuration and frozen
calibration-backed service allocations are required before a passing joint run
can be demonstrated. The approved 10% relative latency contract is now implemented;
its numeric ceilings are derived from isolated results before joint startup.
