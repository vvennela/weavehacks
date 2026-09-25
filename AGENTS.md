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
