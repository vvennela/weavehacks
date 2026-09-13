#!/usr/bin/env bash
# Stage proof: one command that shows a real completion off the real Blackwell.
# Prints the GPU, then a live inference with its measured latency.
#
# Credentials come from the environment on purpose. The molab access token grants
# arbitrary code execution on the sandbox, so it must never live in the repo.
#
#   export MOLAB_URL=https://sb-<id>.sb.molab.run/
#   export MARIMO_TOKEN=<access token>
#   ./scripts/prove_blackwell.sh
set -uo pipefail
cd "$(dirname "$0")/.."

if [ -z "${MOLAB_URL:-}" ] || [ -z "${MARIMO_TOKEN:-}" ]; then
    echo "Set MOLAB_URL and MARIMO_TOKEN first. See the header of this script." >&2
    exit 2
fi
export MARIMO_TOKEN

bash .agents/skills/marimo-pair/scripts/execute-code.sh --url "$MOLAB_URL" - <<'PY'
import json, time, subprocess, urllib.request

print(subprocess.run(
    ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,driver_version",
     "--format=csv,noheader"], capture_output=True, text=True).stdout.strip())

# Chat endpoint, not raw completions: the base model continues the prompt rather
# than answering it, which reads as broken on stage. chat_template_kwargs turns
# off Qwen3's thinking block so the answer is the whole output.
body = json.dumps({
    "model": "Qwen/Qwen3-8B", "temperature": 0, "max_tokens": 80,
    "messages": [{"role": "user",
                  "content": "In two sentences: why does serving configuration "
                             "matter more than raw FLOPs?"}],
    "chat_template_kwargs": {"enable_thinking": False},
}).encode()
req = urllib.request.Request("http://127.0.0.1:8000/v1/chat/completions", data=body,
                             headers={"Content-Type": "application/json"})
t0 = time.time()
out = json.loads(urllib.request.urlopen(req, timeout=180).read())
print("latency_ms: %.1f" % ((time.time() - t0) * 1000))
print("tokens:", out["usage"]["completion_tokens"])
print(out["choices"][0]["message"]["content"].strip())
PY
