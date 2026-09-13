# First uncapped Luna run: confirmation not established

This real run has no total trial-count cap. It completed FP8 deployment and one automatically selected batching trial. Both passed all eight tasks. p95 changed from 771.023249 to 770.337612 ms, a 0.089% gain below the declared 5% target.

That result triggered a second swarm round with `confirmation_round_pending=true`. All three investigators read evidence and exchanged findings, then abstained. Their final explanations cited the prompt sentence “This request does not authorize a GPU trial.” That sentence was intended to separate proposal authority from execution authority; it was ambiguous. The next build clarifies that a specialist may propose a legal untested experiment while execution remains controlled by the arbiter and validator.

Sera returned the working reference, passed its returned-runner request, and closed. This is an early-stop result, not a measured plateau confirmation. `verification.json` fails only the actual-confirmation-trial requirement. Preserve that failed acceptance result rather than treating a second discussion round as a second GPU experiment.

[Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09ac5-56bb-7640-b0c5-0834ec0b5619)

The trace contains 347 completed calls. `launch.json` records the uncapped GPU command; `../live-luna-plateau-controller-v1/controller-launch.json` records the uncapped local controller. Neither this run nor the retry establishes search superiority, global optimality, or a speedup over the infeasible BF16 model.
