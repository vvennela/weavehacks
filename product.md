# Sera

## Product statement

Sera is a Python library that gives any developer fast model inference without requiring inference-engineering knowledge. It finds better ways to run one or more AI models on the hardware the developer already has, rejects quality failures, and returns usable models with evidence for every decision.

## Central pitch

Give Sera your models, representative prompts, and priorities. Sera tests ways to run the workload on the available hardware and returns usable models with the best measured configuration for those priorities. Latency, throughput, and memory can favor different plans; quality remains a hard constraint.

Behind one simple call, a team of inference specialists chooses useful experiments, learns from failed trials, and avoids wasting GPU time on a full grid search. Sera does not guess that an optimization works. It runs the model and proves what changed.

## The problem

Inference configuration is difficult because the important settings interact.

- Quantization can reduce memory use but damage output quality.
- Larger batches can improve throughput but increase request latency.
- Parallelism can make a large model fit but add communication overhead.
- Two models can fit in GPU memory and still interfere through memory bandwidth or compute contention.

A benchmark of one configuration or one model cannot reveal how settings and services interact. Monitoring tools show what happened, but they do not decide what to test next. Static recommendations cannot prove that a change works for the user's model, traffic, and hardware.

Most developers do not know which settings are legal, which measurements matter, or which tradeoffs are safe. Grid search removes some guesswork, but it spends GPU time testing many configurations that basic measurements or feasibility checks can rule out.

## The product

Sera closes the loop between a recommendation and measured proof.

```python
import sera

result = sera.optimize(
    models=["org/model-a", "org/model-b"],
    prompts=prompts,
    objective=sera.Objective(priority="latency"),
)

result.print_summary()
optimized_models = result.models
```

Sera owns model loading so it can reload each model with different quantization, batching, and parallelism settings. Model revisions are pinned so every comparison is reproducible.

With one model, Sera finds several good ways to run that model. With multiple models, Sera also tests how they share the available hardware.

## What Sera does

### Phase 1: optimize each model

Sera establishes a baseline for each model. It then measures the run and gives a small set of derived signals to three specialists:

- The quantization specialist reduces weight and cache memory use.
- The batching specialist changes how requests are grouped and scheduled.
- The parallelism specialist changes how model work is divided.

An arbiter ranks the proposals and selects the strongest useful experiments. A deterministic validator rejects illegal settings and configurations that cannot fit before they consume GPU time.

Normal optimization has no fixed total trial count. The orchestrator measures progress against the user's objective while preserving the quality requirements. A round without a qualifying objective improvement starts a plateau check. Sera allows one further round; qualifying progress resets the check, while a second round without progress ends the search. An experiment failure is evidence for the next round, not a reason to restart the same experiment. No legal proposal, an explicit agent abstention, cancellation, or a runtime safety failure can stop the run earlier, with its actual reason recorded. An optional user limit and the fixed benchmark budget remain separate controls.

Each surviving candidate is loaded, warmed up, tested with representative work, and checked for quality. Sera records successful trials, failed trials, and reverts. It keeps a frontier of useful configurations instead of selecting only the fastest result.

The user can prioritize latency, throughput, or memory. Latency remains the default. The selected priority reaches the agents and the deterministic selector, and is saved with the evidence. Cost optimization requires explicit resource prices and accounting; Sera must not infer a dollar cost from memory use alone.

A model that cannot fit before optimization needs a separate fit-first path: reject impossible loading plans before execution, propose supported weight quantization and placement, then verify a feasible plan against the user's task requirements. An unavailable unquantized baseline cannot supply local latency or token-agreement evidence. The prototype implements this path for pinned Qwen2.5-72B using online FP8 weights on one GPU. It requires a task evaluator and explicit quality floor.

The current single-GPU swarm investigates scheduling, memory/context, and output quality/execution. Each specialist receives up to eight legal candidate options. The menu expands from measured feedback and can combine two separately quality-passing changes. The [verified Astra loop](evidence/live-astra-expanded-v1/README.md) completed three swarm rounds and four GPU trials, then returned a caching/graph configuration with all eight tasks passing and 19.55% lower p95 latency. This gain applies to the measured repeated-prompt workload after warmup. Multi-GPU placement, global optimality, and search superiority over simpler methods are not established.

### Phase 2: optimize the models together

The frontier reader revisits phase-one results with a different goal: find the smallest configuration for each model that still meets its requirements.

Sera proposes a hardware assignment, checks memory fit, and runs the models together. Each model has its own performance and quality gate. If either model fails, Sera restores the prior setup and sends the measured interference back through the optimization loop.

This joint trial matters because memory arithmetic cannot detect bandwidth, scheduling, or compute contention.

## The agent team

Sera uses five AI roles:

1. Quantization specialist
2. Batching specialist
3. Parallelism specialist
4. Arbiter
5. Frontier reader

Agents interpret evidence and propose experiments. They do not declare that an experiment passed.

Metric reduction, configuration validation, trial execution, quality gates, persistence, and rollback are normal deterministic software. This boundary keeps the system testable and prevents agent confidence from replacing measurement.

## Validation levels

### Quick mode

The user supplies models and representative prompts. Sera derives prompt lengths, measures output behavior, sweeps a standard set of loads, and uses documented defaults for the experiment budget and acceptable change.

Quick mode checks deterministic token agreement against saved original-model outputs with fixed generation settings. It requires no external judge. This strict proxy can reject harmless wording changes and does not verify task quality.

### Verified mode

The user also supplies a workload profile, latency requirements, an evaluation function, and a quality floor.

Verified mode returns configurations that passed those requirements under the measured test conditions.

## What the user receives

Sera returns a structured result, not terminal output alone.

- Loaded models or runners configured for later use
- The recommended configuration
- Other configurations on the measured frontier
- Baseline and final latency, throughput, and memory measurements
- Quality results
- Every trial and its outcome
- Failed predictions and observed interference
- A readable notebook report

## Benchmark against naive grid search

Grid search is a benchmark control. It is not part of Sera.

The hackathon benchmark uses Qwen/Qwen3-0.6B only. It gives Sera and naive fixed-order grid search the same pinned model, named baseline, hardware, frozen candidate configurations, workload, quality gate, and trial budget. The grid tries configurations in a fixed order and does not use measurements to choose its next trial. GLM is reserved for the placement demonstration and its preparation.

The benchmark claim passes when Sera reaches a quality-valid result within five percent of the best measured latency in the frozen universe in fewer trials than fixed-order grid search, beats median random search at the same budget, and outperforms at least one ablation. Report an unmet claim when these conditions do not hold.

An exhaustive grid eventually tests every configuration. That is not the comparison. The comparison measures which method finds a strong valid configuration first. Sera uses measurements and past results to choose which experiment is worth running next.

The evaluation also compares Sera with uniform random search and versions of Sera that cannot see reduced telemetry or trial history. These ablations test whether the measured feedback loop causes the improvement.

## Weights & Biases Weave

Weave makes the optimization loop visible. Sera records the complete run as a trace with nested steps for reduction, specialist proposals, arbitration, validation, trials, evaluation, and revision.

The trace shows what each agent predicted, what Sera tested, what happened, and how the next decision changed. This is the proof that the agents form a self-correcting system rather than a chain of prompts.

## Product principles

- Measurements decide whether a configuration works.
- The search must spend fewer trials than an uninformed grid.
- Quality is a gate, not a reward for the optimizer to trade away.
- Cheap deterministic checks happen before expensive GPU trials.
- Failed trials remain useful evidence.
- Initial experiments change one lever at a time.
- Combination experiments use changes that already passed alone.
- Every accepted result can be reproduced from its model revision, configuration, workload, and evaluation record.
- Sera reports that no safe improvement was found when the evidence supports that result.

## Hackathon demonstration

The Marimo notebook is the test and demonstration environment. The product remains an installable Python library.

Molab runs on CoreWeave and provides one NVIDIA RTX Pro 6000 Blackwell GPU with 96 GB of GPU memory. A session can run for up to 12 hours. This is enough to run real vLLM trials instead of a simulation.

The first milestone is one Qwen model, a named baseline, one fixed candidate, a deterministic quality gate, a saved report, and a usable returned runner. Agent selection follows this working measured path.

The later search demonstration compares Sera with fixed-order grid search on Qwen/Qwen3-0.6B using a frozen candidate universe and equal trial budgets. It then adds zai-org/glm-4-9b-chat-hf for joint placement, with only the GLM reference and quantization checks needed for that demonstration. The notebook shows measured decisions and their trace when available.

Joint placement deliberately constrains each service's memory allocation to represent a smaller card. Freeze the allocations before the comparison. State on the placement slide and in the notebook: "Memory budget constrained to represent a smaller card; execution uses an RTX Pro 6000 with 96 GB." Show the declared budget, service limits, and measured peaks. This represents memory capacity, not a smaller card's compute speed or bandwidth. Claim quantization enabled placement only if the unquantized pair fails and the quantized pair passes under the same declared limits.

On a single GPU, trials run sequentially. The demonstration proves better use of that GPU; it does not claim to free a second GPU.

FP8 weights and FP8 KV cache must be checked on each architecture and the actual sm_120 GPU before enabling those levers. The proposed agent model must pass a structured-response check through W&B Inference before controlling trials. These checks remain unverified until their results are saved.

The hackathon ships the highest working level:

- Full live: two usable runners and measured joint placement.
- Joint placement fails or is unfinished: single-model optimization with one usable runner, isolated measurements, and a report. Return the baseline when no safe improvement exists.
- The live runner fails: an explicit replay notebook using saved real records, or a clearly labeled synthetic fixture when none exist. Replay provides no live runner and synthetic results support no performance or quality claim.

State the delivery level and evidence source in the notebook and release notes. The latter two levels are partial deliverables, not the full product described above.

## What Sera is not

- It is not a hosted inference platform.
- It is not a monitoring dashboard.
- It is not a static configuration advisor.
- It does not claim verified task quality without a task evaluator.
- It does not apply untested settings to a production service.

## Intended user

Sera is for any developer who can name a model and provide representative prompts. The developer does not need to understand quantization, batching, parallelism, GPU memory, or placement. Sera exposes the evidence for experts without making that expertise a requirement for use.

## References

- Molab GPU runtime: https://marimo.io/blog/reintroducing-molab
- CoreWeave vLLM deployment: https://docs.coreweave.com/products/cks/tutorials/deploy-vllm-inference
- vLLM supported models: https://docs.vllm.ai/en/latest/models/supported_models/
- W&B Inference: https://docs.wandb.ai/inference
