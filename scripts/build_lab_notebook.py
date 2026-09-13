"""Generate notebooks/lab.py with Sera's source embedded.

The notebook runs the real optimization loop in the browser under Pyodide, so it
carries the package itself rather than a recording of its output. Sera is pure
Python over numpy and pyyaml, and the only module that touches subprocess or
urllib is the vLLM runner, which is excluded here — nothing in the Phase 1 path
imports it.

    PYTHONPATH=src python scripts/build_lab_notebook.py
"""
import base64
import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "scripts" / "lab_notebook_template.py"


def bundle() -> str:
    """Sera's source plus the lab specs, as one base64 zip."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted((ROOT / "src" / "sera_loop").rglob("*.py")):
            # The vLLM runner needs subprocess and urllib, neither of which a
            # browser can offer. Nothing in the Phase 1 path imports it.
            if "vllm" in path.name or "__pycache__" in str(path):
                continue
            z.write(path, path.relative_to(ROOT / "src").as_posix())
        for path in sorted((ROOT / "specs").glob("lab_*.yaml")):
            z.write(path, path.relative_to(ROOT).as_posix())
    return base64.b64encode(buf.getvalue()).decode()


def main() -> int:
    blob = bundle()
    source = TEMPLATE.read_text().replace("__SERA_BUNDLE__", blob)
    target = ROOT / "notebooks" / "lab.py"
    target.write_text(source)
    print(f"wrote {target.relative_to(ROOT)}  ({target.stat().st_size:,} bytes, "
          f"bundle {len(blob):,} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
