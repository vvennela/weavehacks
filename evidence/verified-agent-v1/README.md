# Live verified task gate: no safe configuration

Implementation: da292209a4402cff25e33ac75349feee225585d8.

This new workload, easy-json-system-v1, used all eight existing easy cases plus the benchmark's explicit JSON-only system instruction. The original workload and its records were not changed. The evaluator was the existing strict JSON grader, named sera-easy-strict-json-v1, with a predeclared 0.99 floor. The objective was output throughput.

The baseline passed 2/8 strict tasks. Five other responses contained the correct answer inside forbidden code fences; the filtering answer was wrong. Thus 25% is strict-contract accuracy, not semantic accuracy. All responses finished normally.

The agent returned a schema-valid keep-baseline action, so no candidate trial ran. Its free-text reason discussed an FP8 trial despite that action; this inconsistency is preserved. Sera honored the typed action, did not infer permission to execute from the prose, and did not return the failing baseline. Outcome: no-safe-configuration, no returned models. Runtime cleanup passed.

This proves the fail-closed verified path, not a useful-model or optimization success. The completed notebook cell loads the saved result and does not rerun the job.

[Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a098d3-148c-7dc0-9e8b-deb8f0faff9a).
