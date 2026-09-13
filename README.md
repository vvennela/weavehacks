# Sera

Sera recommends and measures inference configurations, rejects quality failures, and returns a live runner.

## Demo rehearsal: plain-English guide

### Latest swarm recording

The [compact-prompt replay](evidence/failure-replay-v3/README.md) now passes all loop-control checks: all three agents read evidence in both rounds and stop at zero budget. Factual reasoning still fails: some explanations rule out unknown causes, use an incorrect latency target, or deny a supplied memory change. This is saved-evidence replay with real hosted agents and Weave reads, not a new GPU result. Investigator model selection is now configurable without changing gates.

The [corrected-evidence replay](evidence/failure-replay-v2/README.md) still fails reasoning acceptance. All three investigators read evidence in both rounds. Their inputs now include the actual 85–109-token prompt lengths and 94.375-token average, but they still claim 2,265 tokens per request. Round one selected a legal batching proposal; round two proposed unavailable FP8 KV with no trial budget, and validation rejected every proposal. No GPU trial ran. Clearer data did not solve the peer-copying problem. The [readiness audit](docs/demo-readiness.md) keeps the full goal open.

The [two-iteration GPU run](evidence/live-swarm-investigation-v1/README.md) is saved with its [Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09a31-ec01-7c30-86cd-c51337b414a9). Three investigators compared findings. The context candidate crashed at startup; the batch candidate passed quality but gained only 0.054%, below 5%. Sera returned the working baseline and released the GPU.

The run exposed a real gap: round two skipped fresh failure inspections and repeated incorrect token-count explanations. The updated code requires a successful failure inspection and exposes the specific startup-error record, with source hashes. A startup crash is not a measured quality failure; an observed kernel error is not proof of its underlying cause.

The [two-round failure replay](evidence/failure-replay-v1/README.md) used real hosted agents and persisted Weave reads, with no new GPU trials. All three investigators read evidence in both rounds. However, one agent's false claim that 2,265 tokens was a per-request count spread through the shared findings. All six final explanations repeated it. One optional inspection used an invalid query and was rejected. This proves trace access and exposes a reasoning failure; it does **not** prove reliable diagnosis. The replay also supplied diagnostic guidance and revealed a later outcome category too early. That leak is fixed in newer code, not this recording. Round two had no remaining trial budget. The original failed recording is preserved; no extra GPU run was used to hide it.

Open the [failure-replay trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09a63-0465-7324-8010-1db65f99d9cb) to see the inspection, initial proposal, shared findings, and peer review. The next unresolved acceptance item is factual checking before findings can influence the group. The older staged rehearsal below remains a separate recording.

### What we are building

Sera helps someone run an AI model on the GPU they have. A GPU is the hardware that runs the model, and its memory limits how large a model it can hold. Sera checks possible settings, asks an AI agent to recommend a plan, tests that plan, and returns a model the user can actually use. It must reject a plan when the answers fail the user's checks.

Our long-term goal is like choosing a route home: the best plan depends on whether the user cares most about response time, how much work gets done, or memory use. We have proven that Sera can make a model fit, check that it works, test an agent recommendation, and use the result in its next decision. We have not proven that Sera finds the best route among many choices.

### What we have proven

- The original Qwen72B model needs about 135 GiB just for its saved weights. Those weights cannot fit in our GPU's roughly 96 GB of memory.
- A quantization advisor recommended FP8 weights, and an independent arbiter chose to test that plan. In plain English, this stores most model weights using fewer bits. That saves memory, but can change answers, so it needs a quality check.
- Sera loaded the original weights and applied that change during loading. We did not substitute a separately downloaded, already-compressed model.
- The deployed model passed all eight strict tasks. Sera then generated two possible settings from the measured workload: context limit 256 and batch-token limit 2048. The batching advisor chose the batch-token change; context 256 was not tested.
- Both measured configurations passed all eight tasks. Worst-load p95 changed from 773.803563 to 773.496087 milliseconds: only **0.0397357%** better, below the required **5%**. Sera rejected the improvement claim, not the model's answer quality.
- The next-round specialist used the earlier result and abstained. Sera kept the reference, passed an additional returned-runner request, and closed cleanly with GPU memory back at zero. The request repeated a known question; it was not a held-out test.
- The verified Weave trace contains separate advisor, arbiter, reviewer, provider-response, and recorded-model-output calls. Its stored outputs, measurements, and supplied evidence match the local records.

These are small, specific checks, not proof that the model answers every question correctly. We have not demonstrated a speedup over the original model, because that model could not fit. We have demonstrated a staged multi-agent workflow that measures a recommendation and stops when the evidence does not justify another trial. We have not demonstrated the best possible plan, three competing specialists, or two models sharing the GPU.

### Show the completed multi-agent investigation

Open the [team investigation report](evidence/live-team-investigation-v1/report.md) and [verified Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09a0f-065b-7fcd-b076-d419fd5ae02d). Say:

“One advisor found a way to load the model. Sera checked its answers, then generated settings to investigate from the actual workload. A second advisor proposed a change. It passed the answer checks, but improved response time by only 0.040%, below our 5% rule. The reviewer rejected that prediction. In the next round, the specialist stopped instead of spending the remaining trial. Sera returned the working reference and checked another request.”

The run used **2 of 3 total trials**: one FP8 deployment and one batching trial. There were two search decision rounds; round two ran no trial. Quantization and batching acted in separate stages, not as three competing specialists. The runner is now closed, and the notebook displays saved real evidence. The [earlier batching-only investigation](evidence/live-investigation-v1/README.md) remains preserved separately.

### Repeat the rehearsal: let Sera choose the settings

**Live rehearsal passed** from commit `27f877d`. The saved [team-run evidence](evidence/live-team-investigation-v1/README.md) covers automatic settings, measured feedback, the returned runner, and cleanup. The Weave API verified **297 trace calls**, including **273 recorded model requests** and **7 provider responses** with their exact stored reasoning and content; it reported no call errors. These are trace records, not 297 agent API requests.

For a nontechnical partner: “One advisor recommends how to make the model fit. Sera loads it and checks the answers. Then Sera uses the actual input lengths, request load, and available measurements to choose a small set of settings to investigate. A second advisor recommends an experiment. The decision agent can approve it or stop, and every tested change must pass the same answer checks.”

Run from the repository root on the supported Linux GPU, after preparing the model files and setting `WANDB_API_KEY` in the environment. Use the build whose `python -m experiments.run_investigation --help` lists `--auto-space`:

```sh
python -m experiments.run_investigation \
  --model Qwen/Qwen2.5-72B-Instruct \
  --fit-first --auto-space --budget 3 \
  --priority latency --concurrency 1 2 4 8 \
  --project vvennela-n-a/wandb_agent_default_project \
  --provider-check evidence/provider-v5/result.json \
  --output-dir sera-runs/fit-auto-investigation
```

This starts real GPU and agent work. Use a new output directory. Do not combine `--auto-space` with explicit batching, sequence, context, or FP8-KV flags. The budget permits **one deployment and at most two later candidate trials**, not three extra trials. Advisors may stop sooner. Questions and the 99% quality floor remain unchanged; automatic settings do not add another precision mode.

After the command finishes, show these items in order:

1. **The fit decision:** show the quantization advisor's recommendation and the independent arbiter's decision. BF16 rejection is a memory estimate, not a measured BF16 comparison.
2. **The automatic choices:** open `result.json` and its `candidate_policy` record. It explains the proposed values, source measurements, and missing data. No generated candidates means stop, not a hidden default experiment.
3. **The investigation:** open `report.md`. Follow the proposal, arbiter decision, actual trial, quality gate, and prediction review. Count executed trials, not just proposals or decision rounds.
4. **The trace:** open the saved Weave link. Check separate advisor/arbiter/reviewer calls and recorded model-request outputs. Inspect the bounded output examples supplied to later decisions. An agent's stated reason is a hypothesis; it cannot overrule the task evaluator.
5. **The return and cleanup:** check `post_return_task_passed`, `returned_runner_closed`, and the runtime cleanup result. The command sends a new request using a known question and then closes the runner. It does not leave an interactive service open.

Request-log child spans record saved results: their span duration is logging time, not model response time. Use the recorded `latency_ms` for request timing. Queue snapshots are cumulative, not measured-window averages. Neither selected examples nor a passing trace prove a speedup or the best possible plan.

The agents receive a bounded view of local saved request records—the same records exported to Weave. They do **not** query the remote Weave service or use Weave MCP to investigate. Weave makes their inputs, outputs, and decisions visible; it is not a separate evidence-retrieval step in this run.

For a repeat run, check all five items above before claiming success. A different agent choice, abstention, or rejected change is a result to report, not a reason to invent another trial. `demo.py` prefers the saved live-swarm record when available and labels its output as recorded, not live. The team and batching-only recordings are separate earlier evidence, not proof of the newer swarm's reasoning.

### Three-minute walkthrough

1. **Explain the problem:** “I want to run this large model, but its original weights are too large for my GPU.” Show the BF16 plan marked as not fitting. BF16 is the original weight format.
2. **Show the recommendation:** “The quantization advisor recommended fewer bits. The arbiter chose to test it, and all eight answers passed.” Show the deployment plan and gate.
3. **Show the investigation:** “Sera generated a small set of settings from this workload. The batching advisor recommended one; Sera measured it.” Show the automatic-space rationale and the tested batch-token setting. Context 256 remained untested.
4. **Show the correction:** “The change worked, but was not 5% better. The reviewer rejected the prediction, and the next specialist stopped.” Show the second-round abstention and the budget: two total trials used, not three.
5. **Show the return and limits:** Show the saved returned-runner response, successful cleanup, and matching Weave child outputs. Say: “This is a saved real run. It proves a measured, self-correcting workflow on these eight questions, not a speedup or the best possible plan.”

### Before presenting

- Open the recorded demo first. From the repository root, run `uvx marimo@0.24.0 edit demo.py --sandbox`. This uses saved real results and needs no GPU or API key. The Molab notebook also shows this summary near the top.
- For interactive inference, use the separate fit-only command under “Large-model fit-first path” with `--interactive`. The autonomous-loop command above checks and closes its returned runner. Use the supplied Linux GPU environment, not a laptop without that GPU. Keep the W&B API key in the environment; never put it on a slide or in a recording.
- Prepare the model download before the talk. The latest loop's first startup took 64 seconds with model files already present; startup is excluded from request latency. For an interactive segment, start the separate interactive command early and leave its returned runner open.
- Rehearse one fresh prompt, then confirm how to stop: blank input closes the interactive runner. Do not close it just before the live part.
- If the live service fails, use the recorded demo and say: “This is a saved real GPU run, not live inference.” Do not present saved output as a fresh answer.

The earlier interactive rehearsal also **passed**. Its separate command started the model, passed all eight tasks, accepted a fresh prompt through its input, answered `7 + 8` as `15`, and closed cleanly on blank input. Startup was 60 seconds with the weights cached. See [interactive rehearsal evidence](evidence/demo-rehearsal-v1/README.md). The automatic team command above instead checks its returned runner and closes automatically.

## Current implementation

The large-model deployment path passed on the supplied RTX PRO 6000: reject the non-fitting BF16 plan → agent selects FP8 weights → load original Qwen2.5-72B weights with online quantization → pass all eight strict tasks → return a runner → pass a fresh request → save report and Weave trace → clean up. Measured p95 was 573 ms and peak total GPU memory was 86.38 GiB. See [the result and limits](evidence/large-fit-v1/README.md). The original final-agent review exposed an ambiguous prediction contract; that record is preserved and the review question has been corrected.

The smaller Qwen3-0.6B path also completed a live agent-guided rejection and baseline-return check. Both models are pinned; the runtime is Linux with vLLM 0.26.0. See [the small-model result](evidence/mvp-agent-v1/README.md).

The returned baseline runner answered `1` for `1 + 1`. Its runtime worked, but its answer was wrong. Do not treat runtime success or token agreement as model correctness.

The initial live checks used eight easy prompts and 24 measured requests per configuration. Later four-load comparisons used 96 measured requests per configuration, still on eight questions rather than the full 32-prompt acceptance workload. The large-model run proves feasible deployment through weight quantization, not a measured speedup or search advantage. The current team run also proves the connected automatic-space, output-evidence, child-trace, and returned-runner path. Joint placement and the search benchmark remain unfinished. Earlier traces remain unchanged; the new evidence is a separate run.

The W&B client, typed proposal/ranking/final-selection schemas, and bounded provider check are implemented. The client reads `WANDB_API_KEY` from the process environment; it never saves the key or request headers. Agent-controlled GPU execution stays disabled until the provider check passes.

The first provider check failed (19/30 valid first responses; 22/30 after retries). Its records are preserved. After expressing action/cost consistency in the wire schema and bounding ranking to one candidate, the second check passed 30/30 on the first response with no retries. This establishes schema compatibility, not recommendation quality.

The approved proposal expansion adds batch-token limits (1–65,536), sequence limits (1–256), and context limits (65–4,096), alongside FP8 KV. Each proposal changes one setting and must match its actual parent, the run's allowed values, and any frozen candidate list. These are schema bounds, not verified operating points. Existing live defaults remain FP8 KV or batch tokens 2,048. The older provider record does not certify the expanded schema. Provider-v4 had four invalid evidence citations; those failures remain saved. The corrected [provider-v5 check passed 30/30 first responses and all context checks](evidence/provider-v5/README.md), and the current build completed a live investigation.

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

Pass it as `candidate=candidate` to `optimize`. These are the two default milestone candidates. Explicit or automatic investigation spaces require a separate opt-in agent budget.

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

This makes 30 requests using the actual three schemas and synthetic evidence. Each failed response permits one retry. It requires 29 first-pass valid responses, all 30 valid within the retry limit, and all evidence-reference checks passing. Proposal fixtures require trial or keep-baseline shapes so a model cannot pass by avoiding the new controls. All attempts, truncation, errors, and timings are saved. A pass establishes schema compatibility, not useful search or model correctness. Credential/access errors stop the check early.

After a matching check passes, supply `agent=sera.WandbAgent(project=...)` and `provider_check=".../result.json"` to `optimize`. Sera gives the agent the measured baseline, validates one proposal, measures it if legal, applies the unchanged gate, and returns the outcome for a final recommendation. A keep-baseline or invalid proposal consumes no candidate GPU trial. The final agent response cannot change the deterministic selection.

## Bounded agent investigation

### Investigative swarm mode

`--swarm` enables three independent investigators: scheduling, memory/context, and output quality. They choose read-only inspections of persisted Weave records, work concurrently, then read the same shared findings board and refine their proposals. An arbiter can select at most one GPU experiment per round. GPU trials stay sequential.

The investigators are not tied to one hosted model. Both `experiments.run_investigation` and `experiments.replay_failure_investigation` accept `--agent-model`. The default remains `openai/gpt-oss-20b`. Before selecting another W&B model, run `python -m sera.provider_check --project ENTITY/PROJECT --model MODEL_ID --output-dir NEW_DIRECTORY` and pass its matching certificate. A certificate for one model cannot authorize another. The format check does not certify factual reasoning.

Swarm model requests now separate measured facts from peer opinions and omit old response objects. Full source evidence, the actual transmitted compact prompt, and both hashes remain in the audit record. The separate [Astra diagnostic](evidence/astra-swarm-diagnostic-v1/README.md) used Codex subagents, not this hosted runtime, and was not blind.

Use `--swarm --auto-space --budget 2` with the live command below. Weave is required; `--swarm --no-weave` is rejected. The Python interface is `optimize(..., swarm=True, trace_reader=reader)` with a forkable agent and a budget. The command supplies the traced reader automatically. Ordinary calls keep the existing staged loop.

Each inspection records its source call IDs and output hashes. Missing or incomplete remote evidence is marked as a failed inspection; it is not replaced by local outputs. Model answers and peer findings are data, not instructions. These analysis roles do not add multi-GPU controls or enable unverified precision settings.

Failed experiments have a saved diagnosis: the observed error stage or rejected gate, quality scores, measured gain versus the required gain, and constraints on the next proposal. Weave inspections include that diagnosis and relevant failed requests. Quality inspections can show the original answer, fixed expected answer, and strict evaluator result. The agents must separate those facts from a suspected cause, cite available evidence, and explain the next experiment or decision to stop. A failed start with no outputs is not reported as a quality result. No gain does not prove a batching or memory problem.

The live swarm rehearsal is still being checked. The earlier team recording below proves the staged loop, not this concurrent mode.

### Existing staged loop

The production controller accepts `budget=sera.Budget(max_candidate_trials=2)` with an agent and a matching passed provider record. Omitting `budget` preserves the one-candidate path. It completed a [real two-round investigation](evidence/live-investigation-v1/README.md): one measured batch-token candidate, prediction review, later arbitration using that history, reference restoration, a new request, and cleanup.

Each round gives the active quantization and batching specialists the baseline measurements and a short history of previous trials. An arbiter selects an experiment. Sera validates it, measures it with the existing runner, applies the unchanged quality and performance gates, and asks the agent to review its prediction. The next round receives the result, including failures. The current implementation also supplies bounded examples of actual inputs and outputs, prioritizing task failures and slow requests. Complete raw records remain saved; examples are selected evidence, not representative averages or instructions from model output. The team rehearsal verified this richer evidence in the actual provider calls and matching Weave records.

A post-run fix forwards queue/first-token/preemption snapshots for every load and previous trial. Their names state that they are cumulative since startup, including warmup and earlier loads; they are not load-window averages. The first live investigation omitted these fields. The later team run used the corrected evidence path; the older record was not rewritten.

The controller counts failed starts against the budget, excludes tested configurations, stops after two rounds without a frontier change, and stops immediately on cleanup failure. With at least three trials left, it can also select one untested specialist proposal for exploration. It returns the best eligible measured runner; a failed-quality baseline is not a safe fallback. All trials, proposals, reviews, and the measured frontier are saved.

Default values remain narrow: FP8 KV and batch tokens 2,048 for small Qwen; batch tokens 2,048 only for the proven Qwen72B FP8 reference. A caller can now supply `investigation_space=sera.InvestigationSpace(supported_changes={...})` with an explicit budget. This declares up to 32 single-setting candidates using the supported batching/context controls. Sera freezes their full configuration hashes before loading. An optional `candidate_hashes` list restricts the pool further. It rejects no-ops, invalid coupled settings, incompatible sequence limits, and unverified combined FP8 weights/KV. After baseline tokenization, it excludes candidates whose context cannot cover the same input and output limit. It does not silently activate the expanded ranges or execute a full grid.

Normal-mode automatic value generation is opt-in through `automatic_space=True` on `optimize`, with an agent and budget. It runs after baseline measurement and records its full rationale. It proposes bounded single-setting context, sequence, or batch-token changes; it does not generate precision changes or combinations. Explicit/frozen spaces cannot be combined with this mode. Missing essential evidence produces no candidates, not guesses or fallback defaults. The live team rehearsal generated context 256 and batch tokens 2048; only the batch-token change was tested.

Combination trials, joint placement, session-time budgeting, and a live search-advantage claim remain unfinished. The citation fix constrains the provider to exact available metric names and verifies the same request schema locally. The [current hosted check passed 30/30 on the first attempt](evidence/provider-v5/README.md), including every evidence-reference check. The provider gate no longer blocks the current wire schemas; it does not certify useful reasoning about new evidence.

### Run a bounded live investigation

Run from the repository root on the supported GPU, with `WANDB_API_KEY` in the environment:

```sh
python -m experiments.run_investigation \
  --model Qwen/Qwen2.5-72B-Instruct \
  --budget 2 --batching-values 2048 1024 \
  --priority latency --concurrency 1 \
  --project vvennela-n-a/wandb_agent_default_project \
  --provider-check evidence/provider-v5/result.json \
  --output-dir sera-runs/live-investigation
```

This example uses GPU time and requires the large model files. It declares two batch-token alternatives against the proven FP8-weight reference with BF16 KV. It is not a recorded run or a speedup claim. The command checks the provider certificate before loading, keeps the eight strict tasks and 99% quality floor, saves the investigation and trace link, tests the returned runner, and closes it. An agent can decline a trial. Read the recorded trial count before claiming a full round ran. Use a new output directory.

### Connect deployment and the agent team in one run

Add `--fit-first` for Qwen72B to start from the model that does not fit. A quantization advisor recommends a legal memory plan, an independent arbiter decides whether to test it, and the measured deployment must pass the task gate. That same running model then becomes the reference for the batching investigation. There is no reload between those stages.

The budget includes the deployment trial: `--fit-first --budget 3` allows one deployment and at most two tuning trials, not three additional trials. The connected live rehearsal with `--auto-space` used one deployment and one tuning trial, then stopped after the next specialist abstained. An explicit FP8 reference without `--fit-first` retains the previous behavior.

The command also accepts explicit `--sequence-values`, `--context-values`, and `--fp8-kv` controls. Values are checked before execution, and unsupported combinations remain rejected. FP8 KV is not enabled on the Qwen72B FP8-weight reference. The report shows which specialists had legal work and why others were inactive. Parallelism is inactive on this single-GPU runtime.

For a nontechnical partner: “One advisor finds a way to load the model. Another investigates how to serve requests. A decision agent chooses which experiment to run, and a reviewer checks the prediction against what happened.” This is a staged multi-agent workflow, not proof of simultaneous competing specialists or better search than grid search.

### Rehearse the decision loop without a GPU

```sh
python -m experiments.rehearse_investigation --output-dir sera-runs/offline-loop
```

Use a new output directory. This runs the production controller with **synthetic agents, answers, latency, and memory**. It makes no LM or GPU calls. The scripted first trial is fast but wrong, so Sera rejects it. The next round receives that failed prediction and chooses a passing alternative. The rehearsal checks a fresh returned-runner request and cleanup, then saves `result.json`, `report.md`, and `investigation.md`.

For a nontechnical partner: use this to explain how the decision loop works. Say that the inputs and agents are scripted. Use the separate Qwen72B recording to show real GPU results. The offline rehearsal proves software control flow, not agent intelligence or a speedup. The normal result summary now shows specialist predictions, cited evidence, arbitration, trial gates, later history, and the final runner. See the [saved synthetic walkthrough](evidence/synthetic-investigation-v1/README.md).

## User priorities

Pass `objective=sera.Objective(priority="throughput")` to `optimize` to maximize measured output tokens per second. Other choices are `"latency"` (default: minimize p95) and `"memory"` (minimize sampled peak total GPU memory, including runtime reservation). The default required relative improvement is 5%; `min_improvement_fraction` can be declared before the run. The 99% token-agreement gate is unchanged for every priority.

The agent receives the priority, and the deterministic selector applies it. `result.frontier` retains quality-valid latency/throughput/memory trade-offs; it is no longer only the fastest trial. Missing metrics remain missing and cannot prove that one trial dominates another. The report includes the objective, frontier IDs, latency, throughput, and peak memory. No dollar-cost model is implemented.

This wiring passes local synthetic checks, including different recommendations from the same measurements when the priority changes. The saved FP8 KV candidate remains rejected under every priority in quick mode because token agreement failed. The separate fit-first path below enables online weight quantization for the pinned 72B model without a feasible BF16 baseline. Arbitrary models and multi-GPU placement remain unsupported.

For an explicit load sweep, pass `workload=sera.Workload(concurrency=[1, 2, 4, 8])`. Each load receives its own warm-up and three measured passes. Quality checks remain serial. The result stores every load separately; selection uses the worst per-load p95, not pooled latency percentiles. Throughput is total output tokens divided by the sum of measured window durations across the declared loads. Compare only runs with the same load list. The default remains concurrency 1.

After the large model's FP8 weight plan works, pass `baseline_configuration=sera.RuntimeConfig(quantization="fp8_per_tensor")` with that model to compare batching against a feasible FP8 reference. The supported alternative changes only `max_num_batched_tokens` from 4096 to 2048. Both plans keep FP8 weights and BF16 KV. This is named `sera-fp8-weight-reference-v1`, not the non-fitting BF16 baseline and not the Qwen0.6B search benchmark.

The approved live comparison completed at concurrency 1, 2, 4, and 8. Both plans passed all eight tasks and all 96 timed requests. The smaller batch limit improved aggregate throughput by only 0.024%, below the 5% rule. Sera kept the reference, the agent agreed, and the returned runner passed a fresh request. See [the per-load measurements](evidence/large-batch-comparison-v1/README.md). This proves measured selection between working plans, not adaptive search or a performance win.

The delegated [search replay harness](benchmarks/SEARCH.md) implements a frozen universe, equal budgets, grid and seeded random controls, and bounded agent adapters. It now supports multi-round batching comparisons in local tests. It has not established a real benchmark win. Context-varying benchmark universes remain blocked by the workload contract, and the full no-telemetry ablation remains blocked by required metric citations. Wider schema support requires a new matching provider check. No benchmark prompts or thresholds were tuned to make the batching result look better.

## Two-model status: quality and shared execution remain incomplete

The specified Qwen0.6B + GLM-4-9B pair is not ready for verified placement. GLM loaded in BF16 and FP8, but passed 0/8 strict-format tasks. Qwen FP8 passed 1/8; it had both format errors and a wrong filtering answer. The earlier Qwen BF16 result was 2/8. We stopped before running them together. See [the preserved prerequisite results](evidence/placement-prerequisites-v1/README.md).

In plain English: the programs run, but these two smaller models do not yet meet the promised answer contract. More GPU memory does not fix that. Changing the task rules or model pair needs an explicit decision. This does not invalidate the successful Qwen72B deployment and rehearsal. No joint-placement or smaller-card benefit is claimed.

A separate `experiments.run_structured_quality_pilot` command tests native JSON decoding for one specified model at a time, with BF16 weights by default or explicitly requested FP8 weights. It keeps the eight questions, exact answers, generation limits, and 99% floor. Its schema does not contain the answers. It saves raw responses and diagnostic request latency without repairing output. A passing pilot establishes only its declared decoding/precision profile; joint scheduling, a declared smaller-card budget, and a measured concurrent trial would still be needed.

The [Qwen structured-output pilot completed at 7/8](evidence/qwen-structured-quality-v3/README.md): all answers were valid JSON, but filtering was still wrong. Median request latency was 112.60 ms, with a retained 59.21-second filtering outlier. Cleanup passed. This is a quality rejection, not a verified baseline or speedup. The [placement plan](docs/placement-plan.md) separates this quality gate from the remaining shared-runtime work and required budget/latency decisions.

[GLM passed the same structured-output pilot at 8/8](evidence/glm-structured-quality-v1/README.md), including filtering. Median request latency was 141.05 ms, with a 1.36-second maximum on the first request. Cleanup passed. GLM now has a passing isolated BF16 quality profile; Qwen still does not. Neither pilot proves quantized quality, joint fit, or concurrent performance.

The [Qwen FP8-weight structured pilot also scored 7/8](evidence/qwen-fp8-structured-quality-v1/README.md), with the same semantic filtering error and valid JSON throughout. It does not provide a passing Qwen baseline or a new FP8-specific failure. No speedup follows from comparing these short diagnostic runs.

The [saved-results audit](evidence/release-benchmark-audit/README.md) reproduced all 64 saved task grades and the four-load Qwen72B comparison. It found no complete frozen small-model search universe, so a measured grid/random comparison remains unavailable.

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

If only the candidate meets requirements, Sera can select it without claiming a speedup. If neither meets requirements, it closes the runtime and returns `no-safe-configuration` with `models=[]`; it never returns a failed-quality baseline as verified. Scoring uses only the supplied prompts and evaluator and is not a general quality guarantee. Workload concurrency defaults to `[1]`; an explicit sweep can use `[1, 2, 4, 8]`.

The first live verified check returned no safe configuration: the tiny model passed only 2/8 strict JSON tasks and the agent declined a trial. See [the preserved result](evidence/verified-agent-v1/README.md). Do not present this as a quality or optimization success.

## Large-model fit-first path

The same `optimize` entry point now accepts `models=["Qwen/Qwen2.5-72B-Instruct"]`, pinned to revision `495f39366efef23836d0cfae4fbe635880d2be31`. This path requires a versioned task evaluator and explicit quality floor because a non-fitting BF16 baseline cannot provide reference outputs.

It estimates BF16 and online FP8 weight plans before loading. The estimate includes full-context BF16 KV for eight sequences, unquantized embedding/head/norm/bias parameters, 16 MiB of quantization metadata, and an explicit 4 GiB workspace allowance. The 0.90 service fraction leaves physical headroom. Workspace and startup behavior still require measurement.

With an agent, the arbiter selects at most one estimated-feasible plan. Sera then loads the original weights with `fp8_per_tensor`, measures the workload, applies task and resource limits, and returns the live runner only on a pass. The unquantized baseline is marked infeasible, never fabricated. This path passed the live eight-task check. It establishes feasible deployment, not a speedup over a baseline that did not run. No multi-GPU allocation or wider search is implemented.

The original interactive rehearsal used commit `8dcfb00` and its matching provider certificate. Later provider-v5 passed the expanded citation contract and was used by the saved staged and swarm runs. A schema certificate is not proof of useful reasoning or a clean-install release. Use the certificate that matches the checked-out code; do not bypass validation with an older one. On the supplied GPU, with Weave installed and `WANDB_API_KEY` in the environment:

```sh
git worktree add --detach ../sera-rehearsed-demo 8dcfb00
cd ../sera-rehearsed-demo
uv pip install '.[agent]'
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
