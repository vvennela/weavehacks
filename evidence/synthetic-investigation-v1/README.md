# Synthetic investigation rehearsal

This is an offline software check. The agents, answers, latency, and memory values are scripted fixtures. It made **zero provider calls and zero GPU trials**. It does not prove model correctness, agent intelligence, a speedup, or a search advantage.

Source revision: `f00c135`. Command: `python -m experiments.rehearse_investigation --output-dir <new-directory>`.

The production controller completed two rounds:

1. The cache specialist proposed a precision change. Its fast but wrong fixture answer failed the unchanged quality gate. The prediction review was saved as refuted.
2. The batching specialist received that result and cited the prior trial's metric. Its passing fixture was selected. A fresh returned-runner probe passed, and the runner closed.

The second scripted choice requires the first trial's failure and review. This checks that evidence reaches the next decision, not that a real LM learns from it. The record retains both trials and the rejected quality result.

- [Plain-English walkthrough](investigation.md)
- [Complete synthetic record](result.json)

The separate Qwen72B evidence directories contain real GPU measurements. Do not mix their claims with these fixture values.
