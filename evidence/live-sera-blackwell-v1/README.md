# VERDICT: MEASURED — with two named exceptions

The two `substrate: "vllm"` rows in `runs/ledger.jsonl`
(`p1-qwen3_8b-r0-2c41ad`, `p1-qwen3_8b-r1-76f772`) were produced by
`VllmRunner.run()` driving a **real `vllm serve` subprocess on the physical
Blackwell**. The latency, throughput, KV-occupancy and batch-size numbers in
`p1-qwen3_8b-r0-2c41ad` are genuine engine-side measurements.

Two fields on that same row are **not** measured and must not be described as such:

| Field | Status |
|---|---|
| `p50_latency_ms`, `p95_latency_ms`, `throughput_rps` | **MEASURED** — client-side timings of real streamed completions |
| `kv_occupancy`, `mean_batch_size`, `preemptions` | **MEASURED** — scraped from the live vLLM `/metrics` endpoint while load was in flight |
| `footprint_gb` | **DERIVED** — analytic weight arithmetic × measured KV occupancy. Not read from the device. |
| `quality_score: 1.0` | **NOT MEASURED — ANALYTIC.** Produced by `_simulated_score(cfg)` in `src/sera_loop/quality.py:29`, a lookup in `DTYPE_QUALITY_PENALTY`. No eval was run on the GPU. For bf16 it returns 1.0 by definition. |
| `mem_bandwidth_util: null` | Correctly recorded as unknown. The "69.3%" in the run log is *derived from throughput*, and the log says so. |

---

## The proof

### 1. The numbers match neither simulator

I ran both simulators locally against the **identical spec and seed**
(`runs/live_qwen3_8b_blackwell.yaml`, seed 7). Raw output in
`discriminator.json`.

| | **ledger row (r0)** | analytic `SimRunner` | `--fake-vllm` path |
|---|---|---|---|
| p50 ms | **1781.02** | 2697.30 | 272.84 |
| p95 ms | **2141.74** | 3708.28 | 326.45 |
| throughput rps | **1.0497** | 1.0511 | 1.0971 |
| kv_occupancy | **0.002790** | 0.007882 | 0.011724 |
| mean_batch_size | **2.2673** | 2.9628 | 1.1724 |
| footprint_gb | **16.5712** | 16.8836 | 17.1194 |
| mem_bandwidth_util | **null** | 0.5248 | null |

The ledger row is off by 1.5x from the analytic simulator and by 6.5x from the
fake server. It is not either of them.

### 2. The numbers sit inside the independently GPU-attested envelope

From `evidence/live-blackwell-baseline-v1/summary.json` (a separate sweep whose
`nvidia_smi_csv` field attests the RTX PRO 6000 Blackwell, driver 595.71.05,
sm_120), same 1024-in / 128-out shape:

- concurrency 2: p50 **1921 ms**, 1.041 rps
- concurrency 4: p95 **2032 ms**
- concurrency 8: p95 **2278 ms**

The Sera row: p50 **1781 ms** at 1.050 rps with a sampled mean batch of **2.27**,
p95 **2142 ms**. Open-loop bursty arrivals (burstiness 1.5) put p50 a little
under the closed-loop c=2 figure and p95 between the c=4 and c=8 figures.
That is exactly where a real run of this workload on this card lands.
Little's law closes too: 1.0497 rps × 1.781 s = 1.87 resident, against a
sampled 2.27 (the gauge also counts prefilling requests).

### 3. Timing that only a real engine can produce

From `sera_phase1_live.log`:

- `start_utc=2026-09-13T18:34:50Z` → row r0 written at **18:36:52Z** = **122 s**.
  The load replay itself is ~31.4 s. The remaining ~88 s is a real Qwen3-8B
  weight load. The `--fake-vllm` path runs the *entire* same trial in **30.7 s**
  end to end (I timed it) because its server is ready in 0.02 s.
- row r0 → row r1 = **300.05 s**, which is `HEALTH_TIMEOUT_S = 300.0`
  (`vllm_runner.py:49`) to the sample. Round 1 launched a real `vllm serve`
  with `--kv-cache-dtype fp8` and it never came up. `fake_launcher` has
  `startup_s=0.02` and **cannot** emit `"server never became healthy"`.

The run window (18:34:50–18:41:52Z) is 2 min after the baseline sweep
(18:31:40–18:32:39Z) and ~9 min after the engine came up (~18:26Z). Consistent.

### 4. The row was written by the vLLM code path, byte for byte

`footprint_gb` reconstructs **exactly** — all 17 significant digits —
from `vllm_runner.py:431-433` fed with the row's own measured `kv_occupancy`:

```
16.4 GB weights + 4.7186e-06 GB/token × 0.0027898893785482486 × 416124.13 tokens
  = 16.571187612267718   ==   ledger value 16.571187612267718
```

`SimRunner` computes footprint differently and gets 16.8836. This row came out
of `VllmRunner`, not out of the simulator and not out of a text editor.

Two more fingerprints of a live sampler thread:

- `mean_batch_size = 2.267326732673267` is exactly **229/101** — 101 Prometheus
  scrapes with `vllm:num_requests_running > 0` summing to 229. At
  `SAMPLE_INTERVAL_S = 0.25` that is ~25.3 s of in-flight sampling inside a
  ~31.4 s wall.
- `throughput_rps = 1.049701...` is exactly **33 / 31.4375 s**. The generated
  trace for seed 7 is 33 requests with last arrival at 29.83 s. All 33
  completed; zero errors.

---

## The one path that WOULD be fatal (it exists, but it did not produce these rows)

`src/sera_loop/__main__.py:32-39`:

```python
if fake_vllm:
    from .runner.fake_vllm import fake_launcher
    from .runner.vllm_runner import VllmRunner
    return VllmRunner(launcher=fake_launcher)
```

`VllmRunner.substrate` is hard-coded to `Substrate.VLLM` (`vllm_runner.py:266`),
so **`python -m sera_loop --fake-vllm` writes ledger rows labelled
`substrate: "vllm"` whose numbers come from an in-process Python fake with no
GPU, no weights, and — in its own words — "no physics."** Nothing in the
`TrialRecord` schema distinguishes such a row from a real one. I confirmed this
by running it: it emitted `substrate: vllm` with p50 272 ms.

These two rows are provably not from it (§1, §3, §4), but the hazard is live for
any future row. **Recommended fix: make `substrate` an instance attribute that
`fake_launcher` overrides to a third value (`fake_vllm`), or refuse to write a
`vllm` row that carries no captured GPU identity.**

The *other* fallback is honest: `select_runner()` falls back to `SimRunner()`,
which labels its rows `sim`. There is no silent-downgrade path there.

---

## Provenance that is MISSING and should be added

The ledger rows contain **zero** evidence of the hardware they ran on. Every
claim above had to be reconstructed from side channels. Add to `TrialRecord`:

1. **GPU identity** — `nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap`
   captured at trial time. Today `gpu_assignment` says only `"gpu0"`, a label
   from the YAML. The string "RTX PRO 6000 Blackwell" in the spec is *declared*,
   never read from the device.
2. **Engine identity** — `vllm --version` (0.29.0), torch/CUDA versions,
   engine V0/V1.
3. **The actual server argv.** `vllm_flags()` builds it and throws it away. The
   row's `config` block is Sera's `InferenceConfig`, not what the server was
   told. For r0 it would have been:
   `vllm serve Qwen/Qwen3-8B --served-model-name qwen3_8b --revision main --port 8100 --host 127.0.0.1 --max-model-len 4096 --max-num-seqs 256 --max-num-batched-tokens 8192 --tensor-parallel-size 1 --pipeline-parallel-size 1 --gpu-memory-utilization 0.9000 --dtype bfloat16 --kv-cache-dtype auto`
4. **Engine start time, ready time and model-load duration**, plus pid and port.
   The 88 s load is the single strongest signal that weights really moved, and
   it is nowhere in the row.
5. **`TrialOutcome.notes` — computed and discarded.** `vllm_runner.py:446-449`
   builds `errors=… requests=N/M gen_tokens=… gauge_samples=…` and
   `TrialRecord` has no `notes` field to hold it. `gen_tokens` is a delta of the
   real `vllm:generation_tokens_total` counter and is the most direct
   engine-side proof available. **This is the highest-value single addition.**
6. **Failure diagnostics.** `managed_vllm` sends the child's stdout/stderr to
   `DEVNULL` (`vllm_runner.py:244`), so r1's `"server never became healthy"` has
   no cause recorded. It is unknown whether fp8 KV is unsupported on sm_120 in
   vLLM 0.29.0, or whether the round-0 server had not yet released the card.
7. **Per-field measured/derived flags**, so `footprint_gb` and `quality_score`
   cannot be read as measurements.
8. **Host / sandbox identity, run id, git commit, spec hash.** Also note
   `runs/` is `.gitignore`d, so the ledger has no version-control provenance at
   all.

Sera also never reuses an external server: `VllmRunner.run()` ignores
`self.host` (`SERA_VLLM_HOST` gates only `available()`), so every trial launched
its own engine on port 8100.

---

## What is safe to say on stage

> "Sera's baseline trial for Qwen3-8B is a real vLLM measurement on the live
> Blackwell — 2142 ms p95 at 1.05 requests/sec, with a mean batch of 2.3
> sampled straight off the engine's own metrics. The next trial, fp8 KV cache,
> is a real failure: the server never came up, and the ledger records the
> failure rather than hiding it."

**Do not say** "quality held at 1.0 on the GPU." That number is an analytic
penalty-table lookup, not an eval. Say "the quality gate is still analytic; the
latency and throughput are measured."

**Do not say** "the loop improved throughput on the GPU." It did not — one
baseline succeeded, one candidate failed to launch, and the log correctly
reports `p95 2142ms -> 2142ms (+0.0%)`.

---

## Files here

- `README.md` — this verdict
- `discriminator.json` — the three-way numeric comparison, footprint
  reconstruction, and timing arithmetic
- `ledger_vllm_rows.jsonl` — the two rows under examination, verbatim
- `sera_phase1_live.log` — the live run's stdout (copied from
  `evidence/live-blackwell-baseline-v1/`)

Nothing outside this directory was modified. The molab sandbox was not touched.
