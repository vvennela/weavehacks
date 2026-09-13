# Sera: two complete three-investigator searches

Both swarms completed the requested fit-first loop on Qwen2.5-72B and one RTX PRO 6000: make it fit, measure a reference, investigate options, test recommendations, use feedback, measure a combination, stop under the progress rule, and return a tested runner. Luna needed one manual controller reconnection. No human chose its experiment settings.

| Swarm | Measured reference p95 | Winning p95 | Improvement | Winner |
| --- | --- | --- | --- | --- |
| [Astra](../live-astra-expanded-v1/README.md) | 770.49 ms | 619.85 ms | 19.55% | Prefix caching + graph execution |
| [Luna](../live-luna-expanded-v2/README.md) | 769.48 ms | 625.37 ms | 18.73% | Prefix caching |

Each run had three investigation rounds and four GPU trials, including deployment. All four configurations in each run passed all eight tasks. All three investigators read Weave in every round. Each received eight distinct legal options at both proposal stages. GPU trials ran sequentially, not as six competing GPU servers.

Both saved full-loop audits pass with no issues. The traces contain 662 calls / 45 typed agent responses for Astra and 664 calls / 45 typed agent responses for Luna. The independent audits recompute quality and gates, verify combination parents and launch settings, and bind agent responses to real CLI calls. Luna's invalid-output and timeout attempts remain recorded. Its manual connection recovery is not hidden by the passing execution audit.

## Plain-English demo script

“We have a model too large to load normally on our GPU. Sera finds a supported way to make it fit, then checks that it answers our tasks correctly. Three specialists inspect the model's answers and performance records. They propose changes, compare findings, and a decision agent chooses what to test. Sera measures each experiment and sends the results back. It can combine changes, but must test the combination too. When useful progress stops, it tests one confirmation and returns the best working plan it measured.”

Show the Astra trace for the strongest complete recording. Its caching experiment helped, its graph-only experiment missed the target, and its measured combination became the winner. Show Luna next: its batch change did not help, and neither did the combination, so it returned caching alone. This demonstrates that the loop can keep a useful earlier result instead of forcing every later experiment to win.

## Open the evidence

- [Astra Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09b0c-d1ac-74ea-a68c-06a4872829c4)
- [Luna Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09b20-b22e-7adb-8fb2-e7a4b6e4ca17)
- [Molab comparison notebook](https://molab.marimo.io/notebooks/nb_QELFTU8UbjWvKPpNe5ezQT), cell `iGPW`; source saved in `notebook-cell.py`. This is a read-only display, not an inference launcher.
- Repository `demo.py` leads with the saved Astra run, including individual proposals, source calls, measured gates, combination parents, the winner, and its stop reason.

The live comparison cell was refreshed after both runs closed and had no cell errors. It displays both gains and discloses Luna's reconnection. Both returned runners passed another request and were then closed to release GPU memory; there is no server left running for interactive inference.

## What this does not prove

The traffic repeats eight questions after warmup. Prefix caching helps that reuse pattern; these results are not a cold-traffic benchmark. Startup is excluded from request latency. Each improvement is against that swarm's own measured FP8 reference, not an unquantized BF16 model that could not fit. One run per model does not rank agent quality or show that a swarm beats a single agent. Weave supplied evidence and traceability, but there was no no-Weave comparison. A 5% progress threshold plus one confirmation is a stopping policy, not proof of global optimality.

Remaining full-product work includes unattended connection recovery, two-model allocation, multi-GPU support, broader model/backend coverage, and the controlled search-superiority benchmark. These are not prerequisites for showing the completed single-model loop honestly.
