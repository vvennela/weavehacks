# Local SME compute-only calibration and estimates

This is a separate diagnostic, not GEMM or an official hill score. It implements
the accumulator-independence technique described in the [Jena microbenchmarks](https://scalable.uni-jena.de/opt/sme/micro.html).
`probe.S` is an original local implementation; no unlicensed upstream assembly was
copied. It uses64 FP32 FMOPA instructions per counted iteration, one/two/four ZA
tiles, fixed all-one inputs, zeroed accumulators and one SME region per invocation.

Each invocation performs200,000 iterations. Ten rotated-order rounds use a fixed
10,000-iteration warmup per variant. The returned streaming width is16FP32 lanes;
each FMOPA counts512FLOPs, giving6,553,600,000FLOPs per measured invocation. Output
rows are checked against exact representable integer accumulation results. Ten
native tests cover0/1/17iterations, guards and callee-saved vector registers. The
ABI test first exposed missing d8–d15 preservation; the corrected implementation
saves/restores them across streaming transitions, and all10 tests pass.

Current measurement: Apple M4 Pro, Battery Low Power, no affinity, QoS, power or
thread-policy changes. Source/compiler hashes, disassembly, every time sample and
before/after power records are saved. One host thread, no matrix loads or packing.

| Independent tiles | Min | Median | Max GFLOP/s |
| --- | ---: | ---: | ---: |
| 1 | 325.74 | 331.79 | 333.34 |
| 2 | 661.03 | 663.92 | 667.40 |
| 4 | 1294.52 | 1327.43 | 1336.08 |

The four-tile technique works; the best existing Sera kernel already uses it.
These results do not establish a physical ceiling or an Automatic-mode rate.
The full GEMM also loads operands, packs panels, and stores output. Calibration
code is never submitted to the matrix-multiplication hill.

## Conditional estimates

`estimates.py` computes scenarios using268,435,456nominalFLOPs for512-cubed GEMM.
It assumes the chosen compute rate plus10/20/40microseconds of additional,
non-overlapped cost. Those costs are assumptions, not measured components.

| Compute reference | +10 us | +20 us | +40 us |
| --- | ---: | ---: | ---: |
| Local Low Power median1327.43 | 1264.88 | 1207.96 | 1108.22 |
| Published base-M4 compute2008 | 1868.25 | 1746.68 | 1545.55 |

At2008GFLOP/s compute throughput, a2000GFLOP/s complete call allows only0.535us
of extra non-overlapped time;1780allows17.123us. This explains why a compute-only
peak is not a full-kernel forecast. A machine-local full-power calibration is still
needed before estimating this M4 Pro's full-power headroom. The baseline benchmark,
tolerance, scoring and promotion gates remain unchanged.
