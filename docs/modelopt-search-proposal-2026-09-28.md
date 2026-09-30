# ModelOpt search comparison proposal

Historical proposal. Implementation and measured results are in the [current release status](release.md).

Status: ModelOpt integration and backend-independent direction requested;
benchmark rules pending user decision; no GPU experiments run.
Date: 2026-09-28.

Update, September 29: the user approved native MLX first, followed by CUDA and
ROCm runtime adapters, and optimized checkpoint export. The product is managed
by Sera with our W&B key; the repository stays public. These decisions supersede
the earlier CUDA-first proposal. Formal agent-versus-control benchmark rules
still need a decision. [Native MLX smoke results](../evidence/native-mlx-smoke-v1/README.md)
are compatibility evidence, not that comparison.

## User-defined product goal

Sera should be an autonomous research agent that optimizes ML workloads for the
user's current hardware. This is the product direction, not a claim that the
current package already supports arbitrary workloads or hardware.

The user linked [Chris Short's ModelOpt post](https://x.com/ChrisShort/status/2104016943107731934),
which lists quantization, distillation, pruning, neural architecture search, and
speculative decoding. ModelOpt supplies implemented methods within these
families for its supported stack. The families provide a starting vocabulary for
Sera's research; they do not define all possible optimizations or make their
implementations portable to every device.

The intended research loop is:

1. Inspect the supplied workload, available hardware, and installed runtime.
2. Establish a reproducible baseline and identify measured bottlenecks.
3. Use technique families and prior evidence to form concrete hypotheses.
4. Build or configure an experiment through a compatible execution adapter.
5. Check correctness or task quality, then measure performance and resource use.
6. Use the result to revise hypotheses, investigate combinations, and choose the
   next experiment within the user's fixed limits.
7. Confirm the selected artifact on fresh measurements and return it with evidence,
   or report that no verified improvement was found.

For each technique, distinguish its purpose, its prerequisites, the available
implementation, and measured support on the current device. For example,
quantization is a technique family; a ModelOpt recipe and an MLX implementation
are distinct execution paths. A smaller checkpoint alone does not establish a
faster workload.

ModelOpt is both a source of technique knowledge and an execution tool where
supported. Sera owns the research loop across available tools. This direction
does not authorize new compute spending, altered quality gates, or training
budgets. Distillation and training-based methods require resources and data that
must be part of the declared experiment contract.

## Question

Does Sera choose better ModelOpt experiments than a non-agent search under the
same trial budget, quality rules, hardware, and workload? Separately, does its
selected artifact improve on NVIDIA's stock AutoQuantize recipe after including
the cost of finding and preparing that artifact?

These are different comparisons. A faster model than stock AutoQuantize alone
does not establish that agents search better than grid or random search.

The fixed-candidate comparison below tests experiment selection only. It does
not fully test the product goal of generating and revising experiments. Keep it
as a controlled first comparison. A subsequent live research comparison must
allow hypothesis-driven experiments and measure the full preparation and search
cost against non-agent methods with the same allowed tools and resources. Its
experiment rules remain pending; do not present replay results as proof of that
broader capability.

## Findings

- Sera has no ModelOpt integration. Its runtime configuration supports only
  `fp8_per_tensor` weight quantization. Its portable runtime permits BF16 only.
- `benchmarks.collection` and `benchmarks.search` already provide frozen
  identities, quality checks, grid search, 20 seeded random searches, and replay
  that exposes only selected outcomes. The existing agent adapter cannot select
  distinct ModelOpt checkpoints or arbitrary multi-setting candidates.
- The current benchmark contract allows 2–12 candidates and a search budget of
  1–8 trials, strictly smaller than the candidate count. It does not define a
  completed agent-superiority acceptance rule.
- The previous eight-question repeated-prompt workload supports only a narrow
  pilot claim. It is not a general model-quality benchmark.
- The local host is an arm64 Mac without `nvidia-smi`. Codex reports ChatGPT
  login. Earlier GPU evidence identifies a Molab RTX PRO 6000 Blackwell; this
  is historical evidence, not a verified live connection.

## Proposed integration

The user requested that Sera be independent of AMD, MLX, or CUDA. Keep the core
experiment loop independent of those systems. Backend adapters declare supported
techniques, prepare artifacts, run measurements, report evidence, and clean up
their resources. The core controls budgets, evidence access, quality checks, and
selection. Backend-specific configuration remains explicit and hash-bound.

The original CUDA comparison below is retained as a proposal for the later
CUDA adapter; native MLX is now first. It does not provide
AMD ROCm or Apple MLX support. Those need separate adapters and compatibility
tests; a shared interface alone is not working multi-backend support. Agent versus
non-agent comparisons run on the same backend and hardware. Do not pool timing
results across CUDA, ROCm, MLX, or the existing CPU kernel path.

Add the ModelOpt adapter as an opt-in experimental path in `sera`, with a separate
versioned benchmark manifest. Reuse measurement, grading, evidence hashing, and
process cleanup where their contracts fit. Do not silently widen old frozen
manifests. Implement only the ModelOpt execution path in this first comparison;
the backend-independent boundary must not require unimplemented adapters.

1. Pin ModelOpt 0.47.0 and verify its compatibility with the selected GPU
   environment. Preserve the existing working environment; use an isolated
   environment if its dependency set conflicts.
2. Load an exact base-model and tokenizer revision. Calibrate through ModelOpt,
   then export a real checkpoint using its unified Hugging Face export.
3. Record recipe, calibration inputs, seeds, source revision, package versions,
   export file hashes, preparation time, and checkpoint size.
4. Serve the exported checkpoint with a supported vLLM ModelOpt loader. Measure
   this deployed model; simulated quantization timing is not inference speed.
5. Let agents select complete legal candidate IDs with reasons and evidence.
   Keep model loading, execution, validation, and acceptance in deterministic code.
6. The September 28 product direction replaces the earlier GPU-product
   ChatGPT-login proposal with an API-key entry point and mandatory W&B tracing.
   The user selected W&B; its account access and investigator model are now
   verified by the September 29 provider check. Preserve prompts, responses,
   setup cost, and the existing acceptance gates. The separate CPU research
   contract still uses Codex through ChatGPT login and its 180-second timeout.

Recommendation: start with post-training quantization. Pruning, training,
distillation, and speculative-decoding deployment are later experiments.

## Proposed comparisons

| Arm | Purpose |
| --- | --- |
| BF16 base model | Quality and serving-speed reference |
| Stock ModelOpt AutoQuantize | NVIDIA's non-agent automatic optimization reference |
| Fixed grid over ModelOpt candidates | Deterministic search control |
| Seeded random over the same candidates | Search control without model reasoning |
| Sera over the same candidates | Agent-guided search |

For the grid/random/Sera comparison, all arms must have exactly the same legal
candidate set and evidence access. Include AutoQuantize-backed candidates where
supported; agents must not get exclusive access to the stronger optimization
method. Stock AutoQuantize can search a different internal space, so report that
comparison separately rather than treating its internal operations as one equal
Sera trial.

AutoQuantize minimizes an estimate of quantization damage under an effective-bit
constraint. Effective bits measures average weight storage cost; it is not measured
latency. Record this distinction and enforce the same declared resource ceiling
when comparing final artifacts.

Proposed pilot search budget: four candidate trials per grid/random/Sera run,
five independent Sera runs, and the existing 20 random seeds. Freeze a candidate
set larger than four and no larger than 12 after compatibility checks. Fix its
order before performance results exist. Failed trials consume budget; an agent
failure must not fall back to grid search.

Collecting all candidate outcomes once and replaying policies provides a cheaper
first search comparison. Label this as replay, keep unseen outcomes out of agent
context and tools, and account for all collection costs. It does not measure live
end-to-end optimization time. If the user chooses replay, confirm the selected
artifacts on fresh GPU measurements before reporting a speed advantage.

## Measurement and reporting

- Pin GPU identity, driver, runtime, source weights, tokenizer, calibration data,
  evaluation data, seeds, decoding settings, and warmup. Hold serving settings
  constant for the quantization comparison; do not give Sera extra batching or
  caching controls while leaving the stock comparison untuned.
- Separate calibration, search evaluation, and final evaluation inputs. Choose
  the workload and quality scorer before collecting candidate results. Retain
  the existing 0.99 task-quality floor for a compatibility pilot; do not claim
  that eight passing questions establish broad quantization quality.
- Report worst per-load p95 latency, output tokens per second, quality, sampled
  device memory, checkpoint size, preparation/search time, and agent overhead.
  Report the full distributions, invalid candidates, and incomplete runs.
- Repeat GPU measurements with interleaved unchanged controls. Proposed final
  check: ten paired blocks for the selected artifacts, with balanced run order.
  Reuse identical artifacts rather than recalibrating during final confirmation.
- Keep trial efficiency, GPU time, and total elapsed time as separate results.
  Equal trial counts do not imply equal cost. Include calibration, export,
  startup, and agent time in total optimization cost.
- Report ties, losses, and inconclusive results. The pilot reports effects and
  spread, not a general agent-superiority claim. A formal pass/fail claim needs
  a user-approved rule frozen before data collection.

## Decisions needed before implementation and live work

1. Approve the pilot comparison rules above, or specify changes. The user already
   requested ModelOpt integration and the backend-independent direction.
2. Supply an available NVIDIA GPU/session and maximum GPU time or spend. No paid
   compute is provisioned by this proposal. The global cap must include preflight,
   calibration/export, collection, failed trials, and final measurements.
3. Choose the model/workload scope: the existing Qwen3-0.6B workload gives a small
   compatibility pilot; a representative application workload provides a more
   useful result. NVIDIA documents Qwen3-8B deployment, while Qwen3-0.6B requires
   a compatibility test. Model and dataset revisions must be pinned before use.

GPU capability determines which recipes can be tested. NVFP4 serving requires
Blackwell; do not silently substitute FP8-only results for an NVFP4 experiment.
Freeze the exact recipe set and machine-readable run manifest before measuring
candidate performance. Stop on an invalid baseline or exhausted global budget.

## Preparation validation

On the current checkout, these existing tests passed: 82 passed in 3.01 seconds.

```text
.venv/bin/python -m pytest -q tests/test_search_benchmark.py tests/test_search_policy.py tests/test_benchmark_collection.py
```

These checks validate existing software behavior. They do not validate ModelOpt
integration, GPU compatibility, or an agent advantage. Implementation will use
failing behavior tests first, then targeted tests and a real GPU smoke test.

## NVIDIA sources

- [PTQ and AutoQuantize examples](https://github.com/NVIDIA/Model-Optimizer/blob/main/examples/hf_ptq/README.md)
- [AutoQuantize objective](https://nvidia.github.io/Model-Optimizer/announcements/autoquantize.html)
- [Support matrix](https://nvidia.github.io/Model-Optimizer/guides/0_support_matrix.html)
- [Unified export and vLLM deployment](https://nvidia.github.io/Model-Optimizer/deployment/3_unified_hf.html)
- [ModelOpt 0.47.0 release](https://github.com/NVIDIA/Model-Optimizer/releases/tag/0.47.0)

## Concrete adapter boundary for review

The current control schema cannot identify an exported checkpoint:
`Candidate` contains only `RuntimeConfig`, proposals change one serving setting,
and both the public API and pipeline admit only `PortableRuntimeFactory` for
external models. The portable runner rejects prequantized metadata and launches
BF16 from a Hub revision. Adding a recipe name to that config cannot implement
ModelOpt export or deployment.

The proposed change is one opt-in artifact path through the existing optimizer:

- Preparation takes a pinned base model/tokenizer, a complete legal recipe,
  calibration input identity and seed, and an explicit hardware assignment.
- Its output is a durable local checkpoint plus a manifest containing source
  revisions, recipe, calibration identity, package versions, preparation time,
  file hashes and size. A partial export is never a serving candidate.
- A ModelOpt-aware runner verifies the manifest and starts the exported local
  path with its supported vLLM loader. It records the actual command, tokenizer,
  GPU identity, quality, memory, timing, and cleanup through existing contracts.
- Search chooses immutable candidate IDs and reads evidence. Backend details
  stay inside preparation and serving. A changed recipe or checkpoint requires
  a different identity; it cannot reuse a prior measurement.
- The returned result contains the selected artifact and reproduction command,
  plus the prior usable artifact when there is no verified improvement.

This changes candidate identity, serving input, and result persistence, so it is
an architecture decision for user review before implementation. It does not
require changing the CPU path or existing frozen control-search manifests.

Validation must cover export failure and cancellation, checkpoint modification,
wrong tokenizer/loader, illegal recipe selection, quality failure, failed memory
sampling, trial accounting, resume, and worker cleanup. The live acceptance
sequence is baseline → actual export → fresh-process serving → fixed-quality
checks and paired measurements → cleanup → independent reload of the selected
artifact. Workload, GPU access, budgets, and acceptance rules remain unresolved.
