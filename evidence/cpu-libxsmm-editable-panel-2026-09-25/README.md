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

## Completed Low Power measurements

The byte-identical preparation made the selected one-entry64KiB layout implementable within the unchanged180-second call cap. Astra produced a complete candidate; it passed48 correctness cases and fresh paired scoring. It did not pass promotion. This is implementation progress, not a demonstrated speedup.

Two complete15-specialist boards used72 model calls and six attempts. Four distinct kernels were measured; two first-board aliases abstained as duplicates. Both rankings and all28 signed reports were independently verified, along with source hashes, correctness records, unchanged power/settings, and promotion gates.

| Candidate | GFLOP/s | Paired controls GFLOP/s |
| --- | --- | --- |
| libxsmm-n512-panel32-one-streaming-region | 998.37, 1097.52, 1031.45 | 964.15, 1110.77, 964.01 |
| libxsmm-full512-reserve-scratch-once | 1086.23, 1075.00, 816.22 | 1051.48, 1072.13, 1090.65 |
| libxsmm-full512-w32-k-loop-counters | 971.56, 1035.77, 1085.68 | 1062.41, 1068.04, 856.59 |
| libxsmm-full512-fmopa-order-0132 | 1070.71, 1028.00, 1060.31 | 1090.65, 1044.33, 1056.66 |

None passed promotion. The unchanged baseline scored1,049.43,1,045.17,1,031.29 GFLOP/s and its final held-out score was1,094.73. The baseline was retained; target unmet. The four new kernels still need separate AC/Automatic measurements. No power settings changed during this block.

The [duplicate-board audit](duplicate-board-audit-luna.md) documents two wasted implementation slots and proposes grouping repeated source changes before ranking. This is a proposal for user adjudication; no advice schema, ranking architecture, or budget was changed. The feasibility note also records a corrected pointer-rewind description. Live prompts preserve the original frozen text in controls.json; the corrected note does not retroactively change them.

An exact-source Automatic replay is prepared in `../cpu-libxsmm-editable-panel-automatic-2026-09-25`. It is not started: the user was asked for a new temporary mode-change authorization, because the previous one-block approval was already used and restored.
