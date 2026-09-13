# Vishnu: Backend Work

## Current checkpoint

Parallel agent-loop work is merged from three isolated worktrees. The controller now handles lifecycle errors, budgets, scoped proposal IDs, failure history, measured-frontier stopping, and explicit frozen candidate spaces. A plain-English report and a synthetic offline rehearsal are available. The integrated suite passes 271 tests and the wheel builds. The provider citation constraint is fixed locally; its new hosted check and a real multi-round GPU investigation have not run. No live search advantage is claimed.

The narrow Qwen72B deployment and interactive rehearsal passed. A live four-load FP8-reference batching comparison also passed quality and returned the unchanged reference because the alternative did not meet the improvement threshold. Load sweeps, deterministic selection, raw evidence, and the delegated saved-outcome benchmark harness are implemented; 221 tests pass.

An opt-in bounded investigation controller is now connected to the production runner and passes local tests: proposals, arbitration, measurement, gates, prediction review, history, and best-runner return. It has not run live. The approved schema expansion adds bounded batch-token, sequence, and context controls while preserving the existing live defaults. The new provider check reached 30/30 valid JSON responses, but four citation failures keep new agent-controlled runs blocked. Context-varying benchmark universes and the exact no-telemetry ablation still need contract decisions. Joint placement has not been implemented or executed: the specified Qwen0.6B/GLM pair failed isolated task requirements, so that path is blocked pending user direction. See plan.md and evidence/placement-prerequisites-v1/README.md. The work sections below describe the broader target, not a claim that all items are complete.

## Mission

Build the measured optimization system behind Sera's simple public interface.

Vishnu owns:

- Python package and public types
- Hugging Face model resolution
- vLLM lifecycle and SeraModel
- Load generation and measurements
- Deterministic reduction and validation
- Quality gates
- Minimal local ledger
- Agent search and orchestration
- Final result and model activation
- Joint placement
- Weave instrumentation
- Benchmark harness
- Tests and packaging

Vishnu does not own notebook layout, product language, charts, demo script, or submission text.

## Work rules

- Build one measured vertical slice before adding agents.
- Keep agents behind typed schemas.
- Keep validation, quality, budgets, pass, fail, and rollback deterministic.
- Deliver fixture data before live integration.
- Write a failing test before each behavior.
- Mark tasks TODO, DOING, BLOCKED, or DONE.
- Send public schema changes to Barrat before implementation.

## Explicit cuts

These items are not on the hackathon critical path:

- Private or gated Hugging Face models
- Resume after process interruption
- Database migrations and corruption recovery
- CPU, Apple, and AMD runtimes
- Kubernetes provisioning
- Multi-GPU trial execution
- Pipeline parallelism
- Full power and hardware-counter coverage
- More than two jointly placed models
- Production deployment

## V1 — Live environment smoke tests

Priority: P0

Status: TODO

Todo:

- Start a GPU-enabled Molab session.
- Record Python, CUDA, driver, PyTorch, vLLM, and GPU versions.
- Install vLLM in a clean uv environment.
- Serve Qwen/Qwen3-0.6B and run one request.
- Read the vLLM metrics endpoint.
- Stop the exact process and confirm memory release.
- Call W&B Inference with the user key.
- Write and open one Weave test trace.
- Lock the working dependency versions.

Result:

- Reproducible smoke-test script
- Locked environment versions
- Saved vLLM metrics sample
- Working W&B Inference call
- Working Weave trace

Win condition:

One clean Molab session proves all three external integrations: vLLM, W&B Inference, and Weave.

Depends on:

- GPU-enabled Molab access
- User-provided W&B API key

## V2 — Package scaffold and public contract

Priority: P0

Status: TODO

Todo:

- Create the installable sera package scaffold.
- Define ModelSpec, PromptSample, Constraints, Workload, Budget, progress events, SeraResult, SeraModel, Candidate, and TrialResult.
- Define optimize for one or two models.
- Define generate, close, and print_summary.
- Implement fixture construction and serialization.
- Add contract tests.

Result:

- Importable package
- Typed public API
- Versioned fixture
- Passing contract tests

Win condition:

Barrat's notebook imports the real package and renders the fixed fixture with no backend internals.

Depends on:

- Barrat B1

## V3 — Deterministic run state

Priority: P0

Status: TODO

Todo:

- Define baseline, proposal, validation, trial, gate, rollback, and completion states.
- Define legal state transitions.
- Emit progress events through one callback interface.
- Cover success, no-safe-improvement, cancellation, and system failure.
- Redact secrets from every event.

Result:

- Tested run-state machine
- Typed progress stream

Win condition:

Tests cover one successful run, one quality rejection, one runtime failure, and one no-safe-improvement result.

Depends on:

- Vishnu V2
- Barrat B3 golden events

## V4 — Demo model resolver

Priority: P0

Status: TODO

Todo:

- Resolve public Hugging Face model IDs to exact revision SHAs.
- Read architecture, heads, context length, data type, and license metadata.
- Reuse the Hugging Face cache.
- Reject missing and unsupported model repositories.
- Add tests with fixed Hub responses.

Result:

- Pinned ModelSpec records for Qwen and GLM
- Tested public-model resolver

Win condition:

Both demo model IDs resolve to immutable revisions and contain every field required by validation.

Depends on:

- Vishnu V2

## V5 — vLLM runner and SeraModel

Priority: P0

Status: TODO

Todo:

- Start vLLM on a selected GPU and loopback port.
- Wait for readiness with a timeout.
- Send normalized generation requests.
- Expose the service through SeraModel.
- Stop only the owned child process.
- Confirm GPU memory cleanup.
- Record startup, timeout, out-of-memory, crash, and cleanup outcomes.

Result:

- Working SeraModel
- Safe vLLM process lifecycle

Win condition:

An integration test starts Qwen, generates text, stops it, and starts it again with a second legal configuration.

Depends on:

- Vishnu V1
- Vishnu V2
- Vishnu V4

## V6 — Controlled load and minimum metrics

Priority: P0

Status: TODO

Todo:

- Normalize text and chat prompts.
- Run warm-up requests.
- Run the concurrency sweep at 1, 2, 4, and 8.
- Record p95 end-to-end latency.
- Record input and output token throughput.
- Record peak GPU memory.
- Record queue time, KV-cache use, and preemptions.
- Save raw samples for replay.

Result:

- Controlled load generator
- Minimum raw metric record

Win condition:

Three runs of one fixed configuration produce complete records and report their measurement variance.

Depends on:

- Vishnu V5
- Barrat B1 prompt corpus

## V7 — Reducer and validator

Priority: P0

Status: TODO

Todo:

- Reduce raw metrics into the agreed evidence fields.
- Calculate changes from baseline.
- Keep causal claims out of reduction.
- Define the small allowed setting space.
- Check vLLM, model, data-type, and quantization support.
- Reject tensor parallelism when only one GPU exists.
- Estimate model, KV-cache, runtime, and reserve memory.
- Hash and reject duplicate candidates.

Result:

- ReducedEvidence object
- Deterministic candidate validator
- Explainable rejection records

Win condition:

Saved samples always produce the same evidence. Fixed invalid, duplicate, oversized, and one-GPU parallel candidates are rejected without starting vLLM.

Depends on:

- Vishnu V4
- Vishnu V6

## V8 — Quality gate and rollback

Priority: P0

Status: TODO

Todo:

- Reject errors, empty output, corrupt output, and severe length collapse.
- Compare candidate outputs with baseline outputs.
- Call the versioned quick-mode judge.
- Accept a user evaluator in verified mode.
- Enforce the quality floor.
- Restore the last valid configuration after failure.

Result:

- Quick quality proxy
- Verified evaluator interface
- Tested rollback

Win condition:

A faster fixture candidate that fails quality is rejected, and the last valid runner becomes active.

Depends on:

- Vishnu V1
- Vishnu V2
- Vishnu V5
- Barrat B1 quality-check intent

## V9 — Minimal append-only ledger

Priority: P0

Status: TODO

Todo:

- Create the SQLite schema.
- Store run spec, environment, model revisions, proposals, validation, trials, metrics, quality, and final result.
- Use canonical configuration hashes.
- Write each completed trial in one transaction.
- Redact secrets.
- Exclude resume, migrations, and corruption recovery.

Result:

- Local source-of-truth ledger
- Deterministic trial history query

Win condition:

One baseline, one rejected candidate, and one executed candidate can be reconstructed from SQLite with no secret values.

Depends on:

- Vishnu V2
- Vishnu V3

## V10 — Measured vertical slice and final result

Priority: P0

Status: TODO

Todo:

- Run one model baseline.
- Run one fixed legal candidate.
- Apply validation and quality gates.
- Select the valid winner.
- Assemble the complete SeraResult.
- Implement result.print_summary() from Barrat's golden output.
- Keep the selected vLLM process alive behind SeraModel.
- Return the baseline runner when no improvement passes.
- Define ownership and cleanup for returned runners.

Result:

- One complete measured optimization without agents
- Usable returned SeraModel
- Complete SeraResult

Win condition:

One call runs baseline and candidate, returns the correct active runner, prints the approved summary, and closes every discarded process.

Depends on:

- Vishnu V3 through V9
- Barrat B3 golden summary

## V11 — Agent search and phase one

Priority: P0

Status: TODO

Todo:

- Connect the quantization, batching, parallelism, and arbiter roles to W&B Inference.
- Require typed proposals.
- Let a specialist mark its lever inactive.
- Rank candidates from reduced evidence and trial history.
- Enforce one-lever initial trials.
- Run at most two agent rounds for the demo.
- Reserve two candidate trials for phase two.
- Prevent duplicate trials.
- Feed failures and reverts into the next round.

Result:

- Complete evidence-driven phase-one loop
- Trial history showing changed selection

Win condition:

On one GPU, parallelism consumes no trial. In the prepared pressure scenario, measured failure or success changes the next selected candidate.

Depends on:

- Vishnu V1
- Vishnu V7 through V10

## V12 — Phase-one Weave instrumentation

Priority: P0

Status: TODO

Todo:

- Implement Barrat's trace contract.
- Trace baseline, reduction, specialists, arbiter, validation, trials, gates, and revised phase-one actions.
- Link trial IDs and configuration hashes to SQLite records.
- Log quality results with Weave.
- Return the trace URL in SeraResult.
- Check every logged field for secrets.
- Add instrumentation as each backend stage becomes available.

Result:

- Complete Weave trace
- Linked quality records

Win condition:

One trace matches the SQLite history and shows evidence causing a changed action with no secret values.

Depends on:

- Start: Vishnu V1 and Barrat B4
- Complete: Vishnu V9 and V11

## V13 — Frontier and joint placement

Priority: P0

Status: TODO

Todo:

- Calculate each model's valid frontier.
- Add the frontier-reader agent.
- Select one small valid configuration per model.
- Check combined memory with a reserve.
- Start two vLLM services on one GPU.
- Run both loads at the same time.
- Gate each model separately.
- Revert when either model fails.
- Feed measured contention into one revised decision.
- Trace joint placement, per-model gates, revert, and revision with the V12 instrumentation helpers.

Result:

- One complete phase-two trial
- Accepted joint placement or measured no-safe-placement result

Win condition:

Both models are tested together. Sera accepts the placement only when both pass and records the isolated-to-shared change for each model.

Depends on:

- Vishnu V10
- Vishnu V11
- Barrat B1 two-model scenario

## V14 — Grid, random, and ablation benchmark

Priority: P0

Status: TODO

Todo:

- Freeze the small legal candidate universe before results are known.
- Execute each candidate once to establish the oracle.
- Replay naive fixed-order grid search.
- Replay uniform random search with 20 recorded seeds.
- Replay Sera without telemetry or without history.
- Calculate trials-to-near-oracle and regret after each trial.
- Export stable chart data.

Result:

- Reproducible benchmark dataset
- Grid, random, and intelligence-ablation results

Win condition:

Under the same budget, Sera reaches a quality-valid result within five percent of the oracle before naive grid search, beats median random search, and beats one intelligence ablation.

Depends on:

- Vishnu V7 through V13
- Barrat B1 frozen candidate universe

## V15 — Clean package and release candidate

Priority: P0

Status: TODO

Todo:

- Lock runtime and development dependencies.
- Build the package.
- Run unit and contract tests.
- Run the one-model and two-model Molab acceptance paths.
- Install from the repository in a clean Molab session using Barrat's draft.
- Fix the installation path.
- Tag the tested release candidate.

Result:

- Installable Sera release candidate
- Passing tests
- Recorded clean-install run

Win condition:

A clean Molab session installs Sera, completes the documented quick-mode example, returns a usable SeraModel, and opens the linked Weave trace.

Depends on:

- Vishnu V1 through V14
- Barrat B7a

## Shared checkpoints

### C1 — Contract

Required:

- Barrat B1
- Vishnu V2

Pass condition:

The notebook and package use the same fixture, events, result fields, and names.

### C2 — Fixture product

Required:

- Barrat B2 through B4

Pass condition:

The user and judge experience works before GPU integration.

### C3 — Measured vertical slice

Required:

- Barrat B3
- Vishnu V1 through V10

Pass condition:

One model completes baseline, one fixed candidate, quality gate, final result assembly, final runner activation, and cleanup.

### C4 — Agent proof

Required:

- Barrat B5
- Vishnu V11
- Vishnu V12

Pass condition:

A measured result changes the next selected trial, and Weave shows the full decision.

### C5 — Demo proof

Required:

- Barrat B6 through B9
- Vishnu V13 through V15

Pass condition:

Joint placement, benchmark, clean install, live demo, and submission work from one release candidate.

## Cross-person contracts

| Contract | Barrat owns | Vishnu owns | Handoff |
| --- | --- | --- | --- |
| Public API | Shape and names | Types and behavior | B1 to V2 |
| Fixture | Golden content | Typed construction | V2 to B2 and B3 |
| Progress | Wording and layout | Events and order | B3 to V3, then V3 to B3 |
| Results | Information order and copy | Values, assembly, runner | B3 to V10, then V10 to B3 |
| Weave | Trace story and display names | Instrumentation and data | B4 to V12, then V12 to B5 |
| Benchmark | Candidate intent and charts | Fair harness and data | B1 to V14, then V14 to B6 |
| Installation | Written steps | Package and verification | B7a to V15, then V15 to B7b |

## Vishnu definition of done

A task is done only when:

- Its stated artifact exists.
- Its behavior has a system-relevant test.
- Named failure paths are covered.
- Secrets are redacted.
- Public data matches the shared fixture.
- Its win condition has been checked.
- Any cross-person dependency is complete.
