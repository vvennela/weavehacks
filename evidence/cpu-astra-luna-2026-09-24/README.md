# Astra with 15 Luna specialists: live preparation

This captures the design before the user requested joint swarm experiment selection. It is retained as evidence, not presented as the final swarm design.

Astra selected 15 distinct roles from the fixed CPU catalog. All 15 GPT-6 Luna specialists returned recommendations. GPT-6 Astra at high reasoning effort then implemented `sme-512-constant-bound-full-tiles`. Logs verify the models and reasoning settings; each request used Codex ChatGPT login. There were 17 calls: two Astra calls and 15 Luna calls.

The generated kernel retains FP32 arithmetic and a general-size fallback. It passed the original 45 public correctness cases and then 48 cases after the validator was extended to cover the 512-square fast path. Worst relative error in the expanded check: 0.0000010017721, below the unchanged 0.002 tolerance. These are correctness checks, not timing scores.

No performance measurement or adoption decision has occurred. The Mac still reported battery power after generation. Historical battery measurements supplied to the agents were explicitly labeled historical context, not an AC baseline. Scoring will require AC power and a fresh paired baseline under the unchanged frozen hill.

The preparation began at commit `96ea7d9`. A small concurrent wrapper change tightened Python wrong-type errors from ValueError to TypeError and was committed in `47fd6e6`; this was not a frozen-release certification run. The later measured-adjudication hook is not exercised by preparation. Exact prompts, response schemas, outputs and logs are retained.

- `candidate/kernel.c`: unedited Astra implementation.
- `candidate.json`: source hash and model-authored hypothesis (not a measured claim).
- `correctness.json`: original public shape checks.
- `correctness-with-512.json`: added fast-path correctness coverage.
- `agent/state.json`: selected roles and all specialist recommendations.
- `agent/round-001/`: per-agent evidence.
