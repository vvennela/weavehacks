# Sera as an engineer-facing optimizer

Date: 2026-09-24. Scope: optimization, execution, evaluation, and developer integration. Frontend and notebooks are excluded.

## Conclusion

The product should be an optimization library that owns a measured experiment loop and returns a usable, verified artifact. It should accept an engineer's workload, runtime or kernel, correctness contract, resource limits, and budget. Codex agents propose changes. Sera controls what can execute and what can be retained. The evaluator, not the agent, determines success.

The existing package implements part of this contract for narrow vLLM configurations. It does not implement a general optimizer for arbitrary models or CPU kernels. Its useful assets are typed candidate validation, task-quality gates, measured feedback, owned runtime cleanup, local evidence, and checkpointing. These deserve reuse. The model-specific assumptions should move into adapters rather than define the whole product.

The earlier MatMul task used a Codex subagent named `sera`. It did not invoke this repository's Python package. Its reported 1,160–1,449 GFLOP/s cannot be credited to `import sera`. The new CPU integration in this change is the first package path tested here for this task.

## What an engineer should supply

| Input | Required contract |
| --- | --- |
| Subject | A pinned model/runtime configuration or kernel source and ABI; retain the original artifact. |
| Workload | Real input shapes, data types, layouts, batch sizes, sequence lengths, and traffic mix. |
| Correctness | A versioned independent reference and tolerance; separate search and final cases. |
| Objective | One primary metric plus hard quality, latency, memory, and resource constraints. |
| Execution | An owned local or remote worker with explicit hardware capabilities and isolation policy. |
| Budget | Maximum trials, elapsed time, agent calls, and resource use. |
| Result | Verified source/configuration, evidence, compatibility limits, and an explicit unsuccessful outcome. |

“Any engineer can slot it in” means the adapter boundary is stable and setup is small. It does not mean every model and hardware combination works without an adapter. A CPU MatMul kernel is an operator-level capability test; it does not prove faster end-to-end model inference.

## Core design

1. Preflight the workload, reference implementation, compiler/runtime, hardware, and objective. Reject missing capabilities before an agent call.
2. Freeze a deterministic baseline. Record seeds, input identities, build flags, versions, thread settings, hardware, and warmup. Preserve all repetitions and timing spread.
3. Give a Codex agent the allowed source/configuration, public contract, and measured history. Require a concrete hypothesis and an explicit artifact change.
4. Validate the proposed artifact, then run correctness before performance. Compilation failure, wrong answers, timeout, and invalid telemetry are outcomes, never improvements.
5. Measure candidate and unchanged control in a fixed reproducible interleaved order. Reject gains inside observed noise. Preserve original and current-best artifacts separately.
6. Select only an eligible improvement. Perform a separate final evaluation on the frozen selected artifact. Return no deployable artifact if that final check fails.
7. Export the accepted change with its source hash, compatibility requirements, raw measurements, and exact reproduction command. Installation into a serving model is a separate explicit adapter action.

The agent should not own the metric, seeds, acceptance rule, evaluator source, or resource accounting. A model answer saying “faster” has no authority. More agents do not repair a weak evaluator or an incomplete search space.

## Existing implementation: strengths and gaps

| Area | Existing evidence | Gap for the intended product |
| --- | --- | --- |
| Search | Three-investigator proposals, peer review, arbiter, typed controls, expanding neighborhoods | vLLM-specific controls; no source-editing contract in stable paths |
| Quality | Caller evaluator and fixed quality floor; quick mode is explicitly unverified | Small prompt sets; evaluator behavior is not cryptographically bound on resume |
| Measurement | Warmup, per-load request records, task checks, timing and memory | Repeated-prompt results do not establish cold/unseen workload gains; no general statistical acceptance contract |
| Lifecycle | Owned processes, cleanup checks, SQLite ledger and explicit resume | No proof of unattended live outage recovery; generic native-code worker absent |
| Adoption | Python API and wheel; pinned live demonstrations | Default model restrictions, exact runtime requirement, provider certificate and Weave setup |
| Scope | `sera` and independent `sera_loop` both ship | Two product paths with separate contracts; select one public core before expanding support |

The saved roughly 20% latency gains are useful evidence for repeated-prompt Qwen/vLLM workloads. They do not prove that Sera beats random search, tunes arbitrary models, or generates better CPU kernels.

## CPU work delivered in this change

`sera.kernel_search` is an explicitly experimental source-search path. `sera.kernel_tools` connects it to a Codex CLI proposer and the existing frozen `kernel-opt` evaluator. It avoids forcing C kernels into the vLLM configuration schema. It is a narrow integration seam, not a replacement production engine.

The Codex adapter checks ChatGPT login, strips API credentials from the child environment, ignores user provider configuration, forces the OpenAI provider with ChatGPT login, and supplies a read-only policy. The agent returns structured C source; Sera writes each candidate into a distinct trial directory. No hosted AutoLab agent, W&B, or API-key client is used by this path. Authentication follows the [official Codex non-interactive workflow](https://learn.chatgpt.com/docs/non-interactive-mode) and [authentication documentation](https://learn.chatgpt.com/docs/auth).

The scorer invokes the frozen Hills evaluator, verifies each signed report, and checks evaluator, workload, machine, compiler, flags, OS, and architecture identity before comparison. It neither reads nor changes private seeds. The search saves source hashes, raw reports, hypotheses, repeated scores, unchanged controls, and one final held-out report. A hard candidate cap and command timeouts bound the research run.

The target is strictly greater than **1,780 GFLOP/s**, with the full single-threaded row-major float32 product at n=512, tolerance 0.002, no external libraries, and the existing fixed compiler flags. Packing, allocation, and call overhead remain inside the evaluator's timing. The evaluator's best-of-three rule is unchanged; Sera adds repeated reports and conservative promotion above it.

## Remaining production gates

- **Native execution isolation:** the local Hills path executes trusted research code as the user. Read-only agent tools and timeouts do not sandbox a compiled kernel. Production needs a disposable worker with no credentials, network, or unrelated mounts, plus CPU, memory, process, and output limits.
- **Complete CPU correctness contract:** exercise odd shapes, tails, alignment, alias rules, output overwrite, nonfinite values where supported, and numerical edge cases. The existing hill's n=96/n=512 checks alone are not general ABI certification.
- **Durable kernel recovery:** the experimental JSON journal is inspectable after interruption but does not resume execution. Use an owned worker and transactional state before unattended production.
- **Hard deadline across agents:** evaluator timeouts are bounded by remaining run time; arbitrary caller-supplied proposer callbacks must enforce their own timeouts. The provided Codex proposer has a separate command timeout.
- **End-to-end integration:** a winning C file still needs CPU capability dispatch, build/package handling, and integration into a real model operator. Benchmark a representative model before claiming model speedup.
- **Search competence:** compare against a fixed baseline and equal-budget deterministic/random search on several workloads and CPUs. Report failed runs and noise; do not select only successful examples.

The independent [GPT-6 Luna audit](sera-production-audit-luna-2026-09-24.md) provides prioritized production findings. The intended next release is a supervised CPU research adapter with clear failure behavior, not an unattended general optimizer.
