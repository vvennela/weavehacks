#!/usr/bin/env bash
# Push notebooks/molab_lab.py into a live molab kernel.
#
# molab gives you a sandbox URL and an access token, and the notebook inside it
# starts blank. This puts Sera's notebook in it. Nothing here is hardcoded: the
# URL and token are arguments, because attaching a GPU in molab's notebook-specs
# UI mints a new sandbox.
#
#   MARIMO_TOKEN=... scripts/push_notebook_to_molab.sh --url https://sb-XXXX.sb.molab.run/
#   scripts/push_notebook_to_molab.sh --url 'https://sb-XXXX.sb.molab.run/?access_token=...'
#   scripts/push_notebook_to_molab.sh --url ... --dry-run
#
# Run it twice and you get the same notebook, not two copies of it.
set -euo pipefail

cd "$(dirname "$0")/.."

# The parser is marimo's own, so we need the interpreter that has marimo.
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

exec "$PY" scripts/push_notebook_to_molab.py "$@"
