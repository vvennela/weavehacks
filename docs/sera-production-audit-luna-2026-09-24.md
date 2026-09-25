# Sera production audit — GPT-6 Luna

Date: 2026-09-24  
Scope: `import sera` core library and its supported runtime. Frontend, notebooks, and `sera_loop` are excluded. This report does not modify product code.

## Verdict

**Not ready for general production use or CPU kernel optimization.** The current release is a carefully measured, controlled vLLM inference experiment for a narrow NVIDIA setup. Its own release record says the latest installed-wheel joint run missed one latency gate, and live outage recovery and soak testing are deferred. The code has good controls around candidate validation, quality gates, process ownership, and saved evidence. It does not provide a CPU execution-kernel adapter or a general drop-in model optimizer.

The `kernel-opt` AutoLab hill and its earlier 1160–1449 GFLOP/s result are a separate project and are not evidence for this Python Sera package. The `/root/sera` agent name in that task did not refer to this repository's `sera` package. The user's reported 1780 GFLOP/s on the same M4 Pro hill is also external to this library. The mature paths audited here invoke vLLM; any new CPU-kernel adapter/search work is experimental and has not been reviewed or accepted by this audit.

## Prioritized findings

### P0 — The current optimizer cannot modify CPU execution kernels

The `SeraModel` runtime launches vLLM's OpenAI API server and requires Linux plus an NVIDIA GPU. The default API accepts only the two pinned Qwen model IDs, while candidate configuration is restricted to a small set of vLLM controls. The portable adapter is also a vLLM/GPU path and only accepts BF16 weights and KV. There is no CPU backend, kernel ABI, build/validation path, or CPU correctness/performance gate in these stable paths. See [api.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/api.py:97), [runtime.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/runtime.py:230), [config.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/config.py:48), and [portable_runtime.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/portable_runtime.py:17).

**Impact:** The existing optimizer cannot satisfy “get Sera ready to modify CPU execution kernels.” Treat the new kernel integration as a separate experimental feature until it can select, run, validate, and roll back a CPU kernel without passing through vLLM-only assumptions.

### P1 — The managed model process inherits provider and user credentials

`_child_environment` starts with a copy of the full parent environment. The resulting environment is passed to the vLLM server process. It can therefore include `WANDB_API_KEY`, `OPENAI_API_KEY`, `HF_TOKEN`, relay configuration, and unrelated application secrets. See [runtime.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/runtime.py:123) and the `Popen` call at [runtime.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/runtime.py:260).

**Impact:** A bug or compromise in the inference process exposes credentials that are only needed by the optimizer or trace client. Build the child environment from a small allowlist, then add only CUDA/runtime variables and credentials proven necessary for model download. Remove credentials after weights are loaded if the runtime permits it.

### P1 — Default search has no hard trial, time, or cost ceiling

The configured API sets `Budget(max_candidate_trials=None)`, and its docstring describes plateau-plus-confirmation stopping without a total cap. See [api.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/api.py:48) and [api.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/api.py:110). `Budget` supports an explicit cap of up to eight trials, but the default has no total cap. The live model startup and generation calls can each consume substantial GPU time.

**Impact:** Ongoing measured progress can keep an unattended run alive and consume an unbounded amount of GPU time and provider usage. Require or default to a hard trial/time budget for production; retain an explicit opt-in for uncapped research runs.

### P1 — Task-evaluator identity is not protected on resume

Recovery checks that a callable is supplied and that its `evaluation_version` string equals the saved version. It cannot verify that the callable has the same behavior. See [recovery.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/recovery.py:121). A different evaluator can be passed with the same version string, then influence subsequent selection under a checkpoint created by another evaluator.

**Impact:** A resumed run can mix incompatible quality evidence while reporting one evaluator version. Require a caller-supplied evaluator artifact/code hash (or a signed immutable evaluator identity) and persist it in the run specification. Test that a changed evaluator is rejected.

### P1 — The “drop-in model” contract is much broader than the implemented API

The default `sera.optimize` path allows only `[Qwen/Qwen3-0.6B]` or `[Qwen/Qwen2.5-72B-Instruct]`; it rejects other model IDs and all multi-model lists. Prompts are limited to 1–32 items. The GPU runner pins vLLM to exactly 0.26.0 and only enables tested FP8 paths on compute capability 12.0. See [api.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/api.py:97), [api.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/api.py:104), [api.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/api.py:106), and [runtime.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/runtime.py:218).

**Impact:** This is a narrow supported-model product, not a general drop-in optimizer. Keep the public claim narrow until arbitrary model revisions, runtime compatibility, and resource limits have an explicit adapter contract and live acceptance. The broad `gpu` dependency ranges in [pyproject.toml](/Users/vishnuv/Documents/Documents/weavehacks/pyproject.toml:33) are not a reproducible installation recipe; the docs correctly warn that they do not define the checked runtime.

### P1 — Configured runs persist and export raw prompts and model outputs

The pipeline stores supplied prompts in `result.json`; trial records retain generated text, and trace export sends prompt/response records to Weave. See [pipeline.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/pipeline.py:332) and [measurement.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/measurement.py:41). The configured API always initializes Weave and requires `WANDB_API_KEY` (see [api.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/api.py:127) and [api.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/api.py:157)).

**Impact:** Sensitive prompts and outputs leave the process and remain in local artifacts. Add an explicit data-handling mode with trace opt-out, retention controls, and redaction or hashed evidence where full text is not required. Document artifact permissions and cleanup expectations.

### P2 — Memory limits rely on incomplete sampling, and telemetry errors do not invalidate a trial

GPU memory is sampled once per second. Sampling errors only increment `telemetry_errors`; memory-based selection and constraints use the sampled peak without rejecting a trial that had telemetry errors. See [runtime.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/runtime.py:190) and [measurement.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/measurement.py:240). Existing release documentation also states that short peaks can be missed and service allocations are not separately verified hard caps.

**Impact:** A reported memory result can be understated and may pass a caller's memory ceiling on incomplete evidence. Mark memory evidence invalid when sampling fails; report sample count and coverage, and use runtime/device enforcement if a hard cap is required.

### P2 — “Verified” means only the caller's small supplied evaluator set

The evaluator runs in-process against each output and the mean score across the supplied prompts is compared with the floor. It is not sandboxed or given a timeout. The API allows as few as one prompt, so a passing score can be based on one case. See [quality.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/quality.py:6) and [api.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/api.py:106). The code does correctly keep the evaluator caller-owned and labels quick mode as unverified; it does not establish general task correctness.

**Impact:** Production acceptance depends on the caller's test design and evaluator behavior. Require minimum coverage or separate calibration/holdout cases for production certificates, and run evaluators with explicit time and resource limits when callers are not fully trusted.

## Readiness by area

| Area | Assessment |
| --- | --- |
| Optimization path | Sound for controlled, pinned vLLM experiments. It cannot search CPU kernels or arbitrary model/runtime settings. |
| API | Usable for a narrow one-model GPU workflow; setup requires environment configuration, a provider certificate, Weave, and trace credentials. |
| Evaluation | Deterministic gate code is clear, but correctness depends on caller tests. Evaluator identity is not bound during resume. |
| Resource budgets | Explicit candidate caps exist, but the configured default is uncapped. GPU limits are sampled and not per-service hard caps. |
| Security | Commands are launched without a shell and the runner owns its process group. Credential inheritance and prompt/response export need remediation for sensitive workloads. |
| Persistence/recovery | SQLite checkpointing and ownership locking are useful. Fault tests do not establish live outage recovery; placement resume is documented as absent. |
| Packaging | Clean wheel evidence is recorded. Runtime support requires a separately prepared environment; optional GPU dependency ranges are intentionally broad. |
| Observability | Run, request, and trace evidence is detailed. Trace completion, telemetry errors, and sampled-memory coverage must remain visible in acceptance decisions. |

## Verification performed

Ran these targeted tests with the clean audit virtual environment: `tests/test_public_api.py`, `tests/test_measurement_tracing.py`, `tests/test_optimizer_recovery.py`, and `tests/test_vllm_runner.py` — **67 passed** in 137.21 seconds. The first `uv run` attempt stalled while reading the workspace `.venv`; it was interrupted. No GPU, provider, or production outage test was run. The repository's documented source suite and release evidence are treated as recorded evidence, not rerun acceptance.

## Recommended release gates for CPU-kernel work

1. Add a dedicated CPU runtime adapter with an explicit model/operator/kernel contract. Do not route it through vLLM.
2. Make candidate generation Codex-agent-only as requested, with deterministic local validation and no hosted-provider fallback. The current configured API still permits W&B, OpenAI-compatible, and LiteLLM providers; see [api.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/api.py:21).
3. Add hard trial and wall-clock budgets, plus a safe stop/rollback path.
4. Run correctness tests against a trusted reference, including edge shapes, tails, alignment, and numerical tolerances, before measuring speed.
5. Bind every measurement to CPU model, compiler, hardware, kernel source hash, benchmark inputs, and evaluator identity. Randomize repeated baseline/candidate order and preserve raw results.
6. Prove that the generated artifact is the one executed; measure warm and cold behavior separately; test cleanup and recovery after a killed trial.

Until these gates pass, describe the CPU path as experimental and do not combine its AutoLab hill results with Sera library production claims.

## Addendum — experimental CPU kernel path

Reviewed `sera/kernel_search.py`, `sera/kernel_tools.py`, and `tests/test_kernel_search.py` plus `tests/test_kernel_tools.py` after the initial audit. Targeted tests pass: **19 passed** in 0.23 seconds. The module clearly labels itself experimental and does not export a model deployment path. The Codex adapter removes common API-key variables from its child environment, requires a ChatGPT login, ignores user config, requests read-only mode, and does not provide a provider fallback. The Hills adapter verifies the evaluator report. Those are useful controls, but they do not sandbox generated native code.

### P1 — The final holdout does not gate performance before exposing `winner_source`

Promotion uses the candidate's validation scores against interleaved measurements of the current best at [kernel_search.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/kernel_search.py:139). The final evaluation checks the report identity and correctness, but `winner_source` is set whenever the final score is non-null; it does not require the held-out score to beat the baseline or meet the declared improvement threshold ([kernel_search.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/kernel_search.py:189)). For example, a candidate can beat the baseline in validation, pass final correctness, then score below baseline on the final run. The report still marks it completed and exposes it as `winner_source`; only `target_met` becomes false. Gate source delivery on an explicit holdout performance rule, or rename the field and status so “selected by validation, holdout speed not confirmed” is unambiguous. Add a regression test for a correct but slower final score.

### P1 — Read-only Codex execution does not enforce the prompt's confidentiality rules

The proposal prompt says not to inspect other files or private evaluator inputs, but the invocation uses `--sandbox read-only`, which limits writes while still allowing read operations through model tools. The prompt is an instruction, not an access boundary. `HOME` and `CODEX_HOME` are also passed for login. See [kernel_tools.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/kernel_tools.py:17) and [kernel_tools.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/kernel_tools.py:110). No test proves private hill inputs cannot be read. Run Codex in a disposable account/worktree that contains only public candidate source and measurements, with private evaluator files outside its readable area; otherwise state that confidentiality depends on trust in agent behavior.

### P1 — The Hills evaluator executes generated C with the user's privileges

This is stated in the module docstring, but it is a material execution boundary: `hills eval` compiles and runs the candidate as the current user ([kernel_tools.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/kernel_tools.py:50)). A timeout kills the process group; it does not constrain memory, file access, network access, or children that detach from that process group. A model-generated kernel is arbitrary native code. Keep this path in an explicitly trusted research environment until evaluation runs inside an OS/container sandbox with resource and filesystem limits.

### P2 — The advertised total search deadline does not include proposer time

`optimize_kernel` checks `max_seconds` before calling `propose`, then relies on a separate proposer timeout and checks the deadline only on a later measurement ([kernel_search.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/kernel_search.py:167), [kernel_tools.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/kernel_tools.py:84)). `CodexKernelProposer` defaults to 180 seconds and does not receive the remaining search budget. With `max_seconds=10`, proposal generation can still run for up to its own timeout before the search fails at its next evaluator call. Pass the remaining time into the proposer or enforce one outer deadline across all work.

### Score comparability and Codex-only scope

The search compares reports only when their frozen tree, non-mode config, and recorded compiler/runtime identity match ([kernel_search.py](/Users/vishnuv/Documents/Documents/weavehacks/sera/kernel_search.py:33)). It also uses repeated measurements of the current best in alternating order to reduce drift bias. These checks improve comparability, but timing still has no statistical uncertainty estimate, and the final performance rule above is missing. The new adapter uses Codex ChatGPT login only and does not call W&B/OpenAI model clients; its separate Hills evaluation is local native execution. This is distinct from the older `sera.optimize` path, which still has its earlier provider behavior and must not be used as evidence that the new CPU path satisfies the Codex-only requirement.
