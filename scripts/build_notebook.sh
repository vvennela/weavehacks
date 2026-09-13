#!/usr/bin/env bash
# Build the Sera Lab notebook: capture -> compact -> generate -> WASM export.
#
# The exported notebook is ~27MB of vendored marimo runtime and is not committed.
# Run this once before demoing, or after changing a lab spec.
#
#   scripts/build_notebook.sh            # reuse existing ledgers
#   scripts/build_notebook.sh --rerun    # re-run the specs first
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

MODELS=(qwen3_8b deepseek_r1_14b moonlight_16b)

if [ "${1:-}" = "--rerun" ]; then
    mkdir -p runs/lab
    for model in "${MODELS[@]}"; do
        printf '\n\033[1m== measuring %s ==\033[0m\n' "$model"
        # --sim today; swap for --vllm on a GPU node and the page relabels itself,
        # because the substrate is read from the ledger rather than hardcoded.
        "$PY" -m sera --spec "specs/lab_${model}.yaml" --sim --fresh --phase 1 \
            --ledger "runs/lab/${model}.jsonl" --quiet
    done
fi

# Ledgers live under runs/, which is gitignored, so a fresh clone will not have
# them. The compacted notebooks/lab_runs.json IS committed and is all the notebook
# needs, so fall back to it rather than forcing a re-measure.
have_ledgers=1
for model in "${MODELS[@]}"; do
    [ -f "runs/lab/${model}.jsonl" ] || have_ledgers=0
done

if [ "$have_ledgers" = "1" ]; then
    "$PY" scripts/build_lab_data.py
elif [ -f notebooks/lab_runs.json ]; then
    echo "No captured ledgers; using the committed notebooks/lab_runs.json."
    echo "Run '$0 --rerun' to measure again from the specs."
else
    echo "No ledgers and no notebooks/lab_runs.json — run: $0 --rerun" >&2
    exit 1
fi

"$PY" scripts/build_lab_notebook.py

rm -rf output/notebook
"$PY" -m marimo export html-wasm notebooks/lab.py -o output/notebook --mode edit >/dev/null
# marimo copies a CLAUDE.md into the export; it is not ours to serve.
rm -f output/notebook/CLAUDE.md

printf '\n\033[32m\033[1mNotebook built\033[0m  output/notebook  (%s)\n' "$(du -sh output/notebook | cut -f1)"
echo "Start the site with: python3 web/server.py   then open http://localhost:8765/notebook"
