# Finish the search comparison

The live Qwen72B comparison and the strict spec benchmark are different claims.
Do not change the frozen candidates, quality floor, questions, or trial order after
reading the results. Do not relabel the 72B comparison as a section 19.4 pass.

## Closed live run

Run these commands in order on the saved run directory. Only `collect-missing`
can start GPU trials. It measures only configurations the live loop did not select.
It is a no-op when all candidates already have audited outcomes.

```bash
python -m benchmarks.live_comparison import-live --run-dir RUN
python -m benchmarks.live_comparison collect-missing --run-dir RUN
python -m benchmarks.live_comparison compare-grid --run-dir RUN
python -m benchmarks.run_search replay --collection RUN --output-dir REPLAY --live-run
```

`import-live` requires a closed loop, exact registration/result hashes, ordered
trial evidence, no future trial history in saved prompts, a passing fresh returned
runner request, successful cleanup, and measured runtime ownership intervals.
Already imported runs must not be imported again. Later commands re-audit the
original sources instead of trusting their summary files.

The last command reports the original live choices, lexicographic grid, and all
20 random seeds frozen before collection. It uses the same cached outcomes for
all methods. It does not call a provider or GPU. Unreached thresholds remain null.
The baseline counts as zero trials. A tie is not a win.

## Agent and ablation replays

Add the provider arguments to run three independent CPU-side searches. These
call the chosen investigator provider; they do not repeat GPU experiments:

```bash
python -m benchmarks.run_search replay --collection RUN --output-dir AGENT_REPLAY \
  --live-run --agent-provider codex-relay --agent-model gpt-5.6-luna \
  --project TEAM/PROJECT --provider-check CERTIFICATE --relay-dir RELAY_DIRECTORY
```

The matching controller must be connected to `RELAY_DIRECTORY`. W&B Inference
is also supported with `--agent-provider wandb` and without `--relay-dir`.
Each variant gets a fresh client and audit file:

- Full evidence: the production three-investigator, peer review, and arbiter code.
- No history: prior trial outcomes and prior proposal prose are removed from both
  prompts and inspection results. The baseline and remaining candidate mask remain.
- Round-robin: one rotating investigator, with no peer board or arbiter.

All variants see only the baseline and outcomes they selected. Their inspection
tool reads saved metrics and task scores, not raw Weave outputs. This limit is
included in their prompts and reports. The original live run used Weave reads;
the cached replay must not be presented as that same execution. Policies may
abstain, fail validation, or lose. No fallback replaces a failed policy with grid.

The approved 72B exception preserves FP8 weights and BF16 KV in every candidate.
Its manifest and model identity are checked through the same replay adapter.

## Still required for the strict spec claim

- Two predeclared Qwen3-0.6B pressure profiles, each established by a real pilot.
- A passing baseline under the unchanged task and quality rules for each profile.
- Complete measured outcomes for each preregistered universe, with a common search
  budget smaller than the nonbaseline candidate count.
- Independent full-policy and ablation provider runs on those outcomes.
- A success rule frozen before measurement that defines exactly how to beat the
  random median and an ablation. The current spec does not define those comparisons
  precisely enough to choose a rule after seeing results.
- A defined no-reduced-telemetry ablation compatible with mandatory metric citations.
  The current exact removal deletes all citeable metrics, so it is rejected rather
  than presented as an executed ablation.

The 72B profile can establish an exploratory grid advantage and report a random
distribution. Its full-universe budget, repeated prompts, prior candidate knowledge,
and absent pressure reversal prevent the strict section 19.4 claim. A negative or
tied result must remain in the report.
