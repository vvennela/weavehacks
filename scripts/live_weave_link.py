"""Answer one question before the demo: does the live run have a Weave trace?

The proof beat opens a real trace on stage. This tool reports either a live trace
URL or the precise reason there is none, so nobody discovers the answer in front
of an audience. It never prints a secret — only whether a variable is set.

    python3 scripts/live_weave_link.py
    python3 scripts/live_weave_link.py --json

Exit status: 0 when a live trace URL is available, 1 when it is not.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The trace the recorded Astra run links, and what the demo falls back to.
RECORDED_TRACE_URL = (
    "https://wandb.ai/vvennela-n-a/wandb_agent_default_project"
    "/r/call/01a09b0c-d1ac-74ea-a68c-06a4872829c4"
)
RECORDED_EXPORT = REPO / "evidence/live-astra-expanded-v1/weave-calls-normalized.json"

# Entry points that drive the live GPU loop. Tracing is opt-in: sera_loop.tracing
# only starts emitting after init() is called, so an entry point that never calls
# it produces zero Weave calls no matter what credentials exist.
LIVE_ENTRY_POINTS = (
    "scripts/live_sera_run.py",
    "scripts/live_bench_vllm.py",
)

CRED_VARS = ("WANDB_API_KEY", "WANDB_PROJECT", "WANDB_ENTITY", "WANDB_MODE")


def credentials() -> dict[str, bool]:
    """Which W&B variables are present. Values are never read out."""
    return {name: bool(os.environ.get(name)) for name in CRED_VARS}


def netrc_has_wandb() -> bool:
    netrc = Path.home() / ".netrc"
    if not netrc.is_file():
        return False
    try:
        return "api.wandb.ai" in netrc.read_text(errors="ignore")
    except OSError:
        return False


def weave_installed() -> bool:
    return importlib.util.find_spec("weave") is not None


def local_trace_cache() -> list[str]:
    """Directories a wandb/weave client would have created had one run here."""
    found = []
    for name in ("wandb", ".weave", ".wandb"):
        path = REPO / name
        if path.is_dir():
            found.append(str(path))
    cache = Path.home() / ".cache/weave"
    if cache.is_dir():
        found.append(str(cache))
    return found


def entry_point_inits_tracing() -> dict[str, bool]:
    """Static check: does the live entry point turn tracing on?

    Cheaper and safer than instrumenting a run in progress — the decorator in
    sera_loop.tracing is inert until init() runs, so this text search is the
    whole answer.
    """
    out = {}
    for rel in LIVE_ENTRY_POINTS:
        path = REPO / rel
        if not path.is_file():
            continue
        text = path.read_text(errors="ignore")
        out[rel] = ("tracing.init" in text) or ("weave.init" in text)
    return out


def recorded_urls_on_disk() -> list[str]:
    """Any weave_url a run actually wrote, newest first."""
    hits: list[tuple[float, str]] = []
    for ledger in (REPO / "runs").rglob("*.jsonl"):
        try:
            for line in ledger.read_text(errors="ignore").splitlines():
                if "weave" not in line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                url = row.get("weave_url")
                if url:
                    hits.append((float(row.get("timestamp") or 0), url))
        except OSError:
            continue
    hits.sort(reverse=True)
    return [url for _, url in hits]


def live_calls_today(entity: str | None, project: str | None) -> tuple[str | None, str | None]:
    """Ask Weave for today's most recent call. Returns (url, error)."""
    if not weave_installed():
        return None, "the weave package is not installed in this environment"
    if not os.environ.get("WANDB_API_KEY") and not netrc_has_wandb():
        return None, "no WANDB_API_KEY and no wandb entry in ~/.netrc"
    target = f"{entity}/{project}" if entity and project else (project or "sera")
    try:
        import weave  # noqa: PLC0415

        client = weave.init(target)
        calls = list(client.get_calls(limit=1))
    except Exception as exc:  # noqa: BLE001 - a probe must not raise on stage
        return None, f"weave query failed: {type(exc).__name__}: {exc}"
    if not calls:
        return None, f"project {target} has no calls"
    call = calls[0]
    call_id = getattr(call, "id", None)
    if not call_id:
        return None, f"project {target} returned a call with no id"
    return f"https://wandb.ai/{target}/r/call/{call_id}", None


def git_head() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def collect() -> dict:
    creds = credentials()
    inits = entry_point_inits_tracing()
    any_init = any(inits.values())
    on_disk = recorded_urls_on_disk()

    live_url: str | None = None
    reason: str | None = None
    if on_disk:
        live_url = on_disk[0]
    elif not any_init:
        reason = (
            "no live entry point calls sera_loop.tracing.init(); the @tracing.op "
            "decorator stays inert, so the run emits zero Weave calls regardless "
            "of credentials"
        )
    elif not creds["WANDB_API_KEY"] and not netrc_has_wandb():
        reason = "tracing.init() returns False without WANDB_API_KEY (or a ~/.netrc wandb entry)"
    elif not weave_installed():
        reason = "the weave package is not importable, so tracing.init() returns False"
    else:
        live_url, reason = live_calls_today(
            os.environ.get("WANDB_ENTITY"), os.environ.get("WANDB_PROJECT")
        )

    return {
        "checked_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_head": git_head(),
        "credentials_present": creds,
        "netrc_has_wandb": netrc_has_wandb(),
        "weave_importable": weave_installed(),
        "live_entry_points_enable_tracing": inits,
        "local_trace_cache_dirs": local_trace_cache(),
        "weave_urls_written_by_runs": on_disk,
        "live_trace_url": live_url,
        "no_live_trace_reason": reason,
        "fallback_recorded_trace_url": RECORDED_TRACE_URL,
        "fallback_export_on_disk": str(RECORDED_EXPORT),
        "fallback_export_exists": RECORDED_EXPORT.is_file(),
        "fallback_export_bytes": RECORDED_EXPORT.stat().st_size
        if RECORDED_EXPORT.is_file()
        else 0,
    }


def render(state: dict) -> None:
    print(f"Weave trace check  {state['checked_utc']}  (HEAD {state['git_head']})")
    print()
    print("  credentials (presence only, never values)")
    for name, present in state["credentials_present"].items():
        print(f"    {name:<16} {'set' if present else 'NOT SET'}")
    print(f"    ~/.netrc wandb   {'yes' if state['netrc_has_wandb'] else 'no'}")
    print(f"    weave importable {'yes' if state['weave_importable'] else 'no'}")
    print()
    print("  live entry points")
    if state["live_entry_points_enable_tracing"]:
        for rel, on in state["live_entry_points_enable_tracing"].items():
            print(f"    {rel:<32} tracing {'ENABLED' if on else 'never initialised'}")
    else:
        print("    none found")
    caches = state["local_trace_cache_dirs"]
    print(f"    local weave/wandb cache          {', '.join(caches) if caches else 'none'}")
    print()
    if state["live_trace_url"]:
        print("  LIVE TRACE: yes")
        print(f"    {state['live_trace_url']}")
    else:
        print("  LIVE TRACE: NO")
        print(f"    reason: {state['no_live_trace_reason']}")
        print()
        print("  Open this on stage instead (recorded Astra run):")
        print(f"    {state['fallback_recorded_trace_url']}")
        exists = state["fallback_export_exists"]
        size = state["fallback_export_bytes"]
        print(
            f"    local export: {'present' if exists else 'MISSING'} "
            f"({size:,} bytes) {state['fallback_export_on_disk']}"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="live_weave_link", description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    state = collect()
    if args.json:
        print(json.dumps(state, indent=2))
    else:
        render(state)
    return 0 if state["live_trace_url"] else 1


if __name__ == "__main__":
    sys.exit(main())
