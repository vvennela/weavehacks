# Repeatability inventory: strongest Sera source

The exact source under review is `libxsmm-n512-panel32-one-streaming-region`, SHA-256 `eb091b1eca431f0760d0d61e4c0c6e748c1a9e34466a87ac15ad9cb238b5aecf`. It uses a 32-row packed-A panel, one 64 KiB scratch allocation, one SME streaming region, and sixteen row bands. The source was measured in two phases with paired controls: three pairs on Battery Low Power and ten pairs on AC Automatic. The 1701.65 GFLOP/s result is one AC sample, not repeatable evidence of a gain.

Each score below is one frozen-hill report using its best-of-three timing. Candidate and control values are listed in their recorded pair order; deltas are candidate minus control. The score lists are not raw individual timed calls.

## Battery Low Power: three paired reports

Recorded in `evidence/cpu-libxsmm-editable-panel-2026-09-25/search/trial-001/source/kernel.c`, exact hash above. Host capture at phase start: Apple M4 Pro, drawing from Battery Power at 19% and discharging; Battery `powermode=1`, AC `powermode=0`. Profile records CPU, arm64, SME/SME2, NEON/SIMD, single-thread capability, 16 streaming FP32 lanes, P-core L1D 128 KiB, E-core L1D 64 KiB, 128-byte cache lines.

| Pair | Candidate | Paired control | Delta | Delta % |
|---:|---:|---:|---:|---:|
| 1 | 998.365 | 964.149 | +34.216 | +3.55% |
| 2 | 1097.523 | 1110.770 | −13.248 | −1.19% |
| 3 | 1031.452 | 964.007 | +67.445 | +7.00% |

Candidate range was 998.365–1097.523, median 1031.452 GFLOP/s. Controls ranged 964.007–1110.770, median 964.149. The candidate won 2/3 pairs and exceeded its paired control by more than 5% once. The ranges overlap, so the source did not pass the unchanged separated-range promotion gate. This phase used three repeats, not the later ten-repeat series.

## AC Automatic: ten paired reports

Recorded in `evidence/cpu-libxsmm-ten-run-ac-2026-09-25/search/trial-001/source/kernel.c`, exact hash above. Host capture at phase start: Apple M4 Pro, drawing from AC Power; profile records AC Automatic. The unchanged settings capture shows AC `powermode=0`, Battery `powermode=1`; the replay README reports settings remained unchanged. It used the same n=512, tolerance 0.002, Apple clang 21.0.0, flags `-O3 -march=native -ffast-math -shared -fPIC -lm`, arm64/Darwin, single-thread capability, and same comparison tree/config as the Battery Low Power phase.

| Pair | Candidate | Paired control | Delta | Delta % |
|---:|---:|---:|---:|---:|
| 1 | 1293.148 | 1673.371 | −380.223 | −22.72% |
| 2 | 1251.202 | 1553.149 | −301.947 | −19.44% |
| 3 | 1456.577 | 1260.752 | +195.825 | +15.53% |
| 4 | 1570.184 | 1387.557 | +182.626 | +13.16% |
| 5 | 1684.301 | 1414.985 | +269.316 | +19.03% |
| 6 | 1457.241 | 1629.350 | −172.109 | −10.56% |
| 7 | 1679.906 | 1539.786 | +140.120 | +9.10% |
| 8 | 1352.892 | 1385.173 | −32.281 | −2.33% |
| 9 | 1701.651 | 1225.263 | +476.388 | +38.88% |
| 10 | 1528.824 | 1640.132 | −111.308 | −6.79% |

Candidate range was 1251.202–1701.651, median 1493.032 GFLOP/s. Controls ranged 1225.263–1673.371, median 1477.385. It won 5/10 pairs; the mean paired change was +26.641 GFLOP/s and median paired change +53.919, with paired deltas from −380.223 to +476.388. Candidate/control ranges overlap. The existing 5% separated-range gate failed. The peak 1701.651 exceeded the fresh AC baseline peak 1685.623 in 1/10 reports and the saved Battery Automatic historical peak 1668.596 in 3/10. Do not pool those power modes or treat a single maximum as consistent performance.

## Other records and limits

- `evidence/cpu-libxsmm-editable-panel-2026-09-25/README.md` and `evidence/cpu-libxsmm-ten-run-ac-2026-09-25/README.md` summarize the same reports; they are not additional runs. The AC replay independently verifies report signatures, source hashes, identities, score vectors and paired gates.
- `evidence/cpu-libxsmm-editable-panel-automatic-2026-09-25/` contains a prepared replay driver and preflight tests, but no official result set; it adds no measurement.
- `evidence/cpu-libxsmm-dataflow-board-2026-09-25/` was interrupted with `KeyboardInterrupt`/SIGINT (exit 130) before any candidate implementation. Its baseline source hash is `8bb0113e377808a841819354296fa0ef02ff49e4188d57a091afc6463fc0ca18`, not the exact hash inventoried here. Its baseline-only scores are not additional measurements of this source. The phase recorded zero implementations.

No exact-hash candidate result was found beyond the three Battery Low Power pairs and ten AC Automatic pairs listed above. Neither series establishes a promotion or a repeatable win over its paired control distribution.


## Fresh ten-pair Battery Low Power replay

`evidence/cpu-best-kernel-repeatability-2026-09-25` remeasured the same eb091b1e
candidate and04fc3ff control with unchanged settings. All31 reports and93raw timings
verified. Candidate714.79–1108.66GFLOP/s, median1076.95; paired controls933.42–1094.73,
median1056.19. Candidate won7/10pairs and exceeded the fresh initial1100.52peak3/10times.
It failed the unchanged5%separated-range gate and was not promoted. Final1034.27
confirms only the imported baseline. No source changed. Total exact-source paired
evidence is now3priorLowPower +10AC +10freshLowPower; keep these blocks separate.
The per-report median slowest/fastest raw timing ratio is1.33x for candidate and1.31x
for controls. The causes of this variation remain unmeasured.
