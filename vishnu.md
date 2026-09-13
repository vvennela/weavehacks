# Vishnu: Backend Work

## Mission

Build the measured optimization system behind Sera's simple public interface.

Vishnu owns:

- Python package and public types
- vLLM process lifecycle
- Hugging Face model resolution
- Load generation
- Metrics and reduction
- Deterministic validation
- Agent calls and proposal schemas
- Search and experiment control
- Quality gates
- Frontier and joint placement
- SQLite and Weave records
- Benchmark harness
- Tests and packaging

Vishnu does not own the notebook layout, product copy, demo script, or submission narrative.

## Working agreement

- Deliver a stable SeraResult fixture before the full backend works.
- Keep agents behind typed interfaces.
- Keep pass, fail, budget, and rollback decisions deterministic.
- Build one end-to-end path before adding more levers.
- Add each behavior through a failing system-relevant test.
- Mark each task TODO, DOING, BLOCKED, or DONE.
- Send schema changes to Barrat before implementation.

## Task order

Complete V1 through V5 first. They create the first real vertical slice.

## V1 — Molab and vLLM smoke test

Priority: P0

Status: TODO

Todo:

- Start a GPU-enabled Molab notebook.
- Record Python, CUDA, driver, PyTorch, vLLM, and GPU versions.
- Install vLLM in a clean uv-managed environment.
- Load Qwen/Qwen3-0.6B.
- Run one completion through the vLLM Python or local server API.
- Read the vLLM metrics endpoint.
- Stop the process and confirm GPU memory is released.
- Record the exact working dependency versions.

Result:

- Reproducible Molab smoke-test script
- Locked runtime versions
- A saved successful output and metrics sample

Win condition:

A clean Molab session installs the dependencies, serves Qwen, returns output, exposes metrics, and releases GPU memory after shutdown.

Depends on:

- GPU-enabled Molab access

Blocks:

- Vishnu V3
- Barrat B7

## V2 — Package skeleton and public contracts

Priority: P0

Status: TODO

Todo:

- Create the sera package.
- Define ModelSpec, PromptSample, Constraints, Workload, Budget, SeraResult, SeraModel, TrialResult, and Candidate.
- Define optimize for one or two models.
- Define normalized generate and close methods.
- Create the fixed SeraResult fixture agreed with Barrat.
- Add schema and serialization tests.

Result:

- Importable package
- Typed public API
- Versioned SeraResult fixture
- Passing contract tests

Win condition:

Barrat's notebook runs against the fixture using the same public types that the real optimizer returns.

Depends on:

- Barrat B1

Blocks:

- Barrat B2
- Vishnu V3
- Vishnu V5
- Vishnu V10

## V3 — Event and run-state model

Priority: P0

Status: TODO

Todo:

- Define run, phase, model, proposal, trial, gate, rollback, and completion events.
- Define success, no-safe-improvement, cancellation, and system-failure states.
- Add a callback or iterator for progress events.
- Ensure events contain no secrets.
- Add ordering and transition tests.

Result:

- Typed event stream
- Deterministic run-state machine

Win condition:

Every backend action produces one valid public state, and invalid state transitions fail before work starts.

Depends on:

- Vishnu V2
- Barrat B1

Blocks:

- Barrat B3
- Vishnu V10
- Vishnu V12

## V4 — Hugging Face model resolver

Priority: P0

Status: TODO

Todo:

- Accept public and authenticated model identifiers.
- Resolve each model to an exact revision SHA.
- Read architecture, attention heads, KV heads, context length, data type, and license metadata.
- Use HF_TOKEN without logging it.
- Reuse the local Hugging Face cache.
- Reject unsupported or incomplete model repositories.
- Add tests with mocked Hub responses.

Result:

- Model resolver
- Pinned ModelSpec records
- Safe authentication path

Win condition:

The same input resolves to an immutable model revision, and secrets never enter logs, SQLite, or Weave.

Depends on:

- Vishnu V2

Blocks:

- Vishnu V6
- Vishnu V8
- Vishnu V10

## V5 — vLLM process manager and SeraModel

Priority: P0

Status: TODO

Todo:

- Start vLLM on a selected GPU and loopback port.
- Use explicit, typed runtime settings.
- Wait for readiness with a timeout.
- Send generation requests.
- Expose the process through SeraModel.
- Stop only the owned child process.
- Confirm GPU memory cleanup.
- Record startup, timeout, out-of-memory, crash, and cleanup failures.

Result:

- Working SeraModel backed by vLLM
- Safe start, health, request, and stop lifecycle

Win condition:

One test starts Qwen, generates text, records its configuration, stops it, and starts it again with a different legal configuration.

Depends on:

- Vishnu V1
- Vishnu V2
- Vishnu V4

Blocks:

- Barrat checkpoint P-B
- Vishnu V6
- Vishnu V10
- Vishnu V12

## V6 — Load generator and raw metrics

Priority: P0

Status: TODO

Todo:

- Normalize string and chat prompts.
- Run the default concurrency sweep of 1, 2, 4, and 8.
- Separate warm-up requests from measured requests.
- Record end-to-end latency, time to first token, time per output token, and queue time.
- Record input and output throughput.
- Read vLLM request, queue, KV-cache, and preemption metrics.
- Read NVIDIA memory, compute, memory-controller, and power metrics.
- Mark unavailable metrics as unavailable.
- Save raw samples for deterministic replay.

Result:

- Repeatable controlled load generator
- Raw request, vLLM, and GPU metric record

Win condition:

Repeated baseline runs on the same configuration produce complete records and expose measurement variance instead of hiding it.

Depends on:

- Vishnu V5

Blocks:

- Vishnu V7
- Vishnu V10
- Barrat B4

## V7 — Deterministic metric reducer

Priority: P0

Status: TODO

Todo:

- Calculate p50, p95, and p99 latency values.
- Calculate token throughput.
- Calculate peak and mean resource use.
- Calculate preemptions per request and error rate.
- Calculate change and remaining margin against the baseline.
- Produce the fixed reduced-evidence schema.
- Keep causal language out of reducer output.
- Add tests with saved raw samples.

Result:

- ReducedEvidence object
- Tested metric calculations

Win condition:

The same raw samples always produce the same reduced evidence, including explicit unavailable values.

Depends on:

- Vishnu V6

Blocks:

- Barrat B4
- Vishnu V9
- Vishnu V10

## V8 — Candidate validator and VRAM estimator

Priority: P0

Status: TODO

Todo:

- Define the allowed candidate settings.
- Check model and vLLM support.
- Check data-type and quantization support.
- Check tensor-parallel device count and head divisibility.
- Estimate weights, KV cache, runtime workspace, and safety reserve.
- Validate joint gpu_memory_utilization totals.
- Hash and reject duplicate candidates.
- Reject invalid candidates without starting vLLM.
- Add boundary and property tests.

Result:

- Deterministic validator
- Explainable rejection records
- Tested VRAM estimator

Win condition:

Every known illegal or oversized configuration is rejected before GPU execution, and every rejection states the failed rule.

Depends on:

- Vishnu V1
- Vishnu V4

Blocks:

- Vishnu V10
- Vishnu V12
- Vishnu V14

## V9 — Agent client and specialist contracts

Priority: P0

Status: TODO

Todo:

- Connect to W&B Inference through its OpenAI-compatible API.
- Read WANDB_API_KEY from the environment.
- Make the agent model configurable.
- Implement quantization, batching, and parallelism specialist prompts.
- Require structured Proposal responses.
- Allow zero proposals when a lever is inactive.
- Validate agent responses and retry one malformed response.
- Record prompts and responses through Weave with secrets removed.
- Test with a fake OpenAI-compatible client.

Result:

- Agent client
- Three specialist implementations
- Validated proposal schema

Win condition:

Given fixed reduced evidence, each specialist returns valid proposals or an explicit inactive-lever result without executing code.

Depends on:

- Vishnu V2
- Vishnu V7
- Vishnu V8

Blocks:

- Vishnu V10
- Vishnu V13

## V10 — Arbiter and phase-one orchestrator

Priority: P0

Status: TODO

Todo:

- Implement the arbiter prompt and ranked-candidate response.
- Enforce one-lever initial trials.
- Allow combinations only after their parent changes pass alone.
- Reserve two candidate trials for phase two when two models are present.
- Select one exploration trial when the policy requires it.
- Prevent duplicate execution.
- Stop on budget, lack of frontier improvement, lack of legal proposals, or time limit.
- Feed every result back into the next round.
- Keep trials sequential on one GPU.

Result:

- Complete phase-one optimization loop
- Ledger history showing changed decisions across rounds

Win condition:

For one model, Sera runs a baseline, chooses a valid candidate from evidence, tests it, applies quality gates, updates the frontier, and returns a usable SeraModel.

Depends on:

- Vishnu V3
- Vishnu V5
- Vishnu V7
- Vishnu V8
- Vishnu V9
- Vishnu V11

Blocks:

- Barrat B8
- Vishnu V12
- Vishnu V14

## V11 — Quality gates

Priority: P0

Status: TODO

Todo:

- Reject generation errors, empty outputs, corrupt requests, and severe output collapse.
- Implement the quick-mode behavior proxy against baseline outputs.
- Accept a user evaluation callable in verified mode.
- Enforce the quality floor before frontier admission.
- Record score, floor, pass state, and rejection reason.
- Restore the last viable model after quality failure.

Result:

- Quick and verified quality gates
- Tested rollback path

Win condition:

A faster candidate that fails quality never becomes the recommendation, and Sera returns the last viable configuration.

Depends on:

- Vishnu V2
- Vishnu V5
- Vishnu V6

Blocks:

- Barrat B3
- Vishnu V10
- Vishnu V12
- Vishnu V14

## V12 — SQLite ledger and resume

Priority: P0

Status: TODO

Todo:

- Store the run specification and environment fingerprint.
- Store model revisions, proposals, validation, trials, metrics, quality, frontier state, and reverts.
- Use canonical configuration hashes.
- Use transactions for trial-state changes.
- Resume an interrupted run without repeating completed trials.
- Redact secrets before persistence.
- Add migration and corruption tests.

Result:

- Local source-of-truth ledger
- Safe resume behavior

Win condition:

Killing Sera after a completed trial and restarting it continues from the next legal trial with the earlier evidence intact.

Depends on:

- Vishnu V2
- Vishnu V3

Blocks:

- Vishnu V10
- Vishnu V13
- Vishnu V14

## V13 — Frontier reader and joint placement

Priority: P1

Status: TODO

Todo:

- Calculate each model's valid non-dominated frontier.
- Implement the frontier-reader agent.
- Select small configurations that still meet requirements.
- Propose per-service GPU memory limits.
- Run the deterministic joint fit check.
- Start two vLLM services on the same GPU.
- Run both workloads at the same time.
- Gate each model separately.
- Revert both services when either model fails.
- Feed contention evidence into a new optimization round.

Result:

- Complete phase-two loop
- Accepted joint placement or measured no-safe-placement result

Win condition:

Sera tests two models together, reports each model's isolated-to-shared change, and never accepts placement when either model fails.

Depends on:

- Vishnu V8
- Vishnu V10
- Vishnu V11
- Vishnu V12

Blocks:

- Barrat B4
- Barrat B8

## V14 — Weave instrumentation

Priority: P1

Status: TODO

Todo:

- Create one root trace for each optimize call.
- Trace baselines, reduction, specialists, arbitration, validation, trials, gates, frontier selection, joint placement, and revision.
- Use Barrat's display names.
- Attach configuration hashes and ledger identifiers.
- Log evaluations with Weave EvaluationLogger.
- Return the trace URL in SeraResult.
- Confirm that no secret enters a trace.

Result:

- Complete W&B Weave trace
- Linked evaluation results

Win condition:

One trace proves the complete self-correcting loop and matches the corresponding SQLite records.

Depends on:

- Barrat B5 for display requirements
- Vishnu V9
- Vishnu V10
- Vishnu V12
- Vishnu V13

Blocks:

- Barrat B4
- Barrat B5
- Barrat B8

## V15 — Benchmark and ablations

Priority: P1

Status: TODO

Todo:

- Generate one small legal candidate universe.
- Execute every candidate once to establish the oracle.
- Implement preregistered fixed-order naive grid search.
- Implement uniform random search with 20 recorded seeds.
- Replay Sera without reduced telemetry.
- Replay Sera without trial history.
- Replay round-robin specialists without the arbiter.
- Calculate trials-to-near-oracle and regret after each trial.
- Export one stable summary schema for Barrat.

Result:

- Reproducible benchmark dataset
- Grid, random, and ablation results
- Machine-readable chart data

Win condition:

Under the same trial budget, Sera reaches a quality-valid configuration within five percent of the oracle before naive grid search and beats median random search.

Depends on:

- Vishnu V8
- Vishnu V10
- Vishnu V11
- Vishnu V12

Blocks:

- Barrat B6
- Barrat B8

## V16 — Packaging and release candidate

Priority: P0

Status: TODO

Todo:

- Define locked runtime and development dependencies.
- Add the pyproject configuration.
- Add unit, contract, integration, and Molab system test commands.
- Add a package build check.
- Add installation from the repository.
- Run the complete CPU test suite.
- Run the Molab GPU acceptance test.
- Tag the tested release candidate.

Result:

- Installable Sera package
- Passing test suite
- Tested Molab release candidate

Win condition:

A clean Molab notebook installs Sera from the repository and completes the documented quick-mode example.

Depends on:

- Vishnu V1 through V15
- Barrat B7 for the exact clean-install path

Blocks:

- Barrat B9
- Barrat B10

## Backend checkpoints

### Checkpoint V-A: Real model

Required:

- Vishnu V1
- Vishnu V2
- Vishnu V4
- Vishnu V5

Output:

Sera returns one working SeraModel from one pinned Hugging Face model.

### Checkpoint V-B: First measured optimization

Required:

- Vishnu V3
- Vishnu V6
- Vishnu V7
- Vishnu V8
- Vishnu V11
- One hard-coded legal candidate

Output:

One model completes baseline, candidate trial, quality gate, result, and cleanup without agents.

### Checkpoint V-C: Agent loop

Required:

- Vishnu V9
- Vishnu V10
- Vishnu V12

Output:

Measured evidence changes the selected experiment across two rounds.

### Checkpoint V-D: Full product

Required:

- Vishnu V13
- Vishnu V14
- Vishnu V15
- Vishnu V16

Output:

Two-model optimization, joint placement, Weave trace, benchmark, and installable release work together.

## Cross-person dependencies

| Contract | Barrat owns | Vishnu owns | Ready when |
| --- | --- | --- | --- |
| Public API | User shape and names | Types and behavior | Fixture passes in notebook |
| Progress | Visible wording and layout | Event schema and ordering | Every backend state renders |
| Results | Information order and explanation | Metrics and result values | Real trial matches fixture |
| Weave | Judge-facing story | Trace operations and data | Trace matches ledger |
| Benchmark | Charts and claims | Fair harness and data | Chart rebuilds from export |
| Installation | Quick-start steps | Package and locked runtime | Clean Molab run passes |

## Vishnu definition of done

A Vishnu task is done only when:

- Its behavior has a test.
- The test checks system behavior, not private implementation.
- Failure paths are covered.
- Secrets are redacted.
- The public schema matches Barrat's fixture.
- The relevant integration checkpoint runs.
- The result is committed with no unrelated changes.
