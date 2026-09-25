# Exact best-kernel repeatability

Status: completed on Battery Low Power; candidate not promoted. The final check confirmed only the imported control.

The user redirected work to repeatability of Sera's strongest existing kernel.
This replays only source `eb091b1eca431f0760d0d61e4c0c6e748c1a9e34466a87ac15ad9cb238b5aecf`
against its original imported control
`04fc3ff86669c2ca123e3b390b662637cd69c21f3d63fa26f7a5f0f0a882317c`.
No new algorithm, source modification, specialist selection or proposal is included.
One Astra Codex review adjudicates fresh evidence under the existing gates.

Measure on the current power source/settings without changing them. Keep the frozen
hill/compiler/thread/tolerance/timing rules; 48 public correctness cases; 10 baseline
reports; 10 alternating candidate/control pairs; and the held-out check. Every raw
three-call timing set is preserved in its signed report. Do not pool AC and battery
or change the official best-of-three score. Existing caps remain6 attempts,108 calls,
180seconds per agent call,1800seconds per block; replay stops after this one source.

The previous1701.65 GFLOP/s sample is evidence of one winning report, not a consistent
speedup. The priorAC series had5/10pairedwins and1/10above its fresh initial baseline
peak. Report the full range, medians, paired outcomes, historical and fresh same-mode
peaks, and within-report raw timings. The5% separated-range gate remains unchanged.
Preflight/source-integrity and kernel-search checks pass23 tests.


## Verified replay

All31 signed reports and93 raw timed calls verified. Both exact sources passed48
correctness cases. Power source/settings remained unchanged. One Astra review call
rejected the candidate; there were no new implementations or proposal calls.

| Source | Minimum | Median | Maximum GFLOP/s |
| --- | ---: | ---: | ---: |
| Imported baseline, initial10 | 917.47 | 1073.20 | 1100.52 |
| Exact best Sera kernel | 714.79 | 1076.95 | 1108.66 |
| Its10 paired controls | 933.42 | 1056.19 | 1094.73 |

The candidate won7/10pairs and exceeded the fresh initial baseline peak3/10times.
It exceeded the saved Automatic/AC peaks0/10times. Its minimum is below the required
1149.46GFLOP/s promotion threshold. Final1034.27belongs to the unchanged imported
baseline, not a Sera gain. The ten-run goal remains unmet.

Within-report median slowest/fastest timing ratios are1.33x for the candidate and
1.31x for paired controls. The fastest call was number1/2/3 in1/5/4candidate reports
and0/2/8control reports. This records variation and call position without attributing
a cause. `verification.json` retains every raw triplet and signature/source identity.
Scores are separated from the earlierAC measurements of the identical kernel.
