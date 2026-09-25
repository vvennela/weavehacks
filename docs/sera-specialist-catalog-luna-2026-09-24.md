# Sera specialist catalog for CPU optimization

Date: 2026-09-24  
Scope: Sera's optimizer, CPU execution kernels, and a future engineer-facing model-optimization adapter. Frontend and marimo are excluded. This is a design catalog; it makes no product-code changes and reports no new benchmark results.

## Recommendation

Use a small catalog of bounded specialist roles. A specialist identifies a bottleneck, proposes one legal experiment, states a measurable prediction, and updates its own short evidence record only after a verified result. Specialists do not run trials, edit evaluator inputs, select winners, or change correctness gates, quality floors, objective, candidate limit, time limit, or resource policy. The evaluator and existing search policy remain authoritative.

The current `sera.swarm` is a read-only proposal and review process for the vLLM controls in `sera/techniques.py`. Its investigator names (`scheduling`, `memory_context`, `output_quality`) describe analysis focus, not CPU hardware roles. The current `sera/kernel_search` instead asks one proposer for a complete GEMM source replacement and compares verified reports. Do not make the CPU path inherit GPU roles or treat these two APIs as interchangeable. Add specialist routing behind a future optimizer adapter, after it supplies a workload contract and hardware capability profile.

## Minimal CPU roster

These twelve roles are distinct, but only roles with a matching workload signal and legal control surface should be active for a round. A specialist can abstain. "Allowed edits" below means the candidate artifact surface it may propose through the adapter; it does not authorize edits to Sera, the evaluator, tests, or the source of truth.

| ID | Focus and activation signal | Expected evidence | Candidate surface allowed | Inactive when |
| --- | --- | --- | --- | --- |
| `algorithm` | Operation count or algorithm choice dominates, e.g. dense GEMM with a fixed ABI | Complexity, dimensions, reference comparison, per-shape timing | Algorithm and loop structure within the declared operator contract | Operation is fixed or proposal changes mathematical semantics |
| `blocking_locality` | Working set exceeds a relevant cache level or repeated data movement is visible | Cache sizes from target profile, tile working set, cache-miss counters when available, timings by shape | Loop order, tile sizes, bounded packing inside timed contract | No evidence of locality pressure or packing is outside permitted ABI |
| `simd_vector` | Compiler output or counters show scalar work and the CPU exposes a usable vector ISA | CPU model/ISA flags, compiler version/flags, vectorization report or assembly, tail correctness | Portable intrinsics or compiler-friendly vector loops for detected ISA | ISA is absent/unknown, or shape and ABI cannot support safe vector tails |
| `threading_numa` | Large workload leaves cores idle or memory placement/remote access is measurable | Core/thread count, affinity, NUMA topology, scaling curve, thread settings | Worker partitioning, affinity hints, parallel loop policy within declared limits | Small workload, single-thread contract, unknown topology, or control has no threading surface |
| `memory_bandwidth` | Arithmetic intensity and measured bandwidth indicate data movement limits | Bytes moved, arithmetic intensity, bandwidth counters or controlled size scaling | Reuse, streaming, write policy, and prefetch changes supported by the target | Compute-bound evidence or counters unavailable for a claim that depends on them |
| `compiler_codegen` | Compiler/runtime build or generated code is an identified source of cost | Exact compiler/build identity, flags, optimization remarks, disassembly or build logs | Candidate source constructs and only caller-authorized build options | Compiler identity is not pinned or compiler flags are frozen |
| `shape_dispatch` | Real model/operator workload has materially different shape regimes | Shape histogram, per-shape correctness and latency, dispatch overhead | Small shape-based kernel variants with a declared fallback | Shape mix is unknown, dispatch violates ABI, or any path lacks validation |
| `numerical_semantics` | Optimization changes reduction order, precision, rounding, or exceptional-value behavior | Reference/tolerance, dtype, accumulation mode, edge and nonfinite test results | Numerically equivalent reduction/accumulation choices within the fixed contract | No independent reference, or proposal needs a changed tolerance/quality floor |
| `abi_build_integration` | Drop-in use needs a stable operator ABI, packaging, dispatch, or platform build support | ABI, alignment/alias rules, build matrix, supported OS/architecture, artifact identity | Adapter-owned wrapper/build metadata and candidate-compatible dispatch glue | No public adapter contract exists; the specialist cannot alter optimizer policy |
| `operator_fusion` | A real model graph shows launch/intermediate-memory cost across adjacent operators | Graph/operator trace, tensor sizes, launch count, end-to-end and operator timings | Fusing eligible adjacent operators behind a model adapter | Only a standalone kernel is in scope or model graph evidence is absent |
| `model_memory_precision` | Model capacity or bandwidth is constrained by weights or activation/cache footprint | Model/checkpoint identity, dtype, memory breakdown, exact hardware support, quality tests | Adapter-supported quantization or storage format for named tensors | No compatible kernels/checkpoint or quality gate is missing; CPU format unsupported |
| `inference_workload_runtime` | End-to-end model latency/throughput changes with queueing, batch, sequence, or cache behavior | Declared request/shape mix, queue and per-request latency, memory, cache state | CPU runtime batch/thread/pinning/cache controls exposed by adapter | Standalone operator task, workload is not representative, or controls are unsupported |

This roster includes general CPU concerns and future model-level areas without claiming they are implemented. For the existing standalone GEMM task, likely eligible roles are `algorithm`, `blocking_locality`, `simd_vector`, `compiler_codegen`, `shape_dispatch`, and `numerical_semantics`; `threading_numa` is inactive under the current single-threaded evaluation contract, while all model-level roles are inactive. Activation still requires relevant evidence and an allowed candidate surface.

## Hardware profiles and applicability

Every run needs a frozen profile before routing: architecture and CPU model, usable ISA features, core and thread count, cache sizes if known, NUMA layout if present, memory type/capacity, OS, compiler and linker versions, flags, and thread/affinity controls. Identify the exact machine where possible. A family label such as "ARM" or "x86" is not sufficient to authorize ISA-specific code.

Route `simd_vector` and any architecture-specific technique only when the profile proves that the target supports it. `-march=native` is machine-local and does not establish portability. A candidate must either target the named profile or include a validated fallback and capability dispatch. Never generalize an Apple Silicon result to ARM servers, or a single x86 result to all x86 CPUs. Treat different CPUs, OS/compiler combinations, and relevant thread settings as separate comparison identities. A change to that identity requires a new baseline; do not compare its score with old runs.

The existing CPU validator fixes one-thread environment variables and compiles with `-O3 -march=native -ffast-math`. This makes threading inactive for that contract, and means numerical behavior must be checked against the stated tolerance. The existing public correctness sizes are useful but do not certify every model operator, alias rule, dtype, or deployment ABI. Keep the specialist roster broader than this one GEMM evaluation, while requiring each adapter to state its exact supported contract.

GPU-only techniques such as CUDA graphs, KV-cache formats, tensor parallelism, and GPU allocation are not CPU specialist roles. Do not activate `sera/techniques.py`'s GPU controls in a CPU run. A heterogeneous host may support separate CPU and GPU profiles; route by the device that executes the target operation, not by the host's installed devices.

## Reflexive update rules

Reflexive means the specialist's future proposal can use compact lessons from prior measured outcomes. It does not mean an agent edits its own instructions or Sera's policy after a conversation.

1. A specialist may add or revise one bounded memory record only after the evaluator report passes signature/identity verification and the trial record binds the report to source hash, workload hash, hardware profile, build identity, and objective. Correctness failures and timeouts are valid negative outcomes when their verified diagnosis is recorded. Unverified claims, agent explanations, and unmeasured predictions never become learned facts.
2. Record the pre-run hypothesis and prediction before execution. Afterward append the observed result, including no gain, quality failure, build failure, noise, or missing telemetry. Do not rewrite the prediction to match the outcome.
3. Separate observation from cause. For example, "this tile size scored lower on this machine in three repeats" is an observation; "L2 capacity caused the loss" remains uncertain unless cache evidence supports it.
4. Generalize only within the same workload family, hardware/build identity, and candidate contract. An out-of-profile result can inform a new hypothesis but cannot raise confidence for a different profile.
5. Bounded memory per specialist: maximum 32 entries, each with one hypothesis/result pair, and maximum 4 KiB serialized per entry. Keep the latest relevant entries and a small aggregate by exact profile/workload key; link to evidence by content hash rather than copying raw traces or prompts. Expire or mark stale entries when the profile, workload, evaluator, compiler, or contract changes.
6. Store confidence as `low`, `medium`, or `high`, plus support and contradiction counts. Start `low`. Use `medium` only after at least three independent verified outcomes support the same scoped claim. Use `high` only after at least five such outcomes across two clean runs, with unchanged controls showing gains outside observed variation and no contradictory result. A contradiction lowers confidence and is preserved. These labels guide proposal ranking only; they never gate trials or acceptance.
7. A failed or inconclusive measurement must not create a positive performance claim. If controls drift, identity differs, repeats are missing, or uncertainty overlaps the claimed gain, record the outcome as inconclusive and do not update a gain estimate.
8. Keep learned records append-only in run evidence. Creating a compacted memory is a deterministic reduction of verified records with source hashes and schema version, not an agent-authored rewrite of past evidence.

These rules do not modify the task's fixed objective, quality criteria, tolerance, deployment constraints, candidate space, maximum trials, elapsed-time limit, CPU/memory cap, or final holdout requirement. Only the user or calling optimizer configuration can set those values; specialist output cannot widen them.

## Smallest next-step schema

Keep routing separate from `Proposal`, and do not extend `RuntimeConfig` with speculative specialist settings. The smallest useful record is:

```json
{
  "schema_version": "sera-specialist-v1",
  "specialist_id": "blocking_locality",
  "profile_key": "sha256:...",
  "workload_key": "sha256:...",
  "status": "active",
  "activation_evidence": ["working_set_bytes", "shape_histogram_hash"],
  "allowed_artifact_paths": ["src/kernel.c"],
  "memory_refs": ["sha256:..."],
  "proposal": {
    "hypothesis": "...",
    "prediction": {"metric": "gflops", "direction": "increase", "minimum_change": 0.05},
    "falsification": "...",
    "candidate_hash": "sha256:..."
  },
  "outcome_ref": "sha256:..."
}
```

For abstention or ineligibility, retain `specialist_id`, `status`, and a short reason; do not create an agent call. The memory record can be:

```json
{
  "schema_version": "sera-specialist-memory-v1",
  "specialist_id": "blocking_locality",
  "profile_key": "sha256:...",
  "workload_key": "sha256:...",
  "claim": "...",
  "support_refs": ["sha256:..."],
  "contradiction_refs": [],
  "confidence": "low",
  "support_count": 1,
  "contradiction_count": 0,
  "stale_after": {"profile_key": "sha256:...", "workload_key": "sha256:..."}
}
```

`status` should use `active`, `inactive`, `abstained`, or `rejected`, matching the distinction already used by specialist participation. `active` means eligible for this legal candidate pool, not that the specialist executed or improved anything. A future code step should implement one router and one memory reducer, then connect them to the CPU adapter. Do not start by multiplying investigators or adding twelve concurrent agent calls.

## Required evidence and candidate restrictions

Before proposing, a specialist receives only the public task contract, frozen baseline identity, legal candidate/artifact surface, applicable measured history, and relevant bounded memory references. It must cite exact evidence keys, propose one testable change, state a prediction and a result that would refute it, or abstain. It cannot select an unsupported candidate, change the workload, inspect private evaluator inputs, or infer that an unmeasured technique is runnable.

Candidate source must remain within adapter-owned paths. Sera keeps control of hashes, candidate directories, compilation, correctness checks, timing order, unchanged controls, budgets, quality checks, final evaluation, and promotion. The user-facing drop-in model adapter owns model-specific graph and runtime metadata. It supplies a stable operator/runtime interface and independent correctness evaluator; specialists do not create those contracts during a run.

## Test obligations for the next code step

The next implementation should add focused tests for these system outcomes:

- A CPU-only profile activates only matching CPU roles; a GPU-only technique is recorded inactive and gets no agent call.
- Missing ISA, compiler, workload, or legal artifact capability makes the related specialist inactive with a reason.
- Active specialists can abstain; an agent error is `rejected`, not an invented inactive result.
- A proposal cannot write outside adapter-owned artifacts or alter candidate budget, objective, correctness contract, quality floor, or acceptance policy.
- A memory update rejects unsigned, mismatched, incomplete, or identity-drifted result evidence.
- Repeated verified outcomes update only the matching profile/workload record; contradictory and inconclusive outcomes remain visible and confidence does not rise.
- Memory limits, entry expiry, deterministic compaction, and stale-profile invalidation hold at their documented bounds.
- Threading stays inactive when the evaluator fixes one thread; architecture-specific proposals require an exact capability match and a validated fallback when portability is claimed.

Do not add performance claims or run benchmarks as part of the routing/schema implementation. Existing tests for `sera/swarm`, `sera/techniques`, `sera/search_policy`, `sera/investigation`, and `sera/kernel_search` describe current separate contracts; keep them passing when product code later changes.
