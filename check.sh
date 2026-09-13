#!/usr/bin/env bash
# One command that proves the demo is intact. Run this before submitting.
#
# PYTHONPATH is set explicitly rather than relying on an editable install,
# because `uv` operations elsewhere in the repo uninstall it without warning.
set -uo pipefail

cd "$(dirname "$0")"
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

fail=0
step() {
    local name="$1"; shift
    printf '\n\033[1m== %s ==\033[0m\n' "$name"
    if "$@"; then
        printf '\033[32mPASS\033[0m  %s\n' "$name"
    else
        printf '\033[31mFAIL\033[0m  %s\n' "$name"
        fail=1
    fi
}

step "Test suite" "$PY" -m pytest -q

step "Public API imports cleanly" "$PY" -c "
import sera_loop as sera
from sera_loop import fixtures, report
assert callable(sera.optimize)
for fn in (fixtures.demo_result, fixtures.no_safe_improvement_result):
    r = fn()
    report.state_banner(r); report.progress_rows(r); report.recommendation_md(r)
    assert r.summary_lines()
print('public surface ok')
"

# Scoped to the product surface on purpose. The backend modules are owned by the
# other half of the team and are edited concurrently; linting them here would
# report failures that are neither ours to fix nor a reason to hold the demo.
PRODUCT_FILES=(
    src/sera_loop/types.py
    src/sera_loop/fixtures.py
    src/sera_loop/report.py
    src/sera_loop/__init__.py
    tests/test_contract.py
    tests/test_report.py
    tests/test_notebook.py
)

if command -v uvx >/dev/null 2>&1; then
    step "Lint (product surface)" uvx ruff check "${PRODUCT_FILES[@]}"
fi

printf '\n'
if [ "$fail" -eq 0 ]; then
    printf '\033[32m\033[1mALL GREEN\033[0m — safe to demo.\n'
else
    printf '\033[31m\033[1mSOMETHING FAILED\033[0m — do not demo until this is green.\n'
fi
exit "$fail"
