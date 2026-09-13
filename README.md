# Sera

Sera measures a model configuration, rejects quality failures, and returns a live runner.

## Current implementation

The first fixed-candidate path is implemented. It supports one pinned Qwen3-0.6B model on Linux with vLLM 0.26.0 and an NVIDIA GPU. BF16 and FP8 KV ran on the supplied RTX PRO 6000. The packaged runner passed one live lifecycle check; the full optimization path still needs live acceptance.

The latest runner check returned `2` for `2 + 3`. Its runtime worked, but its answer was wrong. See [the saved evidence](evidence/sera-runner-v1/README.md). Do not treat runtime success as model correctness.

Agent selection, Weave traces, task-correctness acceptance, joint placement, and the search benchmark are not implemented. A fixed candidate is not an agent recommendation.

The W&B client, typed proposal/ranking/final-selection schemas, and bounded provider check are implemented. The client reads `WANDB_API_KEY` from the process environment; it never saves the key or request headers. Agent-controlled GPU execution stays disabled until the provider check passes.

## Install

Use the existing GPU environment with its working vLLM and CUDA packages. Installing Sera does not install or change the GPU stack.

```sh
uv pip install -e .
```

For local development without a GPU:

```sh
uv sync --extra dev
uv run pytest -q
```

## One runner

Run this in the supplied Linux GPU environment, not on the local Mac:

```python
from sera import SeraModel

with SeraModel(artifact_dir="sera-runs/runner-check") as model:
    response = model.generate('What is 2 + 3? Return only the number.')
    print(response.text)
```

The output directory must be new. The server stays alive between requests. `close()` stops the owned process group and checks that GPU memory returns to the pre-launch range. A failed cleanup blocks another trial. Server logs, versions, tokenizer information, configuration, startup time, and cleanup are saved in that directory.

## Baseline → candidate → gate → returned runner

```python
import sera

with sera.optimize(
    models=["Qwen/Qwen3-0.6B"],
    prompts=prompts,  # Supply 32 representative prompts for milestone acceptance.
    output_dir="sera-runs/first-comparison",
) as result:
    result.print_summary()
    response = result.models[0].generate("What is 2 + 3? Return only the number.")
    print(response.text)
```

The model and tokenizer revision is `c1899de289a04d12100db370d81485cdf75e47ca`.
The named baseline is BF16 weights and KV cache. The predeclared default candidate changes only KV cache to FP8. It is a hypothesis, not a promised improvement.

The other planned candidate can be supplied explicitly:

```python
candidate = sera.Candidate(
    name="batch-2048",
    reason="Test the predeclared batch-token alternative",
    config=sera.RuntimeConfig(max_num_batched_tokens=2048),
)
```

Pass it as `candidate=candidate` to `optimize`. These are the two milestone candidates; the broader search space is not enabled.

The comparison uses concurrency 1, up to 16 warm-ups, and three measured passes. Quality uses separate serial passes and a baseline self-check. One to 32 prompts are accepted; fewer than 32 are a quick check, not the full milestone measurement contract. Each request permits 64 output tokens. Overlong inputs are rejected, never silently truncated.

Sera switches only when the candidate has no generation errors, token agreement is at least 0.99, and p95 latency is at least 5% lower. Otherwise it keeps or reloads the baseline. Baseline startup or cleanup failure raises an error and preserves the failure record; it does not return a pretend runner.

`result.json` contains the workload, raw request samples, token IDs, quality scores, and selection reason. `report.md` is a readable summary. Each trial has server logs and raw Prometheus snapshots. Request timing excludes startup, token-length preflight, and local report writes. Throughput includes output token counts. Unavailable timing percentiles stay unavailable.

Token agreement checks preserved behavior, **not correct answers**. No performance win, task-quality result, or agent-selection result is established merely by running this code.

See [plan.md](plan.md) for delivery status and [spec.md](spec.md) for the full target. W&B agent wiring will use its [structured-output API](https://docs.wandb.ai/inference/response-settings/structured-output); provider validation is still pending.

## Provider compatibility check

Install the `agent` extra. With `WANDB_API_KEY` already supplied through the environment:

```python
from sera.provider_check import check_provider

provider_report = check_provider(
    project="vvennela-n-a/wandb_agent_default_project",
    output_dir="sera-runs/provider-check",
)
```

This makes 30 requests using the actual three schemas and synthetic evidence. Each failed response permits one retry. It requires 29 first-pass valid responses and all 30 valid within the retry limit. All attempts, truncation, errors, timings, and separate evidence-reference checks are saved. A pass establishes schema compatibility, not useful search or model correctness. Credential/access errors stop the check early.
