# Packaged runner: one live case

Code: `18298b5e8ce4e285ab31d423cc90993a17bbdf87`, installed from GitHub in Molab through marimo's package manager.

**Runtime passed. Answer correctness failed.** The `status: passed` field in result.json refers only to lifecycle success; `answer_correct` is false.

- Pinned Qwen3-0.6B, named BF16 baseline, vLLM 0.26.0.
- Startup: 40.041 seconds.
- Prompt: `What is 2 + 3? Return only the number.`
- Expected: `5`. Actual: `2`.
- One generation request; 68.986 ms end-to-end generation latency.
- Metrics exposed one completed request and zero engine-reported errors.
- Close completed; GPU memory returned to 0 MiB.

This used the one remaining authorized GPU test case. No candidate comparison, warm-up, retry, or full optimize run was executed. One request establishes no latency percentile, task-quality rate, optimization win, or agent recommendation.

The live cell is frozen to read the saved JSON. The original model output, token IDs, rendered prompt, versions, tokenizer configuration, server log, and metrics are preserved here. The cause of the wrong answer was not established. Do not change the model or lower the quality gate based on this check without approval.
