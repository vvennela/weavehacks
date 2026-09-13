# Sera — an agentic inference optimization team

Sera finds a faster, smaller way to serve your models on the hardware you already
have, and proves every change with a measurement.

Three specialist agents tune a model's serving configuration, argue over a bounded
trial budget, and write every result to a ledger including the ones that failed. Then
a second phase re-reads that ledger with a different question — not "what was fastest"
but "what is small enough that both models could share one GPU" — and finds out by
running them together.

**Phase 1: how should each model run?**
**Phase 2: how should they share the hardware?**

---

## Run it

```bash
uv venv --python 3.12 && uv pip install -e .
PYTHONPATH=src python -m sera --spec specs/molab.yaml --fresh
```

`specs/molab.yaml` is the target environment: **one** RTX PRO 6000 Blackwell, 96GB,
running Qwen3-0.6B beside GLM-4-9B. On one GPU the claim is better use of that device
— not that a second card was freed.

No GPU required. No API key required. The loop runs against a simulator by default and
prints its full reasoning. Set `SERA_VLLM_HOST` to run trials on real hardware, and
`WANDB_API_KEY` to trace the run in Weave.

```bash
PYTHONPATH=src python -m pytest tests/ -q      # 32 tests
PYTHONPATH=src python -m sera --spec specs/demo.yaml --fresh    # 2-GPU variant
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

## The result it reaches on `specs/molab.yaml`

Both models are improved alone — Qwen3 3446ms → 856ms p95, GLM-4 7057ms → 2789ms — and
GLM-4's int4 candidate is reverted for scoring 0.945 against a 0.975 floor despite being
the fastest thing tried. Then Phase 2 asks whether they can share the card:

```
[fit check]  10.21GB against 86.40GB usable — 76.19GB headroom
[joint trial 1]
  qwen3_06b: p95  856ms solo -> 4466ms co-resident (+422%)
  glm4_9b:   p95 2789ms solo -> 7589ms co-resident (+172%)
  both FAIL

[retune] feeding qwen3_06b's contended measurement back to the reducer
  -> under contention the digest reads 50.8% bandwidth, not 25.9%, so the
     quantization specialist argues from bandwidth instead of tensor cores
  -> finds 792ms

[joint trial 2]
  qwen3_06b: p95 792ms solo -> 2934ms co-resident (+271%)
  still FAIL. Phase-2 allowance spent.

[result] no safe joint placement. The per-model configurations stand.
```

Three things worth noticing. Memory was never the binding constraint — the fit check
cleared with 76GB spare and the trial still failed, which is why the joint trial exists
at all. The back-edge is not narration: the contended measurement re-enters the reducer,
the digest genuinely changes, and the specialist changes its *mechanism* in response.
And the run ends in a refusal. Sera reports that no safe placement was found rather than
shipping a configuration that breaks both SLOs.

## Honest comparison against a conventional tuner

`src/sera/baseline.py` sweeps the identical candidate universe with the identical
budget through the identical gates, choosing by fixed order or at random instead of by
reasoning. The metric is the one the specification asks for: **trials to reach a valid
configuration within 5% of the oracle**, where the oracle is the best viable p95 in the
whole universe, found by running all 288 configurations once.

On `specs/tight.yaml`:

| | oracle | Sera | fixed-order grid | random (30 seeds) |
|---|---|---|---|---|
| model_a — 6.2% of legal configs qualify | 362ms | **trial 6, reaches 362ms** | never in 12 | median 4.5, **fails 16/30** |
| model_b — 25% qualify | 352ms | **trial 4, reaches 352ms** | never in 12 | median 3.0, fails 0/30 |

Read that carefully, because the headline is not "we win."

**Sera beats fixed-order grid search outright** — grid never reaches the threshold
within budget on either model. That is condition 1 of the spec's §19.4.

**Sera does not beat random search on median trials**, and we are not going to claim it
does. But the median hides the thing that matters: on the hard model, random search
**fails outright in 53% of seeds**, while Sera reaches the oracle deterministically.
Comparing a median-over-successes against a result that always succeeds is survivorship
bias. The defensible claim is reliability on hard search problems, not speed on easy
ones — and on the easy model, random genuinely wins.

### A negative result we are keeping in the repo

The specification's §13 calls for an exploration trial, to stop the arbiter spending
every slot on the lever it already trusts. It is implemented and unit-tested.

**It fires zero times in every scenario we ship.** With three lever groups and two
slots, the selected set already covers every live lever, so there is no unselected
lever to promote. The code is correct and currently inert.

What actually improved the search was unrelated: letting a specialist offer **two**
candidates instead of one, per §13's "zero to two proposals". That alone moved model_a
from *never reaching the target* to *reaching the oracle exactly*. We found that by
ablating the feature we expected to matter and measuring no difference.

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
