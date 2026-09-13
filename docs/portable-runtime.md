# Explicit model and multi-GPU runner

Status: implemented and tested offline. No live multi-GPU result exists. The available Molab host has one GPU. This is a runner for explicit experiments, not automatic multi-GPU optimization through `sera.optimize`.

`PortableSeraModel` accepts a pinned model identity and an explicit list of physical GPU UUIDs. It starts one vLLM service with tensor parallelism across 1, 2, 4, or 8 GPUs on one Linux host. Tensor parallelism divides model computation across GPUs. Its command uses vLLM's single-host `mp` backend. See [vLLM engine arguments](https://docs.vllm.ai/en/stable/configuration/engine_args/) and [model configuration checks](https://docs.vllm.ai/en/latest/api/vllm/config/model/).

The default `SeraModel`, `sera.optimize`, and certified agent control schema are unchanged.

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
3. Connect this explicit adapter to the autonomous optimizer's model descriptors, fit planning, candidate generation, deterministic validator, and returned-runner restoration. The current agent schema cannot propose tensor-parallel changes.
4. Certify the expanded provider schema and compare measured TP configurations under equal workloads and quality rules before enabling automatic multi-GPU recommendations.

DGX Spark, different CUDA stacks, multi-node execution, and multi-GPU FP8 remain unverified. This implementation does not close the complete multi-GPU product requirement.
