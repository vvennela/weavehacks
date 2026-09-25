# Swarm layout experiments with a verified panel primitive

This new bounded block retains the approved 15-Luna shared-board ranking and Astra-high implementation/review. It starts from the original LIBXSMM GEMM body with an optional, unused generated 32-row primitive. Because the build identity changed, its baseline and all paired controls are measured fresh. No old scores enter eligibility.

The primitive preparation passed 12 deterministic panel correctness tests and byte/relocation checks; the augmented baseline passed 48 deterministic GEMM cases. These checks prove neither a full-product candidate nor a speedup. The swarm must select an experiment, Astra must implement it, and Sera must check correctness and repeated signed scores. The optional helper makes a smaller-buffer layout expressible as a short wrapper change instead of a large assembly rewrite.

The fixed limits remain six implementation attempts, 108 Codex calls, 180 seconds per agent call, and 1,800 seconds overall. No pending timeout increase has been applied. The frozen hill, compiler flags, tolerance, single-thread rule, license, promotion gate, and final held-out evaluation remain unchanged. The initial AC or battery source/settings must stay fixed during the block, and both modes' records remain separate.

Preparation: the driver parses as Python and reuses the tested Sera search, correctness, signing, and power-check paths. Fresh agent/search directories prevent overwriting old evidence. The helper is embedded code, with no LIBXSMM runtime linkage. Source hashes and prior experiment context are saved in controls.json when the run starts.

Run once:

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-panel-swarm-2026-09-25/run.py
```
