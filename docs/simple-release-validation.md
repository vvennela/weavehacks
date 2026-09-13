# Local release validation

## Merged candidate

The merged API and recovery wheel was checked again outside the checkout.

- Package: `sera-inference` 0.2.0, source `d8c7304`.
- Wheel SHA-256: `1617374eb978c15f67c85fa0464af2d288474af1721c2a9be240500a80982e6a`.
- Fresh Python 3.11.15 base install: seven packages; isolated import passed without Weave, vLLM, or repository modules.
- Fresh swarm install: 67 packages; dependency checks, installed provider-check help, and the isolated package smoke all passed.
- GPU, provider, certificate, and Weave service boundaries were stubbed in that smoke. It made no live calls.
- Combined API, recovery, and benchmark suite at `316de88`: **917 passed**.
- The same wheel was installed in Molab through marimo's package manager. A fresh isolated process found `sera.api.optimize` in site-packages and accepted the existing 34-case Luna certificate. It reused the existing GPU runtime and cached model files.

The live check is separate from these local checks. Do not treat the local smoke as a GPU result.

## Original API worker check

These checks validate the 0.2.0 package candidate. They do not replace the final
live GPU rehearsal after all worker branches are merged.

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

The final merged wheel can have a different hash. Save its hash with the live
rehearsal before tagging the release. The Codex controller remains separate
repository tooling; its restart behavior is not certified by this package smoke.
