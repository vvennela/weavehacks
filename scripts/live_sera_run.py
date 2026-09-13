"""Drive Sera's real Phase-1 loop against a physical GPU via the vLLM runner.

No source change to src/sera_loop is required: this constructs VllmRunner directly
with its default `managed_vllm` launcher, so every trial really starts a vLLM server
with that trial's configuration, replays the spec's trace at it, and measures.
Substrate is recorded as "vllm" on every ledger row it writes.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.environ.get("SERA_SRC", "/tmp/sera-src"))

from sera_loop.ledger import Ledger  # noqa: E402
from sera_loop.phase1 import Phase1  # noqa: E402
from sera_loop.runner.vllm_runner import VllmRunner  # noqa: E402
from sera_loop.spec import load_spec  # noqa: E402

SPEC = os.environ.get("SERA_SPEC", "/tmp/sera-src/live_qwen3_8b_blackwell.yaml")
LEDGER = os.environ.get("SERA_LEDGER", "/tmp/sera-runs/ledger.jsonl")


def main() -> int:
    spec = load_spec(SPEC)
    runner = VllmRunner(base_port=8100)
    ledger = Ledger(LEDGER)
    print(f"spec={SPEC} substrate={runner.substrate.value} ledger={LEDGER}", flush=True)
    print(f"start_utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", flush=True)
    p1 = Phase1(spec, runner, ledger, verbose=True)
    try:
        outcomes = p1.run()
    except Exception:
        traceback.print_exc()
        print("PHASE1_ERROR", flush=True)
        return 1
    print(json.dumps(ledger.summary(), indent=2), flush=True)
    print(f"end_utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", flush=True)
    print("PHASE1_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
