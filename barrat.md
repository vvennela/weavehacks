# Barrat: Product-Facing Work

## Mission

Make Sera useful to a developer who has no inference-engineering knowledge.

Barrat owns:

- Public API shape and product language
- Demo prompts and expected story
- Marimo notebook
- Progress, failure, and result views
- Weave trace presentation
- Benchmark charts
- Quick start, demo, and submission

Barrat does not own runtime control, measurements, search logic, validation, or persistence.

## Work rules

- Build the notebook against a fixed SeraResult fixture first.
- Use only Sera's public API.
- Keep setup, live execution, and prepared demo data separate.
- Mark tasks TODO, DOING, BLOCKED, or DONE.
- Record the exact dependency when work is blocked.
- Integrate at each shared checkpoint.

## B1 — Product contract and demo inputs

Priority: P0

Status: TODO

Todo:

- Finalize the one-model and two-model API examples.
- Define quick mode and verified mode in user language.
- Define the visible run stages and final outcomes.
- Choose and version the prompt corpus.
- Define the quality-check intent.
- Define the expected demo story without hard-coding trial results.
- Define the benchmark candidate universe with Vishnu.
- Give Vishnu golden examples of progress events and SeraResult.

Result:

- Approved public API example
- Versioned prompt corpus
- Golden progress and result examples
- Written demo scenario

Win condition:

A developer can understand the input, run, and output without knowing vLLM settings. Vishnu can implement every public object without guessing.

Depends on:

- product.md
- spec.md

## B2 — Fixture-driven Marimo notebook

Priority: P0

Status: TODO

Todo:

- Create the Marimo notebook as a normal Python file.
- Add model, prompt, and secure W&B key inputs.
- Add setup, run, progress, result, benchmark, and evidence sections.
- Render the complete flow from the fixed fixture.
- Keep one switch between fixture mode and live Sera mode.
- Make reruns safe.

Result:

- Complete notebook using fixture data
- One integration point for the live library

Win condition:

The notebook tells the complete product story before GPU work is ready. Connecting the live backend changes one construction point.

Depends on:

- Barrat B1
- Vishnu V2

## B3 — Progress, failure, and result views

Priority: P0

Status: TODO

Todo:

- Show the current phase, model, trial, and remaining budget.
- Show why each specialist is active or inactive.
- Separate validation rejection, GPU failure, quality failure, and rollback.
- Compare baseline with the recommendation.
- Lead with p95 latency, throughput, peak memory, and quality.
- Show alternatives on the frontier in plain English.
- Show no-safe-improvement as a valid result.
- Define the exact text used by result.print_summary().

Result:

- Fixture-backed progress view
- Fixture-backed result view
- Golden plain-text summary
- Complete success and failure copy

Win condition:

Using the fixture, a new reader can answer what Sera changed, why it changed it, whether quality passed, and which returned model to use.

Depends on:

- Start: Barrat B1 and Vishnu V2
- Live acceptance: Vishnu V3, V7, V10, and V13

## B4 — Weave presentation contract

Priority: P0

Status: TODO

Todo:

- Name the root trace and child operations.
- Define the visible fields for evidence, proposal, prediction, trial, gate, revert, and revision.
- Define one quality-rejection trace story.
- Define one failed-prediction-to-revised-action trace story.
- Remove noisy backend fields from the judge-facing view.

Result:

- Trace naming and field contract
- Two golden trace stories

Win condition:

Vishnu can add Weave instrumentation without choosing product language or trace layout.

Depends on:

- Barrat B1

## B5 — Live Weave trace QA

Priority: P0

Status: TODO

Todo:

- Compare live trace names and fields with the B4 contract.
- Confirm that one trace shows agent disagreement and arbitration.
- Confirm that one trace shows measured failure changing the next action.
- Confirm that evaluations link to the correct trial.
- Confirm that no secret appears.

Result:

- Judge-ready Weave trace
- Trace defects reported to Vishnu

Win condition:

A judge can understand the self-correcting loop from one trace without a spoken explanation.

Depends on:

- Barrat B4
- Vishnu V12

## B6 — Benchmark and ablation view

Priority: P0

Status: TODO

Todo:

- Plot best valid p95 latency after each trial.
- Compare Sera with naive fixed-order grid search under the same budget.
- Show the uniform-random distribution.
- Show one intelligence ablation.
- Mark quality failures.
- State that grid search is a test control, not part of Sera.
- Write one exact benchmark conclusion from the measured data.

Result:

- One search-efficiency chart
- One ablation chart
- One accurate benchmark statement

Win condition:

The view makes trial efficiency clear. It does not rely on an unfair candidate set, hidden failures, or an unbounded grid.

Depends on:

- Barrat B1
- Vishnu V14

## B7a — Quick-start draft

Priority: P0

Status: TODO

Todo:

- Write installation steps from Vishnu's recorded environment.
- Write the smallest working call.
- Explain W&B and Hugging Face environment variables.
- Explain quick mode, verified mode, and limits.
- Add one-model and two-model examples.

Result:

- Draft README quick start

Win condition:

The instructions contain every command and input needed for a clean Molab run.

Depends on:

- Vishnu V1
- Vishnu V2

## B7b — Clean-install documentation QA

Priority: P0

Status: TODO

Todo:

- Follow the quick start in a clean Molab session.
- Record every failed or missing step.
- Correct the documentation.
- Repeat the clean install once.

Result:

- Verified quick start

Win condition:

The second clean session installs Sera and completes the documented quick-mode example without verbal help.

Depends on:

- Barrat B7a
- Vishnu V15

## B8 — Three-minute live demo

Priority: P0

Status: TODO

Todo:

- Write a three-minute script with at most two slides.
- Start with the one-call user experience.
- Show one live lever and one skipped dead lever.
- Show a quality or contention failure.
- Show the next action changing from measured evidence.
- Show the final model, Weave trace, and benchmark.
- Keep downloads and long trials outside the live path.
- Record a backup demo.

Result:

- Timed live demo
- Prepared notebook state
- Backup recording
- At most two slides

Win condition:

Three timed rehearsals finish within three minutes and prove utility, collaboration, self-correction, measured performance, and sponsor use.

Depends on:

- Barrat B2
- Barrat B3
- Barrat B5
- Barrat B6
- Barrat B7b
- Vishnu V11 through V15

## B9 — Hackathon submission

Priority: P0

Status: TODO

Todo:

- Write the two-to-three sentence summary.
- Explain the self-improving loop.
- Explain the fair benchmark against naive grid search.
- List every sponsor tool and its exact use.
- Add the repository, notebook, trace, charts, and demo video.
- Check every link in a signed-out browser.
- Complete team and survey requirements.

Result:

- Complete AGI House submission
- Public project material
- Demo video under two minutes

Win condition:

Every required field is complete, every link opens, and the two-minute submission video is distinct from the three-minute live demo.

Depends on:

- Barrat B8
- Vishnu V15

## B10 — Unassisted usability test

Priority: P2

Status: TODO

Todo:

- Give the notebook to one developer who did not build Sera.
- Observe the first run without explaining it.
- Record confusion and errors.
- Fix the highest-impact problem.

Result:

- Short usability log
- One tested improvement

Win condition:

The developer starts a quick-mode run and identifies the returned model without help.

Depends on:

- Barrat B7b

## Shared checkpoints

### C1 — Contract

Required:

- Barrat B1
- Vishnu V2

Pass condition:

The notebook and backend use the same fixture, events, result fields, and names.

### C2 — Fixture product

Required:

- Barrat B2
- Barrat B3
- Barrat B4

Pass condition:

The complete user and judge experience works from fixed data.

### C3 — Measured vertical slice

Required:

- Barrat B3
- Vishnu V1 through V10

Pass condition:

One model completes a baseline, one fixed candidate trial, quality gate, final result assembly, final runner activation, and cleanup.

### C4 — Agent proof

Required:

- Barrat B5
- Vishnu V11
- Vishnu V12

Pass condition:

A measured failure changes the next selected experiment, and Weave shows why.

### C5 — Demo proof

Required:

- Barrat B6 through B9
- Vishnu V13 through V15

Pass condition:

Joint placement, benchmark, install, demo, and submission all work from one release candidate.

## Barrat definition of done

A task is done only when:

- Its stated artifact exists.
- Success, failure, and empty states are covered.
- It matches the shared fixture or live schema.
- The language is simple and direct.
- Its win condition has been checked.
- Any cross-person dependency is complete.
