# Approved 24 GiB capacity calibration

The 3 GiB Qwen + 17 GiB GLM pair passes both **isolated** references. Joint
placement is not established. Molab's GPU process accounting blocks verification
of separate live service memory caps.

The physical card has 97,887 MiB. The declared 24 GiB budget represents a smaller
card's memory capacity, not its speed. Each approved allocation reserves 1 GiB
internally for process overhead; the remaining bytes set the vLLM memory fraction.
The total allocations leave the required 10% shared reserve.

| Isolated service | Hard allocation | Sampled peak | Task checks | Timed checks | Worst-load p95 | Joint p95 limit |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen3-0.6B, BF16 weights/KV | 3 GiB | 2,803 MiB | 8/8 | 96/96 | 136.49 ms | 150.14 ms |
| GLM-4-9B, FP8 weights/BF16 KV | 17 GiB | 17,105 MiB | 8/8 | 96/96 | 170.85 ms | 187.93 ms |

Both use the unchanged eight questions, 99% quality floor, zero errors, requested
output-type schemas, and concurrency 1/2/4/8. Joint limits apply the approved 10%
slowdown rule to each matching isolated reference. No joint latency was measured.
Startup was 46.05 s for Qwen and 65.07 s for GLM, separate from request latency.
Both servers closed and device memory returned to zero.

The 2.5 GiB Qwen + 15 GiB GLM plan was rejected before GPU startup: the declared
Qwen component estimate exceeds 2.5 GiB. Both matching all-BF16 alternatives were
also rejected by estimate. These are not measured failures, and they provide no
measured BF16 latency or memory-savings comparison. All four plans are preserved.

## Accounting blocker

[process-accounting.json](process-accounting.json) records the running GLM API
process 58350 and engine 58452. Both nvidia-smi and direct NVML instead attribute
GPU memory to PID 1. The gVisor sandbox exposes no usable namespace translation.
Total device memory is visible; separate service memory ownership is not.

No joint search or extra GPU startup was attempted after discovering this limit.
Sera must not infer per-service use by subtracting old isolated measurements or
mark unresolved GPU memory as safely released. A supported accounting source or
an explicitly changed total-device-only contract is needed for the next step.

## Evidence and repeat audit

Calibration ran repository source `4f47448` with an explicit source import check.
The pinned GLM files were downloaded first; preparation is saved separately.
[manifest.json](manifest.json) and [registration.json](registration.json) were
committed before measurement. The raw results, metrics, server logs, and exported
Weave calls are saved here. The downloaded archive SHA-256 was
`bc78c4b48048c366c14abb5d20546f9b7a1a6609356747768706e2ed00f555b1`.

```sh
uv run --frozen python evidence/capacity-calibration-v1/audit.py
```

The audit recomputes gates from raw requests, checks exact configuration/workload
binding, and matches all 272 saved request outputs to the Weave export. There are
284 completed trace calls across the passing reference and three fit rejections,
with no call errors. No hosted investigator was called during calibration.

[Open the isolated reference trace](https://wandb.ai/vvennela-n-a/wandb_agent_default_project/r/call/01a09bc3-5455-7e16-9529-8d561889ebf4).

This is an artifact consistency audit, not independent proof of execution or
completed two-model acceptance. The original failed quality profiles are unchanged.
