"""Push a local marimo notebook into a live molab kernel.

molab hands you a sandbox URL and an access token; the notebook inside it starts
blank. This pushes notebooks/molab_lab.py into that running kernel so the demo
notebook is the one on screen.

The transport is marimo's agent API, `marimo._code_mode` (`cm`), executed in the
kernel's scratchpad over `POST /api/kernel/execute`. That is the only path that
reaches the *running* kernel: writing the .py in the sandbox, or POSTing
/api/kernel/save, updates the file and the server-side app object but leaves the
kernel graph and the open browser editor untouched, and the next autosave
overwrites the file again. `cm` mutates the graph, broadcasts a document
transaction to the browser, and the server autosaves the .py from that — one
write, three consistent views.

Cell bodies come from marimo's own parser (`marimo._ast.parse.parse_notebook`),
which strips the `@app.cell` wrapper and the trailing `return (...)` tuple and
hands back exactly the text that belongs in a cell.

    scripts/push_notebook_to_molab.sh --url https://<sandbox>.sb.molab.run/

Token: MARIMO_TOKEN (preferred), --token, or ?access_token= on the URL.
URL:   --url, or SERA_MOLAB_URL.

Idempotent: cells are matched to the live notebook by position, so a second push
edits in place rather than appending a duplicate copy.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTEBOOK = ROOT / "notebooks" / "molab_lab.py"
DEFAULT_EXECUTE_CODE = (
    ROOT / ".agents" / "skills" / "marimo-pair" / "scripts" / "execute-code.sh"
)
# Already in every marimo kernel; asking for it again is a slow no-op.
SKIP_PACKAGES = {"marimo"}
SETUP_CELL_NAME = "setup"
DEFAULT_CELL_NAME = "_"
MARK = "SERA-PUSH"

BOLD, GREEN, RED, YELLOW, DIM, OFF = (
    "\033[1m", "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m",
)
if not sys.stdout.isatty():
    BOLD = GREEN = RED = YELLOW = DIM = OFF = ""


def step(msg: str) -> None:
    print(f"\n{BOLD}== {msg} =={OFF}", flush=True)


def ok(msg: str) -> None:
    print(f"{GREEN}ok{OFF}    {msg}", flush=True)


def note(msg: str) -> None:
    print(f"{DIM}      {msg}{OFF}", flush=True)


def warn(msg: str) -> None:
    print(f"{YELLOW}warn{OFF}  {msg}", flush=True)


def die(msg: str) -> NoReturn:
    print(f"\n{RED}{BOLD}FAILED{OFF}  {msg}", file=sys.stderr)
    raise SystemExit(1)


# --------------------------------------------------------------- parsing ---


def parse_cells(path: Path) -> tuple[list[dict], dict]:
    """Split a marimo app .py into cell bodies plus the App(...) options.

    marimo's own parser does the work: `parse_notebook` walks the module AST,
    finds each `@app.cell`-decorated function (and a `with app.setup:` block if
    present), and returns a CellDef per cell whose `.code` is the dedented body
    with the trailing `return (...)` removed. Hand-rolling this gets the
    return-tuple, trailing-comment and decorator-kwarg cases wrong.
    """
    try:
        from marimo._ast.parse import parse_notebook
    except ImportError as exc:  # pragma: no cover - environment problem
        die(
            f"cannot import marimo's notebook parser ({exc}).\n"
            "        Run through scripts/push_notebook_to_molab.sh so the "
            "repo's .venv is used."
        )

    source = path.read_text(encoding="utf-8")
    nb = parse_notebook(source, filepath=str(path))
    if nb is None:
        die(f"{path} is empty")
    hard = [v for v in nb.violations if v.description not in _SOFT]
    if hard:
        for v in hard:
            warn(f"{path.name}:{v.lineno}  {v.description}")
        die(f"{path} does not parse as a clean marimo notebook")

    cells: list[dict] = []
    for cd in nb.cells:
        kind = type(cd).__name__
        if kind == "UnparsableCell":
            die(f"{path} has an unparsable cell at line {cd.lineno}")
        if kind in ("FunctionCell", "ClassCell"):
            # @app.function / @app.class_definition serialize as top-level
            # defs, not cell bodies; cm has no equivalent op.
            die(
                f"{path} uses @app.{'function' if kind == 'FunctionCell' else 'class_definition'} "
                f"at line {cd.lineno}, which cm cannot push"
            )
        opts = dict(cd.options or {})
        config = {"hide_code": bool(opts.get("hide_code", False))}
        if "disabled" in opts:
            config["disabled"] = bool(opts["disabled"])
        if opts.get("column") is not None:
            config["column"] = int(opts["column"])
        cells.append(
            {
                "code": cd.code,
                "name": None if cd.name in (DEFAULT_CELL_NAME, "") else cd.name,
                "setup": kind == "SetupCell",
                "config": config,
            }
        )
    if not cells:
        die(f"{path} has no cells to push")
    return cells, dict(nb.app.options or {})


try:
    from marimo._ast.parse import SOFT_VIOLATIONS as _SOFT
except ImportError:  # pragma: no cover - older marimo
    _SOFT = frozenset()


PEP723 = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def pep723_dependencies(path: Path) -> list[str]:
    """Return the PEP 723 inline-script dependencies declared by the notebook."""
    blocks = [m for m in PEP723.finditer(path.read_text(encoding="utf-8"))
              if m.group("type") == "script"]
    if not blocks:
        return []
    content = "".join(
        line[2:] if line.startswith("# ") else line[1:]
        for line in blocks[0].group("content").splitlines(keepends=True)
    )
    deps = tomllib.loads(content).get("dependencies", []) or []
    return [d for d in deps if _dep_name(d) not in SKIP_PACKAGES]


def _dep_name(spec: str) -> str:
    return re.split(r"[<>=!~\[; ]", spec.strip(), maxsplit=1)[0].lower()


# ------------------------------------------------------------ kernel side ---

# Runs in the kernel scratchpad. Everything it binds is `_`-prefixed so it
# cannot shadow a notebook global in the scratchpad's copy of the namespace.
PUSH_SCRIPT = '''
import base64 as _b64, json as _json
import marimo._code_mode as cm

_spec = _json.loads(_b64.b64decode("@@PAYLOAD@@").decode("utf-8"))
_want, _pkgs, _run_all = _spec["cells"], _spec["packages"], _spec["run"]

if _pkgs:
    async with cm.get_context() as ctx:
        ctx.packages.add(*_pkgs)

async with cm.get_context() as ctx:
    # Read every cell before writing: edit_cell raises StaleCellError rather
    # than clobber a cell the agent has not read at its current version.
    _live = [(c.id, c.name, c.code) for c in ctx.cells]
    _setup_id = next((i for i, n, _ in _live if n == "setup"), None)
    _body_ids = [i for i, n, _ in _live if n != "setup"]

    _w_setup = next((c for c in _want if c["setup"]), None)
    _w_body = [c for c in _want if not c["setup"]]
    _touched = []

    if _w_setup is not None:
        if _setup_id is not None:
            ctx.edit_cell(_setup_id, code=_w_setup["code"], **_w_setup["config"])
        else:
            _kw = dict(_w_setup["config"])
            if _body_ids:
                _kw["before"] = _body_ids[0]
            _setup_id = ctx.create_cell(_w_setup["code"], name="setup", **_kw)
        _touched.append(_setup_id)
    elif _setup_id is not None:
        ctx.delete_cell(_setup_id)
        _setup_id = None

    _prev = _setup_id
    for _i, _c in enumerate(_w_body):
        _kw = dict(_c["config"])
        if _c["name"]:
            _kw["name"] = _c["name"]
        if _i < len(_body_ids):
            _cid = _body_ids[_i]
            ctx.edit_cell(_cid, code=_c["code"], **_kw)
        else:
            if _prev is not None:
                _kw["after"] = _prev
            _cid = ctx.create_cell(_c["code"], **_kw)
        _touched.append(_cid)
        _prev = _cid

    for _cid in _body_ids[len(_w_body):]:
        ctx.delete_cell(_cid)

    if _run_all:
        for _cid in _touched:
            ctx.run_cell(_cid)

print("@@MARK@@ pushed %d cell(s)" % len(_want))
'''

VERIFY_SCRIPT = '''
import base64 as _b64, hashlib as _h, json as _json
import marimo._code_mode as cm

_want_n = _json.loads(_b64.b64decode("@@PAYLOAD@@").decode("utf-8"))

def _norm(s):
    return "\\n".join(l.rstrip() for l in s.strip().splitlines() if l.strip())

_live = [{"id": c.id, "name": c.name,
          "sha": _h.sha256(c.code.encode()).hexdigest(),
          "norm": _h.sha256(_norm(c.code).encode()).hexdigest()}
         for c in cm.get_context().cells]
print("@@MARK@@JSON " + _json.dumps({"want": _want_n, "live": _live}))
'''


def render(template: str, payload: object) -> str:
    blob = base64.b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    return template.replace("@@PAYLOAD@@", blob).replace("@@MARK@@", MARK)


# ---------------------------------------------------------------- server ---


def http(base: str, path: str, token: str, body: object | None = None) -> object:
    url = base.rstrip("/") + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        die(f"{path} -> HTTP {exc.code}. {detail}")
    except urllib.error.URLError as exc:
        die(f"cannot reach {url}: {exc.reason}")
    return json.loads(raw) if "json" in ctype else raw


def split_token(url: str) -> tuple[str, str | None]:
    """molab hands out the URL with the token on it; accept that form."""
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parts.query)
    token = (query.pop("access_token", [None]) or [None])[0]
    clean = urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path or "/",
         urllib.parse.urlencode(query, doseq=True), "")
    )
    return clean.rstrip("/") or clean, token


def pick_session(sessions: dict, want_file: str | None) -> tuple[str, str | None]:
    if not sessions:
        die("no active marimo sessions. Open the notebook in the browser first.")
    if want_file:
        hits = [(sid, s) for sid, s in sessions.items()
                if want_file in (s.get("path"), s.get("filename"))]
        if not hits:
            die(f"no session for --file {want_file!r}. Open: "
                + ", ".join(str(s.get("path")) for s in sessions.values()))
        sid, info = hits[0]
        return sid, info.get("path") or info.get("filename")
    if len(sessions) > 1:
        die("several notebooks are open; choose one with --file:\n        "
            + "\n        ".join(f"{sid}  {s.get('path')}"
                                for sid, s in sessions.items()))
    sid, info = next(iter(sessions.items()))
    return sid, info.get("path") or info.get("filename")


def run_in_kernel(args, code: str, capture: bool) -> str:
    cmd = [str(args.execute_code), "--url", args.url]
    if args.session_selector:
        cmd += args.session_selector
    cmd.append("-")
    env = dict(os.environ, MARIMO_TOKEN=args.token)  # never on argv
    proc = subprocess.run(
        cmd, input=code, text=True, env=env, check=False,
        stdout=subprocess.PIPE if capture else None,
    )
    if proc.returncode != 0:
        die("the kernel rejected the change (see the traceback above). "
            "Nothing was applied: cm discards the whole batch on error.")
    return proc.stdout or ""


# ------------------------------------------------------------------ main ---


def main() -> int:
    p = argparse.ArgumentParser(
        prog="push_notebook_to_molab.sh",
        description="Push a local marimo notebook into a live molab kernel.",
    )
    p.add_argument("--url", default=os.environ.get("SERA_MOLAB_URL", ""),
                   help="molab sandbox base URL (or SERA_MOLAB_URL). An "
                        "?access_token= on it is used as the token.")
    p.add_argument("--token", default="",
                   help="access token; prefer the MARIMO_TOKEN env var, which "
                        "keeps it out of process listings")
    p.add_argument("--notebook", type=Path, default=DEFAULT_NOTEBOOK,
                   help=f"notebook to push (default {DEFAULT_NOTEBOOK.name})")
    p.add_argument("--file", dest="target_file", default=None,
                   help="path of the sandbox notebook to target, when several "
                        "are open")
    p.add_argument("--no-run", dest="run", action="store_false",
                   help="push the cells but do not execute them")
    p.add_argument("--no-deps", dest="deps", action="store_false",
                   help="skip installing the notebook's PEP 723 dependencies")
    p.add_argument("--no-app-config", dest="app_config", action="store_false",
                   help="leave the sandbox app title and width alone")
    p.add_argument("--show-code", action="store_true",
                   help="ignore hide_code and leave every editor expanded")
    p.add_argument("--dry-run", action="store_true",
                   help="print the plan and the generated kernel script; "
                        "touch nothing")
    p.add_argument("--execute-code", type=Path, default=DEFAULT_EXECUTE_CODE,
                   help="path to the marimo-pair execute-code.sh")
    args = p.parse_args()

    # ---- inputs -----------------------------------------------------------
    if not args.url:
        die("no --url. Pass the molab sandbox URL, or set SERA_MOLAB_URL.")
    args.url, url_token = split_token(args.url)
    args.token = args.token or os.environ.get("MARIMO_TOKEN", "") or url_token or ""
    if not args.token:
        die("no token. Set MARIMO_TOKEN, pass --token, or use the molab URL "
            "with ?access_token= on it.")
    if not args.notebook.is_file():
        die(f"{args.notebook} does not exist")
    if not args.dry_run and not os.access(args.execute_code, os.X_OK):
        die(f"{args.execute_code} is missing or not executable "
            "(it ships with the marimo-pair skill)")
    args.session_selector = []

    step(f"Read {args.notebook.relative_to(ROOT) if args.notebook.is_relative_to(ROOT) else args.notebook}")
    cells, app_options = parse_cells(args.notebook)
    if args.show_code:
        for c in cells:
            c["config"]["hide_code"] = False
    packages = pep723_dependencies(args.notebook) if args.deps else []
    digest = hashlib.sha256(args.notebook.read_bytes()).hexdigest()[:12]
    ok(f"{len(cells)} cell(s), {sum(len(c['code'].splitlines()) for c in cells)} "
       f"lines of cell code, sha256:{digest}")
    if packages:
        note(f"PEP 723 dependencies to install: {', '.join(packages)}")
    if app_options:
        note(f"app config: {app_options}")

    payload = {
        "source": args.notebook.name,
        "sha256": digest,
        "cells": cells,
        "packages": packages,
        "run": args.run,
    }
    push_code = render(PUSH_SCRIPT, payload)

    if args.dry_run:
        step("Dry run")
        out = Path(os.environ.get("TMPDIR", "/tmp")) / "sera_push_notebook.py"
        out.write_text(push_code, encoding="utf-8")
        ok(f"kernel script written to {out} ({len(push_code)} bytes); nothing sent")
        note(f"target would be {args.url} (token {len(args.token)} chars, not shown)")
        return 0

    # ---- target -----------------------------------------------------------
    step("Find the live kernel")
    health = http(args.url, "/health", args.token)
    if isinstance(health, dict) and health.get("status") not in (None, "healthy"):
        warn(f"/health says {health}")
    version = http(args.url, "/api/version", args.token)
    sessions = http(args.url, "/api/sessions", args.token)
    if not isinstance(sessions, dict):
        die(f"/api/sessions returned {type(sessions).__name__}, not a mapping")
    session_id, session_path = pick_session(sessions, args.target_file)
    # A file key survives a browser reconnect; a session id does not.
    args.session_selector = (["--file", session_path] if session_path
                             else ["--session", session_id])
    ok(f"marimo {str(version).strip()} at {args.url}")
    ok(f"session {session_id}  ->  {session_path or '(unnamed)'}")
    if not session_path:
        warn("the sandbox notebook is unnamed, so marimo cannot autosave the "
             "push to disk. It will live in the kernel only.")

    # ---- required first kernel command (marimo-pair) ----------------------
    # The skill's contract: `help(cm)` must succeed before any other cm call,
    # because it is what reports the kernel's installed capabilities.
    step("Probe code mode")
    probe = run_in_kernel(args, "import marimo._code_mode as cm; help(cm)", True)
    if "get_context" not in probe:
        die("the kernel answered, but marimo._code_mode looks wrong:\n"
            + probe[:400])
    caps = re.findall(r"^    (\w+)    import ", probe, re.MULTILINE)
    ok("marimo._code_mode reachable in the kernel scratchpad"
       + (f" (capabilities: {', '.join(caps)})" if caps else ""))

    # ---- app config, before the cells -------------------------------------
    # save_app_config bumps the autosave generation, which drops an in-flight
    # code-mode autosave. Doing it first keeps the cell push as the last write.
    if args.app_config and app_options:
        step("Apply app config")
        http(args.url, "/api/kernel/save_app_config", args.token,
             {"config": app_options})
        ok(f"set {', '.join(f'{k}={v!r}' for k, v in app_options.items())}")

    # ---- the push ---------------------------------------------------------
    step("Push cells" + (" and run them" if args.run else ""))
    if packages:
        note(f"installing {', '.join(packages)} first; the install log "
             "appears in the browser, only the result comes back here")
    run_in_kernel(args, push_code, False)
    ok("code mode applied the batch")

    # ---- verify -----------------------------------------------------------
    step("Verify")
    raw = run_in_kernel(
        args, render(VERIFY_SCRIPT, len(cells)), True
    )
    match = re.search(rf"{MARK}JSON (\{{.*\}})", raw)
    if not match:
        warn("could not read the notebook back; check it in the browser")
        return 0
    live = json.loads(match.group(1))["live"]

    def norm(s: str) -> str:
        return "\n".join(l.rstrip() for l in s.strip().splitlines() if l.strip())

    if len(live) != len(cells):
        die(f"the sandbox has {len(live)} cell(s), expected {len(cells)}")
    exact, whitespace, differs = 0, 0, []
    for i, (want, got) in enumerate(zip(cells, live)):
        if hashlib.sha256(want["code"].encode()).hexdigest() == got["sha"]:
            exact += 1
        elif hashlib.sha256(norm(want["code"]).encode()).hexdigest() == got["norm"]:
            whitespace += 1
        else:
            differs.append(f"{i} ({got['id']})")
    ok(f"{len(live)} cell(s) in the sandbox, in order; {exact} byte-identical"
       + (f", {whitespace} whitespace-only differences" if whitespace else ""))
    if differs:
        # marimo reformats on save (format_on_save, and codegen re-indents
        # triple-quoted mo.md blocks). Cosmetic, and the next push converges.
        warn(f"{len(differs)} cell(s) came back reformatted: {', '.join(differs)}")
        note("that is marimo's own formatting, not a failed write; the cells "
             "are in the notebook")

    print(f"\n{GREEN}{BOLD}NOTEBOOK PUSHED{OFF}  open {args.url}")
    if not args.run:
        note("cells were not executed; press Run in the browser")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
