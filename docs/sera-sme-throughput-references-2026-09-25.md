# Published SME throughput references for the 2 TFLOP/s target

## Finding

I found no primary published single-thread FP32 SME/FMOPA peak measurement for an Apple M4 Pro. The strongest directly relevant source is the Hello SME study on a 2024 11-inch iPad Pro with the base M4, not an M4 Pro. Its measured single performance-core FP32 FMOPA peak is 2,008 GFLOP/s using all four ZA tiles. Its best measured square GEMM result is 1,825.1 GFLOP/s at 512³, reported as 91% of that peak. These are useful reference points, not M4 Pro measurements.

A 2,000 GFLOP/s GEMM target is 99.6% of the base-M4 measured microbenchmark rate (within 0.4% of that measurement) and 9.6% above the paper's best measured GEMM result. That arithmetic does not establish that the target is achievable on M4 Pro. The published GEMM implementation remained below the measured microbenchmark rate.

The current local four-tile calibration result supplied for this review is 1,327.4 GFLOP/s median, measured under Battery Low Power. It is 66.1% of 2,008 GFLOP/s, but it is not a normal-power M4 Pro peak measurement and cannot support a hardware-ceiling estimate. Do not extrapolate from it without a fresh controlled calibration.

## Evidence and limits

- The [Hello SME microbenchmark report](https://scalable.uni-jena.de/opt/sme/micro.html) identifies its device as an 11-inch iPad Pro M4 and reports single-core four-tile FP32 FMOPA at 2,008 GFLOP/s; its multi-core results reach about 2,341 GFLOP/s only when using both shared SME units. The latter is not a single-thread result and must not be presented as one.
- The [Hello SME GEMM report](https://scalable.uni-jena.de/opt/sme/gemm.html) reports 1,825.1 GFLOP/s for M=N=K=512 on an M4 performance core. It describes this as 91% of the measured 2,008 GFLOP/s peak. This is the closest published application-kernel comparison for the 2,000 target.
- The [Hello SME paper](https://arxiv.org/abs/2409.18779) states that all experiments used a 2024 11-inch iPad Pro with an M4, four performance cores, and six efficiency cores. It reports more than 2.3 FP32 TFLOP/s for multi-core SME, not for an M4 Pro or a single core.
- A [personal M4 Pro CPU-baseline report](https://www.saisasank.com/blog/machine-baseline-for-cpu-performance-engineering) reports a single-P-core FP32 Neon ceiling and measured Neon throughput, but it does not measure SME. It cannot fill the missing M4 Pro SME datum.

The M4 paper's 2,008 GFLOP/s is a compute microbenchmark peak, not a guarantee for a GEMM benchmark. Its 1,825.1 GFLOP/s GEMM point is an M4 result, not a measured M4 Pro result. The sources do not justify scaling either value by M4 Pro core count or by CPU/GPU specifications.

## Use for Sera

Use 2,008 GFLOP/s as a published base-M4 single-P-core SME reference and 1,825.1 GFLOP/s as a published base-M4 512³ GEMM reference. Label both by device and workload. Report any M4 Pro result as a local measurement with its power mode and thermal state; do not call it published peak unless a directly comparable M4 Pro SME source is found.
