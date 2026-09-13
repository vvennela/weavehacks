# Local release validation

## Latest recorded package check

The [final combined package audit](../evidence/final-package-release-v3/README.md)
checks source `6130d9e60a91e558c9dff6130ed608066dbe818f`:

- Package: `sera-inference` 0.2.0.
- Wheel SHA-256: `7be439e26fc5f68aacc35ae2f49e261e3198769c818e90549061357a8a43b6bf`.
- All 66 packaged Python files match that source tree.
- Clean Python 3.11.15 base and swarm installs pass dependency checks: nine and
  68 packages, respectively. These are macOS installation checks, not CUDA tests.
- Base imports work without Weave, OpenAI, vLLM, Torch, or repository modules.
- Both environments pass SQLite storage, owner-lock, unsafe recovery rejection,
  and explicit total-device accounting checks. Service execution is stubbed.
- The installed swarm API smoke and provider-check help pass outside the checkout.
- The recorded focused source suite passes 147 tests. Exact commands and outputs
  are saved in [result.json](../evidence/final-package-release-v3/result.json).

The [task-verified joint run](../evidence/live-placement-total-v1/README.md) used
the same source revision through an explicitly selected checkout. Both models
passed quality and latency gates, returned usable runners, and closed cleanly.
That is source-runtime evidence, not an installed-wheel GPU rehearsal. The older
installed-wheel check below establishes runtime wiring but not task correctness.

The wheel contains both `sera` and the partner's independent `sera_loop` package.
The investigator swarm and placement evidence above concern `import sera`;
they do not certify the other package's loop. See the
[current release checklist](release-acceptance.md) and
[completion checkpoint](../completion.md) for scope and unproven acceptance.
Use the wheel hash, not only version 0.2.0, to identify the tested artifact.

## Historical merged API candidate

The merged API and recovery wheel was checked again outside the checkout.

- Package: `sera-inference` 0.2.0, source `d8c7304`.
- Wheel SHA-256: `1617374eb978c15f67c85fa0464af2d288474af1721c2a9be240500a80982e6a`.
- Fresh Python 3.11.15 base install: seven packages; isolated import passed without Weave, vLLM, or repository modules.
- Fresh swarm install: 67 packages; dependency checks, installed provider-check help, and the isolated package smoke all passed.
- GPU, provider, certificate, and Weave service boundaries were stubbed in that smoke. It made no live calls.
- Combined API, recovery, and benchmark suite at `316de88`: **917 passed**.
- The same wheel was installed in Molab through marimo's package manager. A fresh isolated process found `sera.api.optimize` in site-packages and accepted the existing 34-case Luna certificate. It reused the existing GPU runtime and cached model files.

The [separate live installed-package check](../evidence/public-api-release-v1/README.md) passed its runtime acceptance: three investigation rounds, a returned runner, a Weave trace, and cleanup. It used quick-mode token agreement and failed arithmetic correctness. Do not treat either the local smoke or that runtime acceptance as task-quality validation.

## Historical original API worker check

These checks validate an earlier 0.2.0 package candidate. They do not replace the
latest package check or a task-verified installed-wheel GPU rehearsal.

- Full local suite: **876 passed**, 12.74 seconds.
- `git diff --check`: passed.
- Wheel build: passed with `uv build --wheel`.
- Wheel SHA-256: `ad621088405f3361e310214438396d9d4075d575825e577ce69ce04d367af225`.
- Wheel-only base import: passed outside the checkout with Python `-I`; Weave,
  experiment modules, CUDA, and vLLM were not installed in that environment.
- Clean `swarm` install: passed with Python 3.11.15 on macOS; 67 packages.
- `uv pip check`: all 67 installed packages compatible.
- Installed `sera-provider-check --help`: passed.
- Installed minimum-call smoke: passed with GPU, provider, certificate, and Weave
  service boundaries explicitly stubbed. It checked setup, trace hook scope,
  usable-result ownership, and caller cleanup. See `tests/installed_package_smoke.py`.
- No GPU experiment or provider request was run for these local checks.

The installed extra resolved Weave 0.53.2, OpenAI 3.13.0, Pydantic 2.13.5, and
prometheus-client 0.26.0. This is an install record, not a new hosted-provider
certificate. Certificate request schemas and cases were not changed.

Later 0.2.0 wheels have different hashes, including the artifact listed above.
Save the exact hash with each live rehearsal. The Codex controller remains separate
repository tooling; its restart behavior is not certified by this package smoke.
