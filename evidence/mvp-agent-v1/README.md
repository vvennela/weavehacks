# Live agent-guided quick check

Implementation: `a2554ae27bda5473691ef837460da75c0f4dceae`.
Hardware: RTX PRO 6000 Blackwell Server Edition; vLLM 0.26.0.
Model: pinned Qwen/Qwen3-0.6B. Agent: W&B Inference `openai/gpt-oss-20b`.

The complete live path ran: measured BF16 baseline, validated agent proposal, measured FP8 KV candidate, deterministic quality gate, agent feedback, returned baseline runner, fresh generation, saved report, and cleanup.

- Workload: all eight prepared easy prompts; concurrency one, eight warm-ups and 24 measured requests per configuration, plus separate quality passes.
- Provider prerequisite: 30/30 first-pass valid responses in provider-v2; no retries.
- Proposal: change only KV cache precision to FP8. The agent predicted lower latency and higher throughput. This was a hypothesis, not measured evidence of memory pressure.
- Baseline token self-check: 100% agreement.
- Candidate token agreement: 72.4609375%; required 99%. Candidate rejected.
- Final agent recommendation: keep baseline; prediction refuted. No agent error recorded.
- Returned runner served a fresh request and then closed. GPU memory returned to 0 MiB.
- Fresh request `What is 1 + 1? Return only the number.` returned `1`: runtime success, answer failure.

This is a successful live rejection/fallback path, not an optimization win. Eight prompts do not satisfy the formal 32-prompt/96-request measurement contract. Token agreement does not establish task correctness. Search quality, FP8 weights, and joint placement remain unproven.

[Saved report](report.md), [raw result](result.json), and [Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a098be-3446-747e-b1e8-3213ff3298aa).

Weave tracing used an experiment wrapper. The completed notebook cell now loads this saved result instead of starting another GPU run.
