# molab recovery — what to do when the live GPU misbehaves

Companion to `STAGE.md` §0. `STAGE.md` tells you which opening to give;
this file tells you what is actually wrong, what fixing it costs, and — for
almost every case — why you should not try to fix it while people are watching.

**The decision rule, in one sentence:**

> Run `scripts/molab_health.sh` once, 60 seconds before you walk up, and speak
> the opening its verdict names — READY is Opening A, anything else is the
> recorded demo — and never run it a second time on stage.

---

## The probe

```sh
cd "/Users/barratm/Desktop/Coreweave Hackathon"
export MOLAB_URL='https://sb-<id>.sb.molab.run/'
export MARIMO_TOKEN='<access token>'      # never write this into a file in the repo
./scripts/molab_health.sh
```

Read-only: it queries `nvidia-smi` and does an HTTP GET on the vLLM model list.
It never restarts vLLM, kills a process, installs anything, or writes a file.
It is safe to run while an optimization run is driving the card. It returns in
about a second and is hard-capped so it cannot hang.

| Verdict | Exit | Means | STAGE.md |
|---|---|---|---|
| `READY` | 0 | Sandbox up, Blackwell attached, vLLM answering on `127.0.0.1:8000` | Opening A, badge **LIVE** |
| `GPU-BUT-NOT-SERVING` | 3 | Sandbox up, card present, no vLLM on 8000 | Opening B, badge **RECORDED** |
| `SANDBOX-DOWN` | 4 | Sandbox unreachable, or reachable with no GPU / no kernel session | Opening C, badge **RECORDED** |
| (usage) | 2 | `MOLAB_URL` or `MARIMO_TOKEN` not set | fix your shell, not the sandbox |

`GPU-BUT-NOT-SERVING` is a real rung, not a degraded one. Opening B is written
to be delivered from `nvidia-smi` alone and it is honest: the card is there, the
engine loads, it is not answering requests this second.

---

## The three costs you need in your head

These are measured on this sandbox, not estimates.

1. **A cold vLLM start is about 3 minutes.** Weight load ~7 s, `torch.compile`
   ~31 s, CUDA graph capture ~61 s, plus engine init and server bring-up around
   them. That is *after* the weights are already on disk.
2. **`VLLM_USE_FLASHINFER_SAMPLER=0` is required.** Without it vLLM picks the
   FlashInfer sampler, which JIT-compiles a CUDA kernel at startup. The sandbox
   ships the CUDA runtime but no `nvcc`, so the compile fails and the engine
   **dies after graph capture** — roughly 100 seconds in, having already loaded
   the weights. You pay the full load cycle to learn nothing.
3. **Attaching a GPU mints a new sandbox.** molab does not upgrade the sandbox
   you are looking at; it provisions a fresh one with a **new
   `sb-<id>.sb.molab.run` hostname and a new access token**. Every URL and token
   captured before that moment is dead — including the one in your shell, the
   one in the site's connect form, and the one in any browser tab you pre-opened.

A cold rebuild from nothing (attach, install the vLLM wheel, pull weights, start
the server) is **25–35 minutes**, per `docs/live-molab-setup.md`.

---

## Failure modes

### 1. `READY` at the check, dead at the podium

**Symptom.** The probe said READY, then the live request in §3A hangs or errors.

**Do.** Nothing. Say "that one didn't come back — everything from here is a
recorded run on this same card," and go to Opening B's script. Then the body.

**Cost of debugging.** Unbounded, in front of an audience. A hung request tells
you nothing about whether the cause is the request, the engine, the sandbox, or
the venue wifi.

**Prevention, before you go up.** Run `scripts/prove_blackwell.sh` once. It does
a real completion and prints its own latency. A warm engine that just answered
is far likelier to answer again than one that has only been probed.

### 2. `GPU-BUT-NOT-SERVING`

**Symptom.** `nvidia-smi` prints the card; nothing on `127.0.0.1:8000`.

**Cause.** vLLM was never started, exited, was killed, or died on the missing
`nvcc` (fact 2 above).

**Do.** Opening B. Show `nvidia-smi` (STAGE.md §3B), say the engine loads and
that it is not serving this second, and move on.

**Cost of recovery.** ~3 minutes minimum if the weights are cached and you get
the environment right first time — i.e. your entire slot, spent watching a log.
If the sampler flag is missing it is ~3 minutes to a *failed* start, then
another ~3 to retry. **Not recoverable inside the slot.**

If you are recovering *before* the slot and have 5+ minutes, the start command
is step 8 of `docs/live-molab-setup.md`. It must carry
`VLLM_USE_FLASHINFER_SAMPLER=0`.

### 3. `SANDBOX-DOWN` — HTTP unreachable, or 410 Gone

**Symptom.** `/health` and `/api/status` time out, or return 410.

**Cause.** The sandbox idled out or was replaced. molab sandboxes expire; the
URL and token die with them. A 410 means that hostname is gone for good.

**Do.** Opening C. Everything is recorded, and Opening C is written to say so
cleanly.

**Cost of recovery.** A new sandbox means a new URL and token (fact 3), a fresh
vLLM wheel install and a fresh weight download: **25–35 minutes**. **Not
recoverable inside the slot, and not recoverable in the ten minutes before it
either.**

### 4. `SANDBOX-DOWN` with `GPU NONE`

**Symptom.** The sandbox answers, the probe reports `GPU NONE`.

**Cause.** You are on the CPU-only sandbox — usually the pre-attach URL, or a
tab that outlived a GPU attach (fact 3).

**Do.** Opening C, unless you happen to still have the post-attach URL and token
to hand, in which case re-export them and re-run the probe **once**. Recovery is
otherwise a re-attach: **25–35 minutes**.

### 5. `SANDBOX-DOWN` with "No active sessions on the server"

**Symptom.** HTTP is 200, but the code probe reports no session.

**Cause.** The notebook is not open in a browser, so there is no kernel to
execute in. The card may be perfectly fine.

**Do.** If you are not yet on stage: open the notebook from the molab dashboard
and re-run the probe. That is seconds, and it is the one failure worth touching.
On stage: Opening C.

### 6. Exit 2 — credentials not set

Your shell, not the sandbox. `export MOLAB_URL` and `export MARIMO_TOKEN` and
re-run. Never paste the token into a file in this repo: it grants arbitrary code
execution on the sandbox.

### 7. marimo will not start locally for the recorded demo

This is the one that actually loses the demo, because the recorded run is the
fallback for everything above. In order (STAGE.md §3C):

```sh
.venv/bin/marimo edit demo.py                  # normal
uvx marimo@0.24.0 edit demo.py --sandbox       # if that fails
open evidence/live-astra-expanded-v1/README.md # no network needed
```

Check the first one works **before** you leave for the venue. Also open the
Weave trace in a tab in advance — it needs network.

---

## What is not recoverable in a 3-minute slot

Everything except re-opening a closed notebook tab.

- Restarting vLLM: ~3 minutes on a warm sandbox with cached weights. Your whole slot.
- A vLLM start that dies on the FlashInfer/`nvcc` path: ~3 minutes to find out it failed.
- Re-attaching a GPU: new sandbox, new URL, new token, 25–35 minutes.
- A 410 sandbox: gone. Nothing to reconnect to.
- Venue network trouble: not yours to fix.

**So the move on stage is to switch to the recorded demo, not to debug.** The
recorded run is not a consolation prize — it is a real GPU run on this same
card, real vLLM, saved with the Weave trace that produced it, and STAGE.md §5
already has the answer for a judge who asks whether it is live. Debugging in
front of an audience costs you the body of the talk, which is the part that
carries the argument, in exchange for a badge.

Rungs A, B and C all end at the same body at 0:40. Only the first forty seconds
differ.
