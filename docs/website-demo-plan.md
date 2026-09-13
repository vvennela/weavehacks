# Website and loop demo plan

## Decision summary

The website is a useful presentation shell, but it does not show the current
Luna/Astra swarm. Its dashboard reads a different implementation's saved ledger.
The strongest demo is a **recorded real loop with a visible feedback edge**, plus
a separate live-status panel. Do not wait for a whole GPU search on stage.

This document proposes a read-only integration. It does not choose which backend
the product will retain, change the optimizer, or authorize a new GPU run.

Reviewed source: `ad1f24e`. The timing measurements below were supplied by the
main worker from the saved Weave exports. No new GPU or provider calls were made
for this review.

## What the website does now

| Surface | Implemented behavior | Gap for the current swarm demo |
| --- | --- | --- |
| Homepage | Branded landing page, animated three-specialist graphic, product pages | Animation is decorative, not agent activity. Copy emphasizes quantization/batching/parallelism and two-model placement. |
| Local account server | Local sign-in, protected pages, loopback-only server | It is not a hosted control plane. Do not spend stage time signing in. |
| `/lab` | Charts, filters, trial details, failures, CSV export | `/api/metrics` reads only local `runs/ledger.jsonl`. Refresh is manual. No live investigator states or run-control endpoint. |
| `/notebook`, GPU tab | Opens a configured Molab notebook; optional read-only preview | `notebooks/molab_lab.py` runs `sera_loop.phase1.Phase1`, not `sera.optimize`. Its install button points to `@test1`, with fixed eight-trial profiles. |
| `/notebook`, local tab | Browser-based `sera_loop` analytic simulator | Simulated measurements, not the saved GPU swarm. First load needs external runtime packages; offline operation depends on the cache. |
| Root `demo.py` | Reads saved, measured `sera` evidence and links the actual Weave trace | Correct evidence source, but mainly tables rather than an animated, step-by-step loop. |

Sources: [website guide](../web/README.md), [server](../web/server.py),
[dashboard code](../output/sera-lab.js), [notebook launcher](../output/sera-notebook.js),
[GPU notebook](../notebooks/molab_lab.py), [current evidence demo](../demo.py).

The repository contains two separate systems, as the [root README](../README.md)
states. The website's `sera_loop` specialists use rule-based Python policies.
The measured `sera` swarm uses three concurrent LM investigators:
`scheduling`, `memory_context`, and `output_quality`. These investigation focuses
are not identical to the control roles a proposal names.

HTTP smoke check: homepage returned 200; unauthenticated metrics access was
rejected. No browser was available to this worker, so visual rendering and
interactive browser behavior were not verified.

## Is it a strong demo?

**Unchanged: no.** A static metrics dashboard shows results but hides the product's
main claim: agents use an experiment's outcome to choose their next experiment.
Opening the other implementation's notebook also creates a false impression that
the website runs the measured swarm.

**With a small evidence adapter: yes, it has a clear story.** Keep the website's
styling and trial details. Add one focused “Optimization loop” view that shows
decisions changing after measurement. Use the existing measured Astra run as the
main recording; show Luna as an independent repeat, not a simultaneous GPU run.

Fix these presentation risks before using the website:

- Show a persistent source badge: **Live GPU**, **Recorded GPU**, or **Simulator**.
- Make the main result the best **quality-valid** configuration. The current
  “lowest p95” card includes rejected trials. A fast rejected trial is not a winner.
- Keep metrics bound to one configuration. Lowest latency, peak throughput, and
  lowest memory can belong to three different trials.
- Use actual investigator names and no fixed trial cap for the measured swarm.
- Do not use the old [demo script](../demo-script.md) unchanged. Its 35% improvement
  and rejected FP8 example are fixed example data, not the current measured run.
- Mark two-model and multi-GPU claims by their own evidence status. Do not infer
  them from the single-model recording.

## The screen that makes the loop visible

A graph-shaped view does not require rewriting Sera with a graph framework.
Render the events from its existing control flow. This is a proposed layout:

```text
Qwen72B · 1 × RTX PRO 6000 · latency objective · quality floor 99%
RECORDED GPU — accelerated playback       Round 2 of 3 · actual elapsed 05:54

                    ┌ Scheduling ──────┐
Evidence / Weave ────┼ Memory & context ┼── Shared findings / peer review
       ▲            └ Output quality ─┘                  │
       │                                          Arbiter chooses
       │                                                 │
       │                                       Validator: legal to run?
       │                                                 │
       └──── Review / keep or reject ◄── Quality gate ◄── GPU trial
                              │
                    Continue / confirm / stop

Best valid p95: 770.49 → 625.34 ms     Current trial: graphs only
8/8 tasks passed                     Result: 764.91 ms — no useful progress

[Timeline: reference | caching | graphs | combination] [Open exact Weave call]
```

Use separate states: waiting, reading, proposing, peer review, selected,
validation rejected, starting server, measuring, quality failed, reviewed, and
finished. Three investigator lanes may overlap; GPU trials must not appear to
run concurrently when the measurements were sequential.

Clicking a node should show just four things: evidence read, stated hypothesis,
proposed change, and actual result. Link to the underlying record. Agent statements
are hypotheses, not verified facts or private chain-of-thought. Never invent text
to make an idle node appear active.

Make the feedback edge the visual center: “Batching did not help → inspect that
result → try or reject a combination → retain the best valid runner.” Show an
abstention as a valid decision, not a broken agent.

Quality failures must remain visible in the UI. All four trials in the selected
Astra recording passed its eight tasks, so do not insert a fake quality failure
into that run. A separate saved failure may be shown with its own run label.

## Actual iteration time

A round here starts at the first swarm inspection after the preceding review and
ends when the corresponding candidate's frontier reviewer completes. It excludes
initial model fitting/reference measurement and final runner restart.

| Saved run | Three full rounds | Mean | Mean pre-trial agent wall time | Mean server startup |
| --- | --- | --- | --- | --- |
| Astra | 3m43s, 5m54s, 4m21s | **4m39s** | 1m48s | 1m51s |
| Luna | 4m26s, 7m15s, 3m30s | **5m04s** | 1m47s | 1m03s |

These are observed samples, not a promised runtime. Astra's graph trial took
191.2 seconds to start. Luna's second round includes a known manual controller
reconnection; its review phase took 238.6 seconds. The mean therefore includes
that delay. Parallel agent wall time is elapsed time, not the sum of three calls.

Do not use a `recorded_model_request` Weave span's duration as inference latency:
that span records an already-completed request. Use its saved `latency_ms` field.
Model request latency, server startup, agent time, and whole-round time are four
different measurements.

Sources: [Astra recording](../evidence/live-astra-expanded-v1/README.md),
[Luna recording](../evidence/live-luna-expanded-v2/README.md), and the
[reproducible timing audit](../evidence/demo-iteration-timing-v1/result.json),
which binds the saved Weave exports to their source hashes and trial IDs.

## Three-minute judge flow

1. **0:00–0:15 — Problem.** “I want this large model to run on this GPU. I care
   about latency, but the answers still have to pass my checks.” Show the model,
   hardware, objective, and quality floor. Skip the login and product tour.
2. **0:15–0:35 — Fit and reference.** Show that BF16 weights cannot fit by the
   memory estimate. Sera uses supported FP8 weights and passes 8/8 tasks. The
   speed comparison starts from that measured FP8 reference, not BF16.
3. **0:35–1:40 — The loop.** Play 65 seconds of accelerated real events. Show
   concurrent investigations, peer review, a selected experiment, and the result
   entering the next round. Pause briefly at the graph-only no-progress result.
   Keep the recording badge and actual elapsed time visible.
4. **1:40–2:10 — Outcome.** Show Astra's 770.49 → 619.85 ms worst-load p95,
   19.55% improvement, 8/8 tasks, and measured combination. Explain that the
   confirmation added less than the 5% progress target, so the loop stopped.
5. **2:10–2:35 — Proof.** Open one exact Weave evidence read and the next decision
   that cites it. Show the saved returned-runner request and successful cleanup.
   The recording's runner is now closed; this is not a currently live endpoint.
6. **2:35–3:00 — Live status and limits.** Show the current run's real status if
   available. State that the traffic repeats eight questions after warmup. Show
   the grid comparison only after its frozen, quality-gated result is complete.

Closing sentence: “Sera returns the best working plan it measured, and the full
record explains why it tested, rejected, combined, and stopped.” Do not claim a
global optimum or that Weave caused the gain without the corresponding comparison.

## Minimal integration work, in order

1. **Recorded adapter first.** Read one allowlisted `sera` run's `result.json`
   and normalized Weave export. Convert them into a versioned, read-only display
   model. Do not pretend they use the `sera_loop` ledger schema. Pin run ID,
   source revision, evidence hashes, and trace URL. No model calls.
2. **Replay graph.** Add the graph, timeline, play/pause/step, and event detail.
   Preserve event order and actual timestamps; label compressed wall time. Only
   display events known by the playback cursor so the final winner does not leak
   into earlier rounds. Reuse the existing colors, charts, and detail drawer.
3. **Live adapter second.** Feed the same display model from a server-side reader
   of the active run. Polling is sufficient for the demo. `result.json` is saved
   at checkpoints, not every agent transition. Start/end states need existing
   Weave call records or explicit safe instrumentation; do not infer them from
   a timer. Use the existing tracing hooks without replacing Weave's sink.
4. **Reconnect honestly.** Keep the last verified snapshot, show its age, and mark
   disconnection. Resume from the last event ID. Never substitute a replay under
   a live badge. Keep credentials server-side and endpoints read-only.

Required event fields: schema version, run/round/trial/config IDs, event ID,
parent event ID, start/end timestamp, phase, investigator ID, status, safe summary,
source record path/hash, and Weave call URL. Trial result payloads need actual
configuration, request profile, task scores/floor, quality verdict, latency,
startup duration, incumbent before/after, and declared stop reason. A missing
measurement stays null; a failed startup never becomes zero latency.

Acceptance tests before presenting:

- Replay reproduces the saved trial count, quality gates, winner, and stop reason.
- Rejected, failed, abstained, and incomplete states remain distinct.
- No simulator or different run's data can appear under a measured run ID.
- Concurrent investigator intervals come from recorded times, not fake animation.
- No duplicate events after reconnect; stale data is visibly marked.
- The site cannot launch trials or expose credentials through the new read API.
- Visual check at the presentation resolution; keyboard pause/step; reduced motion.

## Fallback ladder

1. **Live run healthy:** show live status beside the recorded walkthrough. Do not
   promise it will finish during the presentation.
2. **GPU or connection unavailable:** show the same recorded GPU trace and result,
   clearly labeled. Open the saved request and cleanup evidence.
3. **Website integration incomplete:** use root `demo.py` and the
   [existing comparison script](../evidence/expanded-swarm-comparison/README.md).
4. **No network:** use a rehearsed local recording or static export of that same
   evidence. The website's simulator is a separate, labeled UI demonstration,
   not a substitute for a measured result.

Do not add a new orchestration framework, ARIA UI automation, a remote run-start
service, or a two-backend merge just to draw this graph.
