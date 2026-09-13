# Stable release package checkpoint

The combined release passes clean base and swarm installation checks. Two
independent wheel builds produce the same bytes. No packaging blocker was found.

- Source: `64dc67145fc0e139183ffbc36776d9091e02e749`.
- Validation checkout: `7faa04e47d57d45a9ddabd250a50bae55208465d`.
- Both source trees: `2f4a37b66f70c0ec7a886e4d4cb25e2f4e12825c`.
- Package: `sera-inference` 0.2.0; no version change, tag, or publication.
- Wheel: `sera_inference-0.2.0-py3-none-any.whl`, 222494 bytes.
- SHA-256: `8dc17e7c9c2b7b968febfc09d3e1416e77e1d0cf6acfab0590260ae529474eba`.

The wheel includes the updated package README from the GPU runtime contract
change. The runtime contract and constraint files are repository documents, not
an installer for a fresh CUDA machine.

## Passed checks

- All 66 packaged Python files match the source bytes.
- Fresh Python 3.11 macOS base and swarm installs pass dependency checks.
- Base imports need no Weave, OpenAI, vLLM, Torch, or repository modules.
- Both installed environments pass SQLite roundtrip, exclusive owner lock, and
  unsafe pre-baseline recovery rejection checks.
- Installed swarm API smoke and `sera-provider-check --help` pass outside the
  checkout, with isolated Python for import and API checks.
- Both installed environments preserve the default per-service accounting mode,
  forward explicit total-device accounting, mark service memory unknown in that
  mode, and reject an invalid mode before execution. External boundaries are
  stubbed.
- The source quick suite plus runtime contract checks pass: **51 tests**.
- The earlier source synthetic rehearsal passes two rounds: reject a candidate
  with bad quality, select the next passing candidate, probe the returned runner,
  and close it. Its exact earlier source is recorded separately.

## Artifact and reproduction

The exact tested wheel is retained at:

```text
/var/folders/4f/r4sxs9j97fdf1c4x4r1wxlt40000gn/T/sera-final-package-w4y6m5yg/dist/sera_inference-0.2.0-py3-none-any.whl
```

[result.json](result.json) records the commands, dependencies, outputs, checksums,
and source identity. [quick-checks.json](quick-checks.json) records the earlier
source tests and synthetic rehearsal. Repeat from a clean checkout of the source:

```sh
python evidence/final-package-release-v1/audit.py \
  --source /path/to/clean/checkout \
  --expected-source 64dc67145fc0e139183ffbc36776d9091e02e749
```

Use each generated base and swarm environment to repeat the accounting check:

```sh
/path/to/environment/bin/python -I \
  /path/to/checkout/evidence/final-package-release-v3/installed_total_device_smoke.py
```

## Limits

No GPU, model-provider, or Weave service calls occurred in this audit. The package
checks ran on macOS, not Linux CUDA. They do not prove inference quality,
performance, search advantage, live restart recovery, multi-GPU support, outage
handling, or soak stability. GPU support remains limited to the separately
recorded tested runtime. This checkpoint is not generic production certification.
The parent task owns the installed-wheel live GPU rehearsal and its evidence.
