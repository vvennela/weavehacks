# STAGE — read this, speak this

## 0. THE ONE DECISION (make it 60 seconds before you walk up)

Run the probe below. Its output picks your opening. Nothing else changes.

| Probe output | Opening | Badge on screen |
|---|---|---|
| `SERVING on <port>` | **Opening A** | LIVE |
| GPU line prints, `NOT SERVING` | **Opening B** | RECORDED |
| No output / can't reach the sandbox | **Opening C** | RECORDED |

**Probe — paste into a new cell in the molab notebook:**

```python
import subprocess, urllib.request, json
print(subprocess.run(["nvidia-smi","--query-gpu=name,memory.total,driver_version",
                      "--format=csv,noheader"], capture_output=True, text=True).stdout.strip())
for _p in range(8000, 8011):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{_p}/v1/models", timeout=2) as _r:
            print("SERVING on", _p, json.load(_r)["data"][0]["id"]); break
    except Exception: pass
else:
    print("NOT SERVING")
```

Same probe from the laptop, if you are driving from the terminal:

```sh
cd "/Users/barratm/Desktop/Coreweave Hackathon"
MARIMO_TOKEN="$MARIMO_TOKEN" .agents/skills/marimo-pair/scripts/execute-code.sh \
  --url "$SERA_MOLAB_URL" -c 'import subprocess,urllib.request,json
print(subprocess.run(["nvidia-smi","--query-gpu=name,memory.total,driver_version","--format=csv,noheader"],capture_output=True,text=True).stdout.strip())
for p in range(8000,8011):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{p}/v1/models",timeout=2) as r:
            print("SERVING on",p,json.load(r)["data"][0]["id"]); break
    except Exception: pass
else: print("NOT SERVING")'
```

**Rule: if the probe says NOT SERVING, you are on Opening B. Do not retry it on stage.**

---

## 1. THE THREE OPENINGS (0:00–0:40) — pick ONE

Shared last lines of every opening (the problem):

> "The problem: making a model serve well means picking quantization, caching, batch
> sizes, context limits. They interact. Most people guess, or grid-search and burn GPU
> hours. Sera picks which experiments are worth running, measures them, and throws out
> whatever fails the quality check."

### Opening A — live Blackwell, serving now

> "This is a molab sandbox on CoreWeave. One RTX PRO 6000 Blackwell, 96 gigabytes, and
> it is live. vLLM is running Qwen3-8B on that card right now."

Run the live request (§3A). Wait for it.

> "That came back off this GPU, just now."

Then the problem lines. Then:

> "The run I'm about to walk through is a recorded one — and it's labeled recorded."

### Opening B — Blackwell attached, provably present, vLLM not serving

Show `nvidia-smi` (§3B).

> "This is a molab sandbox on CoreWeave, and this is the card: one RTX PRO 6000
> Blackwell, ninety-seven thousand megabytes, compute capability 12.0. vLLM 0.29 is
> installed on it and it loads Qwen3-8B — fifteen gigabytes of weights, sixty-one
> gigabytes left for cache.
> It is not serving requests this second, so I won't pretend it is. Everything from here
> is a recorded run on this same hardware, labeled recorded."

Then the problem lines.

### Opening C — nothing live, recorded evidence only

> "Nothing on this screen is live, so let me be exact about what it is. Every number I
> show you came off a real GPU — an RTX PRO 6000 Blackwell on molab, real vLLM, real
> measurements, saved with the trace that produced them. No simulator, no example data."

Then the problem lines.

---

## 2. THE BODY (0:40–3:00) — identical for all three rungs

Screen: root `demo.py`, the recorded Astra run. Its banner already says
"Recorded real run — status: closed." Lines marked **[cut if long]** go first.

**0:40–1:20 — what it actually did**

> "Real run. Qwen 2.5, 72 billion parameters. Its weights are about 135 gigabytes. The
> card has 96. So the first question is whether it runs at all.
> An advisor proposes FP8 weights, an arbiter decides to test it, Sera loads it and
> checks the answers — eight out of eight tasks pass. That becomes the reference.
> Then three investigators work in parallel: scheduling, memory and context, output
> quality. They read the real measurements out of Weave, propose experiments, compare
> findings, and an arbiter picks one to run. Sera runs it, measures it, gates it on
> quality, and hands the result back. The next round is chosen from what actually
> happened."

**1:20–2:00 — the result** *(point at the trial table)*

> "Round one: prefix caching. Passed quality, took worst-load p95 from 770 milliseconds
> to 625.
> Round two: graph execution on its own. Passed quality, gained 0.7 percent. Not enough.
> Round three: both had passed alone, so the loop offered the combination and tested it.
> 619.85 milliseconds — 19.55 percent better than the reference it measured itself. But
> that's only 0.9 percent over caching, under the 5 percent rule, so Sera stopped.
> **[cut if long]** Four GPU trials, three rounds, no trial cap. Nobody chose a setting
> by hand."

**2:00–2:30 — proof** *(open the Weave trace)*

> "Here's the trace for that run. 662 calls. You can open one evidence read, then the
> decision that cites it.
> This is the part that matters: an agent's reason is a hypothesis — the measurement
> decides. All four configurations passed eight out of eight tasks. The winner came back
> as a working runner, took a fresh request, and closed with GPU memory at zero."

**2:30–3:00 — limits, then close**

> "What this isn't. The 19.55 percent is against Sera's own FP8 reference — the
> unquantized model couldn't run at all. The traffic repeats eight prompts after warmup,
> so caching flatters it. **[cut if long]** And I'm not claiming we beat grid search;
> that benchmark isn't finished.
> What it is: Sera returns the best plan it actually measured, and the record says why
> it tested, rejected, combined, and stopped."

Stop talking.

---

## 3. COMMANDS

Set once, before you go up:

```sh
cd "/Users/barratm/Desktop/Coreweave Hackathon"
```

### 3A. Rung A — live serving

In the molab notebook, new cell (`PORT` and `MODEL` come from the probe output):

```python
import urllib.request, json, time
PORT, MODEL = 8000, "Qwen/Qwen3-8B"
body = json.dumps({"model": MODEL, "temperature": 0, "max_tokens": 24,
                   "messages": [{"role": "user",
                                 "content": "What is 2 + 3? Return only the number."}]}).encode()
req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions",
                             data=body, headers={"Content-Type": "application/json"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=60) as r:
    out = json.load(r)
print(out["choices"][0]["message"]["content"].strip(), f"({(time.time()-t0)*1000:.0f} ms, live)")
```

Then switch to the recorded run for the body:

```sh
.venv/bin/marimo edit demo.py
```

### 3B. Rung B — attached, provably present, not serving

In the molab notebook, new cell:

```python
import subprocess, torch
print(subprocess.run(["nvidia-smi"], capture_output=True, text=True).stdout)
print("torch", torch.__version__, "| cuda", torch.cuda.is_available(),
      "| devices", torch.cuda.device_count(),
      "|", torch.cuda.get_device_name(0), "| sm_%d%d" % torch.cuda.get_device_capability(0))
```

Optional second beat — the engine start already in the notebook's scroll-back: point at the
KV-cache line (61.76 GiB, 449,680 tokens). Say the engine loads, do not say it serves.

Then the body:

```sh
.venv/bin/marimo edit demo.py
```

### 3C. Rung C — recorded only

```sh
.venv/bin/marimo edit demo.py
```

If marimo will not start:

```sh
uvx marimo@0.24.0 edit demo.py --sandbox
```

If that fails too, no network needed:

```sh
open evidence/live-astra-expanded-v1/README.md
```

Weave trace (needs network — open it in a tab *now*, before you present):
`https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09b0c-d1ac-74ea-a68c-06a4872829c4`

**Never open `output/sera-demo-backup.html` or `notebooks/sera_demo.py`.** Those render
fixed example data (35%, 231 ms, 0.961). They are not measurements.

---

## 4. DO NOT SAY

Hard rules:

1. **A recorded run never appears under a live badge.** If it's saved, the word
   "recorded" comes out of your mouth before any number does.
2. **"35% faster."** Fixed example data in `demo-script.md` / `sera_demo.py`. Not measured.
3. **"It rejected FP8 because quality scored 0.961."** Same fixture. The real rejections
   are the 0.7% and 0.9% gains that missed the 5% rule.
4. **"19.55% faster than the model you'd normally run."** It is 19.55% against Sera's own
   measured FP8 reference. The BF16 model never ran — there is no BF16 comparison.
5. **"It'll speed up your traffic."** The workload repeats eight prompts after warmup.
   Prefix caching gains apply to that reuse pattern. Not cold or unseen traffic.
6. **"We beat grid search."** One exploratory three-candidate comparison (Sera 1 trial,
   grid 3, random median 2). Not the specified benchmark. All ablations tied.
7. **"Weave made it faster."** Weave gave visibility and evidence. There was no no-Weave
   comparison.
8. **"The swarm beats a single agent."** One run per model. Investigators often agreed.
   Never tested against one agent.
9. **"The agents diagnose problems correctly."** The saved failure replays failed on
   factual reasoning — agents repeated a false token-count claim. That's on record.
10. **"Optimal" / "best configuration."** Best *measured* under a stopping policy.
11. **"You can hit that endpoint."** Every recorded runner is closed. GPU memory zero.
12. **"Two models on a smaller card."** The 24 GiB joint-placement budget is a declared
    limit on the 96 GB card. It represents memory capacity only — not a smaller card's
    compute or bandwidth. And it's a *different* run from the 72B one — never merge them.
13. **"Multi-GPU" / "2, 4, 8 GPUs."** Not implemented, not validated.
14. **"It recovers from outages unattended."** Luna's run needed a manual reconnection.
    Live outage tests are deferred.
15. **Any latency, throughput, or quality number for today's Qwen3-8B.** Nothing has been
    measured on it. Engine start is not a result. Don't quote 449,680 tokens or 109.79x
    concurrency as a Sera result — that's vLLM's own startup log for one config.
16. **"1,360 tests pass, so the performance claims hold."** Tests are software checks.
17. **"The website runs this."** The site's dashboard and local tab read a different
    implementation and a simulator. Only `demo.py` and `evidence/` are the measured swarm.
18. Never combine numbers from two different runs into one story.

---

## 5. THREE JUDGE QUESTIONS, 20 SECONDS EACH

**Q: "Is what I'm looking at live, or recorded?"**
> "Recorded, and labeled recorded. It's a real GPU run — real vLLM on an RTX PRO 6000,
> saved with its Weave trace, and you can open any call in it. What's live today is the
> card and the engine; the loop you're watching ran earlier and its runner is closed.
> I'd rather show you a real saved run than a live one that might not finish in three
> minutes."

**Q: "How is this better than just grid-searching the settings?"**
> "In the one frozen comparison we've run, Sera reached a valid configuration within
> 5% of the best in one trial; fixed-order grid took three, and random search took two
> at the median. That's three candidates — it's exploratory, not the full benchmark, and
> I'm not claiming the benchmark. The structural argument is that illegal and
> non-fitting configurations get rejected by arithmetic before they cost GPU time, and
> a failed trial changes what gets proposed next. Grid search does neither."

**Q: "What stops the agents from just shipping a fast, broken model?"**
> "The agents never decide. They propose. Deterministic code validates, runs the trial,
> grades every answer against a 99% floor, and picks. A configuration that's faster but
> fails quality is rejected — quality is a gate, not something the optimizer can trade.
> In this run every trial passed the tasks, and the two that were rejected were rejected
> for missing the 5% improvement rule, not for quality."
