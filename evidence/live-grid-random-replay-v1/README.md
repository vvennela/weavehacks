# Audited live search and seeded random replay

Source: `evidence/live-grid-comparison-v1`, registration
`2843eee593b706529bd178369ef91a529900ee6cb8412ce27ffa553e019c1eb5`.
The live source result hash is
`1c4d5b7c80386fdce73c5f28c1efc057f056522d8c05d4636cc0d917184117d3`.

The recorded Luna loop reached the near-oracle threshold after **one** candidate.
Lexicographic grid required **three**. The median of the **20 preregistered random
seeds** required **two**. The baseline is shared setup and counts as zero trials.

| First-hit trial count | Random seeds |
| --- | --- |
| 1 | 5 |
| 2 | 8 |
| 3 | 7 |

All methods eventually see all three candidates at this exploratory full-universe
budget. Their final best p95 is therefore tied at **625.727727 ms**. The live
baseline p95 was **770.682321 ms**. This is a search-order result, not a better
terminal configuration or a statistical performance claim.

The same saved outcomes were used for all methods. No provider or GPU calls were
made for this random replay. Owned runtime intervals total **754.314436 seconds**,
including **284.300691 seconds** of startup. Do not add startup a second time.
The owned intervals can include waiting for agents while a runtime stays alive.

The full strict section 19.4 claim remains false: this is the approved 72B model
exception, one repeated-prompt profile, and a full-universe budget. Prior measured
results informed candidate selection. The required two pressure profiles and
strict small-model baseline are not established by this run. Provider ablation
replays are separate artifacts; this folder does not claim an ablation win.

## Reproduce

```bash
python -m benchmarks.run_search replay \
  --collection evidence/live-grid-comparison-v1 --output-dir NEW_DIRECTORY --live-run
python -m experiments.verify_registered_grid --run-dir evidence/live-grid-comparison-v1
```

`comparison.json` contains every random seed, choice, and curve. `summary.json`
and `measurements.md` contain source-bound objective and quality measurements.
`swarm-verification.json` applies the shared concurrent-investigator, Weave-read,
peer-review, feedback, trial, diagnosis, plateau, and cleanup checks through an
explicit adapter for the registered public-API driver. It does not rewrite the
original report to match the historical command-line driver. The separate
returned-runner probe is regraded by the live import audit, not claimed as a
post-return Weave span.

[Live Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09b97-cb9a-701a-a608-ea20decf8416).

## Retrospective source-path correction

The recorded launcher used the benchmark driver from checkout `6601669`. It did
not record Python module import paths. Later inspection found `PYTHONSAFEPATH=1`
and installed packages before the checkout. The Sera library therefore likely
came from the installed 0.2.0 wheel built from `d8c7304`; that path is an inference,
not a fact captured at launch.

The complete `sera/` source trees at `d8c7304` and `6601669` are byte-identical.
This source-path uncertainty does not introduce a code difference between those
two library versions. The driver's checkout revision must not be described as
proof of where Python imported the library. `source-comparison.json` records
every file hash and the driver's hash. Reproduce with:

```bash
PYTHONPATH=. python evidence/live-grid-random-replay-v1/audit_source.py
```

This retrospective git audit does not attest the wheel or running-process bytes.
No original source artifact was edited and no GPU result was rerun.
