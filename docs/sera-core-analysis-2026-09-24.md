# Sera as an engineer-facing optimizer

Date: 2026-09-24. Scope: optimization, execution, evaluation, and developer integration. Frontend and notebooks are excluded.

## Conclusion

The product should be an optimization library that owns a measured experiment loop and returns a usable, verified artifact. It should accept an engineer's workload, runtime or kernel, correctness contract, resource limits, and budget. Codex agents propose changes. Sera controls what can execute and what can be retained. The evaluator, not the agent, determines success.

The existing package implements part of this contract for narrow vLLM configurations. It does not implement a general optimizer for arbitrary models or CPU kernels. Its useful assets are typed candidate validation, task-quality gates, measured feedback, owned runtime cleanup, local evidence, and checkpointing. These deserve reuse. The model-specific assumptions should move into adapters rather than define the whole product.

The earlier MatMul task used a Codex subagent named `sera`. It did not invoke this repository's Python package. Its reported 1,160–1,449 GFLOP/s cannot be credited to `import sera`. The new CPU integration in this change is the first package path tested here for this task.

## What an engineer should supply

| Input | Required contract |
| --- | --- |
| Subject | A pinned model/runtime configuration or kernel source and ABI; retain the original artifact. |
| Workload | Real input shapes, data types, layouts, batch sizes, sequence lengths, and traffic mix. |
| Correctness | A versioned independent reference and tolerance; separate search and final cases. |
| Objective | One primary metric plus hard quality, latency, memory, and resource constraints. |
| Execution | An owned local or remote worker with explicit hardware capabilities and isolation policy. |
| Budget | Maximum trials, elapsed time, agent calls, and resource use. |
| Result | Verified source/configuration, evidence, compatibility limits, and an explicit unsuccessful outcome. |

“Any engineer can slot it in” means the adapter boundary is stable and setup is small. It does not mean every model and hardware combination works without an adapter. A CPU MatMul kernel is an operator-level capability test; it does not prove faster end-to-end model inference.

## Core design

1. Preflight the workload, reference implementation, compiler/runtime, hardware, and objective. Reject missing capabilities before an agent call.
2. Freeze a deterministic baseline. Record seeds, input identities, build flags, versions, thread settings, hardware, and warmup. Preserve all repetitions and timing spread.
3. Give a Codex agent the allowed source/configuration, public contract, and measured history. Require a concrete hypothesis and an explicit artifact change.
4. Validate the proposed artifact, then run correctness before performance. Compilation failure, wrong answers, timeout, and invalid telemetry are outcomes, never improvements.
5. Measure candidate and unchanged control in a fixed reproducible interleaved order. Reject gains inside observed noise. Preserve original and current-best artifacts separately.
6. Select only an eligible improvement. Perform a separate final evaluation on the frozen selected artifact. Return no deployable artifact if that final check fails.
7. Export the accepted change with its source hash, compatibility requirements, raw measurements, and exact reproduction command. Installation into a serving model is a separate explicit adapter action.

The agent should not own the metric, seeds, acceptance rule, evaluator source, or resource accounting. A model answer saying “faster” has no authority. More agents do not repair a weak evaluator or an incomplete search space.

## Existing implementation: strengths and gaps

| Area | Existing evidence | Gap for the intended product |
| --- | --- | --- |
| Search | Three-investigator proposals, peer review, arbiter, typed controls, expanding neighborhoods | vLLM-specific controls; no source-editing contract in stable paths |
| Quality | Caller evaluator and fixed quality floor; quick mode is explicitly unverified | Small prompt sets; evaluator behavior is not cryptographically bound on resume |
| Measurement | Warmup, per-load request records, task checks, timing and memory | Repeated-prompt results do not establish cold/unseen workload gains; no general statistical acceptance contract |
| Lifecycle | Owned processes, cleanup checks, SQLite ledger and explicit resume | No proof of unattended live outage recovery; generic native-code worker absent |
| Adoption | Python API and wheel; pinned live demonstrations | Default model restrictions, exact runtime requirement, provider certificate and Weave setup |
| Scope | `sera` and independent `sera_loop` both ship | Two product paths with separate contracts; select one public core before expanding support |

The saved roughly 20% latency gains are useful evidence for repeated-prompt Qwen/vLLM workloads. They do not prove that Sera beats random search, tunes arbitrary models, or generates better CPU kernels.

## CPU work delivered in this change

`sera.kernel_search` is an explicitly experimental source-search path. `sera.kernel_tools` connects it to a Codex CLI proposer and the existing frozen `kernel-opt` evaluator. It avoids forcing C kernels into the vLLM configuration schema. It is a narrow integration seam, not a replacement production engine.

The Codex adapter checks ChatGPT login, strips API credentials from the child environment, ignores user provider configuration, forces the OpenAI provider with ChatGPT login, and supplies a read-only policy. The agent returns structured C source; Sera writes each candidate into a distinct trial directory. No hosted AutoLab agent, W&B, or API-key client is used by this path. Authentication follows the [official Codex non-interactive workflow](https://learn.chatgpt.com/docs/non-interactive-mode) and [authentication documentation](https://learn.chatgpt.com/docs/auth).

The scorer invokes the frozen Hills evaluator, verifies each signed report, and checks evaluator, workload, machine, compiler, flags, OS, and architecture identity before comparison. It neither reads nor changes private seeds. The search saves source hashes, raw reports, hypotheses, repeated scores, unchanged controls, and one final held-out report. A hard candidate cap and command timeouts bound the research run.

The current approved target is strictly greater than **1,800 GFLOP/s**, with the full single-threaded row-major float32 product at n=512, tolerance 0.002, no external libraries, and the existing fixed compiler flags. Packing, allocation, and call overhead remain inside the evaluator's timing. The evaluator's best-of-three rule is unchanged; Sera adds repeated reports and conservative promotion above it.

## Remaining production gates

- **Native execution isolation:** the local Hills path executes trusted research code as the user. Read-only agent tools and timeouts do not sandbox a compiled kernel. Production needs a disposable worker with no credentials, network, or unrelated mounts, plus CPU, memory, process, and output limits.
- **Complete CPU correctness contract:** exercise odd shapes, tails, alignment, alias rules, output overwrite, nonfinite values where supported, and numerical edge cases. The existing hill's n=96/n=512 checks alone are not general ABI certification.
- **Durable kernel recovery:** the experimental JSON journal is inspectable after interruption but does not resume execution. Use an owned worker and transactional state before unattended production.
- **Hard deadline across agents:** evaluator timeouts are bounded by remaining run time; arbitrary caller-supplied proposer callbacks must enforce their own timeouts. The provided Codex proposer has a separate command timeout.
- **End-to-end integration:** a winning C file still needs CPU capability dispatch, build/package handling, and integration into a real model operator. Benchmark a representative model before claiming model speedup.
- **Search competence:** compare against a fixed baseline and equal-budget deterministic/random search on several workloads and CPUs. Report failed runs and noise; do not select only successful examples.

The independent [GPT-6 Luna audit](sera-production-audit-luna-2026-09-24.md) provides prioritized production findings. The intended next release is a supervised CPU research adapter with clear failure behavior, not an unattended general optimizer.

## Current measured outcome and approved research scope

The approved target is strictly greater than **1,800 GFLOP/s** on the unchanged single-thread FP32 n=512 kernel-opt hill. The user now requires retaining both AC and battery measurements, with fresh baselines and paired controls within each mode. The current swarm uses 15 GPT-6 Luna specialists to propose and rank experiments on one shared board. GPT-6 Astra-high selects the roster, implements the selected experiment, and reviews measured results. The run is bounded by the caller's declared trial, elapsed-time, and model-call budgets; the standard research configuration allows up to six implementation attempts and 108 calls.

The earlier [AC idle block](../evidence/cpu-swarm-ac-idle-2026-09-24/README.md) produced no new candidate. Fourteen specialists abstained from proposing a distinct experiment; all 15 ranked the remaining `loop_order` proposal. Astra-high correctly abstained because it matched the baseline traversal. The unchanged baseline measured 1,504.19, 1,372.78, and 1,451.00 GFLOP/s in validation, then 1,640.55 GFLOP/s in the held-out final report. All four signed reports were independently verified. No source was promoted and the target was not met.

Earlier battery measurements from this package remain historical planning context and are not AC comparison evidence. The separate earlier AutoLab task did not use this Python package. The current CPU path has finite deterministic correctness coverage, executes native code in a trusted local research environment, and does not integrate into end-to-end model inference. Do not claim production readiness or an end-to-end model speedup from this operator-level work. The user has approved the 15-Luna/Astra-high architecture and 1,800 GFLOP/s goal; do not present these as pending choices.

## LIBXSMM reference checkpoint

The user chose a new research direction: reproduce the published LIBXSMM SME approach, then optimize it. The [standalone reference](../evidence/cpu-libxsmm-reference-2026-09-24/README.md) pins upstream LIBXSMM, exports its beta-zero n=512 kernel ahead of time, and adapts its column-major ABI to the frozen row-major hill. Its editable assembly reassembles to the exact 2,500 generated bytes. No LIBXSMM library is linked during scoring; generated packing remains inside the timed call. License and provenance are retained.

The first reference-only block passed 48 deterministic correctness cases and four signed reports. Its validation scores were 1,541.25, 1,333.28, and 1,328.07 GFLOP/s; the final report was 1,533.19. A subsequent fresh swarm baseline reached 1,643.48 in one report but remained variable. These are reference measurements, not a Sera-discovered improvement. Published repeated-call results are not directly comparable to this hill's allocation-inclusive timing.

The first implementation call on the larger assembly file timed out. Sera now supports small exact edits against a measured source hash, rejecting unknown bases, altered source hashes, and ambiguous spans before compilation. It still saves complete candidate source and applies the same correctness and performance gates. The relevant CPU-path suite passes 108 tests. The swarm also skips identical generated sources and continues after Astra skips an entire selected batch as already tested, within the existing attempt/call/deadline caps.

No Sera kernel has yet met the 1,800 GFLOP/s goal or passed promotion in these experiments. The production verdict remains unchanged. The CPU path uses Codex through ChatGPT login; the legacy stable model API's broader provider behavior remains a separate unresolved production issue.

## AC and battery evidence retained

The completed [LIBXSMM battery block](../evidence/cpu-libxsmm-measure-prepared-2026-09-24/README.md) measured three source changes proposed by the Luna swarm and implemented by Astra. All passed 48 deterministic correctness cases; none passed the repeated-control promotion gate. The two-step K unroll measured 1,047.55–1,091.20 GFLOP/s against controls of 873.32–1,040.11. Its smallest paired gain was 0.7%, so it remains an unproven hypothesis. The unchanged reference's final 801.30 GFLOP/s failed the confirmation floor; Sera returned no winner.

All 22 signed reports were verified, with unchanged battery power and settings before/after each score. The continued plan consumed 71 calls and six attempts including earlier work. Seven continuation tests pass. The [comparison inventory](../evidence/cpu-libxsmm-power-comparison-2026-09-24/report.md) keeps each exact source and measurement phase separate. The same kernel method works in both modes, but each mode needs its own measured improvement. New battery candidates still need AC measurements. The target and production-readiness verdict remain unmet.

## Next source-grounded search

The next plan retained the LIBXSMM baseline and supplied concise packing/source reviews and all prior candidate outcomes. Sera now shares unimplemented proposal dispositions across roles so a new roster receives reasons for skipped work. A bounded implementation timeout also advances the existing ranked queue when call, attempt, and deadline budgets remain; it is not retried automatically. The continuation retained 32 spent calls, one failed attempt, and the original absolute deadline.

The [completed continuation](../evidence/cpu-libxsmm-next-continue-2026-09-25/README.md) used 72 total calls and six attempts across the plan. Three scheduling changes passed correctness but failed promotion. Two broader implementation calls timed out at the unchanged 180-second cap, and one scratch-buffer proposal was internally inconsistent. All 22 continuation reports were independently verified. The unchanged baseline's held-out result was 1,081.13 GFLOP/s; this confirms the baseline for that battery block and is not an optimization gain. Both power modes remain recorded separately; the new source variants have no AC measurements yet.

The source reviews reduced neither the need for implementation feasibility checks nor the need for measured proof. Some proposals still misdescribed the baseline or imposed incompatible constraints. The current evidence establishes a working guarded research loop, not reliable optimizer competence or production readiness. The target remains unmet.


## Exact-source battery energy-mode comparison

The swarm implemented three new candidates using an optional verified LIBXSMM 32-row primitive and a packing-layout change. None passed promotion in the [Low Power block](../evidence/cpu-libxsmm-panel-swarm-2026-09-25/README.md). The user then authorized one temporary Automatic battery block with restoration. The [completed replay](../evidence/cpu-libxsmm-automatic-2026-09-25/README.md) retained the exact four source hashes and original swarm order, with fresh controls and three fresh Astra reviews. All 22 reports verified; all sources passed 48 deterministic correctness cases.

The best single Sera-candidate report now reaches **1,630.17 GFLOP/s** (sixteen 32-row calls), but that candidate's median is **1,410.96**, and it failed the repeated-control gate. The historical best Sera-candidate median remains **1,546.80** from the earlier loop-order experiment. The imported reference's new single-report high is **1,668.60**; it is not a Sera improvement. Its held-out result of **1,153.52** failed the confirmation floor, so the replay returned no winner. No candidate reached 1,800 or passed promotion.

Battery Low Power was restored and verified immediately after the run. AC remains Automatic. Both modes' evidence is preserved separately; these three exact candidates still lack AC measurements. Sequential power-mode blocks do not isolate causality, and changing energy settings is not an algorithmic improvement. The remaining useful research input is that splitting calls, replacing the generated full kernel with constant-shape C/SME, and padding packed A slices did not establish gains under either measured battery mode. Production readiness remains unproven.


## Further source-grounded layout batch

The [next specialist board](../evidence/cpu-libxsmm-next-board-2026-09-25/README.md) incorporated actual outcomes from five previous phases and three Luna source reviews. Two complete 15-specialist rankings produced five distinct implemented kernels: row-half-first traversal, contiguous B packing, column-panel-first traversal, bounded software prefetching, and joint pointer-end checks. All passed the 48-case correctness checks; none passed promotion. The selected 64 KiB packed-A layout timed out at 180 seconds and remains unimplemented.

This Low Power block used 73 model calls and six attempts. All 34 signed reports, source identities, power captures, and board rankings verified. The unchanged baseline's final score was 1,026.19 GFLOP/s. The target remains unmet, and the five new sources have not yet been measured on AC or Automatic battery mode. Root corrected duplicate-work claims in a Luna review, and Astra corrected a wrong B-stride claim in the prefetch advice. The evidence supports the need for these checks; it does not establish reliable optimization competence. No production gate was removed.


## Smaller-panel implementation completed

The [editable-panel preparation and run](../evidence/cpu-libxsmm-editable-panel-2026-09-25/README.md) exposed the imported helper as readable assembly with an exact1,536-byte helper match and full7,640-byte compiled-text match.16 preparation tests and48 baseline correctness cases passed. This mechanical source change enabled Astra to implement the previously timed-out64KiB panel layout with one SME region within the unchanged call limit.

Four distinct candidates passed correctness in the new Low Power block, but none passed promotion. Two duplicate recommendations consumed the remaining attempts. All28 signed reports and both15-ballot rankings verified; the unchanged baseline's held-out score was1,094.73 GFLOP/s. The target and production-readiness claim remain unproven. A [Luna audit](../evidence/cpu-libxsmm-editable-panel-2026-09-25/duplicate-board-audit-luna.md) proposes grouping duplicate source changes before voting; it remains a user decision and has not been implemented. The new exact-source Automatic replay is prepared but awaits a fresh temporary-setting authorization.


## Ten-run AC replay, 2026-09-25

The user replaced the1800 GFLOP/s objective with beating the imported baseline peak consistently over ten runs. The exact four most recent swarm-selected kernels were replayed on AC Automatic with ten validations each and ten paired controls each. All91 signed reports were independently verified; source hashes, frozen hill/compiler identity, public correctness, and power settings were preserved. No candidate met the goal or passed the existing promotion gate.

Fresh imported-baseline peak:1685.6231 GFLOP/s, median1529.2057. Best candidate sample:1701.6510, from the one-entry32-row panel kernel; its median1493.0324 and minimum1251.2024 show why the peak does not establish a consistent gain. It exceeded the prior1668.5964 imported peak3/10 times and the fresh AC peak1/10. The other candidates exceeded the fresh peak0/10. The final1495.8121 report belongs to the unchanged baseline. All candidates were rejected by Astra after fresh measurement. Four Codex review calls; no new implementations or hosted provider calls.

The historical-versus-fresh peak definition remains awaiting user adjudication; this block reports both without changing promotion policy. Full evidence: `evidence/cpu-libxsmm-ten-run-ac-2026-09-25/README.md`, `verification.json`, and signed reports. This supplies AC evidence for the same sources previously measured in Low Power. The prepared second Automatic battery replay remains unstarted and its setting-change permission remains pending.


## Full-size transpose swarm, 2026-09-25

The15 specialist swarm received verified optional TA/TB/TT primitives and the ten-run history. Three boards used83 Codex calls. Of four implementation attempts, one produced a valid new kernel: TRANS_B with fresh timed A transpose. It scored 1045.00–1556.15 GFLOP/s, median 1491.34, with 3/10 paired wins and 0/10 runs above either saved or fresh imported baseline peaks. No promotion. All 31 signed reports and the two complete 15 ballot rankings verified. Final1660.00held-out score belongs to the imported baseline.

Astra caught a wrong transpose equation and an already-existing store order before submitting sources. Another assembly edit exceeded180 seconds. The final 15 advisors abstained; TA/TT full-call paths remain unmeasured. Some advisors incorrectly treated unmeasured descriptors as exhausted. This reinforces the production-readiness gap: guards protect promotion, but proposal accuracy and experiment coverage are not reliable. No architecture or threshold change was made. The actual compiler output requested by the assembly advisor was captured after measurement for future proposals. Evidence: `evidence/cpu-libxsmm-transpose-swarm-2026-09-25`.


## Compiler-guided phase and lossless prompts, 2026-09-25

The next Low Power board measured the earlier SME-transpose TB source again, then
four new kernels: NEON-transpose TB, four-step K unroll, 288-byte packed-A slices,
and SME-transpose TA. All five failed promotion and exceeded the fresh initial
baseline peak zero times out of ten. TA now has full-call evidence; TT remains
unmeasured. A final general-size direct-gather source failed compilation.
All110 signed reports, source hashes, power captures and both15-ballot rankings
verified. The phase used73 Codex calls and five implementation attempts.

The final Astra review failed because its repeated source history made the prompt
1,108,459 characters, above the1,048,576 input limit. The phase remains failed:
no holdout and no winner. Sera now shares identical source text in prompt displays
using reversible exact replacements. Raw measured sources, hashes, metadata and
edit bases remain unchanged. Offline reconstruction of the failed prompt reduced
it to437,183 characters and restored all seven sources exactly. This fixes that
observed failure; arbitrary unrelated large sources can still exceed input limits.
The prompt, advisory, edit, ranking and search suite passes64 tests. This remains
an experimental trusted-local optimizer, not a production-ready service.

The user approved one-level FP32 Strassen alongside the existing methods. A pinned
LIBXSMM256-square primitive passed byte, ABI, license and correctness checks.
It is available for the same15-specialist board; no Strassen performance claim
exists yet. Benchmark rules, ten-run checks, power separation and budgets remain
unchanged. Evidence: `evidence/cpu-libxsmm-compiler-board-2026-09-25` and
`evidence/cpu-libxsmm-256-primitive-2026-09-25`.


## Approved one-level Strassen results, 2026-09-25

The prepared baseline preserves the active full512 NN source and adds an unused,
byte-verified256-square primitive. Its source is8bb0113e377808a841819354296fa0ef02ff49e4188d57a091afc6463fc0ca18.
All imported bodies match their exports. The new deterministic correctness suite
adds two cancellation and two scale-separated cases while preserving all48 existing
cases and tolerance.002. Preparation, driver and core tests pass73 checks.

Two15-specialist boards used71 Codex calls and six implementation attempts. Three
produced distinct measured sources, all passing52 correctness cases:

| Candidate | Ten-run GFLOP/s range | Median | Paired wins | Promotion |
| --- | ---: | ---: | ---: | --- |
| One-level Strassen, three reusable buffers | 432.96–567.57 | 550.44 | 0/10 | Rejected |
| Classical NN condition-code K loop | 819.86–1108.66 | 1071.60 | 7/10 | Rejected |
| Strassen with explicit NEON operand packing | 454.69–559.53 | 538.94 | 0/10 | Rejected |

This block is Battery Low Power. The fresh baseline range is905.47–1102.21,
median1067.08. The two Strassen sources were consistently slower than every paired
control. Their arithmetic reduction did not yield a full-call improvement; these
measurements do not isolate which component caused the regression. Neither Strassen
source has AC or Battery Automatic evidence yet. Scores are not pooled across modes.
The unchanged baseline's final848.70GFLOP/s was below the860.20confirmation floor,
so the terminal status is `final-performance-unconfirmed`, with no winner.

Astra rejected two duplicate schedules and one infeasible32KiB request for a64KiB
panel. The15 specialists still proposed and ranked those errors despite supplied
history. Guarded review prevented invalid promotion, but experiment selection remains
unreliable. The prompt compaction fix handled both boards and all reviews without
another size-limit failure. Production readiness remains unproven; no model-workflow
integration, native-code isolation or broad accuracy guarantee follows from this run.
The ten-run improvement goal is still unmet. Evidence and independent source audit:
`evidence/cpu-libxsmm-strassen-swarm-2026-09-25`.


## User-directed return to repeatability

The user redirected research to the strongest existing Sera source,
`eb091b1eca431f0760d0d61e4c0c6e748c1a9e34466a87ac15ad9cb238b5aecf`,
instead of further Strassen or broad algorithm searches. The next broad board was
interrupted during coordinator planning:10 baseline reports,1 model call,0candidate
implementations, no holdout. Its raw terminal state is failed/KeyboardInterrupt;
all10 reports and its source/power records verified. No background run remains.

That best source uses32-row panels,64KiB scratch and one SME region across16panels.
The source change is real, but the previous AC series won5/10pairs and exceeded the
fresh imported initial peak1/10times. Both candidate and control have substantial
variation among their three raw timed calls. The next step is an exact-source replay
with the original imported control, preserving all raw timing triplets and gates.
No claim of system-wide optimality or production readiness is established.
