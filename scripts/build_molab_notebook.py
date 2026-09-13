"""Generate notebooks/molab_lab.py with the lab specs embedded.

This notebook targets molab, where there is a real RTX Pro 6000 Blackwell and a
real vLLM. It installs Sera from the public repo rather than bundling source, so
it gets the full package including the vLLM runner.

The specs are embedded because pip installing the package does not bring
specs/*.yaml with it, and a notebook that fetched them at run time would have one
more thing to fail on stage.

    python scripts/build_molab_notebook.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "scripts" / "molab_notebook_template.py"
SPECS = ["lab_qwen3_8b", "lab_deepseek_r1_14b", "lab_moonlight_16b"]


def main() -> int:
    embedded = {name: (ROOT / "specs" / f"{name}.yaml").read_text() for name in SPECS}
    for name, text in embedded.items():
        if '"""' in text:
            raise SystemExit(f"{name}.yaml contains a triple quote and would break the literal")
    block = "\n".join(
        f'    SPECS["{name}"] = r"""{text}"""\n' for name, text in embedded.items()
    )
    source = TEMPLATE.read_text().replace("    __EMBEDDED_SPECS__\n", block)
    target = ROOT / "notebooks" / "molab_lab.py"
    target.write_text(source)
    print(f"wrote {target.relative_to(ROOT)}  ({target.stat().st_size:,} bytes, "
          f"{len(embedded)} specs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
