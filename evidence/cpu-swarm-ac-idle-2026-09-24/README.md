# AC idle baseline-only block

This block completed on the Apple M4 Pro while on AC power, with the user idle request recorded. It **did not produce or measure a new kernel**. The approved target was strictly greater than 1,800 GFLOP/s; this block did not meet it.

The swarm made 32 Codex model calls: 15 Luna calls for proposals, 15 Luna calls for rankings, one Astra-high call to select the 15-role roster, and one Astra-high implementation call. All 15 role rankings were received and valid. Fourteen specialists abstained from proposing an experiment; `loop_order` was the sole board item. Astra-high then abstained from implementation because that proposal described the baseline's existing outer-loop order. No candidate was compiled or timed, no candidate controls were run, and no source was promoted. The call and abstention record is in `agent/state.json`.

The unchanged `existing-sme` baseline passed the public correctness validator's 48 deterministic cases (16 sizes, three input kinds). Its three official validation scores were **1,504.19, 1,372.78, and 1,451.00 GFLOP/s**. The held-out final report scored **1,640.55 GFLOP/s**. The target remains unmet. These reports are baseline evidence, not an optimization gain.

I independently ran `hills verify --json` on all four reports. All four signatures are valid; each report is official and passed. They use the same hill tree, configuration, runtime identity, and submission hash. Host observations before and after every report show AC power, unchanged power settings, and no recorded thermal or performance warning. See `verification.json` for the report paths and checks.

No candidate promotion or end-to-end model speedup is established. The run uses the trusted local native-code evaluator; it is not a production sandbox. The public validator covers a finite set of cases and does not prove correctness for every dimension.
