# CPU kernel optimization with Sera and Codex

This is an experimental trusted-local workflow. It modifies standalone C GEMM source using Codex agents signed in through ChatGPT. It does not call a hosted AutoLab agent, Weave, LiteLLM, or an API-key provider. It does not install a kernel into a production model.

## Run the M4 Pro benchmark

Install the Sera package and a current Codex CLI. Run `codex login status` and confirm ChatGPT login. The separate `hills` command and complete frozen `kernel-opt` evaluation must already be available. Public hill downloads without private inputs cannot score this example.

From this repository:

```sh
python examples/optimize_cpu_kernel.py \
  --baseline /absolute/path/to/kernel.c \
  --hill-workspace /absolute/path/to/kernel-opt \
  --output /absolute/path/to/new-run \
  --max-candidates 6 \
  --agent-timeout 180 \
  --max-seconds 1200 \
  --target-gflops 1800
```

The output directory must not exist. Connect AC power before running. The example uses an Astra coordinator (`gpt-6-astra`, high reasoning effort) and 15 Luna advisors (`gpt-6-luna`, medium reasoning effort). Each planning batch makes one Astra call to select roles, 15 specialist recommendation calls, and 15 specialist ranking calls. Each selected experiment adds one Astra implementation call and one Astra measured-result review. The default batch size is three and the candidate limit is six: two full batches use 74 calls. A separate hard ceiling of 108 model calls remains in force; it also covers shortened batches, abstentions, and failures. `--batch-size` and `--max-model-calls` record explicit caller limits. The 1,800-second overall deadline remains in force. Plan usage is consumed; no dollar-cost guarantee is inferred from a call limit.

The old source-producing `KernelSpecialistTeam` and single `CodexKernelProposer` remain available as Python APIs, but this example uses the new `KernelAdvisoryTeam`.

The M4 example fixes single-thread float32 row-major `C=A@B` with `void gemm(int n, const float *A, const float *B, float *C)`. It targets Apple clang and the existing 512×512 hill with tolerance 0.002. Adapt the task and hardware profile before using this example for another CPU or operator.

## What runs

1. Sera snapshots the original source and fixes thread environment controls.
2. Public correctness checks compile the source and verify 16 zero/small/odd/tile-edge and 512-square dimensions using seeded random, identity, and zero inputs, a float64 reference, input preservation, and output guards. These tests do not produce performance scores.
3. The frozen hill supplies three signed baseline reports. Each report retains its original best-of-three scoring convention.
4. Astra selects exactly 15 distinct roles from the fixed CPU advisory catalog. It may replace roles between rounds. All 15 Luna specialists receive the same measured history and their own bounded prior advice/outcomes. Each recommends an experiment. All 15 then rank the same immutable proposal board. A complete ranking gives N points to first place, then N-1 down to one; total points determine experiment order, with experiment ID breaking ties. The selected batch is capped by the remaining candidate budget. Astra implements that order with fresh measured history after each experiment. Advisors do not submit kernels directly. Incomplete advice or an invalid/incomplete ranking is recorded as a failed batch; it cannot silently select experiments. Codex uses ChatGPT login, ignored user configuration, and disabled shell/image/web tools; Sera writes the returned source.
5. Each candidate passes correctness before timing. Three candidate reports alternate with three unchanged-control reports. Eligibility for promotion requires the candidate's slowest report to exceed the control's fastest report by at least 5%. Astra then reviews the measured experiment and records its decision to adopt, reject, or revise. Only an eligible candidate that Astra adopts replaces the incumbent.
6. The selected artifact gets one final held-out evaluation. Correctness failure or a material final timing regression returns no accepted source. The 1,800 target requires every selected validation report and the final score to exceed 1,800.

The catalog contains 24 fixed CPU roles, with a default roster of 15. Roles cover FP32 SME tiles, scheduling, packing, cache behavior, address calculations, compiler output, tails, scratch lifetime, constant-shape paths, and fallbacks. Role prompts must obey the hardware profile. The compiler permits only four FP32 ZA tile selectors for the MOPA operation used by the baseline.

Specialist descriptions are fixed contracts; Astra changes the roster, not those contracts. Bounded in-run memory pairs prior advice with the joint candidate outcome and report identity. Advice is not measured evidence, and joint results do not establish which advisor caused a gain. Agents cannot rewrite the evaluator, tolerance, hardware assignment, thread limit, or budget. Cross-run learning is not implemented.

Power and thermal observations are captured around every signed evaluation. AC power and unchanged power settings are required throughout the run. Earlier battery results are not treated as AC baseline measurements. FP32 arithmetic, the hill score convention, and the existing 5% separated-range promotion rule remain unchanged.

## Inspect the result

- `controls.json`: baseline source, implementation hashes, thread controls, and limits.
- `search/result.json`: authoritative experimental search summary, every trial, control scores, and final decision.
- `search/trial-*/source/kernel.c`: exact source snapshots.
- `search/trial-*/*.json`: public correctness and unedited signed hill reports.
- `agent/state.json`: batch rosters, shared board hashes, every ranking, selected order, source hashes, and measured outcomes.
- `agent/round-*/`, `agent/implementation-*/`, and `agent/review-*/`: prompts, responses, schemas, and command logs.
- `journal.md`: short run summary.

Verify a hill report with `hills verify /absolute/path/to/report.json` using the evaluator's matching Hills signing home. Compare reports only within the same machine, workload, evaluator, compiler, flags, and mode. No leaderboard publication is performed.

## Limits

The local evaluator executes generated C with the current user's privileges. Timeouts, stripped environment credentials, source snapshots, and correctness guards do not provide a security sandbox. This workflow is for supervised, trusted research; a production service needs an isolated native worker with resource and data-access limits.

The baseline controls reduce avoidable variation but do not fix CPU scheduling, temperature, frequency, interrupts, or other applications. Timing spread remains visible and can prevent promotion. The supplied correctness checks cover the declared examples, not every shape, dtype, alias rule, or CPU. The journal supports inspection after failure; automatic kernel-run recovery and model integration are not implemented.

The shared board avoids all-to-all agent conversations. Each of 15 voters still reads the board, so board text is repeated across calls; this is not a claim of linear token growth for arbitrarily large swarms. CPU evaluations remain serial.

Astra can return exact source edits for large kernels. Sera binds those edits to a
source hash in measured history, requires each old span to match exactly once,
and applies them to an in-memory copy. Unknown or changed bases and ambiguous
spans are rejected before compilation. The saved trial still contains complete
standalone source and follows the same correctness and performance gates.
Full-source responses remain supported. This avoids returning an unchanged
assembly file for each small experiment; it does not increase agent budgets.
