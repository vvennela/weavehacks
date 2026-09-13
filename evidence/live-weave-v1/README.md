# Live Blackwell run: is there a Weave trace?

**No.** The live Sera run against the RTX PRO 6000 Blackwell (`evidence/live-blackwell-baseline-v1`,
2026-09-13 18:34:50Z – 18:41:52Z UTC) emitted **zero Weave calls**. There is no live trace URL to open.

On stage, open the recorded Astra trace instead:

    https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09b0c-d1ac-74ea-a68c-06a4872829c4

## Why there is no live trace

Tracing in `src/sera_loop/tracing.py` is **opt-in and off by default**. The `@tracing.op` decorator is
inert until `tracing.init()` flips the module-level `_ENABLED` flag; before that it calls the undecorated
function and records nothing.

`tracing.init()` has exactly one caller in the repository:

| Caller | Path |
| --- | --- |
| the `python -m sera_loop` CLI | `src/sera_loop/__main__.py:76` |

The live run was not driven by that CLI. It was driven by `scripts/live_sera_run.py`, which constructs
`Phase1(spec, runner, ledger)` directly and never calls `tracing.init()`. So the run could not have been
traced **regardless of credentials** — this is a code-path fact, not a missing-key fact.

Two independent confirmations, in order of strength:

1. **Code path.** Neither `scripts/live_sera_run.py` nor `scripts/live_bench_vllm.py` contains
   `tracing.init` or `weave.init`. Nor does `notebooks/sera_demo.py`: its "Tracing enabled" callout only
   checks that `WANDB_API_KEY` is present in the environment, and its live branch calls
   `sera_loop.optimize(...)`, which does not initialise tracing either.
2. **Artifacts.** The live console log (`../live-blackwell-baseline-v1/sera_phase1_live.log`) contains no
   `[trace]` line and no `weave.init` output. No ledger row in `runs/ledger.jsonl` or in
   `../live-blackwell-baseline-v1/sera_phase1_ledger_rows.jsonl` carries a `weave_url`
   (`SeraResult.weave_url`, `src/sera_loop/types.py:276`, stayed `None`). There is no `wandb/`, `.weave/`
   or `~/.cache/weave` directory anywhere in the workspace — a client that had started would have created
   one.

Credentials in this environment, presence only (no value was read or printed):

| Variable | State |
| --- | --- |
| `WANDB_API_KEY` | **not set** |
| `WANDB_PROJECT` | not set (would default to `sera`) |
| `WANDB_ENTITY` | not set |
| `WANDB_MODE` | not set |
| `~/.netrc` wandb entry | absent (no `~/.netrc` at all) |
| `weave` package importable | **no** |

So even had the entry point called `init()`, it would have returned `False` at the very first check
(`if not os.environ.get("WANDB_API_KEY"): return False`) and then again on the `import weave`.

## What it would take to get a live trace

All three are required; any one missing yields an untraced run, silently.

1. `WANDB_API_KEY` exported in the process that runs the loop — for the Blackwell run that means inside
   the molab sandbox, not on this laptop. Optionally `WANDB_PROJECT` and `WANDB_ENTITY`; without an
   entity the target is the bare project name.
2. `weave` installed in that same interpreter.
3. A `tracing.init()` call on the live entry path — either run the loop as `python -m sera_loop --spec …`,
   which already does it, or add one line to `scripts/live_sera_run.py` before `Phase1(...)` runs.

**This was deliberately not attempted mid-run.** The Blackwell run is owned by another agent and holds the
single GPU; enabling tracing would have meant restarting it, and a restarted run is a worse demo asset
than an untraced finished one.

## The fallback the demo should use

The recorded Astra run's trace is real, reachable, and backed by a local export.

| Check | Result |
| --- | --- |
| URL well-formed | yes — `https://wandb.ai/<entity>/<project>/r/call/<uuid>`, entity `vvennela-n-a`, project `wandb_agent_default_project`, call `01a09b0c-d1ac-74ea-a68c-06a4872829c4` (canonical 8-4-4-4-12 hex) |
| Local export present | yes — `../live-astra-expanded-v1/weave-calls-normalized.json`, 61,195,055 bytes |
| Call ID present in export | yes — 619 occurrences: once as a top-level `"id"` (the root call), 616 times as `"parent_id"` on its descendants, once as `"root_call_id"`, and once inside a `"weave_url"` field holding this exact URL |
| Entity/project string in export | yes — `vvennela-n-a/wandb_agent_default_project` |
| Cross-referenced | the same URL appears in `../live-astra-expanded-v1/` README.md, console.log, verification.json, result.json and invocation.json, and in `STAGE.md:213` — the demo's proof beat |

The URL was **not** fetched over the network — doing so needs W&B credentials that are not present here.
Everything above is verified against the local export only.

## Reproducing this check

    python3 scripts/live_weave_link.py          # human-readable
    python3 scripts/live_weave_link.py --json   # machine-readable

Exit status 0 means a live trace URL was found, 1 means there is none. It reports credential
**presence** only and never prints a secret. When credentials and `weave` are both available it queries
the project for the most recent call and prints that URL; otherwise it names the specific reason and
prints the recorded fallback above. As of 2026-09-13T18:47Z at HEAD `8e19302` it exits 1.
