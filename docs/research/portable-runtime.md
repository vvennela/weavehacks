# Explicit model and multi-GPU runner

Status: runner and fixed-hardware optimization are implemented and tested offline. No live multi-GPU result exists. The available Molab host has one GPU. Sera can search scheduling and execution settings on a caller-selected GPU assignment; it cannot select GPU counts or new precision formats automatically.

`PortableSeraModel` accepts a pinned model identity and an explicit list of physical GPU UUIDs. It starts one vLLM service with tensor parallelism across 1, 2, 4, or 8 GPUs on one Linux host. Tensor parallelism divides model computation across GPUs. Its command uses vLLM's single-host `mp` backend. See [vLLM engine arguments](https://docs.vllm.ai/en/stable/configuration/engine_args/) and [model configuration checks](https://docs.vllm.ai/en/latest/api/vllm/config/model/).

The default `SeraModel`, `sera.optimize`, and certified agent control schema are unchanged. `RuntimeConfig` can now record TP counts 1, 2, 4, and 8, but `SeraModel` and shared single-GPU placement still reject TP above 1. A configuration record alone does not authorize a multi-GPU launch.

## Run an explicit experiment

Install the existing GPU environment with vLLM 0.26.0 first. The Sera wheel does not install CUDA or vLLM. Model metadata uses `huggingface_hub`, which is included in the GPU runtime's dependencies. Use `HF_TOKEN` for a gated model; never put a token in this script.

Find physical identities with `nvidia-smi --query-gpu=uuid --format=csv,noheader`. Set `MODEL_REVISION` to a full, lowercase, 40-character commit hash from the model repository. Select only GPUs assigned to this job. If `CUDA_VISIBLE_DEVICES` is set, use full GPU UUIDs in it. Numeric CUDA masks are rejected because CUDA ordinal order can differ from `nvidia-smi` order.

```python
import os
from sera import HardwareAssignment, ModelDescriptor, PortableSeraModel, RuntimeConfig

model = ModelDescriptor(
    model_id=os.environ["MODEL_ID"],
    revision=os.environ["MODEL_REVISION"],
)
hardware = HardwareAssignment(gpu_uuids=os.environ["SERA_GPU_UUIDS"].split(","))

with PortableSeraModel(
    model=model,
    hardware=hardware,
    configuration=RuntimeConfig(),
    artifact_dir="portable-run",  # Must not already exist.
) as runner:
    response = runner.generate("What is 2 + 2? Return only the number.")
    print(response.text)
    print(response.latency_ms)
```

This example checks the returned interface, not workload quality or performance. Use saved representative prompts, repeated timing passes, and the same versioned task evaluator before comparing configurations. A fast answer to one question is not a benchmark.

## Run the existing swarm on fixed hardware

`optimize_on_hardware` uses the existing public API setup, measurement loop, three investigators, arbiter, quality gate, progress stop rule, Weave trace path, and returned-runner restoration. It does not contain a second optimization engine. Configure the same `SERA_AGENT_PROVIDER`, `SERA_AGENT_MODEL`, `SERA_PROJECT`, `SERA_PROVIDER_CHECK`, relay when applicable, and `WANDB_API_KEY` described in [the simple API guide](simple-release.md).

```python
from sera import Constraints, optimize_on_hardware

with optimize_on_hardware(
    model=model,
    hardware=hardware,
    prompts=representative_prompts,
    evaluation=score_task,  # Your deterministic task evaluator.
    evaluation_version="your-task-suite-v1",
    constraints=Constraints(quality_floor=0.99),
    output_dir="portable-optimization",
) as result:
    result.print_summary()
    answer = result.models[0].generate("A new task") if result.models else None
```

The default call runs the configured swarm with automatic legal scheduling/execution candidates, concurrency 1/2/4/8, and plateau plus one confirmation round. There is no fixed total trial cap. As with `sera.optimize`, explicit lower-level agent/search options retain their existing behavior. `mode="fixed"` uses one batching candidate and no provider. Supplying a different baseline requires its TP count to match the explicit assignment; a default fixed candidate that is identical to that baseline is rejected.

Every trial and restored winner uses the same model revision and ordered GPU UUIDs. Its saved configuration and hash contain the actual TP count, not a placeholder of one. The agents cannot propose a TP change. Portable runs never inherit FP8 permissions from the model name, including when the name is one of the demonstration Qwen models. Provider response schemas and their certificate hash remain unchanged.

This path requires a versioned task evaluator and quality floor. It first measures a BF16 baseline. If the baseline cannot load, it reports the startup failure and stops; it does not automatically quantize an unfamiliar model. New-model memory fit is unknown until runtime startup. Search values use measured input lengths, workload, latency, and telemetry—not the Qwen demonstration models' parameter counts or fit estimates. Only the existing pinned Qwen72B default path has fit-first FP8 planning.

## Enforced boundaries

- One pinned dense Qwen2, Qwen3, or Llama text model. No model-ID allowlist, remote model code, prequantized checkpoint, expert model, or multimodal model.
- BF16 weights and KV only. New models and tensor-parallel paths do not inherit FP8 certification from the single-GPU demo.
- Actual hardware inventory, exact assignment, unchanged parent UUID visibility, idle memory, matching device type/capability/capacity/driver, BF16-capable GPUs, and no MIG partitions are checked before model metadata or weights are downloaded.
- The exact pinned `config.json` is then read. Attention-head, hidden-size, intermediate-size, KV partition/replication, and context checks run before vLLM can download weights. These checks establish structural eligibility, not kernel compatibility or memory fit.
- The requested memory fraction is recorded separately for each GPU. vLLM startup must establish actual fit. This adapter does not infer weight size, pool unequal GPU memory, or claim that total VRAM alone proves fit.
- The child receives only the selected GPU UUIDs, in declared rank order. Model and tokenizer use the same revision. No notebook dependency is required.
- The runner saves its effective tensor-parallel configuration, model metadata and hash, software versions, launch command, per-device memory, startup time, errors, and cleanup in `runtime.json`. Peak memory is sampled, not an exact allocator maximum.
- Cleanup kills only the owned process group and checks every assigned GPU against its own starting memory, with 128 MiB tolerance. A leak on one GPU cannot be hidden by another GPU's lower usage. Cleanup errors stop the caller; they do not count as successful trials.

Preflight is not a GPU reservation service. The host scheduler must prevent other jobs from taking these GPUs during a trial. No automatic provisioning, spending, distributed-host coordination, or restart after a killed controller is added.

## What remains for item 6

1. Run real 2-, 4-, and 8-GPU startup, generation, measured task-quality, per-device telemetry, and cleanup checks on supplied hardware. Current evidence contains only offline test doubles for those device counts.
2. Measure model/kernel/precision compatibility for each additional requested architecture and model revision. Metadata eligibility alone does not certify a model.
3. Add model-specific fit planning and measured precision compatibility before automatic quantization for additional models. Fixed-hardware scheduling search is integrated, but automatic placement and TP-count selection are not.
4. Expand and certify the provider schema for TP selection, then compare measured TP configurations under equal workloads and quality rules before enabling automatic hardware recommendations.

DGX Spark, different CUDA stacks, multi-node execution, and multi-GPU FP8 remain unverified. This implementation does not close the complete multi-GPU product requirement.
