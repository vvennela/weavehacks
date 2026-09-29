# Competition review guide

Status: draft submission material. This guide is not a submission receipt or a
production certification. The one-call API and ModelOpt integration remain
unfinished. W&B inference and mandatory Weave tracing are the selected direction;
account access and the W&B investigator model now pass the 34-case provider
check. Native MLX traces have been written and read back. See the
[September 29 native evidence](../evidence/native-mlx-smoke-v1/README.md).

## Organizer requirements

Source: the organizer email supplied by the user. The event page could not be
retrieved during this review, so its current contents were not independently
verified.

- Submission cutoff: the email explicitly says one minute after 11:59 p.m.
  September 29, meaning September 30 at 12:00 a.m. PT. Its weekday label conflicts
  with the 2026 calendar. Use the explicit earlier cutoff; do not treat September
  30 at 11:59 p.m. as the deadline.
- Every team member must sign in to AGI House. One person creates the project on
  the [Part 2 event page](https://agihouse.org/events/coreweave-hacks-part-2-fully-connected).
- Choose **Submit Project**, then verify **Submitted**. Saving a draft is not
  submission. No submission has been made or verified in this task.
- Include the W&B project link. Organizers verify usage through account traces.
- Upload a presentation-ready demo. Have a personal laptop ready to dock.
- Check in by October 1, 4:15 p.m. PT, at the Expo Stage or on the organizer's
  Zoom. Awards are 4:30–4:50; winner presentations are 4:50–5:20.
- Registration is closed. Without a ticket, use the supplied Zoom option rather
  than attending in person. Attendance/check-in is not verified here.

## Judge evidence, in review order

| Topic | Open this evidence | What it establishes |
| --- | --- | --- |
| Current native checkpoint | [MLX checks and trace links](../evidence/native-mlx-smoke-v1/README.md) | 8-bit export and fresh-process loading, 24/24 repeated easy checks, and about 38% lower peak allocator memory. Fixed adapter smoke, not agent-led optimization or general task quality. |
| W&B usage | [Project](https://wandb.ai/vvennela-n-a/wandb_agent_default_project) and [completed trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09c11-ca49-7d43-94cf-e56c54f98ac4) | Saved audit records 746 completed calls, zero call exceptions, and eight cited record hashes checked against cloud records. Confirm judge access before submission; this review did not reauthenticate the project. |
| Autonomous experiments | [Direct-API run](../evidence/openai-example-v2/README.md) | Three investigators, shared findings, three measured rounds, 19.77% lower worst-load p95 on eight warmed repeated prompts. Historical OpenAI/LiteLLM route; not a new W&B-inference run. |
| GPU capacity | [72B deployment](../evidence/large-fit-v1/README.md) | Online FP8 deployed with 86.38 GiB sampled peak and 8/8 fixed task checks. BF16 did not run; its 149.43 GiB runtime figure is an estimate. This is a fit result, not measured before/after memory savings. |
| Resilience | [Recovery contract](optimizer-recovery.md), [recovery tests](../tests/test_optimizer_recovery.py), [ledger tests](../tests/test_ledger.py) | Persistent checkpoints, exclusive ownership, interrupted-trial handling, and offline process-kill tests. Live GPU outage/soak reliability remains unverified. |
| Correctness and resource checks | [Quality evaluator](../sera/quality.py), [selection](../sera/measurement.py), [memory evidence tests](../tests/test_memory_evidence.py) | Deterministic quality gates; invalid memory telemetry cannot establish a gain or limit. |
| Build quality | [Build configuration](../pyproject.toml), [lockfile](../uv.lock), [historical clean-install audit](../evidence/stable-release-package-v2/README.md) | Locked dependencies and historical matching, reproducible wheel builds. That wheel predates current changes; do not call it a current-release audit. |
| Current state | [Production checklist](production-demo-workflow.md) | Local validation, unfinished ModelOpt/one-call work, and explicit live acceptance gaps. |

The current checkout has no `.github/workflows` directory. Do not claim hosted
CI passes. No top-level project license was found; choosing a license remains an
owner decision. The later installed-wheel joint run failed GLM's latency gate
(192.68 ms versus 187.93 ms), despite passing quality, memory and cleanup; see
[release acceptance](release-acceptance.md). Do not hide that repeat behind an
earlier passing joint result. The latest local suite report is recorded in the production checklist;
passing software tests does not establish a GPU speed or memory improvement.

## Four-minute evidence-led presentation draft

This is a recommendation for the competition, not a replacement for the full
memory-optimization product goal. Use the existing recorded run until a new live
run is verified. Do not relabel historical evidence as the new implementation.

| Time | Show |
| --- | --- |
| 0:00–0:30 | The problem: GPU capacity limits which models fit. State Sera's goal of one-call research that recovers memory under quality and speed limits. |
| 0:30–1:00 | The separate 72B fit result. Clearly label the BF16 figure an estimate and the FP8 deployment measured. |
| 1:00–2:10 | [Recorded research loop](../demos/recorded-loop.html), marked recorded. Show proposal, measurement, rejected/losing experiment, and revision. State the real 13:58 run duration. |
| 2:10–2:50 | Open the run's W&B trace: an investigator read, model output, measurement and decision. Do not equate trace-call count with experiment count. |
| 2:50–3:30 | Show the quality gate, saved failure, checkpoint/recovery tests and owned-process cleanup evidence. |
| 3:30–4:00 | Show the result and exact scope: historical usable runner, 19.77% latency gain on this repeated-prompt workload; new ModelOpt export and broad production acceptance remain work in progress. |

For a live result, use a fresh verified run and independently loaded artifact;
otherwise show the recorded returned-runner request with its recorded label.
Never claim a currently running model when the recorded runner is closed.

## Before clicking Submit

- Confirm team membership and sign-ins, project title, repository visibility,
  W&B judge access, and the exact W&B project in the submission.
- Pin the reviewed source commit and run the clean installation and relevant
  tests for that commit. Keep command outputs with the submission evidence.
- Upload the final video/demo file and test playback from the submitted page.
  The repository HTML alone is not proof that the platform received a demo.
- Check the presentation duration, laptop adapter, local fallback, and trace links.
- Submit and retain the **Submitted** confirmation. Arrange the required check-in.

No account changes, platform submission, upload, organizer message, or attendance
commitment was made by preparing this guide.
