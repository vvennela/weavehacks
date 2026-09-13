"""The notebook must stay on the public API, and must actually run.

Two different failures are guarded here. The first is silent drift: someone adds
`from sera_loop.phase2 import Phase2` to get at a number quickly, and the notebook
then breaks whenever the backend is refactored. The second is the demo dying on
stage, which only an execution test can catch — importing the file proves
nothing, because marimo cell bodies do not run at import time.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "sera_demo.py"

# Product-side modules the notebook is allowed to reach for. Everything else
# under `sera.` is backend internals and is off limits by the working agreement.
ALLOWED_SERA_SUBMODULES = {"fixtures", "report"}

BACKEND_INTERNALS = {
    "arbiter",
    "baseline",
    "config",
    "ledger",
    "loadgen",
    "phase1",
    "phase2",
    "quality",
    "reduction",
    "runner",
    "spec",
    "specialists",
    "tracing",
    "validator",
}


def imported_modules(path: Path) -> set[str]:
    """Every module name the file imports, dotted form preserved."""
    tree = ast.parse(path.read_text(), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            for alias in node.names:
                found.add(f"{node.module}.{alias.name}")
    return found


def test_notebook_exists():
    assert NOTEBOOK.is_file(), f"{NOTEBOOK} is the demo notebook and must exist"


def test_notebook_imports_no_backend_internals():
    """The integration boundary, enforced rather than merely agreed."""
    offenders = []
    for module in imported_modules(NOTEBOOK):
        if not module.startswith("sera"):
            continue
        parts = module.split(".")
        if len(parts) < 2:
            continue
        submodule = parts[1]
        if submodule in BACKEND_INTERNALS:
            offenders.append(module)
    assert not offenders, (
        f"notebook reaches into backend internals: {sorted(offenders)}. "
        "Use the public API on `sera` instead."
    )


def test_notebook_only_uses_approved_sera_submodules():
    for module in imported_modules(NOTEBOOK):
        parts = module.split(".")
        if parts[0] != "sera" or len(parts) < 2:
            continue
        # `from sera_loop import fixtures` yields both "sera" and "sera_loop.fixtures".
        if parts[1] in ALLOWED_SERA_SUBMODULES:
            continue
        # Names imported from the top-level package are public API.
        if len(parts) == 2 and parts[1][0].isupper():
            continue
        assert parts[1] in ALLOWED_SERA_SUBMODULES, (
            f"{module} is not part of the public product surface"
        )


def test_notebook_has_a_single_switch_point():
    """B2's win condition: swapping to the real backend touches one place."""
    text = NOTEBOOK.read_text()
    assert text.count("THE SWITCH") == 1, "the construction point must be marked exactly once"
    assert "sera_loop.optimize(" in text, "the notebook must call the public entry point"


def test_notebook_executes_and_renders(tmp_path):
    """Render the notebook end to end and confirm the real content appears.

    This is the closest thing to a rehearsal that fits in a test suite.

    PYTHONPATH is set explicitly rather than relying on an editable install: the
    install is easy to clobber, and a demo that only works on one machine's
    site-packages is not a demo that works.
    """
    pytest.importorskip("marimo")
    repo = NOTEBOOK.parent.parent
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo / "src"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)

    out = tmp_path / "rendered.html"
    proc = subprocess.run(
        [sys.executable, "-m", "marimo", "export", "html", str(NOTEBOOK), "-o", str(out)],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=repo,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, f"marimo export failed:\n{proc.stdout}\n{proc.stderr}"
    assert out.is_file(), "export produced no file"

    html = out.read_text()
    # Content that only exists if the cells actually ran and the fixture rendered.
    for marker in (
        "Sera found a faster",
        "Recommended for",
        "max_num_seqs",
        "not verified",
    ):
        assert marker in html, f"rendered notebook is missing {marker!r}"
