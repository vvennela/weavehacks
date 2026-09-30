# Managed native Sera: implementation decision

Historical proposal. Implementation and measured results are in the [current release status](release.md).

September 29, 2026. The repository remains public. The product is a Sera-managed
agent with mandatory service-owned W&B tracing. The exported model runs on the
customer's hardware. Customers never receive our W&B key.

## Verified foundation

- Native MLX preparation, 4/8-bit affine weights, BF16 reference, sealed local
  checkpoints, and fresh-process loading work on the local M4 Pro.
- 8-bit passed 24/24 repeated easy checks with about 38% lower peak allocator
  memory. 4-bit failed quality. These were fixed compatibility checks.
- Worker requests are typed, have explicit deadlines, exclude service keys,
  and retain failures. Their controller verifies completed W&B traces remotely.
- W&B inference passed the existing 34-case serving-agent protocol. That does
  not certify a new native recipe proposal protocol.
- A built wheel installed into a clean environment and loaded the export for
  a new application request outside the checkout.

See [raw evidence and reproduction](../evidence/native-mlx-smoke-v1/README.md).

## Recommended integration

Add a typed native research controller behind the managed API. Reuse artifact
identity, worker cleanup, deterministic evaluation, and required tracing. Keep
the existing vLLM API available to reproduce its historical results.

The existing `pipeline.optimize` and its proposal schemas operate on vLLM
serving controls. MLX `bits` and `group_size` are different controls. Do not
encode them as unrelated vLLM settings or silently reinterpret an old profile.

The Sera operator registers a fixed profile containing the model revision,
workload and evaluator hashes, requested output formats, compatible recipes,
quality and performance gates, and total resource limits. A customer starts a
job using a Sera access token and an assigned profile. The job API must enforce
customer ownership and worker assignment on every read, result, cancel, and
artifact operation. An agent can propose only complete legal recipe IDs; it
cannot send executable code, alter a gate, or access hidden final outcomes.

The controller measures a fresh reference, requests proposals, executes bounded
workers, grades unchanged outputs, records rejected trials, and confirms a
candidate before returning its artifact. A failed or inconclusive run retains
the original checkpoint. Cancellation, restart, and trace-export failures must
not turn an incomplete result into a promoted artifact.

This controller/API integration is not implemented. The deployment host is also
needed before provisioning or live service acceptance.

## Backend boundary

MLX supplies native Apple execution. ModelOpt's supported CUDA export and serving
path should remain the requested NVIDIA adapter; its simulated quantization
timing is not a deployed-model result. The existing vLLM work is a starting
point for serving its exported checkpoints.

ROCm needs its own execution adapter. Current Transformers documentation marks
bitsandbytes ROCm support as partial, so a ROCm implementation must verify the
specific installed build and GPU through export, reload, and measured inference.
Neither a manifest backend label nor a unit test establishes hardware support.

Sources: [ModelOpt requirements](https://nvidia.github.io/Model-Optimizer/getting_started/_installation_for_Linux.html),
[ModelOpt export](https://nvidia.github.io/Model-Optimizer/deployment/3_unified_hf.html),
[Transformers quantization matrix](https://github.com/huggingface/transformers/blob/main/docs/source/en/quantization/overview.md).
No CUDA or ROCm validation was performed in this native MLX work.

## Formal research comparison still needs a decision

The [existing comparison proposal](modelopt-search-proposal-2026-09-28.md)
contains proposed trial counts, fixed and random controls, evaluation separation,
and confirmation rules. Its formal benchmark rules were not approved by the
MLX/export decision. The native smoke cannot substitute for that comparison.

Freeze the native profile and comparison before collecting research outcomes.
Use the same allowed recipes, hardware, data access, trial limits, and quality
requirements for Sera and its non-agent controls. Report preparation, agent, and
worker time separately and include failures. An exhaustive fixed recipe search
can outperform an agent on a small space; the demo must report the measured
result rather than promise agent superiority.
