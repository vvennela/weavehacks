#!/usr/bin/env bash
# Build the Sera Lab notebook and export it to WebAssembly.
#
# The notebook embeds Sera's source and runs the real optimization loop in the
# browser, so there is no captured data to refresh — rebuilding is just
# re-bundling the current source.
#
# The export is ~27MB of vendored marimo runtime and is not committed.
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

"$PY" scripts/build_lab_notebook.py

rm -rf output/notebook
"$PY" -m marimo export html-wasm notebooks/lab.py -o output/notebook --mode edit >/dev/null
# marimo copies a CLAUDE.md into the export; it is not ours to serve.
rm -f output/notebook/CLAUDE.md

printf '\n\033[32m\033[1mNotebook built\033[0m  output/notebook  (%s)\n' "$(du -sh output/notebook | cut -f1)"
echo "Restart the server (python3 web/server.py) and open http://localhost:8765/notebook"
