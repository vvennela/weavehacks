# Editable panel primitive for the selected smaller-buffer work

The last 15-specialist board selected a 64 KiB packed-A layout with one SME entry, but its implementation timed out. This preparation exposes the existing 32-row helper as editable assembly. It changes instruction spelling and local branch labels only. Sera still owns kernel changes and experiment ranking.

`prepare.py` validates the disassembly against the pinned exported bytes, replaces direct branch addresses with local labels, compiles the helper and both baselines, and compares the actual Mach-O text sections including padding. The 1,536-byte helper and the entire 7,640-byte baseline text section are byte-identical. The helper has no relocations. Both complete license notices are preserved; the baseline wrapper still calls only the original full512 kernel. See `byte-verification.json` for hashes.

Four transformation tests and twelve panel ABI tests passed. The exact new baseline source passed the standard48 deterministic GEMM cases. No performance result is claimed for this mechanical preparation.

The next bounded run supplies six prior phases and the new Luna feasibility review to15Luna specialists. They rank the experiments; Astra-high implements and reviews them. Limits remain six attempts,108calls,180seconds per call,1800seconds overall. The frozen hill, flags, FP32 tolerance, full-call timing, three paired repeats,5% gate,heldout result and1,800target remain unchanged. Current power source/settings must stay fixed; this driver changes none. Old scores are context only. New source identity requires fresh controls even though compiled text is identical.

```sh
PYTHONPATH=. /tmp/sera-audit-venv/bin/python evidence/cpu-libxsmm-editable-panel-2026-09-25/prepare.py
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -m pytest -q evidence/cpu-libxsmm-editable-panel-2026-09-25/test_translation.py evidence/cpu-libxsmm-editable-panel-2026-09-25/test_panel_editable.py
PYTHONPATH=. /tmp/sera-audit-venv/bin/python -u evidence/cpu-libxsmm-editable-panel-2026-09-25/run.py
```
