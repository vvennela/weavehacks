# Standing up the live molab Blackwell, from scratch

This is the runbook for the thing the demo actually runs on: a **live marimo
server** in a molab sandbox with an **RTX PRO 6000 Blackwell** attached, serving
**Qwen3-8B** under **vLLM**, embedded in the Sera site.

Everything below was performed today. The numbers in "What good looks like" are
measured, not estimated. Where a step is environment-dependent it says so.

Budget about **25-35 minutes** end to end from a cold start, almost all of it
the vLLM wheel install and the weight download.

---

## What good looks like (observed today)

| Fact | Value |
|---|---|
| Sandbox | `https://sb-2775239e4080cee4.sb.molab.run/` |
| GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition |
| VRAM | 97887 MiB total |
| Compute capability | 12.0 (`sm_120`) |
| Driver | 595.71.05 |
| marimo | 0.24.0, **edit mode** (a real kernel, not a WASM export) |
| vLLM | 0.29.0 |
| Model | `Qwen/Qwen3-8B` |
| Live completion | **587.9 ms for 40 tokens** |

The sandbox id changes every time you attach a GPU. Nothing in the repo hardcodes
it, and nothing should — see step 2.

---

## 0. Before you start

You need:

- A molab account (`https://molab.marimo.io`).
- This repo checked out, with its virtualenv: `.venv/bin/python`.
- Nothing else. The GPU, the CUDA stack and the driver are molab's.

The molab **access token grants arbitrary code execution on the sandbox**. Treat
it like a password: pass it through the environment or the site's connect form,
never commit it, never paste it into a shared doc.

---

## 1. Create a molab notebook

1. Go to `https://molab.marimo.io` and sign in.
2. **New notebook**. A blank one is fine — Sera's notebook gets pushed into it in
   step 5. (You can also create a *synced* notebook from the GitHub URL of
   `notebooks/molab_lab.py`, but the push script is faster to iterate on and does
   not require the branch to be pushed first.)

At this point you have a CPU-only sandbox. There is no GPU yet.

## 2. Attach the Blackwell — this mints a NEW sandbox URL and token

In the notebook's app header, click **notebook specs**, and select the
**RTX PRO 6000 Blackwell** accelerator.

> **This is the step people get wrong.** Attaching a GPU does not upgrade the
> sandbox you are looking at — it **provisions a new one**. You get a **new
> `sb-<id>.sb.molab.run` hostname and a new access token**. Every URL and token
> you captured before this moment is now dead.
>
> So: **attach the GPU first, then capture credentials, then wire up the site.**
> Doing it in the other order means redoing steps 3-4.

Wait for the sandbox to come back up. Confirm the card is really there before
going further:

```bash
export MOLAB_URL='https://sb-<id>.sb.molab.run/'
export MARIMO_TOKEN='<access token>'

bash .agents/skills/marimo-pair/scripts/execute-code.sh --url "$MOLAB_URL" -c \
  'import subprocess; print(subprocess.run(["nvidia-smi","--query-gpu=name,memory.total,driver_version","--format=csv,noheader"],capture_output=True,text=True).stdout)'
```

Expected today:

```
NVIDIA RTX PRO 6000 Blackwell Server Edition, 97887 MiB, 595.71.05
```

If that prints nothing or errors, the GPU did not attach — re-open notebook specs.

## 3. Get the URL and the token

- **URL**: the browser address of the running notebook, e.g.
  `https://sb-2775239e4080cee4.sb.molab.run/`. Take the origin (scheme + host);
  the trailing path does not matter.
- **Token**: molab puts it on the URL as `?access_token=<TOKEN>` the first time
  you open the sandbox. If the address bar has already dropped it, reload the
  notebook from the molab dashboard and grab it before it is stripped.

Hitting `https://sb-<id>.sb.molab.run/?access_token=<TOKEN>` is what performs the
login: the server responds by setting a **`session_8080` cookie**, and every
subsequent request is authenticated by that cookie rather than the query string.

## 4. Paste them into the site's connect form

Start the site and sign in (`demo@serademo.com` / `clustersss`), go to
`/notebook`, and paste the sandbox URL and access token into the **connect**
form on the molab tab.

The site does **not** iframe the sandbox directly, and cannot. The live sandbox
sends:

```
content-security-policy: frame-ancestors 'self' https://*.marimo.io https://sb-<id>-session.sb.molab.run
```

`http://localhost:<port>` is not in that list, so a browser refuses to render the
frame — silently, with only a console message. The site therefore runs a small
**root-mounted reverse proxy on a second loopback port (default 8878)**, and
frames *that*. The proxy has to be mounted at the root of its own port, not under
a path prefix, because marimo's client requests absolute paths (`/api/...`,
`/assets/...`) and opens a websocket to the origin root.

## 5. Push Sera's notebook into the live kernel

The sandbox notebook is blank. Put Sera's in it:

```bash
MARIMO_TOKEN='<token>' scripts/push_notebook_to_molab.sh --url "$MOLAB_URL"
```

This is idempotent — cells are matched by position, so running it twice edits in
place instead of appending a second copy. Add `--dry-run` to see the plan first.

## 6. Install vLLM — with the FlashInfer sampler off

Install into the sandbox. The wheel is large; this is the long pole.

```bash
bash .agents/skills/marimo-pair/scripts/execute-code.sh --url "$MOLAB_URL" - <<'PY'
import subprocess, sys
print(subprocess.run([sys.executable, "-m", "pip", "install", "-q", "vllm"],
                     capture_output=True, text=True).stderr[-2000:])
PY
```

> **Required:** set `VLLM_USE_FLASHINFER_SAMPLER=0` in the environment of the
> vLLM server process.
>
> Without it, vLLM selects the FlashInfer sampler, which **JIT-compiles a CUDA
> kernel at startup**. The molab sandbox ships the CUDA *runtime* but **not
> `nvcc`**, so that compile fails and the server dies during startup rather than
> falling back. The failure surfaces late — after the weights have already
> loaded — so it costs you a full load cycle each time you hit it.
>
> `VLLM_USE_FLASHINFER_SAMPLER=0` selects the native PyTorch sampler instead. It
> needs no compiler and is not the bottleneck at this scale.

## 7. Download the weights

Keep this separate from the timed run, so the transfer never lands inside a
measured number.

```bash
bash .agents/skills/marimo-pair/scripts/execute-code.sh --url "$MOLAB_URL" - <<'PY'
from huggingface_hub import snapshot_download
print(snapshot_download("Qwen/Qwen3-8B"))
PY
```

In the notebook UI this is the **Download weights** button.

## 8. Start the vLLM server

```bash
bash .agents/skills/marimo-pair/scripts/execute-code.sh --url "$MOLAB_URL" - <<'PY'
import os, subprocess, sys
env = {**os.environ,
       "VLLM_USE_FLASHINFER_SAMPLER": "0",     # no nvcc in the sandbox; see step 6
       "CUDA_VISIBLE_DEVICES": "0"}
subprocess.Popen(
    [sys.executable, "-m", "vllm.entrypoints.openai.api_server",
     "--model", "Qwen/Qwen3-8B",
     "--host", "127.0.0.1", "--port", "8000",
     "--dtype", "bfloat16",
     "--max-model-len", "4096",
     "--gpu-memory-utilization", "0.85"],
    env=env, stdout=open("/tmp/vllm.log", "w"), stderr=subprocess.STDOUT)
print("started; tail /tmp/vllm.log")
PY
```

Give it a couple of minutes (weight load plus CUDA graph capture), then tail
`/tmp/vllm.log` until it prints that it is serving on port 8000.

## 9. Prove it

One command, already in the repo:

```bash
export MOLAB_URL='https://sb-<id>.sb.molab.run/'
export MARIMO_TOKEN='<token>'
./scripts/prove_blackwell.sh
```

It prints the GPU from `nvidia-smi` and then a real completion with its measured
latency:

```
NVIDIA RTX PRO 6000 Blackwell Server Edition, 97887 MiB, ..., 595.71.05
latency_ms: <measured>
tokens: <n>
```

The measurement taken today was **587.9 ms for 40 tokens**, on the card, through
vLLM 0.29.0. Note that the script has since been changed to call
`/v1/chat/completions` with `max_tokens` 80 and Qwen3's thinking block disabled
(the base `/v1/completions` endpoint continues the prompt instead of answering
it, which reads as broken on stage). So a fresh run reports its own number and
token count — quote what it prints, not the 587.9 figure.

### Measured baseline (same card, same day)

A fuller sweep is recorded in
`evidence/live-blackwell-baseline-v1/vllm_qwen3_8b_latency_20260913T183140Z.json`
— Qwen3-8B, vLLM 0.29.0, 1024-token prompts, 128 output tokens, `ignore_eos`, a
fresh uuid per request so prefix caching cannot serve it. Cold prefill, measured
end to end over HTTP. No simulation.

| Concurrency | e2e p50 (ms) | TTFT p50 (ms) | Output tok/s | req/s |
|---:|---:|---:|---:|---:|
| 1 | 1837.17 | 60.37 | 69.71 | 0.5446 |
| 2 | 1921.00 | 87.79 | 133.19 | 1.0406 |
| 4 | 2022.94 | 191.94 | 252.80 | 1.9750 |
| 8 | 2269.91 | 360.55 | 450.15 | 3.5168 |

`nvidia-smi` at the start of that run:

```
NVIDIA RTX PRO 6000 Blackwell Server Edition, 97887 MiB, 81935 MiB, 595.71.05, 12.0, 0 %, 29, 78.08 W
```

---

## Troubleshooting

**The molab tab is blank / the frame never paints.**
CSP. Confirm the proxy port is actually up and that the page is framing
`http://localhost:8878`, not the `sb-*.sb.molab.run` origin. A browser console
message about `frame-ancestors` is the tell.

**401 / the notebook asks to authenticate inside the frame.**
The token is wrong, or it belongs to the pre-GPU sandbox (step 2). Re-capture
both URL and token together, from the sandbox that has the card.

**vLLM dies late in startup, after the weights load.**
Almost always the FlashInfer sampler JIT hitting a missing `nvcc`. Set
`VLLM_USE_FLASHINFER_SAMPLER=0` (step 6).

**Everything was working, now nothing responds.**
molab sandboxes idle out. The URL and token die with them. Re-attach and redo
steps 2-8 — or fall back to the local WASM simulator tab, which is exactly what
it is there for.

**Do not** hardcode a sandbox id anywhere. It is wrong by the next GPU attach.
