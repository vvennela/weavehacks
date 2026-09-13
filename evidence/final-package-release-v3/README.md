# Final wheel: explicit total-device accounting

Source `6130d9e60a91e558c9dff6130ed608066dbe818f` passes clean base and swarm
installation checks after the explicit total-device accounting change.
Earlier v1/v2 records remain unchanged.

- Package: `sera-inference` **0.2.0**.
- Wheel SHA-256: `7be439e26fc5f68aacc35ae2f49e261e3198769c818e90549061357a8a43b6bf`.
- Validation checkout: `50edb13695916a45227b8d950666288eb7eebc24`, with the same
  source tree as `6130d9e`: `15d8910b8a9af3c34f80f1bcced47ac36122c6b6`.
- All **66 packaged Python files** match the source bytes.
- Fresh Python **3.11.15**, macOS base/swarm installs pass dependency checks:
  **9** base packages and **68** swarm packages.
- Base imports work without Weave, OpenAI, vLLM, Torch, or repository modules.
- Both installed environments pass SQLite roundtrip, owner-lock, and unsafe
  pre-baseline recovery rejection checks.
- The installed swarm API smoke and provider-check CLI help pass outside the checkout.
- The focused placement/accounting/API source suite passes **147 tests**.

## New installed accounting checks

[installed_total_device_smoke.py](installed_total_device_smoke.py) runs with
isolated Python in both clean environments. It confirms:

- `per-service` remains the default for `place` and `optimize_placement`.
- The explicit `total-device` argument reaches both execution entry points.
- The shared owner marks per-service memory as unknown, not measured. Allocations
  are configured vLLM budgets, not separately verified process hard caps.
- Unknown accounting modes fail before any external process starts.

These checks inspect installed code and stub execution boundaries. They do not
start a GPU process or establish that live joint placement passed.

## Evidence and repeat

[result.json](result.json) contains exact commands, outputs, dependencies, source
identity, wheel identity, and temporary paths. Repeat the base audit with the
[unchanged audit script](../final-package-release-v1/audit.py) against a clean
checkout of the source SHA above. Then use each new environment's Python:

```sh
/path/to/clean-environment/bin/python -I \
  /path/to/final-package-release-v3/installed_total_device_smoke.py
```

No GPU, provider, or Weave service calls occurred. This is offline package
validation, not a Linux CUDA rehearsal, model-quality result, multi-GPU test,
live recovery test, or generic production certification. Use the wheel hash to
distinguish this artifact from earlier 0.2.0 builds.
