# Two-model placement readiness

This is an implementation plan, not evidence that two-model placement works.
It follows product phase two and specification sections 14, 17, and 23.3.

## Current state

The approved pair is `Qwen/Qwen3-0.6B` and `zai-org/glm-4-9b-chat-hf`, using the pinned revisions already in the library.

Two separate gaps remain:

1. **Task quality:** no tested configuration of the pair passes the current eight-task, strict JSON contract at the fixed 0.99 quality floor. The original isolated results remain preserved: Qwen BF16 passed 2/8, Qwen FP8 weights passed 1/8, GLM BF16 passed 0/8, and GLM FP8 weights passed 0/8. These are task failures, not proof of broken quantization kernels. See [the original prerequisite record](../evidence/placement-prerequisites-v1/README.md).
2. **Joint execution:** the current runtime requires an idle GPU. It rejects a second service once GPU use exceeds 128 MiB. Joint ownership, concurrent measurement, pair selection, and pair rollback are not implemented.

A new native structured-output profile is being tested. Qwen completed at 7/8: all answers were valid JSON, but the filtering answer remained wrong. GLM's isolated pilot is running. A passing pair at the fixed 0.99 floor is not established. The new profile does not replace or regrade the original failures. See [Qwen's preserved result](../evidence/qwen-structured-quality-v3/README.md).

Even if both isolated quality pilots pass, phase two remains unfinished. They do not establish shared-GPU fit, latency, interference, or two usable returned runners.

## Bounded implementation order

### 1. Establish eligible isolated configurations

Keep the specified pair, eight tasks, strict evaluator, and 0.99 floor. Treat native structured decoding as a separate, versioned workload profile. Promote it only after an explicit decision. Carry the same decoding settings into every later isolated and joint measurement.

Start with BF16 weights and BF16 KV. Add only a compatible quantization path needed for the placement comparison. GLM FP8 weights have runtime compatibility evidence, but still need passing task evidence for the selected profile. GLM FP8 KV and combined FP8 weights/KV remain unverified. Do not add a general GLM search or a model-universe benchmark.

Stop before joint execution if either model has no quality-valid configuration.

### 2. Calibrate and freeze the memory profile

Use a separately approved, bounded set of isolated calibration runs to choose the declared smaller-card budget and each service's allocation. Account for weights, KV cache, workspace, process overhead, and startup peaks. Save calibration cost and results separately from the final comparison.

Let `P` be measured physical GPU bytes, `B` the declared smaller-card budget, and `b_i` each service's byte allocation:

- Set each service's `gpu_memory_utilization` to `b_i / P`.
- Require `sum(b_i) <= 0.90 * B`, keeping the specification's 10% shared reserve.
- Enforce physical headroom as well as the declared budget.
- Leave `kv_cache_memory_bytes` unset.
- Freeze `B`, allocations, workloads, and latency limits before final measurement.

No allocations are proposed in this plan. Earlier isolated peaks near 88,300 MiB reflect a 0.9 memory fraction and GPU reservation. They do not establish minimum operating memory or a credible smaller-card budget.

Use the same frozen limits for unquantized and quantized configurations, both alone and together. A configuration rejected by the fit check remains a recorded rejection; it has no measured latency. Do not force an unsafe load to manufacture a comparison.

### 3. Add a strict placement plan and shared runtime owner

Touch `sera/config.py` and `sera/memory.py` for a validated plan containing exactly two pinned configurations, one GPU assignment, per-service allocations, per-model constraints, and the declared total budget.

Touch `sera/runtime.py` to give one owner control of both service process groups. Permit only registered peer services; continue rejecting unrelated GPU use. Record per-service memory and total device memory separately. Device-wide memory samples cannot identify each service's use.

Do not implement sharing by simply disabling the idle-GPU check. Current startup checks, memory monitoring, and cleanup also assume exclusive ownership. Cleanup must attempt to stop both services even when one close operation fails, then verify that all owned resources were released.

### 4. Run one bounded joint comparison

Add a small placement controller, such as `sera/placement.py`, and joint measurement support in `sera/measurement.py`.

Select only configurations backed by passing isolated records. Give the placement agent explicit legal plans, evidence, and a trial budget. It must state the proposed pair, assignment, allocations, and expected contention. Deterministic code validates the choice and gates the results. The current frontier response does not directly describe a two-model plan; placement needs a defined and checked selection contract. Keep that work separate from the single-model provider release.

Start the services under one owner. Start both load generators together and synchronize each declared load phase. Each model receives the same workload it received alone. Save timestamps and overlap coverage; do not assume the services experienced the same interference throughout unequal measurement windows.

Record isolated-versus-shared changes without claiming an unsupported cause. Feed failed joint outcomes and prediction reviews back into the decision history. Do not exceed the approved placement budget or silently start additional calibration.

### 5. Return the pair or report failure explicitly

Extend the result and readable report to include both isolated references, the selected plan, joint measurements, individual gates, total memory, rejected plans, prediction review, and cleanup.

Return two live runners only after both models pass. On failure, stop both joint services and record `no-safe-placement` or `not-attempted` with the reason. The single-model fallback is an explicit one-model call that restores a working isolated configuration. Never silently drop one model from a two-model request.

## Minimum acceptance checks

- Both selected configurations pass their own isolated task requirements under the chosen profile.
- The plan uses approved settings, pinned revisions, frozen memory limits, and the declared reserve. Invalid plans start no GPU service.
- Both load generators run concurrently, with saved overlap evidence and unchanged per-model workloads.
- Each model independently passes the 0.99 task-quality floor, its declared latency limit, and zero-error requirements.
- Observed memory respects the declared limits and physical capacity. A runtime memory fraction alone is not proof of compliance.
- Both returned runners answer a fresh request after the controller returns.
- Startup, measurement, quality, memory, or cleanup failure cannot produce a passing pair. Both services are stopped on failure, and the record is retained.
- The report contains real measurements and marks unavailable values as unavailable. Isolated quality tests alone never count as completed phase two.

Claim that quantization enabled placement only when the unquantized pair fails and the quantized pair passes under the same limits and workloads. State whether the unquantized failure was estimated or measured. If the effect is absent, report it and use the single-model fallback.

Show this disclosure in the notebook and placement slide:

> Memory budget constrained to represent a smaller card; execution uses an RTX Pro 6000 with 96 GB.

This represents memory capacity, not a smaller card's compute speed or bandwidth. Also show measured physical capacity, declared budget, service fractions, and memory peaks.

## Decisions still required

1. **Profile promotion:** after reviewing the new isolated results, may the structured-output profile become the placement workload? Keep the original eight tasks and 0.99 floor; preserve all old results.
2. **Calibration scope:** approve the calibration trial budget and exact precision paths. Calibration uses GPU time and is separate from the final joint comparison.
3. **Frozen memory limits:** choose the smaller-card budget and service allocations from calibration, then approve them before final measurement. This plan supplies no guessed values.
4. **Latency contract:** declare each model's maximum joint p95 latency or an explicit permitted slowdown relative to its matching isolated result. Do not choose thresholds after seeing the joint result.
5. **Joint execution:** approve the bounded comparison profile and trial count before launching it.

Until these gates are met, the working single-model deliverable remains the release fallback. No shared-GPU benefit or completed phase-two claim is established.
