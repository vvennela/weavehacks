# Swarm layout experiments with a verified panel primitive

This new bounded block retains the approved 15-Luna shared-board ranking and Astra-high implementation/review. It starts from the original LIBXSMM GEMM body with an optional, unused generated 32-row primitive. Because the build identity changed, its baseline and all paired controls are measured fresh. No old scores enter eligibility.

The primitive preparation passed 12 deterministic panel correctness tests and byte/relocation checks; the augmented baseline passed 48 deterministic GEMM cases. These checks prove neither a full-product candidate nor a speedup. The swarm must select an experiment, Astra must implement it, and Sera must check correctness and repeated signed scores. The optional helper makes a smaller-buffer layout expressible as a short wrapper change instead of a large assembly rewrite.

The fixed limits remain six implementation attempts, 108 Codex calls, 180 seconds per agent call, and 1,800 seconds overall. No pending timeout increase has been applied. The frozen hill, compiler flags, tolerance, single-thread rule, license, promotion gate, and final held-out evaluation remain unchanged. The initial AC or battery source/settings must stay fixed during the block, and both modes' records remain separate.

Preparation: the driver parses as Python and reuses the tested Sera search, correctness, signing, and power-check paths. Fresh agent/search directories prevent overwriting old evidence. The helper is embedded code, with no LIBXSMM runtime linkage. Source hashes and prior experiment context are saved in controls.json when the run starts.

Run once:

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-panel-swarm-2026-09-25/run.py
```

## Completed Low Power outcome

The block completed with 102 total model calls and six attempts. Three distinct candidates passed correctness; none passed promotion. The unchanged reference's final score was 957.13 GFLOP/s and failed confirmation. No winner was returned, and the target remains unmet. All 22 signed reports were independently verified; exact source hashes and unchanged power/settings checks passed.

| Source | Candidate GFLOP/s | Paired controls GFLOP/s |
| --- | --- | --- |
| libxsmm-n512-sixteen-panel32-calls | 1078.05, 1078.60, 1090.83 | 1112.30, 1073.57, 1066.98 |
| libxsmm-n512-constant-shape-c-sme | 1047.21, 760.44, 1082.40 | 1077.33, 1060.13, 1077.51 |
| libxsmm-full512-padded-272-byte-a-slices | 968.06, 1027.18, 836.03 | 1097.33, 935.45, 1057.70 |

`power-mode-observation.json` records a contemporaneous Foundation API result: Low Power Mode was enabled. The block's battery configuration was `powermode 1`; AC was configured separately as `powermode 0`. System Settings subsequently confirmed the Battery pane values Low Power and Automatic. No settings were changed during this block. The user then approved one temporary Automatic battery measurement block followed by restoration. New scores must use fresh controls in that mode, with prior Low Power scores retained separately.
