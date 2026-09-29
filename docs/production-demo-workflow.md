# Sera production work and 3–5 minute demo

Status: implementation in progress. Sera is not yet production ready for the
user-defined autonomous ML research goal. ModelOpt is not integrated. Native MLX
checkpoint checks now run on the local Apple GPU; see the
[measured evidence](../evidence/native-mlx-smoke-v1/README.md).

September 29 decisions: keep the repository public; provide a Sera-managed agent
using our service-owned W&B key; use native MLX first, then CUDA/ROCm adapters;
allow optimized checkpoint export. The website is outside this implementation.
The managed deployment host is still needed. No service has been deployed.

## Intended outcome

Product direction approved on September 28: free GPU memory through autonomous
ML research, with one call after credentials and the workload are supplied.

**Sera researches how to make your model use less GPU memory, tests its ideas on
your hardware, and returns the best verified result it found.**

Target user experience (proposed API; not available in the current package):

```python
result = Sera.Optimize(
    api_key=sera_access_token,
    model=model,
    workload=workload,
)
```

The target flow is Sera access → model and representative workload → Optimize
→ progress → usable result. The service holds our W&B key. W&B inference with
`openai/gpt-oss-20b` passed all 34 compatibility cases on the first attempt.
Required MLX traces have also been uploaded and read back from W&B. Native
worker processes receive no W&B or agent key. Model access credentials can still
be required for private or gated weights. The current `sera.optimize` remains
the earlier configured vLLM flow; do not present the target call as available.

The headline result is GPU memory recovered in GiB and percent under the same
workload. Keep quality and latency requirements visible. A smaller checkpoint,
a smaller cache reservation, and lower measured serving memory are different
results; label them separately. Do not imply that a smaller reservation alone
improves useful capacity. Show extra concurrent work only after measuring it.

The research loop detects hardware, measures a baseline, proposes compatible
experiments, runs them, checks quality and speed, and revises its next proposal
from the results. ModelOpt supplies supported transformations for its backend.
The user should not need to choose quantization recipes or specialist roles.
A no-improvement result must keep the original usable model.

Simple onboarding still needs an explicit quality contract and bounded resource
use. Whether these come from a saved workload profile or initial setup is an
open API design decision. Do not silently select quality loss, latency limits,
time limits, or spending limits for the user. No run should expose an agent key
to inference workers or include it in reports.

“Rapid research” needs evidence: show actual wall-clock duration, experiments
completed, GPU time, and agent cost. Reuse safe cached preparation and stop
unsupported experiments early, but do not claim rapid optimization from an
accelerated replay. The wider goal remains hardware-independent optimization;
only validated adapters can claim hardware support.

## Four-minute-thirty-second target demo

The story: **“This model uses too much GPU memory. One call starts research.
Sera finds and verifies a smaller working deployment.”** Use the last sentence
only if the measured run succeeds.

| Time | Action | What the audience sees |
| --- | --- | --- |
| 0:00–0:25 | Show the target model running and its baseline GPU memory use. | Real used/free GiB, hardware, workload, quality and latency requirements. |
| 0:25–0:45 | Show credentials already configured, then invoke `Sera.Optimize`. | One user action; secrets stay hidden. Label this target API until implemented. |
| 0:45–2:15 | Show actual hypotheses, trials, measurements and revisions. | Experiments completed and real elapsed time. If replayed, mark recorded and show playback speed. Retain losing trials. |
| 2:15–3:00 | Show the selected result beside baseline and stock ModelOpt/non-agent controls. | GiB and percent recovered, quality, latency spread, research duration and cost. Missing comparisons say not measured. |
| 3:00–3:45 | Run a new request through the independently loaded result. | The result works outside the optimizer. A capacity demo is optional and requires a separate measured result. |
| 3:45–4:15 | Show the returned artifact and its reproduction command. | The audience can use the output; exact hardware and supported scope are clear. |
| 4:15–4:30 | Buffer and questions. | State measured results and remaining limits. |

For three minutes, use 45 seconds for the research trace, 20 seconds for the
comparison, and 25 seconds for the new request. For five minutes, spend the extra
30 seconds on one actual revised experiment and its memory/quality tradeoff.

If research takes longer than the presentation, complete it beforehand and show
an accelerated replay with its real duration visible. Do not spend presentation
time downloading weights, installing packages, or waiting for calibration. Do
not describe the replay duration as research duration.

## Required preparation for the target demo

1. Freeze the approved model, data splits, metric, quality scorer, hardware,
   recipes, control methods, and total resource budget before experiments.
2. Connect the native MLX export/serving path to the research controller, then
   complete compatible CUDA/ROCm adapters and ModelOpt's CUDA execution path.
   Save hashes for weights, tokenizer, calibration data, recipes, evaluator,
   runtime, and trial artifacts. Simulated quantization is not serving speed.
3. Collect the agent and non-agent comparisons using the same allowed tools,
   hardware, data access, and resource rules. Report trial count, GPU time, and
   total elapsed time separately. Include failed preparation and agent calls.
4. Confirm the chosen artifact on data not exposed during search and fresh
   paired measurements. Fix the acceptance rule before collecting these results.
5. End the optimizer. Independently load the exported artifact and verify the
   application before the presentation. Record this fresh-process check. If
   startup is too long for the stage, prepare that application process in advance
   and disclose that it is already loaded; the input can still be live.
6. Build the replay from the completed run and audit every number shown. If timing
   positions are schematic, label them. Keep the full run and unsuccessful trials.
7. Rehearse within the time limit. Check local links and any authenticated trace
   access. Keep the exact recorded run available as a clearly labelled fallback.
8. If a live query fails, show the failure and the recorded evidence separately.
   Never substitute a recorded response while calling it live.

GPU/session access, global compute budget, representative workload, benchmark
rules, and acceptance thresholds remain user decisions. Earlier proposed counts
in the ModelOpt plan are proposals, not authorization. No demo deadline changes
the quality or performance gates.

## Current runnable rehearsal

This historical latency demo does not establish the new memory-recovery promise.

The existing [recorded loop](../demos/recorded-loop.html) is a real September 13
GPU run presented as offline playback. It makes no GPU or agent calls. It is
the current rehearsal material while the target ModelOpt workflow is built.

From the repository root:

```bash
.venv/bin/python -m http.server 8766 --bind 127.0.0.1
```

Open `http://127.0.0.1:8766/demos/recorded-loop.html`. Keep the repository directory
structure intact so the Audit JSON and Proposal history links resolve. Stop the
server with Ctrl-C after rehearsal. Alternatively open the HTML file directly.

Select 16× and press Play. The approximately 14-minute recorded invocation takes
about 52 seconds of playback at that speed. Pause to discuss actual decisions:

- Prefix caching reduced worst-load p95 from 771.046 to 624.785 ms.
- Graph execution alone reached 764.072 ms and lost to the existing best.
- Combining caching and graphs reached 618.588 ms: 19.773% below the initial
  baseline, but only 0.992% better than caching. That last gain was below the
  declared 5% progress threshold; the loop stopped and retained the best result.
- All four configurations passed eight task checks and 96 timed requests each.
  The returned runner answered a known task; cleanup returned GPU use to zero.

Say: “This is a replay of a completed GPU experiment on eight warmed, repeated
prompts.” This recording used the historical OpenAI/LiteLLM agent path. The new GPU
product uses Sera access with mandatory service-owned W&B tracing; W&B account,
model access, and native trace export are now verified. The recording does not show ModelOpt, a held-out
quality test, cross-backend execution, a live service, or agent superiority over
grid/random search. The old runner is closed.

The authoritative explanation and compact audit are in
[the run record](../evidence/openai-example-v2/README.md) and
[audit-summary.json](../evidence/openai-example-v2/audit-summary.json).
The full original optimizer record is retained on Molab, not in this checkout.

## Production completion checklist

These items preserve the full goal. Passing a unit suite does not close a live
acceptance item, and an adapter interface does not establish hardware support.

| Required result | Evidence needed | Current state |
| --- | --- | --- |
| Backend-independent research loop with ModelOpt execution | Actual calibration, export, serving, hypothesis revision, and returned artifact | Planned; existing loop is tied to vLLM controls and separate experimental CPU research |
| Reproducible supported installation | Clean installation and GPU smoke test for each claimed environment | Old narrow environment evidence; new path pending |
| Fixed evaluation identity and independent final data | Changed evaluator/data rejected on resume; unseen-data final test | Version-string check exists; content binding and broader final-data coverage pending |
| Trustworthy quality/performance selection | Correctness gate, repeated controls, no use of invalid telemetry, fresh final confirmation | Existing gates plus ongoing hardening; broad acceptance pending |
| Hard resource bounds and cancellation | Trials, setup, agents, workers, retries, and cleanup obey the approved global limits | Explicit caps exist in some paths; configured swarm is uncapped by default |
| Worker isolation and data handling | Resource/filesystem/network limits; credential separation; trace/retention controls | Environment allowlist implemented and tested locally; native-code sandbox and data controls pending |
| Durable recovery | Real worker/controller interruption, restart, budget accounting, verified cleanup | Local checkpoint/fault tests exist; live outage and sustained-load validation pending |
| Portable usable artifacts and fallback | Export hashes, fresh-process loading, reproduction command, previous artifact retained | MLX exports are hashed and independently reloaded; ModelOpt and cross-runtime export remain pending |
| Evidence for agent value | Same-resource non-agent comparisons and cost accounting on representative workloads | Unproven; no superiority claim |
| Timed demonstration | Rehearsed 3–5 minute workflow with trace-backed numbers and usable output | Run-of-show prepared; current recorded rehearsal available; target demo pending |

The first implementation step restricts model-worker environment inheritance.
Its 110 targeted runtime checks passed, including real child-process checks.
It preserves model-download authentication and home/cache access, so it is not
an operating-system sandbox. A live GPU launch with the new environment remains
required before release.

Memory selection, agent feedback, reports, and generated replays now require a
positive finite peak and an explicit zero sampling-error count. Missing or
failed sampling produces an unavailable metric, while raw evidence is retained.
The targeted selection/benchmark checks passed (123 tests), as did the
feedback/report/replay checks (104 tests). These checks establish software
behavior; they do not establish GPU memory savings.

The offline release audit now reports unreadable or malformed files encountered
during manifest discovery and marks that scan incomplete. Corrupt required
source records still fail the audit. Its five tests passed.

The historical replay was checked locally: play, completion, restart, and the
linked audit/timing JSON worked. It remains a rehearsal of historical latency
evidence, not a completed memory optimization demo.

Validation on September 28: a clean temporary Python 3.12 environment installed
with `uv sync --frozen --extra dev` completed the full suite: **1,822 passed,
15 skipped**. The skips were 14 API-client tests without optional HTTP/OpenAI
packages and one notebook-render test without marimo. After installing the
lockfile versions of HTTPX (0.28.1) and OpenAI (2.54.0) in that temporary
environment, all **27 API-client tests passed**, including those 14 cases.
The notebook-render test remains unrun in this environment. No paid provider
calls or GPU trials were made for these checks.

## One-call setup implementation order

Mandatory W&B tracing is the user-selected design. Keep Weave evidence reads,
the provider compatibility gate, failed-trial inspection, and trace flush checks.
Do not replace these with local-only logs to simplify onboarding.

The existing implementation offers these concrete building blocks:

1. `prepare_provider_check(agent=..., output_dir=...)` in
   `sera.provider_check` creates the existing 34-case check using a separate
   agent history, or revalidates an existing saved check without provider calls.
   The caller chooses the folder. Invalid, interrupted, or mismatched records
   stop setup and remain on disk; retry requires a new folder. This helper does
   not yet run automatically from `sera.optimize`.
2. `experiments/example_run.py` demonstrates explicit W&B credential setup and
   environment restoration, plus existing agent routes. Its fixed Qwen72B tasks
   and thresholds are demo-specific and must not become generic defaults.
3. `sera.api._run_traced` supplies the current Weave trace, bounded evidence
   reader, and cleanup on trace failure. Reuse this path in the target entry
   point rather than adding a second optimizer.
4. The target entry point still needs verified W&B account/model access and a
   concrete workload configuration. It must validate these before billable
   setup calls, retain setup time and request counts, then pass the checked
   agent and certificate into the existing traced research loop.

The setup helper preserves the existing certificate acceptance rule. Reuse does
not prove that an endpoint remains healthy or that a model alias has not changed;
it only rechecks the saved compatibility evidence. No new expiration or provider
acceptance policy was selected. Live provider and GPU checks remain required.

Provider setup validation: **118 related tests passed** across provider checks,
OpenAI-compatible and LiteLLM clients, the public API, and the recording helper.
The tests use simulated provider responses; no paid requests were made. The new
helper is implemented, but the target `Sera.Optimize` entry point is still pending.

## September 29 native implementation checkpoint

The complete local suite passed **1,879 tests, with one optional notebook-render
skip** in the native MLX environment. Two shared-fixture imports were corrected
to avoid a dependency's unrelated `tests` package shadowing the local suite.
Native jobs run in disposable processes with explicit deadlines and retained
failures. The controller requires a completed trace to be read back from W&B
before returning a verified trace record. Actual MLX export and fresh-process
checks are in [the evidence package](../evidence/native-mlx-smoke-v1/README.md).

The 8-bit checkpoint passed the repeated easy checks; the 4-bit checkpoint did
not. The native backend has not been integrated into the agent research loop.
Managed service authentication, tenant/job ownership, remote worker dispatch,
formal comparison rules, CUDA/ROCm acceptance, and deployment remain open.
These are release blockers, not completed features.
