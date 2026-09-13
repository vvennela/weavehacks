# Sera release acceptance

This release covers the `import sera` backend on the pinned, tested NVIDIA
setup. It is a controlled deployment release, not a claim of general production
readiness. The independent `sera_loop` package and partner website remain in the
repository; these measurements do not certify that separate implementation.

See [completion.md](../completion.md) for the full product status. Historical
recordings remain unchanged, including failed experiments.

## Release gates

| Gate | Evidence and status |
| --- | --- |
| Autonomous single-model loop | Passed: three investigators, shared findings, arbiter selection, measured feedback, progress-based stop, usable returned runner, and cleanup in the saved [Astra and Luna runs](../evidence/expanded-swarm-comparison/README.md). |
| Joint model acceptance | Passed: the specified Qwen0.6B + GLM9B pair meets unchanged quality, latency, overlap, total-device memory, returned-runner, and cleanup gates. [Independent audit](../evidence/live-placement-total-v1/README.md). |
| Source regression suite | 1,512 passed, one optional marimo skip on `befda96`, in a fresh frozen development environment. |
| Clean package installation | Passed for the final [staged release wheel](../evidence/stable-release-package-v2/README.md): 23 checks, 68 source files matched, two byte-identical builds. |
| Installed-package live joint run | Failed: GLM p95 was 192.68 ms against the fixed 187.93 ms ceiling. Both task gates, memory, and cleanup passed. The earlier passing source run does not override this repeat. |
| Credential handling | Keys stay in the environment. Reports do not contain secret values. A local Codex controller remains required for the demonstrated investigator route. |

Do not promote a failed gate by lowering its threshold. Preserve the failed
result, fix the cause, and rerun the affected check.

## Supported behavior

- Quick mode uses deterministic token agreement, not task accuracy. Task-verified
  and fit-first deployment require an evaluator, its version, and a quality floor.
  No BF16 output baseline is invented for a model whose BF16 weights do not fit.
- The default investigator search has no total trial cap. It stops under the
  progress and confirmation rule, or when no legal experiment remains. A caller
  can explicitly request a cap. Eight options per specialist is not a trial cap.
- Ordered stages support latency, memory, and supported quantization controls.
  `k` permits bounded regression in earlier objectives; the next objective must
  improve and quality remains fixed. Synthetic integration tests pass. A live
  staged speedup and whole-sequence crash resume remain unproven.
- The joint run uses Qwen3-0.6B BF16 and GLM-4-9B FP8 weights/BF16 KV. Each passes
  eight task checks and 96 timed task checks at concurrency 1/2/4/8. Each model's
  worst-load p95 must stay within 10% of its matching isolated p95.
- The joint device budget is deliberately 24 GiB on a 97,887 MiB physical GPU.
  This represents smaller memory capacity, not another GPU's speed or bandwidth.
  Approved Molab total-device accounting does not verify separate service hard
  caps. The 3 GiB and 17 GiB allocations are configured vLLM budgets. Sampling can
  miss short memory peaks. Strict per-service accounting remains the default.
- Returned runners remain usable until the caller closes them. Rehearsals probe
  both runners, then close them and verify idle-device cleanup. No open service
  is promised after the rehearsal.
- The main Weave trace ends when optimization returns. Later caller requests and
  cleanup must not be presented as children of that completed trace.

## Repeatable checks

From the release checkout:

```sh
uv run --frozen --extra dev pytest -q
PYTHONPATH=. uv run --frozen python evidence/live-placement-total-v1/audit.py
```

The first command checks source behavior. The second rechecks saved measurements
without GPU or provider calls. Neither is a new live performance measurement.
Use the [README quick check](../README.md#quick-test-does-the-loop-work) for a
short offline loop rehearsal. Clean installation and live execution must record
their wheel hash, imported package location, exact configurations, and cleanup.

## Deferred acceptance, not completed work

- Live outage recovery and sustained-load testing are deferred by user request.
  Single-model SQLite resume and controller recovery have offline fault tests;
  placement resume is not implemented.
- Arbitrary models, other GPU/runtime combinations, and real 2/4/8-GPU execution
  are not validated. A dependency range is not a hardware support claim.
- Full grid/random/ablation search superiority and both required pressure
  scenarios remain unproven. The passing joint run has only one eligible plan;
  it does not prove a multi-plan search advantage.
- The same-allocation BF16 joint counterfactual fails an estimate, not a measured
  joint run. No measured BF16 memory savings or global optimum is claimed.
- ARIA is optional and is not in the validated autonomous execution path.

These limits do not block the documented controlled deployment. They do block a
claim that the complete specification or unattended production support is done.
