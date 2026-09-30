# Sera — the 3-minute script

Say the indented lines. Everything else is direction.

Runs against **`pitch-deck.html`** (7 slides + 4 backup) and **`demos/recorded-loop.html`**.
Deck keys: `←` `→` move · **N** notes · **G** all slides · **T** timer · **D** theme · **F** fullscreen.

| | | |
|---|---|---|
| 0:00–1:00 | Slides 1–5 | 163 words |
| 1:00–2:45 | Slide 6 → the recorded run at **8×** | 1:45 |
| 2:45–3:00 | Slide 7 — closeout + QR | 44 words |

---

## 0:00 — Slide 1 · Title

> I'm Barrat. This is Vishnu. We built Sera.
>
> Vishnu built the engine — the runner, the measurements, the agent loop. I built
> everything you touch.

*Look at Vishnu on his line. Don't read the tagline aloud; the room already has it.*

## 0:10 — Slide 2 · Three levers

> How fast a model serves comes down to three choices. **Quantization** — store the
> weights in fewer bits. **Caching** — reuse work you've already done instead of
> recomputing it. **Batching** — run requests together so the card isn't sitting idle.

*Name the three, gesture at the cards, move on. Do not read the cards out — the slide
is doing that. Every card has a **Buys** line and a **Costs** line; that pairing is
the whole argument for why any of this needs measuring.*

## 0:22 — Slide 3 · They interact

> Every one is a trade — and they interact. So people guess, or grid-search and burn
> GPU hours on settings that were never going to fit.

*Land "never going to fit." It sets up why the first thing in the run is a 135 GB
model on a 96 GB card.*

## 0:32 — Slide 4 · One call

> Sera is one function call. Agents propose experiments and review each other.
> Deterministic code runs them on the GPU, measures, and grades every answer.
>
> **Agents propose. Measurements decide.**

*Pause before the last line and say it slowly. It's the line the room should keep —
and it's the whole safety argument: the agents never declare a result.*

## 0:44 — Slide 5 · Seven phases

> What you're about to watch is that loop — seven phases, three times over — on a
> 72-billion-parameter model that doesn't fit on the card.
>
> Watch phase three. The agents read each other and withdraw ideas they can't
> support. And it's a recorded run.

*Say "recorded" out loud, here. Point at the split while you say it: phases 01–04 are
agents, 05–07 are ordinary code. Then advance to slide 6.*

## 1:00 — Slide 6 · The run

Click **Open the recorded run**. Set the speed selector to **8×** and press Play.
The slide has both reminders on it.

**If the video narrates itself, stay quiet.** If it's silent, these are your cues —
times are *into the video*:

| Video | Say |
|---|---|
| 0:00–0:20 | It measures the unchanged model first. FP8 weights, no cache. 771 milliseconds, eight out of eight quality checks. Everything after this is measured against that. |
| 0:21–0:40 | Round one. Three proposals, then peer review — one agent withdraws its own memory change because there were zero preemptions. The arbiter picks caching. 625 milliseconds, nineteen percent off the baseline. |
| 0:44–1:02 | Round two tests graph execution on its own, to isolate it. Under one percent. It misses the bar — so Sera buys one confirmation round. |
| 1:06–1:29 | Round three combines the two. 619 milliseconds, the best measured result — but only one percent over caching alone. Under the five percent bar, so it stops. |
| 1:29–1:45 | It returns the winning configuration, checks the runner answers a fresh request, and releases the GPU. |

*The first 20 seconds is the baseline measuring — that's your window to talk.*

## 2:45 — Slide 7 · Closeout

> So that's what we built. You hand Sera a model and your prompts; it works out how
> to serve them, proves every change on the GPU, and hands back a working model —
> and the record of why.
>
> No inference expertise required. Thank you.

*Point at the QR on the last line. Leave the slide up through Q&A. Add nothing after
"thank you."*

---

## If you're running long

Cut in this order. **Be on slide 7 by 2:45 whatever happens** — if the demo overruns,
skip to it. Never let the ending get squeezed.

1. Slide 3's second sentence — "or grid-search and burn GPU hours…" *(−5s)*
2. "I built everything you touch" *(−3s)*
3. The video's 0:44–1:02 cue; the screen shows it anyway *(−8s)*

Never cut **"against its own measured baseline."**

## Three things that must not come out of your mouth

| Don't say | Why |
|---|---|
| "19.8% faster than normal" | It's against Sera's **own FP8 baseline**. The 16-bit model never ran — it doesn't fit on the card. That's *why* the baseline is FP8. |
| "The website ran that" | The site is the product surface. The measured run is `demos/recorded-loop.html` and `evidence/`. The site's local tab is a simulator. |
| "We beat grid search" | One exploratory three-candidate comparison. The specified benchmark isn't finished. |

Say **"nineteen point eight percent"** or "about twenty" — never "19.773". Fuller list
of traps: `STAGE.md` §4.

---

## Reference — the seven phases

The demo's own step names. Phases 01–04 are agents; 05–07 are deterministic code.

| | Phase | What happens |
|---|---|---|
| 01 | **Inspect** | All three investigators read the same evidence at once — load metrics, latency outliers, where requests wait. |
| 02 | **Propose** | Each proposes one configuration change and its expected effect. Hypotheses, not results. |
| 03 | **Peer review** | They read each other and revise. Round 1: an agent withdrew its own memory change — zero preemptions, no measured constraint. |
| 04 | **Arbiter** | One experiment is selected. Agents converging on the same change costs one trial, not three. |
| 05 | **GPU trial** | The runner loads it on the Blackwell, warms it, drives fixed loads of 1, 2, 4 and 8. |
| 06 | **Measure** | 96 timed requests, 8 strict-JSON quality checks per configuration. Result goes back to the investigators. |
| 07 | **Stop / return** | No qualifying gain buys one confirmation round. When that also misses 5%, stop, return the best valid config, verify the runner, release the GPU. |

## Reference — what the run measured

Qwen2.5-72B-Instruct on 1× RTX PRO 6000 Blackwell. Worst p95 across loads of 1, 2, 4
and 8. **These are the video's numbers — do not mix them with
`evidence/live-astra-expanded-v1/`, which is a different run.**

| Round | Experiment | Worst p95 | vs baseline | Quality | Outcome |
|---|---|---|---|---|---|
| — | Baseline — FP8 weights, BF16 KV cache, eager, no prefix cache | 771.046 ms | — | 8/8 | The reference |
| 01 | Prefix caching | 624.785 ms | **−18.97%** | 8/8 | Kept |
| 02 | Graph execution alone | 764.072 ms | −0.905% | 8/8 | Misses → confirmation round |
| 03 | Caching + graphs | 618.588 ms | **−19.77%** | 8/8 | Best, but only 0.99% over prior best → stop |

Stop reason on record: `objective-plateau-confirmed`. Nothing was rejected for
quality — all four passed every task.

## Backup slides

Press **G** to jump. B1 the four measurements · B2 what peer review changed ·
B3 what we're not claiming · B4 what it runs on.
