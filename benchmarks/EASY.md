# Easier MVP questions

`easy_cases.json` contains eight newly authored sanity-check questions: addition, comparison, list length, indexing, assignment, copying a field, filtering two records, and uppercase conversion. All have exact, independently checked answers. No model-generated code executes.

These replace advanced reasoning and subtle Python behavior for the MVP workload design. They are not a harder-model benchmark and do not establish general coding ability. All eight ran in the live agent-guided BF16/FP8 KV comparison in evidence/mvp-agent-v1. That run applied token agreement, not an exact-answer task gate. Their 64-token limit matches the product default; the existing 24-case collector deliberately rejects that limit, so this file cannot silently replace the frozen pilot.

Keep the original 24 questions, answer keys, grader, and measured results unchanged. Do not drop an easy case after observing a wrong answer. The answer-key validation is a local test, not a new model experiment.

For the future task-based gate, report exact answer correctness separately from JSON-format compliance. Only documented, deterministic normalization is allowed; never use an external judge to reinterpret a response or repair an incorrect value. That scorer is not implemented by this data file. The existing conservative product gate remains in force until an explicit task evaluator is wired in.
