# Installed public API: live rehearsal

**Runtime acceptance passed; task correctness did not.** This checks the new default API from an installed wheel, outside the source checkout. It is not the search benchmark or the task-verified Qwen72B demo.

The call supplied one Qwen3-0.6B model, one prompt, and an output directory. The configured API selected three Luna investigators, automatic candidate generation, Weave reads, and the uncapped plateau-plus-confirmation loop. Provider, project, relay, and the existing 34-case certificate were explicit environment setup. No inference settings or candidate list were supplied in the call.

## Observed result

- One baseline and three candidate measurements across three investigation rounds.
- All three investigators made proposals and reviewed peer findings in every round.
- Sera retained prefix caching, stopped with `objective-plateau-confirmed`, and returned one working runner.
- The caller generated through that runner and closed it. Runtime cleanup passed with GPU memory back at zero; an independent process check found no GPU processes.
- The Weave export has 175 completed calls, no call errors, and 41 typed responses. The audit matches those responses to all 41 saved CLI final outputs. No provider retry or controller outage occurred.

| Configuration | Worst-load p95 |
| --- | ---: |
| Named BF16 baseline | 72.794 ms |
| Prefix caching | 44.002 ms |
| Batch tokens 2048 | 75.500 ms |
| Graph execution | 50.065 ms |

The graph trial was better than baseline but worse than the incumbent. It confirmed the stop rather than replacing the cached runner. These are tiny repeated-prompt measurements, not a general speedup claim. The workload declares concurrency limits 1/2/4/8; one prompt does not establish sustained traffic at those levels.

## Quality failure and limits

The baseline and candidates answered `1 + 1` with `1`. The returned runner answered `2 + 2` with `2` in 72.344 ms. Quick mode checks agreement with the baseline, not truth. The report explicitly sets `task_quality_verified: false`; the probe explicitly sets `probe_matches_four: false`. These answers are preserved, not counted as task success.

The optimization root span ends before the public API returns. Caller generation and cleanup are saved in `rehearsal.json`, not nested under that root. Transport recovery was not exercised by an outage in this run. Use the separate task-verified Qwen72B evidence for the demo's quality claims.

## Reproduce and inspect

- [Weave trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09b42-073e-7c8e-ab79-386fa285b4fa)
- [Rehearsal result](rehearsal.json), [pipeline report](report.md), [audit](audit.json), and [launch cell](notebook-cell.py).
- Source `d8c7304`; installed `sera-inference` 0.2.0. Wheel SHA-256: `1617374eb978c15f67c85fa0464af2d288474af1721c2a9be240500a80982e6a`.
- Molab Python 3.13.11, Weave 0.53.2, vLLM 0.26.0, Torch 2.11.0. Existing runtime and cached weights were reused.
- Run `python evidence/public-api-release-v1/audit.py` from the repository to repeat the read-only audit.

The Linux GPU child used Python `-I` and imported Sera from site-packages. The local Codex controller remains separate repository tooling. This is a release-candidate check, not a published package or release tag.

Temporary GPU library symlinks and the controller lock are excluded from the saved evidence. All measurements, outputs, and trace records remain intact.
