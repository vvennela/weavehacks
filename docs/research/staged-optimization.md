# Ordered optimization stages

The `sera` API can run stages in order. Each stage uses the current swarm and
measures its starting configuration again. It keeps the same prompts, workload,
model revision, GPU identity, runtime versions, and versioned quality evaluator.

```python
import sera

with sera.optimize(
    models=["Qwen/Qwen3-0.6B"],
    prompts=representative_prompts,
    evaluation=evaluate_answer,
    evaluation_version="my-task-check-v1",
    constraints=sera.Constraints(quality_floor=0.99),
    stages=["latency", "throughput"],
    k=3.0,
    output_dir="sera-runs/ordered-example",
) as result:
    result.print_summary()
    if result.models:
        print(result.models[0].generate(representative_prompts[0]).text)
    print(result.checkpoints)
```

Use a new output directory for each call. The evaluator and prompts above are
caller inputs, not an included task benchmark. Provider, certificate, Weave, and
GPU setup are the same as the [single-model API](simple-release.md).

## The trade-off limit

- `k=3.0` allows a later stage to be **at most 3% worse on each earlier frozen
  objective**. The new objective must improve. For latency then memory, a 2%
  memory improvement with 1% worse latency is acceptable; 4% worse latency is not.
- `k` defaults to 0% regression. Values must be finite numbers from 0 inclusive
  to 100 exclusive. This allowance never relaxes the quality floor or an original
  explicit hard limit. It requires an ordered `stages` call.
- `min_improvement_pct` is separate and optional. Stages default to 0%, meaning
  any strictly positive measured gain qualifies; a tie does not. Set it to 3.0
  only if a stage must improve its own objective by at least 3%. It also works on
  standalone calls. Neither parameter imposes a total trial cap.

The limits control acceptance and progress stopping. They are not speed
predictors: some candidates still need measurement before rejection. Percentages
for different metrics are not subtracted to invent one overall score.

## Stage behavior

| Stage | Objective | Available techniques |
| --- | --- | --- |
| `latency` | Lower worst-load p95 | Existing automatically generated legal controls |
| `throughput` | Higher output tokens per measured second | Existing automatically generated legal controls |
| `memory` | Lower sampled device-memory peak | Existing automatically generated legal controls |
| `quantization` or `quant` | Lower sampled device-memory peak | Supported precision controls only; currently FP8 KV for Qwen3-0.6B |

The quantization stage does not enable new weight formats. Qwen72B already uses
FP8 weights in its fit-first path; its combined FP8 weights/FP8 KV path remains
disabled. A quantization stage with no untested supported precision change
remeasures its baseline, records no improvement, and returns it if it passes.
It never labels lower precision as a memory saving without a measured saving.

Stage names can repeat, for example `['latency', 'throughput', 'latency']`. Completed
memory stages freeze their measured peak; later stages may exceed it only within
`k`. Both latency and memory ceilings use frozen measurements, not a previous
derived ceiling, so allowances do not accumulate. The tightest earlier limit
remains, including stricter original hard limits.
Completed throughput stages freeze their measured output tokens per second.
With `k=3`, a measured 100 tokens/second sets a 97 tokens/second floor for every
later stage. The highest earlier floor applies, so repeated stages cannot
compound the allowance. An explicit `Constraints(min_output_tokens_per_second=...,
quality_floor=...)` can set a stricter original floor. Missing, zero, or nonfinite
throughput cannot pass this floor or become a completed throughput checkpoint.
For latency then throughput, the throughput stage must retain the earlier latency
ceiling. For throughput then latency, the latency stage must retain the throughput
floor. Only the `stages` list changes; the API carries the saved configuration and
measured limits forward.

Each stage stops under the existing progress-plus-confirmation rule or when no
legal candidate remains. There is no default total trial cap. If the caller
supplies a budget, it applies separately to each stage. A list of stages runs
once in its given order; it is not an endless outer loop or a claim of a global
optimum.

## Checkpoints, failures, and cost

- Each accepted stage saves a configuration, measured limits, source trial
  snapshot and hash, and its Weave URL under `checkpoints/`. These are not model
  weight files. Normal cleanup cannot change the saved source snapshot.
- The old runner closes before the next stage starts. The next stage remeasures
  the saved configuration; startup and baseline measurement have real costs.
- A failed candidate cannot replace the stage baseline. If the fresh baseline
  itself fails and no candidate passes, the sequence stops without a safe runner.
  Older checkpoints remain saved; Sera does not pretend a closed runner is usable.
- Startup, identity, telemetry, or cleanup errors stop the sequence. No later
  stage starts after cleanup failure. The final successful runner belongs to the
  caller and must be closed, preferably with the context manager above.
- Each stage has its own Weave trace and run ledger. The parent report links
  them. Whole-sequence crash resume and a separate API for resuming a checkpoint
  in a later call are not implemented.

The stage contract has automated synthetic integration tests. Live performance
claims require a new recorded GPU run; earlier single-stage and joint-placement
measurements do not establish a staged speedup.
