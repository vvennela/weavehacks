#!/usr/bin/env bash
# Podium health check for the live molab Blackwell. READ-ONLY.
#
# Answers one question in a few seconds: which STAGE.md opening do I use?
#
#   READY                -> STAGE.md Opening A (badge LIVE)
#   GPU-BUT-NOT-SERVING  -> STAGE.md Opening B (badge RECORDED)
#   SANDBOX-DOWN         -> STAGE.md Opening C (badge RECORDED)
#
# This script only reads. It never restarts vLLM, kills a process, installs
# anything, or writes a file — on the sandbox or here. Another agent may be
# driving the GPU while you run it; that is safe.
#
# Credentials come from the environment on purpose. The molab access token
# grants arbitrary code execution on the sandbox, so it must never live in the
# repo.
#
#   export MOLAB_URL=https://sb-<id>.sb.molab.run/
#   export MARIMO_TOKEN=<access token>
#   ./scripts/molab_health.sh
#
# Exit codes: 0 READY | 3 GPU-BUT-NOT-SERVING | 4 SANDBOX-DOWN | 2 bad usage.
set -uo pipefail
cd "$(dirname "$0")/.."

if [ -z "${MOLAB_URL:-}" ] || [ -z "${MARIMO_TOKEN:-}" ]; then
    echo "molab_health: MOLAB_URL and MARIMO_TOKEN must both be set in the environment." >&2
    echo "  export MOLAB_URL=https://sb-<id>.sb.molab.run/" >&2
    echo "  export MARIMO_TOKEN=<access token>   # never write it into a file in this repo" >&2
    echo "Both are minted together when the GPU is attached; see docs/live-molab-setup.md." >&2
    exit 2
fi
export MARIMO_TOKEN

BASE="${MOLAB_URL%/}"
EXEC=".agents/skills/marimo-pair/scripts/execute-code.sh"

# A hang at the podium is the exact failure this script exists to catch, so every
# remote call is capped. macOS ships no coreutils `timeout`, hence the watchdog:
# it kills the helper and the curl underneath it, and keeps its own output off
# the captured pipe so a fast call still returns fast.
run_capped() {
    local secs="$1"; shift
    if command -v timeout >/dev/null 2>&1; then timeout "$secs" "$@"; return $?; fi
    if command -v gtimeout >/dev/null 2>&1; then gtimeout "$secs" "$@"; return $?; fi
    "$@" &
    local pid=$!
    ( sleep "$secs"
      # Note the order: list the children while the parent still owns them, kill
      # the parent so it cannot run its next line, then kill the orphans.
      children=$(pgrep -P "$pid" 2>/dev/null)
      kill -TERM "$pid" 2>/dev/null
      [ -n "$children" ] && kill -TERM $children 2>/dev/null ) >/dev/null 2>&1 &
    local watchdog=$!
    wait "$pid"; local rc=$?
    kill -TERM "$watchdog" 2>/dev/null
    wait "$watchdog" 2>/dev/null
    return $rc
}

echo "molab health check  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "sandbox: $BASE"
echo

# ---------------------------------------------------------------- a) reachable
reachable=no
for path in /health /api/status; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 \
             -H "Authorization: Bearer ${MARIMO_TOKEN}" "${BASE}${path}" 2>/dev/null)
    if [ -n "$code" ] && [ "$code" != "000" ]; then
        printf 'HTTP  %-12s %s\n' "$path" "$code"
        case "$code" in 2*|3*) reachable=yes ;; esac
    else
        printf 'HTTP  %-12s unreachable (no response in 4s)\n' "$path"
    fi
done

if [ "$reachable" != yes ]; then
    echo
    echo "GPU   not probed (sandbox unreachable)"
    echo "VLLM  not probed (sandbox unreachable)"
    echo
    echo "VERDICT: SANDBOX-DOWN -> STAGE.md Opening C (badge RECORDED). Do not debug on stage."
    exit 4
fi

# --------------------------------------------------- b) GPU and c) vLLM, one hop
# One round trip so the whole check stays inside a few seconds. Both probes are
# reads: an nvidia-smi query and an HTTP GET on the vLLM model list.
PROBE=$(cat <<'PY'
import json, subprocess, urllib.request

try:
    r = subprocess.run(
        ["nvidia-smi",
         "--query-gpu=name,memory.total,memory.used,driver_version",
         "--format=csv,noheader"],
        capture_output=True, text=True, timeout=8)
    line = r.stdout.strip()
    print("GPU   " + (line if r.returncode == 0 and line else "NONE (nvidia-smi returned nothing)"))
except FileNotFoundError:
    print("GPU   NONE (no nvidia-smi on this sandbox)")
except Exception as exc:
    print("GPU   NONE (%s)" % type(exc).__name__)

try:
    with urllib.request.urlopen("http://127.0.0.1:8000/v1/models", timeout=4) as resp:
        models = [m["id"] for m in json.load(resp).get("data", [])]
    print("VLLM  SERVING on 127.0.0.1:8000  models=%s" % (",".join(models) or "<none listed>"))
except Exception as exc:
    print("VLLM  NOT SERVING on 127.0.0.1:8000 (%s)" % type(exc).__name__)
PY
)

echo
# execute-code.sh prints a "non-local server" caution on every call. It is
# expected here and only adds noise to a verdict you read under stage lights.
remote=$(run_capped 20 bash "$EXEC" --url "$BASE" -c "$PROBE" 2>&1 \
         | grep -v '^Warning: connecting to non-local server')
rc=$?
if [ -z "$remote" ]; then
    remote="(no output from the sandbox kernel; probe exit $rc)"
fi
printf '%s\n' "$remote"

# ------------------------------------------------------------------ d) verdict
echo
if printf '%s' "$remote" | grep -q '^VLLM  SERVING'; then
    echo "VERDICT: READY -> STAGE.md Opening A (badge LIVE). Run scripts/prove_blackwell.sh once to warm it."
    exit 0
elif printf '%s' "$remote" | grep -q '^GPU   ' && \
     ! printf '%s' "$remote" | grep -q '^GPU   NONE'; then
    echo "VERDICT: GPU-BUT-NOT-SERVING -> STAGE.md Opening B (badge RECORDED). Show nvidia-smi, do not restart vLLM."
    exit 3
else
    echo "VERDICT: SANDBOX-DOWN -> STAGE.md Opening C (badge RECORDED). Do not debug on stage."
    exit 4
fi
