# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [
#     "marimo==0.24.2",
#     "sera-inference[swarm,litellm] @ git+https://github.com/vvennela/weavehacks.git@f6e0ffdda2be7cb90fb3458688e4b5ffdeea9138",
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
    Select the **RTX PRO 6000 GPU** runtime. Molab installs the pinned Python
    dependencies above. No terminal setup is needed. A CPU runtime cannot run this demo.

    Enter your keys below, then **Shift+Enter on either workflow cell**.
    Each cell checks setup, downloads missing Qwen72B files, runs Sera, tests the
    returned runner, and creates its own downloadable 8× and 16× replay.
    Run one workflow at a time. The first download is large; later runs reuse the cache.

    ## The loop you are running

    **Baseline → three investigators → peer review → validator and arbiter → GPU trial
    → quality and performance checks → Weave evidence → next round.**

    The investigators cover scheduling, memory/context, and output quality.
    They use new measurements and trace evidence to revise their proposals.
    Sera stops after confirmed lack of progress or another valid stop condition.
    A failed proposal is evidence, not an improvement.

    **Weave** records the run and supplies trace evidence to the investigators.
    **ARIA** is a separate read-only advisor. Run this notebook in your own Molab
    account with your W&B key, then give the generated **ARIA agent task** to a
    browser-capable agent signed into your W&B account. It opens the Weave trace,
    asks ARIA for a review, and returns the advice. You can also paste the review
    request into ARIA yourself. No automatic ARIA adapter is installed.
    ARIA requires a team project in W&B Cloud with Smart features enabled;
    owning a Molab account or a W&B key alone does not grant that access.
    [ARIA access requirements](https://docs.wandb.ai/aria/overview).
    The replay says "no review recorded" until a real review is separately recorded;
    it does not credit ARIA with Sera's decisions or measured gains.

    These examples use Qwen72B with FP8 weights and BF16 cache, eight exact-answer
    JSON questions, a 99% quality floor, and concurrency 1/2/4/8.
    This is the tested workload, not support for arbitrary models or hardware.

    **Cost:** GPU time and hosted investigator calls can cost money.
    Replays run offline. Playback speed changes the animation, not GPU execution time.
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


@app.cell
def _(aria_agent_task, aria_review_prompt, mo, os, prepare_demo, sera):
    # WORKFLOW 1 — LATENCY: Shift+Enter runs this complete workflow.
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
    mo.vstack([_replay8,
        mo.download(_replay8.html.encode(), filename='latency-demo-8x.html', label='Download latency demo · 8×'),
        mo.download(_replay16.html.encode(), filename='latency-demo-16x.html', label='Download latency demo · 16×'),
        mo.download(_aria_request.encode(), filename='aria-review-request.md', label='Download manual ARIA review request'),
        mo.download(_aria_task.encode(), filename='aria-agent-task.md', label='Download task for your ARIA browser agent')])
    return (latency_result,)


@app.cell
def _(aria_agent_task, aria_review_prompt, mo, os, prepare_demo, sera):
    # WORKFLOW 2 — LATENCY THEN THROUGHPUT: Shift+Enter runs both stages in order.
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
    mo.vstack([_replay8,
        mo.download(_replay8.html.encode(), filename='latency-throughput-demo-8x.html', label='Download staged demo · 8×'),
        mo.download(_replay16.html.encode(), filename='latency-throughput-demo-16x.html', label='Download staged demo · 16×'),
        mo.download(_aria_request.encode(), filename='aria-review-request.md', label='Download manual ARIA review request'),
        mo.download(_aria_task.encode(), filename='aria-agent-task.md', label='Download task for your ARIA browser agent')])
    return (staged_result,)


if __name__ == "__main__":
    app.run()
