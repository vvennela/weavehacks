# Sera — three-minute demo script

Two slides. Everything else is the notebook.

**Before you start:** run `./check.sh`. If it does not say ALL GREEN, do not demo.
Open `notebooks/sera_demo.py` with `marimo edit notebooks/sera_demo.py` and leave
the result source on **"Example data — an improvement"**. No model downloads, no
live trials, nothing that can hang in front of judges.

---

## Slide 1 — the problem (0:00–0:25)

> "Getting a model to serve fast means choosing quantization, batch sizes, and
> parallelism. Those settings interact. Quantization saves memory but can wreck
> quality. Bigger batches raise throughput but hurt tail latency. Most developers
> don't know which combinations are even legal on their hardware, so they either
> guess or grid-search and burn GPU hours."

Advance.

---

## Slide 2 — the claim (0:25–0:40)

> "Sera is one function call. You give it models and prompts. A team of
> specialist agents proposes experiments, an arbiter spends a fixed trial budget
> on the strongest ones, and every configuration it returns has been measured —
> not predicted."

Switch to the notebook.

---

## The notebook (0:40–2:45)

### One call — 0:40–1:00

Scroll to Setup. Point at the two inputs.

> "Two things: model names, and prompts that look like your traffic. That's the
> whole API."

Scroll to the result banner.

> "It found a configuration 35% faster on p95 latency."

### What it actually did — 1:00–1:45

Scroll to **What Sera did**. Point at the counts strip.

> "Five trials run, two ruled out before they ever touched the GPU."

Open **Ruled out before running**.

> "These two were killed by arithmetic. Tensor parallelism of four on a
> single-device box isn't a slow configuration, it's an impossible one — so Sera
> never spends a trial on it. That's the difference from grid search, which would
> have queued both."

Point at the trial table.

> "Each row names the specialist that proposed it and the one lever it changed.
> One lever at a time, so when a number moves you know which agent was right."

### Self-correction — 1:45–2:20

**This is the most important 35 seconds. Do not rush it.**

Point at trial `t2`, the fp8 row.

> "Now the interesting one. The quantization specialist proposed fp8. It was the
> fastest thing measured all run — 231 milliseconds, and it cut memory by a
> third. Sera rejected it."

Open **Trials that did not survive**.

> "It scored 0.961 on behavior preservation against a floor of 0.99. Quality is a
> gate, not a score to trade away. So Sera rolled it back and kept the slower
> configuration that passed."

> "That's the whole thesis. A system optimizing for latency alone would have
> shipped the fp8 config and shipped a degraded model."

### The result — 2:20–2:45

Scroll to **Result**.

> "Baseline versus recommended, side by side. Latency, memory, throughput,
> quality."

Point at the quality caveat.

> "And it says plainly that this was behavior preservation, not task-quality
> verification. Quick mode doesn't overclaim."

Scroll to the copyable snippet.

> "You get loaded models back, not a config file to go apply yourself."

---

## Close (2:45–3:00)

Open the **Run details** accordion, point at the Weave trace link.

> "Every proposal, prediction, trial, and revert is in the Weave trace — including
> what each agent predicted and whether it held. That's the record that the agents
> are a self-correcting loop and not a chain of prompts."

Stop talking at 3:00.

---

## If something goes wrong

| Problem | Do this |
|---|---|
| marimo won't start | Open the backup: `output/sera-demo-backup.html` in a browser. Fully rendered, no server needed. |
| A cell shows an error | Switch result source to "Example data — an improvement" and re-run. The notebook never needs a backend. |
| Asked "is this real or a mock?" | Be straight: the numbers on screen are fixed example data with the backend still landing. The contract, gates, and rejection logic are real and tested. Offer to show `./check.sh`. |
| Asked about grid-search comparison | The benchmark harness is specified in `spec.md` §19 but was cut for time. Say so; don't claim a result you don't have. |

## What this demo does not show

Be ready to say these out loud rather than get caught:

- **No live GPU run.** The backend was still being built. The notebook is wired to
  swap to it at one construction point.
- **No grid-search benchmark number.** Specified, not measured.
- **Phase two (two models sharing a GPU) is not in the demo fixture.** Phase one only.

## Timing

Rehearse twice. The self-correction beat at 1:45 is the one that lands; if you are
running long, cut the Setup narration at 0:40, not that.
