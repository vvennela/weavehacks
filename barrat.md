# Barrat: Product-Facing Work

## Mission

Make Sera understandable and useful to a developer with no inference-engineering knowledge.

Barrat owns the public experience:

- Product language
- Public API design
- Marimo notebook
- Progress and error presentation
- Results and comparison views
- Weave trace presentation
- Demo and submission material

Barrat does not own vLLM control, measurements, search logic, validation, or persistence.

## Working agreement

- Work against the shared SeraResult fixture before the backend is complete.
- Do not read backend internals from the notebook.
- Treat the Sera public API and result schema as the integration boundary.
- Mark each task TODO, DOING, BLOCKED, or DONE.
- Record blockers under the task that owns them.
- Integrate after each working vertical slice. Do not wait for all backend work.

## Task order

Complete P0 tasks first. They unblock the backend and the first integrated demo.

## B1 — Public experience contract

Priority: P0

Status: TODO

Todo:

- Define the minimum Sera call for one model and two models.
- Define quick mode and verified mode in user language.
- Define the visible stages of an optimization run.
- Define what the user sees when Sera finds an improvement.
- Define what the user sees when no safe improvement exists.
- Define the names and order of result sections.
- Give Vishnu a fixed example of the final SeraResult data.

Result:

- One approved API example
- One approved SeraResult fixture
- User-facing names for states, metrics, failures, and recommendations

Win condition:

A developer can read the example, name models, provide prompts, run Sera, and understand the returned result without learning vLLM settings.

Depends on:

- product.md
- spec.md

Blocks:

- Vishnu V2
- Barrat B2
- Barrat B4

## B2 — Marimo notebook shell

Priority: P0

Status: TODO

Todo:

- Create the demonstration notebook as a normal Marimo Python file.
- Add model and prompt inputs.
- Add a secure W&B API-key input.
- Call Sera through the public API only.
- Build the notebook against the fixed SeraResult fixture first.
- Separate setup, run, progress, result, and benchmark sections.
- Make reruns safe and predictable.

Result:

- A notebook that renders the complete Sera experience from fixture data
- A notebook entry point that can switch from fixture data to the real library

Win condition:

The notebook tells the full product story before the GPU backend is connected, and switching to the real backend requires changing one construction point.

Depends on:

- Barrat B1
- Vishnu V2 for the fixture schema

Blocks:

- Barrat B8
- Barrat B9

## B3 — Progress and failure experience

Priority: P0

Status: TODO

Todo:

- Show the current phase, model, trial, and remaining budget.
- Translate specialist and arbiter actions into short user-facing messages.
- Show deterministic rejections separately from failed GPU trials.
- Show quality failure and rollback clearly.
- Show a clear final state for success, no safe improvement, cancellation, and system failure.
- Keep full technical details available without putting them in the main path.

Result:

- Progress component
- Failure component
- Approved copy for every public run state

Win condition:

A user always knows what Sera is doing, why a candidate was rejected, and whether the returned model is safe to use.

Depends on:

- Barrat B1
- Vishnu V3 event schema
- Vishnu V11 failure states

Blocks:

- Barrat B8

## B4 — Result report

Priority: P0

Status: TODO

Todo:

- Show baseline and recommended configuration side by side.
- Lead with latency improvement, peak-memory change, throughput change, and quality result.
- Show the measured frontier without requiring the user to understand Pareto optimization.
- Show rejected configurations and the reasons for rejection.
- Show phase-two results for each model separately.
- Add a copyable configuration and a copyable usage example.
- Add a link to the Weave trace.

Result:

- Notebook result view
- Plain-text summary used by result.print_summary()
- Report layout that works for success and no-safe-improvement outcomes

Win condition:

A new user can answer four questions in less than 20 seconds:

1. What did Sera change?
2. How much faster is it?
3. Did quality pass?
4. What model object do I use now?

Depends on:

- Barrat B1
- Vishnu V7 reduced metric schema
- Vishnu V13 frontier and placement result
- Vishnu V14 Weave trace URL

Blocks:

- Barrat B8
- Barrat B9

## B5 — Weave trace story

Priority: P1

Status: TODO

Todo:

- Define readable names for the root trace and child operations.
- Define the fields that judges must see for a proposal, prediction, trial, quality gate, and revision.
- Hide noisy implementation fields from the main story.
- Prepare one trace that shows a failed prediction changing the next decision.
- Prepare one trace that shows a quality rejection.

Result:

- Trace naming and display specification for Vishnu
- Two judge-ready Weave traces

Win condition:

A judge can open one trace and see evidence, agent disagreement, experiment selection, measured failure, and the corrected next action.

Depends on:

- Barrat B1
- Vishnu V14 for implemented trace operations

Blocks:

- Barrat B8
- Barrat B9

## B6 — Grid-search benchmark view

Priority: P1

Status: TODO

Todo:

- Show Sera and naive grid search under the same trial budget.
- Plot best valid p95 latency after each trial.
- Mark quality failures instead of hiding them.
- Show trials-to-near-oracle for each method.
- Show the random-search distribution.
- Show the telemetry and history ablation results.
- State that grid search is a benchmark control, not part of Sera.

Result:

- One compact benchmark chart
- One ablation chart
- One paragraph that states the result without exaggeration

Win condition:

The charts show that Sera reaches a strong valid configuration earlier than fixed-order grid search and beats the median random baseline.

Depends on:

- Vishnu V15 benchmark dataset and summary schema

Blocks:

- Barrat B8
- Barrat B9

## B7 — Quick-start documentation

Priority: P1

Status: TODO

Todo:

- Write installation instructions.
- Write the smallest working example.
- Explain quick mode and verified mode.
- Explain required environment variables without exposing keys.
- Explain supported models and hardware.
- Explain what Sera can and cannot prove.
- Add one-model and two-model examples.

Result:

- README quick start
- Notebook setup instructions
- Clear limitations section

Win condition:

A developer can start Sera from a clean Molab notebook without help.

Depends on:

- Vishnu V1 Molab smoke test
- Vishnu V16 package installation
- Barrat B1

Blocks:

- Barrat B10

## B8 — Three-minute demo

Priority: P0

Status: TODO

Todo:

- Write a three-minute script with no more than two slides.
- Start with the one-call product experience.
- Show one specialist disagreement.
- Show Sera choosing a live lever and skipping a dead lever.
- Show a quality rejection or contention failure.
- Show the next decision changing from the evidence.
- Show the final result and grid-search comparison.
- Keep model download and long trials outside the live demo.

Result:

- Timed demo script
- Prepared notebook state
- One backup recording
- At most two supporting slides

Win condition:

The complete demonstration finishes in less than three minutes and proves utility, agent collaboration, self-correction, measured performance, and meaningful Weave use.

Depends on:

- Barrat B2
- Barrat B3
- Barrat B4
- Barrat B5
- Barrat B6
- Vishnu V10 phase-one vertical slice
- Vishnu V13 joint placement
- Vishnu V15 benchmark

Blocks:

- Barrat B10

## B9 — Usability test

Priority: P1

Status: TODO

Todo:

- Give the notebook to one developer who did not build Sera.
- Ask them to start a quick-mode run.
- Record every point where they need an explanation.
- Fix unclear API names, copy, ordering, and errors.
- Repeat the test once.

Result:

- Short usability log
- Fixed notebook and public copy

Win condition:

The second user completes the main flow without verbal help.

Depends on:

- Barrat B2
- Barrat B3
- Barrat B4
- Vishnu V16 installable package

Blocks:

- Barrat B10

## B10 — Hackathon submission

Priority: P0

Status: TODO

Todo:

- Write the two-to-three sentence project summary.
- List W&B Weave, W&B Inference, Molab, CoreWeave, vLLM, and Hugging Face usage.
- Explain the self-improving loop.
- Explain the benchmark against naive grid search.
- Add the public repository link.
- Add the notebook, Weave trace, charts, and demo video.
- Verify team and survey requirements.

Result:

- Complete AGI House submission
- Public repository with clear setup
- Demo video under two minutes

Win condition:

Every submission field is complete, every link works in a signed-out browser, and a judge can understand Sera without running the code.

Depends on:

- Barrat B7
- Barrat B8
- Barrat B9
- Vishnu V16 release candidate

## Product checkpoints

### Checkpoint P-A: Contract

Required:

- Barrat B1
- Vishnu V2

Output:

The notebook and backend use the same SeraResult fixture.

### Checkpoint P-B: First vertical slice

Required:

- Barrat B2
- Barrat B3
- Vishnu V5

Output:

One real model runs through baseline, one candidate trial, result display, and cleanup.

### Checkpoint P-C: Complete story

Required:

- Barrat B4
- Barrat B5
- Barrat B6
- Vishnu V13
- Vishnu V14
- Vishnu V15

Output:

The notebook shows optimization, self-correction, joint placement, Weave evidence, and the grid-search benchmark.

## Barrat definition of done

A Barrat task is done only when:

- The user-facing behavior is present in the notebook or documentation.
- It works with the agreed SeraResult schema.
- Success, failure, and empty states are handled.
- The language is simple and direct.
- The output supports the three-minute demo.
- Vishnu can consume the result without guessing.
