# Native MLX checkpoint checks — September 29, 2026

The 8-bit checkpoint passed the existing eight easy tasks in each of three
repetitions. Its measured peak MLX allocator memory was 38.25% below BF16.
The 4-bit checkpoint failed one answer in every repetition and is rejected.
These are fixed adapter checks. An agent did not select these recipes, and this
record does not establish an agent-versus-fixed-recipe advantage.

| Export | Exact answer checks | Peak allocator bytes | Request latency min / median / max, ms |
| --- | --- | --- | --- |
| BF16 | 24/24 | 1,390,969,552 | 357.23 / 390.18 / 416.77 |
| 4-bit affine | 21/24 | 558,105,356 | 325.09 / 363.15 / 391.20 |
| 8-bit affine | 24/24 | 858,948,316 | 320.92 / 347.08 / 388.61 |

The memory reduction is 532,021,236 bytes. This measures the MLX allocator on an
Apple M4 Pro with 24 GiB unified memory. It does not measure system-wide free
memory, CUDA VRAM, or additional workload capacity. Latency ranges are raw
observations, not a validated speedup claim. No formal noise or power-mode
acceptance block was registered for this compatibility check.

The model is `Qwen/Qwen3-0.6B`, pinned at
`c1899de289a04d12100db370d81485cdf75e47ca`. All exports came from the same local
snapshot. Export manifests bind source, recipe, runtime versions, tokenizer,
configuration, and all weight bytes. Checkpoints use MLX safetensors; they are
not PyTorch-compatible exports. Model weights remain local under the ignored
`sera-runs/mlx-native-smoke/` directory and are not included in this evidence.

Controls: greedy decoding, seed 0, concurrency 1, one warmup per task, 64 output
tokens, and three complete repetitions. JSON schemas specify only the requested
answer type, never its correct value. The existing strict grader is unchanged.
No failing output was stripped, repaired, or excluded. The initial unstructured
BF16 and 4-bit failures are retained alongside the structured results.

Fresh disposable workers loaded the sealed checkpoints and repeated the check:

- [8-bit confirmation](int8-worker-confirmation.json): 24/24, peak 858,030,812 bytes.
  Its [completed W&B trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a0ee86-5f21-7822-81d3-7e144bafd606)
  was read back successfully.
- [BF16 control](bf16-worker-control.json): 24/24, peak 1,390,969,552 bytes.
  Its [completed W&B trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a0ee88-b4df-71d4-9757-18ac8f2c4479)
  was read back successfully.

The worker received no W&B or agent key. Its controller owned trace submission.
This separates process environments; it is not a filesystem or network sandbox.
Each worker had an explicit 180-second deadline. Unit tests cover process-group
termination, retained timeout evidence, credential exclusion, and mismatched
job output. These checks do not establish live outage or sustained-load reliability.

The [installed-wheel probe](installed-wheel-probe.json) loaded the 8-bit export
from a clean package installation outside the checkout and answered a new
`7 + 8` request with `{"answer": 15}`. It records the wheel hash and installed
module location. This is one application request, not an unseen-task benchmark.

The separate [W&B provider check](provider-check.json) passed 34/34 cases on the
first attempt using `openai/gpt-oss-20b`. It validates the existing serving-agent
response contract, not a new MLX recipe-selection contract. The managed transport
removes an incompatible root schema union while retaining local validation.
The required Weave stack pins `gql==4.0.0` to avoid the reproduced HTTPX/HTTPX2
authentication incompatibility.

## Reproduce the checkpoint check

On Apple silicon, install the locked runtime from the repository:

```sh
uv sync --python 3.12 --locked --extra dev --extra swarm --extra mlx
```

The Sera operator supplies `WANDB_API_KEY` and `SERA_PROJECT` through its private
environment. The following code exports a new checkpoint in a disposable worker:

```python
from sera.native_worker import run_native_job

run_native_job({
    "operation": "prepare", "backend": "mlx",
    "source": {"model_id": "Qwen/Qwen3-0.6B",
               "revision": "c1899de289a04d12100db370d81485cdf75e47ca"},
    "destination": "/absolute/path/to/new-int8-checkpoint",
    "recipe": {"bits": 8, "group_size": 64},
}, output_dir="sera-runs/new-int8-preparation", timeout_seconds=180)
```

Use a cached source for that preparation deadline; first-time downloads are
included in the deadline. Existing outputs are never overwritten. Then run:

```sh
uv run --locked --extra swarm --extra mlx python scripts/check_native_checkpoint.py \
  --artifact /absolute/path/to/new-int8-checkpoint \
  --output sera-runs/new-int8-check \
  --timeout-seconds 180
```

This command requires a remotely verified W&B trace before writing
`verified.json`. Raw worker and grading records remain available if tracing
fails. Repeat with `bits: 16` for BF16 and `bits: 4` for the failed recipe.
The command is operator review tooling, not the proposed customer `Sera.Optimize` API.

## Remaining release work

Connect native recipes to the research controller and a bounded managed job API;
freeze the formal agent/control comparison; validate CUDA and ROCm on actual
hardware; and deploy to the selected service host. No managed service has been
deployed, no formal winner has been promoted, and no competition submission has
been made. The repository remains public; credentials are excluded.
