# Final benchmark checks

The saved provider replays and both pressure pilots pass the consistency audit.
The results do **not** establish an ablation advantage or either pressure scenario.

## Agent replay: all three methods tie

| Policy | Trials to near-oracle | Provider calls | Policy wall time |
| --- | --- | --- | --- |
| Full swarm | 1 | 39 | 271.71 s |
| No trial history | 1 | 38 | 221.45 s |
| Round-robin, no arbiter | 1 | 12 | 191.25 s |

All three selected prefix caching first and finished at the same **625.73 ms**
p95. All **89 provider attempts** passed their schemas. No initial or refined
specialist response was rejected. There is no measured benefit from the extra
swarm coordination on this three-candidate workload. Do not label this a win
over an intelligence ablation.

The earlier live loop remains ahead of grid in first-hit count (**1 versus 3**)
and ahead of the 20-seed random median (**1 versus 2**). These exploratory results
do not satisfy the full section 19.4 contract.

The audit replays each recorded choice sequence against the original audited
outcomes. It checks exact curves, oracle, selected IDs, policy hashes, actual
provider prompt hashes, typed responses, three-specialist versus round-robin
structure, and visibility of only previously selected trial evidence. The
no-history calls contain no prior measured trial evidence. These are CPU-side
agent searches over cached metrics, **not fresh Weave inspections or GPU runs**.

The replay driver was from `3a9cb31`; the likely imported installed Sera library
was built from `d8c7304`. This is a retrospective import-path assessment. The ten
relevant investigator, proposal, prompt, relay, validation, and evidence modules
compared by the audit are byte-identical between those versions. The config
change permits TP 1/2/4/8 in the newer checkout; all frozen candidates use TP1.
New placement and portable GPU execution paths were not exercised by replay.

## Pressure pilots: neither scenario established

Both used BF16 weights/KV, eight concurrent requests with exactly 2,304 rendered
tokens each, two warmups, and three measured waves. Memory fractions deliberately
represent smaller cards; the physical device remains the 96 GB RTX Pro 6000.

| Profile | Memory fraction | Peak KV | Preemptions | Measured queue mean | Request p95 |
| --- | --- | --- | --- | --- | --- |
| Cache pressure | 0.025 | 78.99% | 0 | 99.46 ms | 397.92 ms |
| Reversed pressure | 0.10 | 24.58% | 0 | 5.33 ms | 308.57 ms |

Cache pressure required at least **80% KV use and one preemption**. It passed
neither threshold. The reversed profile required **queue mean at least 10 ms**,
KV below 50%, and no preemptions. Its queue threshold failed.

For each pilot, the audit independently reads the raw Prometheus histogram
sum/count differences. The queue count increases by exactly **24**, excluding
warmups. It checks all 24 saved requests, input token identities, finite positive
latencies, sampled KV peak against the raw peak snapshot, profile and workload
hashes, and zero-memory cleanup. Both pilots have zero request or sampling errors.
Startup was **45.05 s** for each, separate from request latency.

These padded diagnostic requests are not task-quality acceptance. No FP8
comparison, candidate search, retuning, or quality-floor change followed from
this audit. Original results and thresholds remain unchanged.

## Reproduce

```bash
PYTHONPATH=. python evidence/final-benchmark-audit-v1/audit.py --evidence-root evidence
```

The script uses no GPU or provider. `result.json` binds the audited files by
SHA256 and records the recomputed measurements. This checks saved-artifact
consistency, not cryptographic proof of execution.
