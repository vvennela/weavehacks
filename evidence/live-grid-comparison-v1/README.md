# Frozen live Sera versus grid comparison

The full Luna loop completed three candidate trials and stopped with
`objective-plateau-confirmed`. Three investigators worked in parallel, read Weave
evidence, shared findings, and sent proposals to the arbiter. The live run had no
total trial cap; its preregistered candidate universe contained three configurations.

| Configuration | Worst-load p95 | Task gate |
| --- | --- | --- |
| Qwen72B FP8 weights / BF16 KV reference | 770.682321 ms | Pass |
| Prefix caching | 625.727727 ms | Pass |
| Batch tokens 2048 | 770.456876 ms | Pass |
| Graph execution | 765.613190 ms | Pass |

Sera selected caching first. The frozen lexicographic grid order selected it
third. Both methods used exactly the same measured outcomes. Sera reached within
5% of the best valid configuration in one candidate, versus three for grid.
Its selected runner passed a fresh, independently graded request and cleanup
returned GPU memory to zero. Request latency excludes startup.

The unchanged eight tasks, 99% quality floor, 5% progress target, and concurrency
1/2/4/8 were used. Prompts repeat after warmup: this is not a cold-traffic claim.
Prior measurements informed the three controls. This approved 72B exception is
an exploratory comparison, not the full specification section 19.4 benchmark.

The registered source was `6601669e47879b0492cab09130123a363ae8b91a`.
Collection import and grid scoring used `002285b` only after the live process
exited. All three candidates already had live outcomes; no extra GPU collection
was needed. `actual-launch.json`, `registration.json`, and `live-run.json` preserve
launch identity and result hashes. Raw measurements and the 661-call Weave export
are included. See the separate [random comparison and trace audit](../live-grid-random-replay-v1/README.md).

The GPU archive was transferred with SHA-256
`748c05a57a01bfdb459d0a238f7c163254700a446685f17a125d956626be69b0`.
The original report was not rewritten to fit a historical verifier.

[Live Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09b97-cb9a-701a-a608-ea20decf8416).
