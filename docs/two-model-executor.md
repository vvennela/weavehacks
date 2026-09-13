# Two-model executor

`sera.place` implements one explicit placement plan. It first measures each model
alone, then starts both under one process owner. It returns two live runners only
when both pass. It never silently drops a requested model.

This path is implemented and tested offline. **A passing live placement is not
established.** Qwen's existing structured-output result is 7/8 at the unchanged
0.99 floor; GLM's result is 8/8. The Qwen result still blocks that workload. This
implementation does not change questions, scores, thresholds, or model choices.

## Required inputs

- A validated `PlacementPlan` for the pinned Qwen3-0.6B and GLM-4-9B pair. It declares
  measured physical capacity, a smaller-card memory budget, each service's byte
  allocation, its full runtime configuration, and its quality and p95 limits.
- One `PlacementWorkload` per model: prompts, a callable absolute task evaluator,
  evaluator version, and declared load levels. Both models use the same load
  levels, but can have different representative prompts. Each model receives
  exactly the same prompts and generation settings alone and together.
- One `PlacementMemoryEstimate` per model: weight, KV cache, workspace, process
  overhead, and fragmentation bytes. These are explicit caller estimates, not
  measured guarantees. Each total must fit its allocation.
- A new output directory. Existing results are never overwritten.

The plan keeps 10% of the declared budget outside service allocations. Each
`gpu_memory_utilization` must equal service bytes divided by physical GPU bytes.
Unsupported precision combinations remain disabled. No automatic calibration,
new precision approval, or allocation choice occurs inside this call.

```python
from sera import place, PlacementWorkload, PlacementMemoryEstimate, Workload

# frozen_plan and frozen_estimates are approved data, not guessed defaults.
# qwen_prompts/glm_prompts and scorers are the user's versioned task contract.
profiles = {
    "Qwen/Qwen3-0.6B": PlacementWorkload(
        qwen_prompts, qwen_scorer, "my-task-v1", Workload(concurrency=[1, 2, 4, 8])),
    "zai-org/glm-4-9b-chat-hf": PlacementWorkload(
        glm_prompts, glm_scorer, "my-task-v1", Workload(concurrency=[1, 2, 4, 8])),
}
with place(plan=frozen_plan, workloads=profiles,
           memory_estimates=frozen_estimates, output_dir="placement-run-001") as result:
    if result.models:
        for model in result.models:
            print(model.model_id, model.generate("A fresh task prompt").text)
    else:
        print(result.report["decision"])
```

This is separate from `sera.optimize`: it executes a supplied plan, not a new
placement-agent schema. An autonomous plan selector and its provider check remain
future integration work. The single-model swarm does not gain untested placement
tools by importing this module.

## What is checked and saved

1. Validate and freeze all inputs before GPU startup. Estimated non-fit produces
   `not-attempted` and starts no service.
2. Run isolated measurements serially under the frozen allocations. Apply the
   task evaluator to both serial quality outputs and timed outputs. Require each
   model's quality floor, latency limit, zero generation errors, valid memory
   telemetry, physical capacity, and cleanup. Any failure prevents joint startup.
3. Start both services on the same GPU. The owner verifies engine children by
   process group, not just the API server PID. Unknown processes are rejected and
   never terminated. A second start failure rolls back the first service too.
4. Synchronize both load generators before and after each measured load and
   quality phase. Save each window's monotonic timestamps, overlap duration, and
   overlap coverage. Require positive overlap at every declared load. Unequal
   window durations remain visible; this does not prove constant interference.
5. Reapply each task and latency gate. Require identical isolated/joint input
   token IDs and GPU identity. Record isolated-versus-joint latency changes with
   no assumed cause. Return both runners only after these gates pass.
6. Save `result.json`, `report.md`, per-service runtime records, requests, and raw
   vLLM metrics. `close()` attempts every owned service even if another close
   fails. Cleanup failure raises, stays saved, and cannot produce a passing pair.

Per-service memory sums NVIDIA compute-process memory for each owned process
group. Device peak is a separate field. Unavailable accounting, an unknown GPU
process, substantial unattributed device memory, or a breached budget fails the
joint gate. Sampling is once per second and can miss short peaks. This is not
hardware partitioning or a continuous memory cap. NVIDIA queries do not run
inside each request's latency timer.

The executor records local evidence. It does not automatically create a Weave
root; no placement trace or placement-agent claim is established by these tests.

## Live gates still open

- A quality-valid Qwen configuration under the unchanged approved task contract.
- Approved calibration and frozen smaller-card allocations and latency limits.
- A passing joint GPU run and fresh returned-runner calls on that hardware.
- An unchanged-budget unquantized comparison before claiming quantization enabled
  placement. One passing pair alone cannot establish that claim.

For the specified RTX Pro 6000 demonstration, show this exact disclosure on the
notebook and slide:

> Memory budget constrained to represent a smaller card; execution uses an RTX Pro 6000 with 96 GB.

This represents memory capacity, not a smaller card's compute speed or bandwidth.
The executor reports actual physical bytes, declared bytes, service fractions,
per-service memory peaks, and device peak. Missing values stay unavailable.
