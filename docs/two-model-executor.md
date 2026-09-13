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
  A latency contract can be an absolute `p95_latency_ms`, a relative
  `max_p95_slowdown_fraction`, or both (the tighter limit wins).
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
           memory_estimates=frozen_estimates, output_dir="placement-run-001",
           weave_project="your-team/your-project") as result:
    if result.models:
        for model in result.models:
            print(model.model_id, model.generate("A fresh task prompt").text)
    else:
        print(result.report["decision"])
```

This is separate from `sera.optimize`: `place` executes one supplied plan.
`optimize_placement` now selects and tests a menu of measured legal plans with the
existing typed arbiter. See [automatic placement](automatic-placement.md). The
single-model swarm does not silently change its tools when this module is imported.

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

## Optional Weave tracing

Set `weave_project` to create a `sera_place` root. Install the `swarm` extra and
configure the usual W&B credentials first. Omit the option to keep execution local
and avoid importing or initializing Weave.

The trace includes each model's saved isolated and joint requests, output text,
token IDs, measured latency, usage, and safe error type. These events are exported
after each service's measurement finishes; their span duration is logging time,
not inference latency. Both service threads retain the same placement root.

`placement_quality_gate` records absolute task scores and per-prompt failures for
serial and timed outputs. `placement_decision` includes rejected requirements,
overlap, measured latency changes, and shared memory failures.
`placement_runtime_failure` uses known startup signatures and hashed log
references, not arbitrary server exception text. The saved result includes the
trace URL and export status. Trace failures do not turn a bad model into a passing
model or rewrite measured quality.

The root ends before returning live runners. Later `close()` exports and flushes
a separate `placement_cleanup` event carrying the original root URL and plan hash.
Fresh user requests after return are not automatically traced by this wrapper.
Failed trace persistence or root export closes runners that cannot reach the
caller. Cleanup failure remains a failure even when trace export also fails.

These tracing paths have offline tests with a fake Weave service. No live
placement trace is claimed until a GPU run passes the existing prerequisites.

## Agent selection contract

`ArbiterDecision` names one legal plan ID or abstains. `optimize_placement` binds
every offered plan to matching isolated requests, task/workload hashes, GPU and
runtime identity, configuration, cleanup, and memory limits. It recomputes quality
and latency gates instead of trusting saved pass flags. The existing provider
certificate is still a schema-format check, not proof of placement reasoning.
Every actual placement response is checked again for a legal, untested plan ID.

The default objective and stop rule follow the specification: latency first,
memory tie-break, and one no-progress round plus one confirmation. An explicit
memory or throughput objective and optional trial limit are supported. No
allocation or quality threshold is invented. The deterministic executor remains
the final authority, including after restoring a previously passing winner.

## Live gates still open

- A quality-valid Qwen configuration under the unchanged approved task contract.
- Approved calibration and frozen smaller-card allocations. The user approved a
  10% joint slowdown allowance: set `max_p95_slowdown_fraction=0.10` before the
  isolated measurements. Keep the same eight tasks, 0.99 floor, and zero errors.
  The executor derives each numeric joint ceiling as that exact plan's isolated
  p95 multiplied by 1.10, and saves its workload/configuration/hash provenance
  before joint startup. Joint results cannot redefine their own acceptance limit.
- A passing joint GPU run and fresh returned-runner calls on that hardware.
- An unchanged-budget unquantized comparison before claiming quantization enabled
  placement. One passing pair alone cannot establish that claim.

For the specified RTX Pro 6000 demonstration, show this exact disclosure on the
notebook and slide:

> Memory budget constrained to represent a smaller card; execution uses an RTX Pro 6000 with 96 GB.

This represents memory capacity, not a smaller card's compute speed or bandwidth.
The executor reports actual physical bytes, declared bytes, service fractions,
per-service memory peaks, and device peak. Missing values stay unavailable.
