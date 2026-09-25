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
  --specialists 3 \
  --max-candidates 6 \
  --agent-timeout 180 \
  --max-seconds 1200 \
  --target-gflops 1780
```

The output directory must not exist. `--model` is optional; omission uses the Codex CLI default. `--specialists 1` selects the simple single-agent proposer. Two or three selects the delegator. The candidate cap also caps total specialist calls in this example. Plan usage is consumed; no dollar-cost guarantee is inferred from a call limit.

The M4 example fixes single-thread float32 row-major `C=A@B` with `void gemm(int n, const float *A, const float *B, float *C)`. It targets Apple clang and the existing 512×512 hill with tolerance 0.002. Adapt the task and hardware profile before using this example for another CPU or operator.

## What runs

1. Sera snapshots the original source and fixes thread environment controls.
2. Public correctness checks compile the source and verify 15 zero/small/odd/tile-edge dimensions using seeded random, identity, and zero inputs, a float64 reference, input preservation, and output guards. These tests do not produce performance scores.
3. The frozen hill supplies three signed baseline reports. Each report retains its original best-of-three scoring convention.
4. A deterministic router scores the reviewed specialist catalog and selects at most three relevant roles. No specialist sends messages to another specialist. Codex returns structured source under a read-only tool policy; Sera writes the candidate snapshot.
5. Each candidate passes correctness before timing. Three candidate reports alternate with three unchanged-control reports. Promotion requires the candidate's slowest report to exceed the control's fastest report by at least 5%.
6. The selected artifact gets one final held-out evaluation. Correctness failure or a material final timing regression returns no accepted source. The 1,780 target requires every selected validation report and the final score to exceed 1,780.

Relevant MatMul specialties include SME tiles, register tiling, packing, cache blocking, instruction scheduling, memory traffic, vectorization, compiler code generation, alignment/tails, numerical semantics, prefetch/TLB behavior, and allocation lifetime. Parallelism and model-graph roles require explicit capabilities and remain inactive in this single-threaded standalone-kernel workload.

Specialist roles are fixed contracts. Their bounded in-run memory records measured outcomes and source/report identities. Later hypotheses can use that history. A specialist cannot rewrite the evaluator, tolerance, hardware assignment, thread limit, or budget. Cross-run learning is not yet implemented.

## Inspect the result

- `controls.json`: baseline source, implementation hashes, thread controls, and limits.
- `search/result.json`: authoritative experimental search summary, every trial, control scores, and final decision.
- `search/trial-*/source/kernel.c`: exact source snapshots.
- `search/trial-*/*.json`: public correctness and unedited signed hill reports.
- `agent/state.json`: selected specialists, call outcomes, and bounded observation memory.
- `agent/call-*/`: Codex prompts, responses, and command logs.
- `journal.md`: short run summary.

Verify a hill report with `hills verify /absolute/path/to/report.json` using the evaluator's matching Hills signing home. Compare reports only within the same machine, workload, evaluator, compiler, flags, and mode. No leaderboard publication is performed.

## Limits

The local evaluator executes generated C with the current user's privileges. Timeouts, stripped environment credentials, source snapshots, and correctness guards do not provide a security sandbox. This workflow is for supervised, trusted research; a production service needs an isolated native worker with resource and data-access limits.

The baseline controls reduce avoidable variation but do not fix CPU scheduling, temperature, frequency, interrupts, or other applications. Timing spread remains visible and can prevent promotion. The supplied correctness checks cover the declared examples, not every shape, dtype, alias rule, or CPU. The journal supports inspection after failure; automatic kernel-run recovery and model integration are not implemented.
