# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [
#     "marimo==0.24.2",
#     "sera-inference[swarm,litellm] @ git+https://github.com/vvennela/weavehacks.git@e702afb27c8a0b558c63c7b60b8d3dd970ccaf83",
#     "vllm==0.26.0; sys_platform == 'linux'",
#     "torch==2.11.0; sys_platform == 'linux'",
#     "transformers==5.17.0",
#     "flashinfer-python==0.6.14; sys_platform == 'linux'",
#     "nvidia-cuda-nvcc==13.0.88; sys_platform == 'linux'",
#     "nvidia-cuda-crt==13.0.88; sys_platform == 'linux'",
#     "nvidia-nvvm==13.0.88; sys_platform == 'linux'",
#     "nvidia-cuda-runtime==13.0.96; sys_platform == 'linux'",
#     "nvidia-cuda-cccl==13.0.85; sys_platform == 'linux'",
#     "nvidia-curand==10.4.0.35; sys_platform == 'linux'",
# ]
# ///
"""One cloneable Sera notebook. Dependencies install from the metadata above."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium", app_title="FAST_START — Sera agent loop")


@app.cell(hide_code=True)
def _():
    # START HERE: clone the notebook, select a GPU, then enter your own keys.
    import os
    import marimo as mo
    import sera
    from sera.demo import aria_agent_task, aria_review_prompt, prepare_demo

    mo.md("""
    # FAST_START

    ## Clone this notebook first

    **Clone this notebook into your own Molab workspace before adding your API keys.**
    Select the **RTX PRO 6000 GPU**, enter your keys below, then
    **Shift+Enter on either workflow cell**. Run one workflow at a time.
    Molab installs the dependencies. Each workflow downloads missing model files,
    runs Sera, tests the returned runner, and saves 8× and 16× replays.
    Later runs reuse cached model files.

    ## The loop you are running

    **Baseline → three investigators → peer review → validator and arbiter → GPU trial
    → quality and performance checks → Weave evidence → next round.**

    The investigators cover scheduling, memory/context, and output quality.
    Each round uses new measurements to revise proposals. Sera stops after
    confirmed lack of progress or another valid stop condition.

    **Weave** records the run and supplies trace evidence to the investigators.
    **ARIA** reviews the completed trace through your signed-in W&B chat.
    Give the downloaded **ARIA agent task** to a browser-capable agent, or paste
    the review request into Ask ARIA yourself. This is a separate advisory step.
    [Requires an ARIA-enabled W&B Cloud team project](https://docs.wandb.ai/aria/overview).

    **Workload:** Qwen72B · FP8 weights · BF16 cache · 8 exact-answer JSON tasks
    · 99% quality floor · concurrency 1/2/4/8.

    **Cost:** GPU time and hosted investigator calls can cost money.
    **Replay:** offline · recorded results · schematic stage timing.
    """)
    return aria_agent_task, aria_review_prompt, mo, os, prepare_demo, sera


@app.cell(hide_code=True)
def _(mo, os):
    # KEYS: keep credentials in this kernel, never in saved notebook source.
    # Callbacks update the environment without triggering either expensive run cell.
    # Every fresh notebook open requires key entry, even if runtime keys already exist.
    os.environ['SERA_DEMO_READY'] = ''
    _entered = {'OPENAI_API_KEY': '', 'WANDB_API_KEY': '', 'SERA_PROJECT': ''}

    def update_demo_key(name, value):
        _entered[name] = value.strip()
        if value.strip():
            os.environ[name] = value.strip()
        else:
            os.environ.pop(name, None)
        os.environ['SERA_DEMO_READY'] = '1' if all(_entered.values()) else ''

    openai_key = mo.ui.text(kind='password', label='OpenAI API key', full_width=True,
        on_change=lambda value: update_demo_key('OPENAI_API_KEY', value))
    wandb_key = mo.ui.text(kind='password', label='W&B API key', full_width=True,
        on_change=lambda value: update_demo_key('WANDB_API_KEY', value))
    project = mo.ui.text(label='Your Weave entity/project', full_width=True,
        on_change=lambda value: update_demo_key('SERA_PROJECT', value))
    mo.vstack([mo.md('## Add your keys here:'), openai_key, wandb_key, project,
        mo.md('Finish each field by pressing Tab. Then run **one** cell below with Shift+Enter. '
              'Entering keys does not start downloads, provider checks, or GPU experiments. '
              'Only enter keys in your own dedicated runtime; do not share an active keyed session.')])
    return


@app.cell(hide_code=True)
def _(mo):
    # RESULTS: each workflow updates its own tab without starting the other workflow.
    get_demo_runs, set_demo_runs = mo.state({})
    return get_demo_runs, set_demo_runs


@app.cell
def _(aria_agent_task, aria_review_prompt, mo, os, prepare_demo, sera, set_demo_runs):
    # WORKFLOW 1 — LATENCY: Shift+Enter runs this complete workflow.
    # WORKLOAD 1: Qwen2.5-72B, FP8 weights, BF16 KV cache; eight exact-answer JSON tasks.
    # Measure concurrency 1/2/4/8. Reduce p95 response time; preserve 99% task quality.
    # Accept improvements of at least 5%. Save this run's replay in the Run 1 tab below.
    # Check GPU/provider, download missing weights, then measure the baseline.
    # THE LOOP: three agents investigate → propose → review → test → learn → repeat.
    # The quality gate remains fixed. The with block always closes the returned runner.
    mo.stop(os.environ.get('SERA_DEMO_READY') != '1', mo.md('Enter all three fields above first.'))
    _config = prepare_demo(project=os.environ['SERA_PROJECT'], download=True)
    with sera.optimize(
        **_config,
        objective=sera.Objective(priority='latency'),
        min_improvement_pct=5.0,
    ) as latency_result:
        latency_result.print_summary()
        if latency_result.models:
            print(latency_result.models[0].generate(_config['prompts'][0]).text)

    # REPLAY: use this run's real agent decisions and measurements, not canned results.
    _replay8 = sera.visualize(latency_result, speed=8)
    _replay16 = sera.visualize(latency_result, speed=16)
    _replay8.save(latency_result.output_dir / 'latency-demo-8x.html')
    _replay16.save(latency_result.output_dir / 'latency-demo-16x.html')
    _aria_request = aria_review_prompt(latency_result)
    (latency_result.output_dir / 'aria-review-request.md').write_text(_aria_request)
    _aria_task = aria_agent_task(latency_result)
    (latency_result.output_dir / 'aria-agent-task.md').write_text(_aria_task)
    _view = mo.vstack([_replay8,
        mo.download(_replay8.html.encode(), filename='latency-demo-8x.html', label='Download latency demo · 8×'),
        mo.download(_replay16.html.encode(), filename='latency-demo-16x.html', label='Download latency demo · 16×'),
        mo.download(_aria_request.encode(), filename='aria-review-request.md', label='Download manual ARIA review request'),
        mo.download(_aria_task.encode(), filename='aria-agent-task.md', label='Download task for your ARIA browser agent')])
    set_demo_runs(lambda previous: {**previous, 'Run 1': _view})
    mo.md('Run 1 saved. Open the **Run 1** tab below for its replay and downloads.')
    return (latency_result,)


@app.cell
def _(aria_agent_task, aria_review_prompt, mo, os, prepare_demo, sera, set_demo_runs):
    # WORKFLOW 2 — LATENCY THEN THROUGHPUT: Shift+Enter runs both stages in order.
    # WORKLOAD 2: the same Qwen2.5-72B model, precision, eight JSON tasks, and concurrency 1/2/4/8.
    # First reduce p95 response time, then increase output tokens per second.
    # Preserve 99% task quality; throughput may worsen the saved latency by at most 3%.
    # Accept improvements of at least 5%. Save this run's replay in the Run 2 tab below.
    # Stage 1 runs the latency loop. Stage 2 starts from its saved winner and remeasures.
    # k=3 allows at most 3% worse earlier-stage performance, not a required 3% gain.
    # Both stages keep the 99% quality floor. This is a separate run from workflow 1.
    mo.stop(os.environ.get('SERA_DEMO_READY') != '1', mo.md('Enter all three fields above first.'))
    _config = prepare_demo(project=os.environ['SERA_PROJECT'], download=True)
    with sera.optimize(
        **_config,
        stages=['latency', 'throughput'],
        k=3.0,
        min_improvement_pct=5.0,
    ) as staged_result:
        staged_result.print_summary()
        if staged_result.models:
            print(staged_result.models[0].generate(_config['prompts'][0]).text)

    # REPLAY: select either stage to inspect its own proposals, trials, and stop decision.
    _replay8 = sera.visualize(staged_result, speed=8)
    _replay16 = sera.visualize(staged_result, speed=16)
    _replay8.save(staged_result.output_dir / 'latency-throughput-demo-8x.html')
    _replay16.save(staged_result.output_dir / 'latency-throughput-demo-16x.html')
    _aria_request = aria_review_prompt(staged_result)
    (staged_result.output_dir / 'aria-review-request.md').write_text(_aria_request)
    _aria_task = aria_agent_task(staged_result)
    (staged_result.output_dir / 'aria-agent-task.md').write_text(_aria_task)
    _view = mo.vstack([_replay8,
        mo.download(_replay8.html.encode(), filename='latency-throughput-demo-8x.html', label='Download staged demo · 8×'),
        mo.download(_replay16.html.encode(), filename='latency-throughput-demo-16x.html', label='Download staged demo · 16×'),
        mo.download(_aria_request.encode(), filename='aria-review-request.md', label='Download manual ARIA review request'),
        mo.download(_aria_task.encode(), filename='aria-agent-task.md', label='Download task for your ARIA browser agent')])
    set_demo_runs(lambda previous: {**previous, 'Run 2': _view})
    mo.md('Run 2 saved. Open the **Run 2** tab below for its replay and downloads.')
    return (staged_result,)


@app.cell(hide_code=True)
def _(get_demo_runs, mo):
    # RUN TABS: compare the two code examples and download each completed run's own replay.
    # This display reads saved results only. Switching tabs never starts GPU or API work.
    _runs = get_demo_runs()
    _latency = mo.md('''
    ## Run 1 · Latency
    Eight exact-answer JSON tasks on Qwen2.5-72B. Lower p95 response time at
    concurrency 1/2/4/8 while keeping the 99% quality floor.
    ```python
    config = prepare_demo(project=os.environ["SERA_PROJECT"], download=True)
    with sera.optimize(**config, objective=sera.Objective(priority="latency"),
                       min_improvement_pct=5.0) as result:
        result.print_summary()
    sera.visualize(result, speed=8)
    ```
    ''')
    _staged = mo.md('''
    ## Run 2 · Latency → throughput
    The same workload, optimized in two stages. Increase throughput while keeping
    p95 within 3% of the saved latency winner and maintaining the 99% quality floor.
    ```python
    config = prepare_demo(project=os.environ["SERA_PROJECT"], download=True)
    with sera.optimize(**config, stages=["latency", "throughput"], k=3.0,
                       min_improvement_pct=5.0) as result:
        result.print_summary()
    sera.visualize(result, speed=8)
    ```
    ''')
    _pending = mo.md('Run this workflow with **Shift+Enter** in its code cell above. '
                     'Its 8× and 16× replay downloads and ARIA review task appear here after completion.')
    mo.ui.tabs({
        'Run 1': mo.vstack([_latency, _runs.get('Run 1', _pending)]),
        'Run 2': mo.vstack([_staged, _runs.get('Run 2', _pending)]),
    })
    return


if __name__ == "__main__":
    app.run()
