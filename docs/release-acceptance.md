# Next release: acceptance checklist

The completed single-model recordings are saved under `evidence/expanded-swarm-comparison`. This checklist covers the next implementation pass, not a claim that it has passed.

## 1. Simple entry point and packaging

- One-time provider and tracing setup is documented. Credentials stay in environment variables; missing or inconsistent setup fails before GPU execution.
- A supported quick-mode call can invoke the full three-investigator loop without exposing inference settings in the call. It reports that task quality is unverified.
- Fit-first deployment still requires an absolute task evaluator, its version, and a quality floor. An unfit BF16 model cannot supply a token-agreement reference.
- Default full-loop behavior and explicit fixed-candidate or bounded modes have tested precedence. The full loop has no total trial cap unless the caller declares one.
- The wheel includes the necessary tracing and evidence readers. Installed runtime code does not import repository-only `experiments` or `benchmarks` modules.
- Build and install the wheel in a clean environment. Exercise imports and preflight failures outside the source checkout. A stub test is not a live GPU rehearsal.
- Rehearse the documented selected path on the supported GPU, generate through the returned runner, close it, and record cleanup and the exact installed source version.

## 2. Connection recovery

- The controller can recover from read outages longer than its former three retries, within declared recovery and request-expiry limits.
- A lost publish acknowledgement is reconciled against remote state. It cannot overwrite a different response or cause another model/GPU trial.
- A controller restart reuses a completed saved response; it does not silently reissue an incomplete model request.
- Expired requests, conflicting records, and permanent errors fail clearly. Recovery logs contain no credentials or raw exception payloads.
- Offline fault tests and actual live recovery are reported separately. Controller reconnection does not establish resume of a killed GPU optimizer or SQLite-backed recovery.

## 3. Configuration measurement and search comparison

- A configuration survey reports latency, memory, quality, errors, and startup separately for each tested full configuration.
- The frozen Qwen0.6B benchmark remains separate from normal expanding search. Each profile has at most twelve nonbaseline configurations, not a claimed 24 independent runnable techniques.
- Eight options per specialist can overlap. The catalog has twenty technique families; unsupported techniques remain unavailable.
- Collect exactly the frozen baseline and candidate outcomes. Failed candidates remain in the result. An incomplete collection has no oracle.
- Grid, twenty seeded random runs, and adaptive policies receive the same outcomes. Each adaptive policy sees only the results it selected.
- Report per-trial latency and trials to the near-oracle threshold. Do not claim Sera beats random search or an ablation until the comparison rule was fixed before observing results and actually passes.
- No new GPU sweep is implied by implementing the collector. Its workload, eligible baseline, memory profile, and quality rules must be fixed before collection.

## Later work, not removed from the product

Two-model allocation and broader hardware/model support follow this pass. Full optimizer resume and SQLite persistence also remain separate from controller transport recovery. The spec's multi-GPU and resume requirements conflict with the historical hackathon cuts; do not call the full spec complete based on the narrower release.
