# Sera: incremental delivery plan

Status: Qwen BF16 and FP8 KV runtime checks passed. The 24-case task-quality pilot is complete; see evidence/tasks-v1-comparison/README.md. The measured first milestone is not complete. Its quality contract needs a decision before implementation continues.

## First milestone

One model → baseline → one candidate → quality gate → usable runner and report.

Use Qwen/Qwen3-0.6B on the supplied NVIDIA runtime. Keep each experiment small, save its evidence, and report the result before choosing the next change. Do not build the entire system in one pass.

The local session is Apple Silicon. The connected Molab runtime has an NVIDIA RTX PRO 6000 Blackwell Server Edition, compute capability 12.0, and 97,887 MiB of GPU memory. Qwen BF16 and FP8 KV runs generated responses through vLLM 0.26.0, exposed metrics, and released GPU memory after shutdown. The baseline started again for the task pilot. FP8 weights, GLM compatibility, provider reliability, and the product quality gate remain unverified. The initial 20-minute compatibility window was spent on runtime setup; the later bounded check established Qwen FP8 KV operation only.

## Work order

| Step | Small experiment or change | Evidence required before proceeding |
| --- | --- | --- |
| 0. Hardware risk | Spend at most 20 minutes on the section 5.1 FP8 matrix for Qwen and GLM. Start with Qwen. | Saved version fingerprint, exact flags, outputs, metrics, cleanup result, and pass/fail/unverified for weight FP8, KV FP8, and their combination on each model. |
| 1. One real runner | Add the minimum package, pinned model configuration, owned vLLM process, generate, and close. | Qwen generates one prompt, stops, releases memory, and starts again. No search code yet. |
| 2. Measured baseline | Run sera-baseline-v1 with 32 saved prompts, concurrency 1, 16 warm-ups, and 96 measured requests. | Saved vLLM metrics sample, raw request samples, token counts, p95, throughput, peak memory, and baseline quality outputs. |
| 3. One candidate | Define a typed candidate and validate its settings and memory estimate. Change one setting and run the same workload. | One candidate outcome, including startup or generation failure if it occurs. No candidate search or retries with new settings. |
| 4. Quality and selection | Apply token-agreement-v1 and the fixed selection rule. | Per-prompt quality scores, overall verdict, and a recorded reason to select the candidate or baseline. Manually exercise rejection with a labeled bad-output fixture. |
| 5. Usable result | Return the selected live runner and render the saved result as a readable report. | A fresh generate call after optimize returns, a report matching saved measurements, and successful close with memory cleanup. |

After each step, share what ran, what happened, the saved evidence location, and the next experiment. If a step fails, diagnose that failure and change one thing before retrying. Do not replace missing measurements with a simulated success.

## Decisions fixed before milestone one runs

- Baseline: sera-baseline-v1 from spec.md section 7; record every resolved setting and exact model/tokenizer revision.
- Candidate: use FP8 KV cache alone if the Qwen hardware check passes. Otherwise use max_num_batched_tokens=2048 after legality validation. Freeze this choice before collecting candidate measurements. This fallback tests the measured pipeline and does not promise a gain.
- Quality: fixed prompts and generation settings; mean position-wise token agreement of at least 0.99, with empty output and generation errors rejected. Run quality at concurrency 1. An unstable baseline self-check cannot approve a candidate.
- Selection: candidate must pass quality, have zero generation errors, and reduce measured p95 latency by at least 5%. Otherwise return the baseline with no-safe-improvement. This threshold is a chosen milestone rule; one comparison does not prove statistical significance.
- Result: one SeraModel plus a versioned JSON record and readable summary. Save model revisions, configuration hashes, workload, raw/reduced metrics, output tokens, quality scores, outcome, and selection reason. Keep secrets out of the record.
- Validation: automated tests only for VRAM arithmetic, candidate schema validation, and the metrics parser against saved vLLM output. Add failing tests in those areas before implementation. Other milestone checks are small manual experiments.

If the candidate passes, return its runner. If it fails or does not improve enough, stop it and reload the baseline. A usable baseline return is a successful milestone. A replay is a fallback deliverable and does not satisfy the live-runner milestone.

## After milestone one

1. Check the LM provider with the actual schemas and synthetic evidence. Use W&B schema-constrained output and record 30 responses, first-pass validity, retries, errors, and latency. Require at least 29 valid first responses and all 30 valid within one retry each. Wait for the user's supplied environment to run this experiment.
2. Add one specialist through the existing typed candidate interface. Give it the measured baseline, execute one validated proposal, and return the outcome as feedback. Add the arbiter and other active specialists only after this path works. Keep budget, quality, and selection decisions deterministic.
3. Prove search quality on Qwen only. Freeze at most twelve nonbaseline configurations per declared workload profile and a common search budget of at most eight, strictly smaller than the universe. Measure the universe, then replay Sera, grid, random search, and ablations with identical outcomes and budgets. Hide unselected outcomes from agents. Report failure if the benchmark conditions are unmet.
4. Add GLM for constrained joint placement. Use only its required reference and proven quantization configurations. Freeze service memory fractions and disclose the smaller-card memory budget on the slide and notebook. Compare both pairs under identical limits; report actual fit and workload outcomes.

SQLite recovery, multi-GPU support, full frontier search, and notebook polish follow the working measured path. They do not block the first milestone.

## What ships if a later step fails

- Joint placement fails or is unfinished: ship the completed single-model milestone with its runner and report. Include only agent and benchmark results that actually ran.
- The real runner cannot work: ship an explicit replay notebook with saved real records. If none exist, ship a labeled synthetic fixture with no live models and no performance claim. Keep the live milestone marked incomplete.
- The LM fails its schema check: keep the fixed-candidate path working. Do not let malformed proposals reach GPU execution. Select another provider model only after it passes the same check.
- FP8 fails: disable only the failed model/precision paths. Keep working paths; if none remain, use batching and remove unsupported quantization claims.

The user requested objective task vectors instead of relying on output similarity. An Astra subagent created and independently checked the frozen 24-case sera-task-v1 pilot. BF16 scored 3/24 and FP8 KV scored 1/24 under its strict JSON contract. Formatting dominates these scores; the report preserves them and separately identifies four correct fenced payloads per run. Both configurations also make task errors. Median latency is effectively tied; a retained 54.626-second BF16 outlier prevents a clean speed claim.

Next decision: should answer correctness and JSON-format compliance be separate gates? Do not silently replace the existing 99% token-agreement rule or promote FP8 based on this pilot. The pilot's 128-token limit and single 24-case pass are not the first milestone's workload. FP8 weights, GLM, agent selection, and a returned Sera runner remain unverified or unfinished.
