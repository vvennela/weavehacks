# Sera

Sera recommends and measures inference configurations, rejects quality failures, and returns a live runner.

## Current implementation

The large-model deployment path passed on the supplied RTX PRO 6000: reject the non-fitting BF16 plan → agent selects FP8 weights → load original Qwen2.5-72B weights with online quantization → pass all eight strict tasks → return a runner → pass a fresh request → save report and Weave trace → clean up. Measured p95 was 573 ms and peak total GPU memory was 86.38 GiB. See [the result and limits](evidence/large-fit-v1/README.md). The original final-agent review exposed an ambiguous prediction contract; that record is preserved and the review question has been corrected.

The smaller Qwen3-0.6B path also completed a live agent-guided rejection and baseline-return check. Both models are pinned; the runtime is Linux with vLLM 0.26.0. See [the small-model result](evidence/mvp-agent-v1/README.md).

The returned baseline runner answered `1` for `1 + 1`. Its runtime worked, but its answer was wrong. Do not treat runtime success or token agreement as model correctness.

The live checks used eight easy prompts and 24 measured requests per configuration, not the full 32-prompt/96-request acceptance workload. The large-model run proves feasible deployment through weight quantization, not a measured speedup or search advantage. Joint placement and the search benchmark remain unfinished. Weave tracing ran through the experiment wrapper, not automatic package instrumentation.

The W&B client, typed proposal/ranking/final-selection schemas, and bounded provider check are implemented. The client reads `WANDB_API_KEY` from the process environment; it never saves the key or request headers. Agent-controlled GPU execution stays disabled until the provider check passes.

The first provider check failed (19/30 valid first responses; 22/30 after retries). Its records are preserved. After expressing action/cost consistency in the wire schema and bounding ranking to one candidate, the second check passed 30/30 on the first response with no retries. This establishes schema compatibility, not recommendation quality.

## Install

For the recorded demo, run `uvx marimo@0.24.0 edit demo.py --sandbox` from this repository's root. It reads committed real evidence, makes no API calls, and needs no GPU. The live GPU command is in the large-model section below. The [corrected final-agent review](evidence/large-fit-review-v2/README.md) passed using the saved measurements.

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

See [plan.md](plan.md) for delivery status and [spec.md](spec.md) for the full target. The W&B agent uses its [structured-output API](https://docs.wandb.ai/inference/response-settings/structured-output).

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

After a matching check passes, supply `agent=sera.WandbAgent(project=...)` and `provider_check=".../result.json"` to `optimize`. Sera gives the agent the measured baseline, validates one proposal, measures it if legal, applies the unchanged gate, and returns the outcome for a final recommendation. A keep-baseline or invalid proposal consumes no candidate GPU trial. The final agent response cannot change the deterministic selection.

## User priorities

Pass `objective=sera.Objective(priority="throughput")` to `optimize` to maximize measured output tokens per second. Other choices are `"latency"` (default: minimize p95) and `"memory"` (minimize sampled peak total GPU memory, including runtime reservation). The default required relative improvement is 5%; `min_improvement_fraction` can be declared before the run. The 99% token-agreement gate is unchanged for every priority.

The agent receives the priority, and the deterministic selector applies it. `result.frontier` retains quality-valid latency/throughput/memory trade-offs; it is no longer only the fastest trial. Missing metrics remain missing and cannot prove that one trial dominates another. The report includes the objective, frontier IDs, latency, throughput, and peak memory. No dollar-cost model is implemented.

This wiring passes local synthetic checks, including different recommendations from the same measurements when the priority changes. The saved FP8 KV candidate remains rejected under every priority in quick mode because token agreement failed. The separate fit-first path below enables online weight quantization for the pinned 72B model without a feasible BF16 baseline. Arbitrary models and multi-GPU placement remain unsupported.

## Verified task requirements

For known-answer tasks, supply a versioned evaluator and explicit limits:

```python
with sera.optimize(
    models=["Qwen/Qwen3-0.6B"],
    prompts=prompts,
    evaluation=evaluate_answer,  # (prompt, output_text) -> bool or numeric score in [0, 1]
    evaluation_version="my-task-evaluator-v1",
    constraints=sera.Constraints(quality_floor=0.99, p95_latency_ms=500),
    objective=sera.Objective(priority="throughput"),
) as result:
    result.print_summary()
    if result.models:
        print(result.models[0].generate("Your next prompt").text)
```

The latency limit above is an example requirement, not a measured guarantee. `max_memory_mib` optionally limits sampled peak GPU memory. Constraints can also be supplied as a one-element list, matching the multi-model target API.

Verified mode uses task scores instead of token agreement for acceptance. It applies the same evaluator to the separate baseline and candidate quality passes, saves per-prompt scores and evaluator errors, and keeps the declared floor fixed. Empty output, invalid scores, evaluator errors, or unmet limits cannot pass. A baseline evaluator error stops the experiment before a candidate is loaded. A wrong but successfully graded baseline does not prevent testing a candidate.

If only the candidate meets requirements, Sera can select it without claiming a speedup. If neither meets requirements, it closes the runtime and returns `no-safe-configuration` with `models=[]`; it never returns a failed-quality baseline as verified. Scoring uses only the supplied prompts and evaluator and is not a general quality guarantee. The workload remains the current serial quick-check workload; concurrency sweeps are not implemented.

The first live verified check returned no safe configuration: the tiny model passed only 2/8 strict JSON tasks and the agent declined a trial. See [the preserved result](evidence/verified-agent-v1/README.md). Do not present this as a quality or optimization success.

## Large-model fit-first path

The same `optimize` entry point now accepts `models=["Qwen/Qwen2.5-72B-Instruct"]`, pinned to revision `495f39366efef23836d0cfae4fbe635880d2be31`. This path requires a versioned task evaluator and explicit quality floor because a non-fitting BF16 baseline cannot provide reference outputs.

It estimates BF16 and online FP8 weight plans before loading. The estimate includes full-context BF16 KV for eight sequences, unquantized embedding/head/norm/bias parameters, 16 MiB of quantization metadata, and an explicit 4 GiB workspace allowance. The 0.90 service fraction leaves physical headroom. Workspace and startup behavior still require measurement.

With an agent, the arbiter selects at most one estimated-feasible plan. Sera then loads the original weights with `fp8_per_tensor`, measures the workload, applies task and resource limits, and returns the live runner only on a pass. The unquantized baseline is marked infeasible, never fabricated. This path passed the live eight-task check. It establishes feasible deployment, not a speedup over a baseline that did not run. No multi-GPU allocation or wider search is implemented.

To run the same eight-task demo from this repository on the supplied GPU, install the `agent` extra and Weave in the existing environment, supply `WANDB_API_KEY`, and use the saved matching provider check:

```sh
python -m experiments.run_fit_demo \
  --project vvennela-n-a/wandb_agent_default_project \
  --provider-check evidence/provider-v2/result.json \
  --output-dir sera-runs/large-fit-demo \
  --priority throughput --interactive
```

Prepare the pinned original weights before presenting; the download is about 135.4 GiB and server startup is separate from request latency. The interactive option keeps a passing returned runner available for new prompts until blank input or EOF. Those extra prompts do not change the saved acceptance score. Without that option, the command probes the returned runner once and closes it. A failed deployment or failed post-return probe exits nonzero. This eight-task demo is not the full search benchmark.

## Cache-pressure pilot

`sera.pressure_pilot.run_pressure_pilot` runs the approved BF16-only profile: GPU memory fraction 0.025, eight concurrent 2,048-token inputs, context limit 4,096, and at most eight sequences. It uses synthetic padding, two warm-ups, and three waves. The predeclared scenario criterion is sampled KV use at least 80% plus at least one measured preemption, with zero request errors and successful cleanup. Otherwise it reports `not-established`. This pilot is separate from answer quality and candidate performance; there is no FP8 trial or automatic tuning.

The approved pilot reached 93.66% sampled KV use, zero preemptions, and zero request errors. Cleanup passed. The full scenario is **not established**. The constrained server budget represents a smaller card; the physical GPU remains a 96 GB card. See [pilot evidence](evidence/pressure-v1/README.md).
