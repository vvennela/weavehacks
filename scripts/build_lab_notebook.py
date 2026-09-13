"""Generate notebooks/lab.py with the captured runs embedded.

The notebook is generated rather than hand-maintained for one reason: it carries
its run data inline so the WASM export is self-contained, and nobody should have
to hand-edit 22KB of JSON inside a source file.

    PYTHONPATH=src python scripts/build_lab_data.py      # capture -> lab_runs.json
    PYTHONPATH=src python scripts/build_lab_notebook.py  # lab_runs.json -> lab.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "scripts" / "lab_notebook_template.py"


def main() -> int:
    data = json.loads((ROOT / "notebooks" / "lab_runs.json").read_text())
    # separators keep the literal tight; the notebook is read in a browser, not a diff.
    blob = json.dumps(data, separators=(",", ":"), allow_nan=False)
    if '"""' in blob:
        raise SystemExit("run data contains a triple quote and would break the literal")
    source = TEMPLATE.read_text().replace("__LAB_DATA__", blob)
    target = ROOT / "notebooks" / "lab.py"
    target.write_text(source)
    print(f"wrote {target.relative_to(ROOT)}  ({target.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
