# Final combined package: offline validation

The wheel built from source `879004c55a7349573946a2448dc75b3d5acc8af1` passes clean
base and swarm-extra installation checks. This source includes automatic
placement, fixed-hardware optimization, and SQLite recovery.

- Package: `sera-inference` **0.2.0**.
- Wheel SHA-256: `5c918990d6ef88dff8fecfb5d0fe386149ba1b5eac2676fa69d658947a7ec30c`.
- Validation checkout: `788a85514cbc9027129bc473b602a726d49f7cd5`; its Git tree is
  identical to the source above: `dbd5fd8c6782a7e3817be6a5e395f921d56181db`.
- Fresh Python **3.11.15**, macOS environments: **9 base packages**, **68 swarm
  packages**. Both pass dependency compatibility checks.
- All **66 packaged Python source files** match the checkout bytes. The wheel
  contains both `sera` and `sera_loop`, not repository tests or experiment tools.
- Isolated base import works without Weave, OpenAI, vLLM, Torch, `experiments`, or
  `benchmarks`. All seven public optimization/placement/recovery functions import.
- Both installed environments pass SQLite roundtrip, exclusive ownership, and
  pre-baseline resume rejection checks.
- The swarm install passes the existing `tests/installed_package_smoke.py` and
  `sera-provider-check --help`, outside the checkout with isolated Python.
- The focused source API/recovery/portable/placement suite passes **93 tests** in
  the separate development environment.

[result.json](result.json) records commands, outputs, resolved dependencies,
temporary paths, source identity, and wheel identity.

## Repeat

Use a clean checkout of the exact source SHA above. The audit script can live in
another checkout; it builds and installs into new temporary directories:

```sh
python /path/to/final-package-release-v1/audit.py \
  --source /path/to/source-checkout \
  --expected-source 879004c55a7349573946a2448dc75b3d5acc8af1
```

## Limits

No GPU, provider, or Weave service calls occurred. The installed API smoke stubs
those boundaries. No CUDA runtime was installed. This does not establish a Linux
GPU rehearsal, live interruption recovery, model quality, multi-GPU performance,
or complete-spec acceptance. The package version remains 0.2.0; use the wheel hash
to distinguish this build from earlier 0.2.0 evidence.
