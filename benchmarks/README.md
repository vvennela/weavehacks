# Sera task-quality pilot: sera-task-v1

This is an original 24-case diagnostic suite for the same Qwen3-0.6B model under BF16 and FP8 KV cache. It measures answer correctness, not similarity to baseline wording. It does not measure official HLE, DeepSWE, or SWE-bench performance.

## Cases and scope

| Category | Cases | What is checked |
| --- | ---: | --- |
| Coding | 12 | Eight Python result predictions and four repair-choice problems |
| Exact reasoning | 6 | Arithmetic, sets, schedules, modular arithmetic, path counting |
| Structured extraction | 6 | Typed fields, filtering, event order, missing values, deduplication |

Each category includes easy, moderate, and harder cases: eight cases per tier overall. Tiers are author estimates, not measured difficulty. Coding dominates the suite, but it is **coding reasoning and repair selection**, not free-form code generation or repository repair. The four repair-choice items have a 25% random-guess success rate each. The suite includes simple cases because an all-zero 0.6B baseline would provide no useful comparison.

All problems are newly authored for this pilot. They were not copied from official datasets. Common programming concepts still overlap public training material; no contamination-free claim is made. Answer keys have fixed, independently written calculations in the validation test, but they have not received independent human review.

## Fixed input contract

Use `load_cases()` and `SYSTEM_PROMPT` from `benchmarks.grade`. Send only the system prompt and each case's `prompt` to the model. Never send `expected` or `rationale`. Preserve case order and record `dataset_hash(cases)` before looking at either configuration's outputs.

Use the same pinned model and tokenizer, chat template, and rendered prompt token IDs for both configurations. Explicitly render Qwen with `enable_thinking=False`. Do not rely on a repository default. Use temperature 0, top_p 1, top_k -1, seed 0, maximum 128 output tokens, normal EOS handling, and concurrency 1. Reject over-context inputs; never truncate silently. Do not use constrained JSON decoding, repair prompts, extra attempts, or different generation settings for one configuration.

The 128-token cap is a named pilot override of the spec's 64-token default. This 24-case task-quality pilot is separate from the 32-prompt milestone workload. Do not silently substitute its results for the milestone's specified measurements or 99% token-agreement gate.

Run one request per case per configuration first: 48 measured requests in total, at most 6,144 generated tokens. Start each configuration once. Use the same warm-up sequence and keep its results out of quality scores. Save raw outputs, request errors, finish reasons, prompt/output token counts, latency, all generation settings, configuration hashes, and runtime versions. An API failure or missing output stays in the denominator. Do not retry only failed or wrong cases. If instability needs a second pass, repeat the complete frozen suite for both configurations and report each pass separately.

## Deterministic grading

Every response must be one JSON object with exactly one field: `{"answer": ...}`. The question specifies the answer type. Comparison ignores JSON object key order and surrounding whitespace. It does not ignore list order, coerce strings to numbers, or equate booleans with integers. An integer answer written as a JSON floating-point value fails. Extra fields, duplicate keys, code fences, explanations, empty output, invalid JSON, and NaN/Infinity fail. The grader never extracts a convenient substring from a wrong response.

Each complete case scores either 1 or 0. There is no partial credit. Report the overall fraction, category/tier fractions, format failures separately from wrong answers, and paired case outcomes: both pass, baseline only passes, candidate only passes, neither passes. Different wording alone is irrelevant when both JSON answers are correct. A partially correct array or object fails that case.

Use `score_responses(cases, responses)` where `responses` maps case IDs to raw model output strings. Missing IDs are failures; unknown IDs are errors. Store request errors separately rather than rewriting them as invented model output.

This pilot does not set a new product acceptance floor or automatically promote FP8. It supplies evidence for choosing a task-quality contract. With 24 cases, one result changes accuracy by 4.17 percentage points. Equal totals can conceal regressions on individual cases. Report regressions and gains; do not claim statistical equivalence or broad preserved quality. A low baseline score means this model/workload pair is not a useful quality reference, not that the candidate is safe.

Latency here is descriptive. Shorter answers and format failures can appear faster. Report token counts and correctness alongside latency; this pilot alone does not prove the spec's 5% p95 improvement claim.

## Execution safety

The grader only uses bounded JSON parsing and typed value comparison. It does not run generated Python, shell commands, SQL, or arbitrary expressions. Test calculations are fixed, reviewed source code, never text returned by the model. No external judge or credentials are required for grading. Generated code must not be executed on the user's machine. Future free-form coding tasks require a separately verified disposable sandbox with no secrets, network, or host mounts, plus CPU, memory, process, output, and wall-time limits; an ordinary subprocess timeout is not a security boundary.

## Reference benchmark styles

- [Humanity's Last Exam](https://agi.safe.ai/) uses closed-ended academic problems, including multiple-choice and short-answer tasks. This pilot borrows the idea of fixed answers, not expert-level difficulty, official questions, the full evaluation procedure, or official scores.
- [Agentica/Together DeepSWE](https://www.together.ai/blog/deepswe) is a coding agent trained with reinforcement learning and evaluated on software-engineering tasks. It is not the name of this pilot dataset. This pilot borrows objective task success, but has no agent tools, repository edits, multi-step interaction, or generated-code execution.
- [Datacurve's DeepSWE benchmark](https://deepswe.datacurve.ai/blog/deepswe) is a different use of the same name: long-horizon repository tasks with behavior-focused verifiers. These 24 microtasks do not reproduce that task scope or difficulty.

## Validation

From the repository root:

```bash
uv run --no-project --with pytest python -m pytest -q tests/test_benchmark_cases.py
```

The tests cover every answer key, valid alternative JSON formatting, strict types and ordering, missing results, malformed/adversarial output, and exact whole-case scoring. They do not call an LM or count as measured model performance.
