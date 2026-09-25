# Sera specialist routing and outcome memory

Date: 2026-09-24  
Scope: proposed contract for the experimental `sera.kernel_search` and `sera.kernel_tools` path. This document does not change product code.

## Recommendation

Replace one general-purpose proposer with a deterministic top-k dispatcher over a fixed registry of hard-described kernel specialists. Start with `k=3`; run those Codex CLI calls in parallel with ChatGPT login, then use one deterministic queueing rule to choose at most one new source for evaluator time in each search round. Specialists do not message each other. A proposal ranker may order candidates, but it cannot mark a source correct, promote it, or make it the returned winner. The signed Hills evaluator and `kernel_search` gates keep those decisions.

Do not use an LLM to route roles. A router call adds latency and cost before useful work, and a model can invent capability matches. A small Python scorer over reviewed role descriptions, task tags, hardware facts, and verified run memory is easier to inspect and bound. This is the JEV-like delegator: it picks the relevant hard-described agents and stops there.

## Existing boundary

`sera.kernel_search.optimize_kernel` accepts one `propose(history)` callback, evaluates the baseline, evaluates a proposed source with repeated measurements and an unchanged control, and only returns a source after a passing final evaluation. `sera.kernel_tools.CodexKernelProposer` makes one `codex exec` call, requires ChatGPT login, and uses a separate per-call timeout. These are the right integration points. Add a router/proposer that implements the same `.propose(history, timeout=...)` contract; leave evaluator behavior in `kernel_search`.

The existing default search cap is eight candidate proposals and three repeats. Keep those defaults. The present candidate loop checks the outer deadline before and after proposal work, but one specialist call must receive the remaining time and enforce it itself, as the current Codex proposer does. The report must record selected roles, call outcomes, and memory decisions alongside each proposed source.

## Fixed registry

Ship a reviewed registry in Python data, not prompts discovered at runtime. Each role has an immutable ID, plain description, applicable task tags, required capability tags, allowed source scope, and proposal category. Initial kernel roles:

| Role ID | Hard description | Primary task tags |
| --- | --- | --- |
| `abi_correctness` | Preserve the kernel ABI, full output semantics, alias rules, and all supported dimensions. | `abi`, `tails`, `correctness` |
| `register_tiling` | Choose register tiles and accumulation layout to reuse loaded values. | `gemm`, `registers`, `reuse` |
| `cache_blocking` | Choose loop order and cache tiles for the measured matrix sizes. | `gemm`, `cache`, `reuse` |
| `simd_vectorization` | Improve vector loads, stores, and arithmetic supported by the target compiler and CPU. | `simd`, `compiler`, `dtype` |
| `packing_layout` | Evaluate packing or transposition only when its cost remains inside the measured call. | `gemm`, `packing`, `memory` |
| `prefetch_tlb` | Reduce measured cache-miss or translation pressure without unsafe assumptions. | `cache`, `tlb`, `memory` |
| `compiler_codegen` | Inspect public compiler flags and source patterns that affect generated instructions. | `compiler`, `codegen`, `simd` |
| `instruction_schedule` | Reduce dependency chains and improve independent work within one thread. | `registers`, `codegen`, `latency` |
| `alignment_tails` | Handle alignment and odd dimensions while keeping the main path efficient. | `abi`, `tails`, `alignment` |
| `measurement_review` | Use only saved evaluator reports to identify drift, noise, or a useful next test. | `measurement`, `history` |
| `memory_traffic` | Reduce unnecessary reads and writes for the supplied layout and data type. | `memory`, `dtype`, `gemm` |
| `baseline_reviewer` | Check a proposed source against the baseline, ABI, and already tested source hashes. | `history`, `abi`, `correctness` |

Descriptions must say what the agent owns and what it may not claim. These are roles, not extra general agents. A role must not propose threading when the workload fixes one thread, a new dependency when the contract forbids it, or any change to the evaluator.

## Routing contract

Build a versioned task profile from caller-owned workload facts and evaluator identity: operation, dimensions, dtype, layout, thread count, target metric, compiler and flags, CPU features, ABI tags, and constraints. Do not infer a hardware feature from an agent's claim. Normalize it to a stable `workload_signature` hash.

For each role, compute an integer relevance score from its declared task-tag overlap, required capability coverage, and verified memory. A simple first version is:

```text
score(role) = 4 * matching_objective_tags
            + 2 * matching_workload_tags
            + 1 * verified_capability_matches
            + min(2, verified_successes_for_signature)
            - 4 * active_exact_failure_suppressions
```

Only registry-declared tags and caller/evaluator facts count. Model-authored role names, capability claims, predicted scores, and unsupported assumptions do not count. Sort by descending score, then role ID for a stable tie break. Exclude roles with score <= 0 and roles whose exact suppression key is active. Select the first `min(k, eligible_count)` roles. If none remain, return `None` and record `no-relevant-specialist`.

The role descriptions define suitable hypotheses; routing does not assert that a hypothesis is valid. Each specialist gets the same immutable measured history and public source artifacts, plus only its own role description, applicable registry facts, workload profile, and role-scoped outcome memory. It receives no peer proposals or private evaluator inputs. A reply schema allows only: `role_id`, `name`, `hypothesis`, `prediction`, `refutation_condition`, and a complete `source` (or an explicit `stop`). It has no metric or pass/fail fields.

Validate `role_id` against the dispatched role; validate source size and non-empty text; hash source; deduplicate by hash; and keep every valid response for the queue. A response that fails schema, times out, or duplicates source consumes its call budget and is recorded. It cannot update performance memory. No agent may edit the shared worktree or evaluator.

## Bounded scheduling and cost

Use these controls in the router constructor and result report:

```text
max_active_specialists = k, default 3, hard maximum 3
max_candidates = existing kernel_search cap, default 8
max_calls = k * max_candidates, hard maximum 24
per_call_timeout = min(configured call cap, remaining outer deadline)
max_source_bytes = existing 256 KiB candidate limit
max_saved_history_bytes = explicit bounded prompt limit
```

Launch no more than `k` CLI processes at once. A search iteration requests up to the available call slots, waits for those bounded calls, then lets a deterministic selector queue at most one unseen, schema-valid source for evaluation. The selector orders by routing rank and role ID; it cannot use an unevaluated performance prediction. Later sources remain queued for later candidate slots. The total proposed-source count stays within `max_candidates`; each role's call count and all unused/failed calls are saved.

The Codex cost bound is **calls, concurrency, prompt bytes, output bytes, and elapsed seconds**. Keep `--ignore-user-config`, forced ChatGPT login, and the environment allowlist from `CodexKernelProposer`; make no API-key or hosted-client fallback. ChatGPT plan usage has no stable per-call dollar price exposed to this program, so do not claim a hard USD ceiling. A hard overall deadline and these call limits provide the enforceable time and usage bounds.

With `C=max_candidates`, `R=repeats`, and `k<=3`, at most `C*k` Codex CLI calls run. Evaluator calls remain at most `R*(1+2*C)+1`: `R` baseline measurements, for each candidate at most `R` candidate and `R` unchanged-control measurements, and one final holdout. If every evaluation call has timeout at most `E` and each agent call timeout at most `A`, evaluator compute is bounded by that call count times `E`, agent wall time per batch is at most `A`, and total wall time is capped by `max_seconds` plus bounded cleanup/report writes. Enforce one deadline around the full batch; do not let a timed-out subprocess group remain alive.

There is no all-to-all review. Specialist communication is O(k) dispatches and O(k) results per round; memory lookup/update is O(number of roles + bounded memory rows). Role count can grow without increasing active calls or peer messages because the router scans the fixed registry and selects top-k.

## Outcome memory

Store versioned, append-only records under the search output directory. One record joins an `agent_call_id` and `role_id` to a `source_hash`, `workload_signature`, evaluator report IDs, and verified outcome. Never store an agent's asserted speedup as a measurement.

Allowed outcome fields are copied only after the evaluator report passes the existing signature and comparison-identity checks: correctness/pass status, metric name/value/direction, source hash, evaluator identity, and final-vs-validation split. Proposal quality and operational outcomes are separate: timeout/schema failure is a call failure; compiler failure or incorrect output is an evaluator failure; a correct but slower result is a measured performance regression. A source with multiple contributors is attributed only to the role that emitted that exact hash.

Update routing memory only from these joined records. Success contributes a capped success count for the exact workload signature and role, after correctness passed; performance success additionally requires the existing separated-range promotion rule. Invalid, missing, unsigned, mismatched, or final-failed reports contribute no success. A failure can suppress only the matching `(role_id, workload_signature, proposal_family, failure_class)` key for the rest of the current run. A duplicate source hash is always skipped within the run. Do not mark a whole role, CPU, compiler, or technique invalid from one failure. New evaluator identity or workload signature starts a separate memory partition. Memory summaries in prompts include record IDs and factual values, not free-form conclusions.

`proposal_family` must be a stable, small registry tag selected from the dispatched role's allowed categories (for example `cache_tile`, `vector_width`, `tail_path`). Unknown family is rejected. Failure-class values come from Sera (`timeout`, `compile`, `incorrect`, `identity_mismatch`, `measurement_invalid`, `performance_regression`), never from agent prose. Never reuse memory across a different evaluator identity or workload signature.

The in-run record is enough for the first implementation. Cross-run memory is opt-in and should be added only with an atomic, versioned store and strict evaluator/workload partitioning. Do not silently load arbitrary prior `result.json` files as trusted memory.

## Ranker and evaluator authority

If a model-based ranker is added later, it may order at most the legal proposal IDs and provide a reason. It receives no authority to change source, evidence, memory, scores, pass state, promotion, stopping thresholds, or final selection. Sera validates that it returns only dispatched IDs; invalid output falls back to the deterministic order. The current smallest design needs no ranker call: route by deterministic role score, then queue by role score and ID.

Only the evaluator can attest correctness and measurements. Only `kernel_search` can apply control separation, candidate promotion, holdout performance, and `winner_source`. Add invariant checks so neither router metadata nor any arbiter field is read by `_score`, the promotion block, or final-output logic.

## Acceptance tests for implementation

1. **Stable relevant top-k:** same task profile and memory return the same sorted role IDs; irrelevant and zero-score roles are omitted; ties use role ID.
2. **Bounded dispatch:** with a registry larger than 12 roles, no run launches more than `k=3` subprocesses at once; total calls never exceed `k * max_candidates`; each receives remaining deadline.
3. **No peer traffic:** every prompt includes shared measured history and one role description, and contains no other specialist proposal or peer message.
4. **ChatGPT-only:** each worker retains the current ignored-user-config, forced ChatGPT login, no API fallback, and credential-filtered environment behavior.
5. **Queue bound:** only one candidate source per search iteration reaches evaluation; invalid, duplicate, and stop replies never reach Hills; queued proposals still obey the candidate and deadline caps.
6. **Schema and authorship:** wrong role IDs, invented metrics, unknown proposal families, oversized sources, and malformed output are rejected and do not change memory.
7. **Authoritative memory:** a signed passing report updates only the source-emitting role and exact workload/evaluator partition; an agent prediction alone never records a gain.
8. **Failure isolation:** compiler, correctness, timeout, and regression outcomes suppress only the matching role/workload/family/failure key for the current run. A different workload or family can still route to that role.
9. **Evaluator authority:** a fast but incorrect candidate, a candidate with a forged router/arbiter pass field, and a candidate with a failed or slow final holdout never populate `winner_source`.
10. **Deadline cleanup:** when one worker reaches its timeout, its process group is terminated and other completed replies remain recorded; the router does not exceed the outer deadline by waiting on an unbounded worker.
11. **Reproducible report:** save registry version/hash, task profile/hash, routing scores, selected IDs, per-call status/duration, source hashes, memory record IDs, all evaluator report IDs, and stop reason. Replaying identical inputs yields the same role ranking and queue order.

Do not add benchmarks to establish this routing contract. First test deterministic selection, subprocess bounds, memory attribution, and unchanged evaluator authority with fakes. Then use equal search budgets to compare the routed proposer against the current single general proposer on fixed workloads before claiming a search-quality gain.
