# Sera 0.2.0: configured single-model swarm

The public API now prepares the same swarm components used by the saved live
loops: three investigators, scoped Weave reads, shared findings, an arbiter,
measured candidates, fixed quality gates, and a returned live runner.

The default search has **no total trial cap**. It stops on the existing objective
plateau plus one confirmation rule, or when no legal experiment can proceed.
Each specialist sees up to eight legal options per round. These are overlapping
shortlists, not 24 distinct features and not eight GPU trials.

## Install on the GPU machine

Use Linux with one supported NVIDIA GPU. The checked GPU runtime is vLLM 0.26.0.
Install that runtime separately in the same Python environment; the small wheel
does not install CUDA or model weights. The existing live runs used Python 3.13,
vLLM 0.26.0, and an RTX PRO 6000 Blackwell. Other backends, general model loading,
joint placement, and multiple GPUs remain unsupported by this public path.

Build from the release checkout, then install the wheel:

```sh
uv build --wheel
uv pip install 'dist/sera_inference-0.2.0-py3-none-any.whl[swarm]'
sera-provider-check --help
```

The `swarm` extra installs the checked Weave SDK (0.53.2) and the OpenAI-compatible
client for the optional W&B provider. Importing `sera` does not import Weave, call
a model, or use the GPU. `sera-provider-check` is an installed entry point. It
returns a nonzero exit status when certification fails.

## Choose the investigator provider once

There is no implicit provider or model choice. Set these variables in the GPU
process. Add `WANDB_API_KEY` through the notebook or environment secret facility;
do not put the key in a notebook cell, source file, or saved report.

For the demonstrated local Codex route:

```sh
export SERA_AGENT_PROVIDER=codex-relay
export SERA_AGENT_MODEL=gpt-5.6-luna
export SERA_PROJECT=your-entity/your-project
export SERA_RELAY_DIR=/tmp/sera-relay
export SERA_PROVIDER_CHECK=/absolute/path/to/passing-check/result.json
```

The certificate must match the exact provider, model, project, and current
34-case schemas. Sera recomputes validity; setting a pass flag does not certify
anything. Reuse a matching current certificate, or run the real provider check:

```sh
sera-provider-check --provider codex-relay --model "$SERA_AGENT_MODEL" \
  --project "$SERA_PROJECT" --relay-dir "$SERA_RELAY_DIR" \
  --output-dir /absolute/path/to/new-provider-check
```

This command makes provider requests. The local controller must already be
running and connected to the GPU notebook. It remains **repository tooling**, not
part of the wheel. On the logged-in Codex machine, use the same release checkout
and installed marimo-pair skill, with `MARIMO_TOKEN` supplied securely:

```sh
python -m experiments.codex_relay_controller \
  --url https://YOUR-CURRENT-SERVER.sb.molab.run \
  --relay-dir /tmp/sera-relay \
  --pair-script /absolute/path/to/marimo-pair/scripts/execute-code.sh \
  --output-dir evidence/new-controller-run \
  --max-requests none --idle-timeout 1800
```

The controller and GPU process need the same relay directory. Keep the controller
connected throughout optimization. Codex inference uses the controller machine's
existing login; `WANDB_API_KEY` is still required on the GPU machine for Weave.
Installing the wheel alone does not create this local controller connection.

For hosted W&B investigators, explicitly set `SERA_AGENT_PROVIDER=wandb`, choose
`SERA_AGENT_MODEL`, unset `SERA_RELAY_DIR`, and use a passing W&B certificate for
that identity. No local controller is needed. Run `sera-provider-check --provider
wandb ...` to create that certificate. The saved Codex certificates do not certify
the hosted route or a different model.

## Minimum quick call

After setup, this runs the configured swarm:

```python
import sera

with sera.optimize(
    models=["Qwen/Qwen3-0.6B"],
    prompts=["What is 1 + 1? Return only the number."],
) as result:
    result.print_summary()
    print(result.weave_url)
    if result.models:
        print(result.models[0].generate("What is 2 + 2?").text)
```

Defaults: latency priority, 5% qualifying improvement, concurrency 1/2/4/8,
automatic candidate generation, and no total trial cap. Quick mode checks
deterministic token agreement against baseline outputs. **It does not verify task
correctness.** A rejected candidate or no safe runner is a valid result; inspect
the report rather than assuming `result.models[0]` exists.

The `with` block closes the runner when done. Without it, call `result.close()`.
Optimization writes local JSON and Markdown reports and returns the Weave URL.
The optimization root trace ends before the API returns. Later user calls to
`generate()` and `close()` are not automatically nested under that completed
trace; add separate application tracing when needed.

## Large-model and task-verified calls

Qwen72B cannot use the two-argument quick call. Its BF16 plan does not fit on the
demo card, so there is no local BF16 output baseline for token agreement. Supply
a real evaluator, its version, and an explicit quality floor. Sera first measures
the FP8 weight deployment, then starts the same swarm using that measured plan.
It does not claim a measured speedup over BF16.

```python
with sera.optimize(
    models=["Qwen/Qwen2.5-72B-Instruct"],
    prompts=representative_prompts,
    evaluation=evaluate_answer,  # (original_prompt, output_text) -> bool or [0, 1]
    evaluation_version="my-task-check-v1",
    constraints=sera.Constraints(quality_floor=0.99),
) as result:
    result.print_summary()
```

Use deterministic, task-specific checks. These caller-defined names are not an
included benchmark or proof that arbitrary tasks pass. The saved eight-task live
demonstrations remain separate evidence. Generic Weave reads show saved task
scores and outputs; they do not invent an answer key for the user's evaluator.

## Explicit overrides and compatibility

`mode="auto"` is the public default. If no low-level search option is present,
it uses the configured swarm above. Missing setup fails before any GPU trial;
Sera does not silently switch to a fixed candidate or another provider.

Explicit `candidate`, `agent`, `budget`, `investigation_space`, `automatic_space`,
`swarm`, `trace_reader`, or `baseline_configuration` preserves the older low-level
API, including its validations. This lets existing experiment commands continue
unchanged. To use configured setup with one of these overrides, add
`mode="swarm"` explicitly. For example:

```python
result = sera.optimize(
    models=["Qwen/Qwen3-0.6B"], prompts=prompts,
    mode="swarm", budget=sera.Budget(max_candidate_trials=2),
)
```

That explicit budget caps this call only. The default remains uncapped. A supplied
fixed investigation space stays frozen. `automatic_space=True` with a fixed space
is rejected. An explicit agent and certificate take precedence over environment
defaults in `mode="swarm"`; the supplied provider is never replaced.

`mode="fixed"` selects the original one-candidate comparison with no agent or
Weave dependency. It rejects agent investigation options. Explicit contradictory
modes fail; there is no silent correction.

## Release checks and limits

The clean-install smoke runs outside the checkout, imports the installed wheel,
and exercises the minimum API with **stubbed** GPU, provider, certificate, and
Weave service boundaries. It checks package dependencies, setup, trace hooks,
result ownership, and cleanup. It is not a provider certificate, a latency
measurement, or a live GPU rehearsal.

```sh
uv venv /absolute/path/to/clean-venv
uv pip install --python /absolute/path/to/clean-venv/bin/python \
  'dist/sera_inference-0.2.0-py3-none-any.whl[swarm]'
/absolute/path/to/clean-venv/bin/python -I tests/installed_package_smoke.py
```

Before tagging the final merged release, run the documented task-verified API on
the live GPU, test the returned runner, close it, and save the exact source and
wheel hashes with the report. Earlier successful loops prove the existing swarm;
they do not replace that final live packaging rehearsal.
