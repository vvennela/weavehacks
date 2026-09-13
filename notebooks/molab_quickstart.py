# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo==0.24.2",
#     "sera-inference[swarm,litellm] @ git+https://github.com/vvennela/weavehacks.git@main",
# ]
# ///
"""Two small real Sera examples. Keys start blank; paid work requires a click."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium", app_title="Sera — simple measured inference")


@app.cell
def _():
    import os

    import marimo as mo

    import sera
    from sera.demo import prepare_demo

    return mo, os, prepare_demo, sera


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Clone this notebook first

    **Clone this notebook into your own Molab workspace.** Then add your keys
    below, check the GPU, and run either example. The key fields start empty.
    Do not run experiments in someone else's shared notebook.

    ## Sera: give it a workload, get a measured runner

    **1.** Use the prepared Molab Linux GPU runtime (vLLM 0.26.0, model files cached).
    **2.** Add your keys below and check setup once.
    **3.** Run either example. Each creates a fresh saved run and closes its runner.

    These examples use Qwen72B with FP8 weights and BF16 KV cache, eight easy
    answer checks, and concurrency 1/2/4/8. Replace the workload and evaluator
    for your own application. This is not arbitrary-model or hardware support.

    **Cost:** GPU time and hosted investigator calls can cost money.
    The saved HTML replay needs neither a GPU nor API calls.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    openai_key = mo.ui.text(kind='password', label='OpenAI API key', full_width=True)
    wandb_key = mo.ui.text(kind='password', label='W&B API key', full_width=True)
    project = mo.ui.text(value='vvennela-n-a/wandb_agent_default_project',
                         label='Your Weave entity/project', full_width=True)
    setup_button = mo.ui.run_button(label='Check setup')
    mo.vstack([mo.md('## Add your keys here:'), openai_key, wandb_key, project,
               mo.md('Blank fields use existing runtime environment variables. '
                     'Keys stay in this dedicated kernel; never paste them into source code. '
                     'Setup can make 34 provider-check calls before any GPU experiment.'),
               setup_button])
    return openai_key, project, setup_button, wandb_key


@app.cell(hide_code=True)
def _(mo, openai_key, os, prepare_demo, project, setup_button, wandb_key):
    mo.stop(not setup_button.value, mo.md('Add your keys, then click **Check setup**.'))
    if openai_key.value:
        os.environ['OPENAI_API_KEY'] = openai_key.value
    if wandb_key.value:
        os.environ['WANDB_API_KEY'] = wandb_key.value
    demo_config = prepare_demo(project=project.value)
    mo.md('Setup passed. Choose one example below. No GPU trial has started.')
    return (demo_config,)


@app.cell(hide_code=True)
def _(mo):
    run_latency = mo.ui.run_button(label='Run example 1: latency')
    mo.vstack([mo.md('## Example 1 — faster responses\n'
                     'The three investigators search for lower p95 latency. '
                     'The measured single-stage rehearsal took about 14 minutes including setup; '
                     'a new run can take longer or return no improvement.'), run_latency])
    return (run_latency,)


@app.cell
def _(demo_config, mo, run_latency, sera):
    mo.stop(not run_latency.value)
    with sera.optimize(
        **demo_config,
        objective=sera.Objective(priority='latency'),
        min_improvement_pct=5.0,
    ) as latency_result:
        latency_result.print_summary()
        if latency_result.models:
            print(latency_result.models[0].generate(demo_config['prompts'][0]).text)
    return (latency_result,)


@app.cell
def _(latency_result, sera):
    sera.visualize(latency_result)
    return


@app.cell(hide_code=True)
def _(mo):
    run_stages = mo.ui.run_button(label='Run example 2: latency → throughput')
    mo.vstack([mo.md('## Example 2 — faster responses, then more work per second\n'
                     'Stage two starts from the saved latency winner and remeasures it. '
                     '`k=3` allows at most 3% worse latency while seeking higher throughput. '
                     'Both stages keep the 99% answer-quality floor. '
                     'This sequence is implemented and tested; a live staged speedup is not yet proven. '
                     'Two stages can take longer than the recorded single-stage run. '
                     'Do not start both examples at the same time.'), run_stages])
    return (run_stages,)


@app.cell
def _(demo_config, mo, run_stages, sera):
    mo.stop(not run_stages.value)
    with sera.optimize(
        **demo_config,
        stages=['latency', 'throughput'],
        k=3.0,
        min_improvement_pct=5.0,
    ) as staged_result:
        staged_result.print_summary()
        if staged_result.models:
            print(staged_result.models[0].generate(demo_config['prompts'][0]).text)
    return (staged_result,)


@app.cell
def _(sera, staged_result):
    sera.visualize(staged_result)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## What to change for your application

    `demo_config` contains the model, representative prompts, answer checker,
    quality floor, workload, investigator, and verified provider certificate.
    The two examples pass these same inputs to `sera.optimize`.

    Use `stages=['throughput']` for a throughput-only search, or
    `stages=['latency', 'throughput', 'memory']` to add a memory stage.
    Earlier limits remain in force. A stage can return its baseline if nothing
    better passes; there is no promise of a perfect model or unlimited improvement.

    The `with` block closes the returned runner even if your request fails.
    Keep your application requests inside that block. `sera.visualize(result)`
    afterward uses saved results; it does not make API calls or run more trials.
    """)
    return


if __name__ == "__main__":
    app.run()
