# Independent audit: local SME calibration

The arithmetic is internally consistent. Each counted loop iteration contains
64 `FMOPA` instructions. With 16 FP32 lanes, each outer product performs
`2 × 16 × 16 = 512` nominal FLOPs, so an invocation performs
`200,000 × 64 × 512 = 6,553,600,000` FLOPs. One, two, and four ZA tiles split
those same 64 instructions evenly; their exact expected output accumulations
are respectively 12.8M, 6.4M, and 3.2M per output element, all exactly
representable as FP32 integers. The saved disassembly and output checks agree
with this accounting. `2 × 512³ = 268,435,456` is the standard classical
GEMM operation count used by the conditional estimates.

The ABI check was expanded to call all three entries (one, two, and four
tiles). Its first parameterized run exposed a real harness bug: the helper
always called `_sera_peak_4`, so the two-tile case failed. The helper now uses
`blr x2` to call the selected entry, and the ABI suite passes 12/12 cases. The
checks assert returned values and output extent, so they verify the selected
entry's result as well as register preservation. `probe.S` and `results.json`
are unchanged; this corrects test coverage without changing the measured
probe or its results.

The ten rotated rounds report medians of 331.79, 663.92, and 1327.43 GFLOP/s
for one, two, and four tiles. This supports the narrow observation that
interleaving independent ZA accumulators raises throughput in this local
compute-only probe. The timer includes the function's SME entry/exit, register
saves/restores, and final stores. The probe uses register-resident all-one
inputs and has no GEMM input loads, packing, allocation, or output traffic.
It is therefore a measured probe rate, not a physical peak, an Automatic-mode
rate, or a prediction that GEMM will attain the same rate.

`estimates.py` is correctly conditional: 10/20/40 microseconds are assumed,
non-overlapped costs, not measured components. The 2008 GFLOP/s reference is
labelled as a published base-M4 result; it is a different machine/reference
from this M4 Pro battery run. Keep its projections separate from local
measurements. The file provides no evidence for the local M4 Pro's full-power
compute rate or full GEMM headroom.

Power records bracket each round and all 20 snapshots show battery input,
battery `powermode 1`, unchanged settings, and no thermal/performance warning.
There are no requested affinity or QoS changes. The records do not capture a
direct Low Power Mode API value, CPU frequency, temperature, or competing
process load; bracketing also cannot rule out a transient mode/load change
between snapshots. The saved evidence supports the recorded battery/settings
condition and the reported samples, but it does not establish why the samples
have their measured values or a ceiling. No GEMM source, hill, score, or
promotion gate is changed by this calibration.
