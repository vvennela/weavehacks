"""Append measured (substrate=vllm) trial rows produced on the GPU box into the
local run ledger the dashboard reads. Never rewrites or removes existing rows."""
from __future__ import annotations

import json
import sys
from pathlib import Path

LOCAL = Path("runs/ledger.jsonl")


def main(incoming: str) -> int:
    rows = [json.loads(l) for l in Path(incoming).read_text().splitlines() if l.strip()]
    existing = set()
    if LOCAL.exists():
        for line in LOCAL.read_text().splitlines():
            if line.strip():
                existing.add(json.loads(line)["trial_id"])
    added = 0
    with LOCAL.open("a") as fh:
        for r in rows:
            if r["trial_id"] in existing:
                continue
            fh.write(json.dumps(r) + "\n")
            added += 1
    print(f"appended {added} rows to {LOCAL} ({len(rows)} offered)")
    for r in rows:
        m = r.get("measurement") or {}
        print(f"  {r['trial_id']:32} substrate={r['substrate']:5} verdict={r['verdict']:16} "
              f"p95={m.get('p95_latency_ms')} tput={m.get('throughput_rps')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
