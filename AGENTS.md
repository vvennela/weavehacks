# Project Rules

## Communication

- Use simple, common English.
- Use Simplified Technical English (STE) for technical writing.
- Be clear, direct, and brief. Use the shortest response that fully answers the request.
- Use high-signal language. Remove filler, vague claims, clichés, and unnecessary jargon.
- Explain uncommon technical terms when they are necessary.
- Do not use hedging language.
- State conclusions clearly. Do not hide them behind qualifications.
- Give honest assessments. If an idea, request, design, or implementation is bad, say that it is bad and explain why.
- Do not flatter the user or agree for the sake of agreement.
- Separate facts from assumptions. State assumptions directly.

## Code

- Use GPT-6 Luna subagents for breadth work, such as exploration, inventories, alternatives, and broad audits. The primary agent handles depth analysis, implementation of user-approved choices, integration, and validation. Delegate only concrete independent tasks.
- The user adjudicates decisions. Present evidence, options, and recommendations; do not independently choose product or research direction, architecture changes, benchmark rules, acceptance thresholds, budgets, or deployment actions. Ask for the user's decision before applying such changes.
- Sera uses a GPT-6 Astra coordinator at high reasoning effort, advised by 15 GPT-6 Luna specialists. The coordinator may select and replace specialist roles within the approved CPU optimization scope. The 15 Luna specialists propose experiments, review a shared proposal board, and jointly rank a batch to run. Astra implements the swarm-selected experiments rather than selecting experiments alone. Each Luna owns a specialist role and recommends a change. Advisors do not independently submit kernels. Astra reviews the experiment results and has the final adopt/reject/revise decision within the fixed correctness and performance gates. Use Codex agents through the user's ChatGPT login; do not substitute API-key or other hosted-provider calls.
- The user approved consistent FP32 CPU optimization toward 1,800 GFLOP/s. Battery measurements are now also authorized: establish fresh baselines and paired controls on the current power source, keep power settings and source unchanged during a block, and do not pool AC and battery scores. Retain both AC and battery results for the same method and source; compare improvements against a baseline in each mode. Measure untested source/power combinations when that power mode is available. Keep the frozen hill, numerical tolerance, compiler flags, thread limit, and repeated-control promotion rules unchanged. Specialist selection and kernel implementation within this contract are delegated to Sera; changes to the contract remain with the user.
- For the CPU MatMul search, start from the published LIBXSMM SME approach, adapt it to the frozen row-major C=A@B contract, establish its local baseline, then optimize it with Sera. Published scores are reference evidence, not comparable local results. Preserve source provenance and license notices; keep the standalone no-external-library rule.
- On 2026-09-25, the user approved one temporary switch from battery Low Power to Automatic for the next measurement block, followed by restoration. Preserve the Low Power evidence and measure fresh controls under Automatic. The proposed longer agent-call timeout remains unapproved; retain 180 seconds.
- Commit completed, tested steps as work proceeds. Do not leave all changes for one final commit. Stage only the files for the completed step and preserve unrelated work.
- Write only the code needed to meet the specification.
- Write readable code. Do not write clever or compressed code when it reduces clarity.
- Use clear, common-sense names for variables, functions, types, and files.
- Keep functions focused on one task.
- Apply Clean Code principles.
- Do not reduce code size at the cost of correctness, readability, or useful structure.

## Specifications and Tests

- Make every optimization baseline as deterministic as possible. Fix seeds, input data, workload, compiler/runtime versions and flags, thread count, hardware, and warmup procedure where possible. Record these controls with the results.
- Repeat performance measurements and report their spread. Use unchanged baseline controls to detect timing drift. Do not promote a candidate based on a favorable timing sample or a gain inside the observed noise.

- For each request, first establish the intended behavior, scope, constraints, and acceptance criteria.
- Resolve material ambiguity before implementation. Make small, safe assumptions when they do not change the product intent, and state them.
- Use test-driven development (TDD): write or update a failing test, implement the smallest correct change, then refactor while the tests pass.
- Test behavior and system outcomes, not implementation details.
- Do not add special cases only to satisfy individual tests.
- Treat tests as one coherent system. Check that they work together and represent the specification.
- Run the relevant test suite after each change. Report any test that cannot be run or does not pass.
