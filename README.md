# weavehacks — an agentic inference optimization team

Three specialist agents tune a model's serving configuration, argue over a bounded
trial budget, and write every result to a ledger including the ones that failed. Then
a second phase re-reads that ledger with a different question — not "what was fastest"
but "what is small enough that two models could share one GPU" — and finds out by
running them together.

**Phase 1: how should each model run?**
**Phase 2: how should they share the hardware?**

---

## Run it

```bash
uv venv --python 3.12 && uv pip install -e .
PYTHONPATH=src python -m loop --spec specs/demo.yaml --fresh
```

No GPU required. No API key required. The loop runs against a simulator by default and
prints its full reasoning. Set `LOOP_VLLM_HOST` to run trials on real hardware, and
`WANDB_API_KEY` to trace the run in Weave.

```bash
PYTHONPATH=src python -m pytest tests/ -q      # 32 tests
PYTHONPATH=src python -m loop --spec specs/tight.yaml --fresh   # harder SLOs
```

---

## What it actually does

```
Spec ──► Reduction ──► 3 specialists ──► Arbiter ──► Validator ──► Trials ──► Gates ──► Ledger
         (no LLM)      propose or         spends      rejects on    run &     SLO then      │
                       declare dead       budget      arithmetic    measure   quality       │
                                                                                            │
         ┌──────────────────── Phase 2 re-reads the same ledger ◄─────────────────────────┘
         │
         └─► Frontier reader ──► Fit check ──► Joint trial ──► Per-model gates ──► verdict
             (smallest, not     (arithmetic)  (both models,    (each independently)   │
              fastest)                         one card)                              │
                                                                                      │
             └──────── contention evidence routed back to specialists ◄───────────────┘
```

**Reduction** turns serving metrics into a dozen named scalars. Deterministic, no LLM.
Every specialist argues from this same digest, so disagreements are about strategy
rather than about arithmetic.

**Three specialists**, each owning a disjoint lever group:

| Specialist | Owns | Can say |
|---|---|---|
| Quantization | `weight_dtype`, `kv_cache_dtype` | proposal, or "not memory bound here" |
| Batching | `max_num_seqs`, `max_num_batched_tokens`, `enable_chunked_prefill` | proposal, or "the batch is not the constraint" |
| Parallelism | `tensor_parallel_size`, `pipeline_parallel_size` | proposal, or "no spare devices" |

Declaring a lever **dead** is a first-class output. A specialist that always finds
something to suggest is not reasoning, it is emitting.

**Arbiter** ranks proposals by confidence × expected magnitude × the proposer's
calibration, and spends the slots. It will not merge two proposals into one config —
one lever group per trial, so a measured change is attributable to a specific claim.
Combinations are proposed explicitly, afterwards, once each constituent has a measured
solo effect.

**Ledger** is append-only JSONL. Every trial: config, who proposed it, what they
predicted, what happened, the quality score, the verdict, the substrate, and whether
the prediction held. Reverts included — they are the most informative rows in the file.

---

## The result it reaches on `specs/demo.yaml`

Both models clear their SLO alone. The fit check says they share a 24GB card with
18.7GB to spare. They still cannot share it:

```
[interference]
  model_a: p99 1607ms solo -> 2501ms co-resident with model_b (+56%)
  model_b: p99  745ms solo -> 4426ms co-resident with model_a (+494%)

[verdict] REVERTED — model_b breached SLO (4426ms vs 3000ms)
  Memory was not the binding constraint: the fit check cleared with 18.73GB spare.
  Device-time contention was — model_b's p99 inflated +494% beside model_a,
  whose traffic is 94% prefill.
```

Two things worth noticing. The frontier reader **rejected the fastest config it
found** (466ms) because it occupied both GPUs, which is the opposite of what freeing a
GPU requires — it took a 1607ms single-device config instead. And when a model had no
viable single-device config at all, the constraint was routed back to the specialists
for a retune with tensor parallelism off the table. That back-edge is the loop closing.

---

## Honest comparison against a conventional tuner

`src/loop/baseline.py` sweeps the identical lever space with the identical budget
through the identical gates, choosing randomly instead of by reasoning.

**Random search matches or beats this loop on trials-to-target.**

| | model_a | model_b |
|---|---|---|
| Agent loop | trial 4 | trial 3 |
| Random search (30 seeds) | median 3, range 1–7 | median 3, range 1–7 |

The reason is measurable rather than mysterious: at the demo SLOs, **62–75% of legal
configurations already pass**, and even at the tightened SLOs in `specs/tight.yaml` it
is still 25%. When most answers are correct, guessing is an excellent strategy, and
this matches the known result that random search is very hard to beat in
low-dimensional discrete spaces.

We are reporting this rather than tuning the scenario until the agents win. A
benchmark adjusted until it flatters the system under test measures nothing.

**So the claim is not trial efficiency.** What this loop does that a sweep cannot:

1. **Phase 2 is not a search problem.** A sweep has no notion of re-reading its own
   history under a new objective, no fit check, no joint trial, and no way to
   attribute a co-tenancy failure to bandwidth rather than memory. Consolidation is
   the product; Phase 1 is the evidence it runs on.
2. **It explains itself.** Per-lever effect sizes and a stated mechanism. A sweep
   returns a config and no understanding of why it works — which is what you need when
   it stops working.
3. **Dead levers are transferable facts.** "Batching is irrelevant for this traffic
   shape" is true of the workload, not of one config, and it holds for the next model
   on the same traffic.
4. **Constraints propagate.** When Phase 2 needed a single-device config, the loop
   re-derived one under that constraint instead of restarting blind.
5. **It tracks whether it was right.** Predictions are scored against measurements and
   the arbiter reallocates budget accordingly.

Where trial efficiency *should* matter is a larger lever space with a sparser solution
set, and continuous rather than discrete values. That is a claim we have not tested,
so we are not making it.

---

## Substrate

One `TrialRunner` interface, two implementations. Everything above it — specialists,
arbiter, gates, both phases — is identical either way, and every ledger row records
which produced it so simulated and measured numbers are never silently compared.

The simulator models continuous batching directly rather than curve-fitting: decode is
bandwidth bound, prefill is compute bound, KV capacity caps concurrency, exhausting it
preempts, chunked prefill trades TTFT for decode smoothness, and TP shards weights at
a per-step sync cost. Co-tenants are scheduled against **one shared device clock**, so
contention is a consequence of sharing rather than a penalty multiplier — which is why
a joint result is comparable to the solo rows it came from.

It is not a claim to predict absolute H100 latency. It is a claim that the mechanisms
driving tuning decisions are represented, so the loop faces real tradeoffs.

---

## Sponsor tooling

| Tool | Role | Status |
|---|---|---|
| **Weave** | traces every proposal, arbitration, trial and gate | wired via `tracing.py`, activates when `WANDB_API_KEY` is set |
| **marimo** | reproducible notebook: baseline → loop → charts | `notebooks/` |
| **ARIA** | between-round analysis of ledger results | `aria/handoff.py` exports the digest; programmatic access unverified |

---

## Scope

The vision describes five optimization roles. This ships **three** — quantization,
batching, parallelism — matching the diagram. Compute/kernel efficiency and serving
strategy (caching, speculative decoding) are the documented extension path: add a
`Specialist` subclass and a disjoint lever group, and the arbiter picks it up.

The general idea is not novel — Baseten has publicly described a related internal
agentic optimization framework. What is here is this specific loop design.
