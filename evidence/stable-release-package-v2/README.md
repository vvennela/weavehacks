# Stable release: ordered stages and checkpoint snapshot fix

The wheel from `befda96a602af9fbf9dd3fd9bb423fb50c894d08` passes clean base and
swarm installs. Two separate builds have identical bytes. This audit does not
claim a live GPU rehearsal.

- Package: `sera-inference` 0.2.0; no version change, tag, or publication.
- Validation checkout: `1a1a38ee9f755c6f51eb305de70ac317d2a3c55b`.
- Both source trees: `8d3af9f0ed2aef319c8b75e97564df80e16f79b2`.
- Wheel: `sera_inference-0.2.0-py3-none-any.whl`, 229796 bytes.
- SHA-256: `e5e3a0856385e4da8523f5d9f4aa294a86bf490dbc99bf1dcd2c1144e653334d`.
- All 68 packaged Python files match the checked source bytes.
- All 23 audit commands pass; the focused source stage suite passes 146 tests.

The exact tested wheel is retained at:

```text
/var/folders/4f/r4sxs9j97fdf1c4x4r1wxlt40000gn/T/sera-final-package-zni1kj4h/dist/sera_inference-0.2.0-py3-none-any.whl
```

## Passed installed checks

Fresh Python 3.11 macOS base and swarm environments pass dependency validation,
isolated imports, SQLite persistence and unsafe-resume checks. The swarm API
smoke and provider-check CLI help also pass outside the checkout. The base
environment has no Weave, OpenAI, Torch, or vLLM dependency.

Both installed environments pass the total-device accounting smoke: per-service
accounting remains the default; explicit total-device mode records service memory
as unknown and rejects an invalid mode before execution.

[installed_stage_smoke.py](installed_stage_smoke.py) checks the corrected contract:

- `k=3` allows at most 3% regression in earlier measured objectives.
- A strictly positive gain is required by default. A percentage gain floor is
  a separate `min_improvement_pct` option.
- A 2% memory gain with a 1% latency regression passes. A 4% latency regression
  fails. Zero gain fails.
- Quality and the original hard limits are not relaxed.

The installed stage execution boundary is stubbed. The actual percentage helpers
and measurement gates run. The separate source suite runs the real staged API,
swarm, candidate filtering, stage handoff, checkpoints, and runner lifecycle with
synthetic GPU/provider/trace boundaries. It includes default small-gain acceptance,
explicit minimum-gain rejection, quality rejection, identity drift rejection,
and the final checkpoint snapshot guard.

## Repeat and limits

[result.json](result.json) contains exact commands, outputs, dependencies, source
identity, and checksums. Repeat from a clean checkout of the source above:

```sh
python evidence/final-package-release-v1/audit.py \
  --source /path/to/clean/checkout \
  --expected-source befda96a602af9fbf9dd3fd9bb423fb50c894d08
```

Then run both installed smoke scripts with each generated environment's isolated
Python. The stage smoke file is in this evidence commit; the earlier accounting
smoke is under `evidence/final-package-release-v3/`.

No GPU, provider, or Weave service calls occurred. This is not Linux CUDA,
multi-GPU, outage, soak, live model-quality, or production certification. The
parent task records any installed-wheel live GPU rehearsal separately. Earlier
release evidence remains unchanged. The interim wheel from `3bfaaf5` was
superseded before live use by this final snapshot-safe build.
