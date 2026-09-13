# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "sera",
# ]
# ///
"""The Sera product experience, end to end.

This notebook talks to Sera through its public API only. It never imports
phase1, phase2, the ledger, a runner, or any other backend module — so it keeps
working while that machinery changes underneath it.

It renders from fixed example data by default, which means the whole story can be
told without a GPU. Switching to a real run is one dropdown, and the only cell
that changes is the single marked construction point below.
"""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo

    import sera
    from sera import fixtures, report

    return fixtures, mo, report, sera


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        # Sera

        Give Sera your models and a few representative prompts. It finds a fast,
        memory-efficient way to run them on the hardware you have, proves the
        change with measurements, and refuses anything that damages quality.

        You do not choose quantization, batching, or parallelism settings.
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## 1. Setup""")
    return


@app.cell
def _(mo):
    models_input = mo.ui.text(
        value="Qwen/Qwen3-0.6B",
        label="Models (comma separated)",
        full_width=True,
    )
    prompts_input = mo.ui.text_area(
        value="Explain paged attention in simple English.\nSummarize why batching affects tail latency.",
        label="Representative prompts (one per line)",
        full_width=True,
    )
    mo.vstack([models_input, prompts_input])
    return models_input, prompts_input


@app.cell
def _(mo):
    # Typed as a password so the key is never rendered into the notebook output.
    # Sera reads WANDB_API_KEY from the environment; this box is only for
    # convenience when running interactively.
    api_key_input = mo.ui.text(
        label="W&B API key (optional, for tracing)",
        kind="password",
        full_width=True,
    )
    api_key_input
    return (api_key_input,)


@app.cell(hide_code=True)
def _(api_key_input, mo):
    import os

    if api_key_input.value:
        os.environ["WANDB_API_KEY"] = api_key_input.value

    _has_key = bool(os.environ.get("WANDB_API_KEY"))
    mo.callout(
        "Tracing enabled — the run will be recorded to Weave."
        if _has_key
        else "No W&B key set. Sera still runs; the trace link will be unavailable.",
        kind="success" if _has_key else "neutral",
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## 2. Run""")
    return


@app.cell
def _(mo):
    source_input = mo.ui.dropdown(
        options={
            "Example data — an improvement": "demo",
            "Example data — no safe improvement": "negative",
            "Live run (needs a backend)": "live",
        },
        value="Example data — an improvement",
        label="Result source",
    )
    source_input
    return (source_input,)


@app.cell
def _(fixtures, models_input, prompts_input, sera, source_input):
    # ---------------------------------------------------------------- THE SWITCH
    # The single construction point. Everything below renders whatever `result`
    # holds, so connecting the real engine changes only this cell.
    #
    # A live run raises SeraBackendUnavailable until a backend is registered.
    # That is caught here and surfaced as a message rather than a traceback: the
    # notebook must degrade to an explanation, never to a broken cell.

    _models = [m.strip() for m in models_input.value.split(",") if m.strip()]
    _prompts = [p.strip() for p in prompts_input.value.splitlines() if p.strip()]

    run_error = None
    if source_input.value == "live":
        try:
            result = sera.optimize(models=_models, prompts=_prompts)
        except (sera.SeraError, ValueError) as exc:
            run_error = str(exc)
            result = fixtures.demo_result()
    elif source_input.value == "negative":
        result = fixtures.no_safe_improvement_result()
    else:
        result = fixtures.demo_result()
    # -------------------------------------------------------------------------
    return result, run_error


@app.cell(hide_code=True)
def _(mo, run_error):
    mo.callout(
        f"Live run unavailable, showing example data instead.\n\n{run_error}",
        kind="warn",
    ) if run_error else None
    return


@app.cell(hide_code=True)
def _(mo, report, result):
    _headline, _kind = report.state_banner(result)
    mo.callout(mo.md(f"### {_headline}"), kind=_kind)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## 3. What Sera did""")
    return


@app.cell(hide_code=True)
def _(mo, report, result):
    _c = report.counts(result)
    mo.hstack(
        [
            mo.stat(_c["trials_run"], label="Trials run"),
            mo.stat(_c["accepted"], label="Accepted"),
            mo.stat(_c["rolled_back"], label="Rolled back"),
            mo.stat(_c["failed"], label="Failed"),
            mo.stat(_c["ruled_out"], label="Ruled out first"),
        ],
        widths="equal",
    )
    return


@app.cell(hide_code=True)
def _(mo, report, result):
    _rows = report.progress_rows(result)
    mo.ui.table(_rows, selection=None) if _rows else mo.md("_No trials executed._")
    return


@app.cell(hide_code=True)
def _(mo, report, result):
    # Deterministic rejections are shown apart from executed trials: they cost no
    # GPU time, and conflating them would overstate what the hardware did.
    _rows = report.rejection_rows(result)
    mo.accordion(
        {
            f"Ruled out before running ({len(_rows)})": mo.ui.table(_rows, selection=None)
            if _rows
            else mo.md("_Nothing was ruled out on paper._")
        }
    )
    return


@app.cell(hide_code=True)
def _(mo, report, result):
    _rows = report.failure_rows(result)
    mo.accordion(
        {
            f"Trials that did not survive ({len(_rows)})": mo.ui.table(_rows, selection=None)
            if _rows
            else mo.md("_Every executed trial was accepted._")
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## 4. Result""")
    return


@app.cell(hide_code=True)
def _(mo, report, result):
    mo.md(report.recommendation_md(result))
    return


@app.cell(hide_code=True)
def _(mo, report, result):
    _rows = report.improvement_rows(result)
    if _rows:
        _out = mo.vstack([mo.md("**Measured improvement**"), mo.ui.table(_rows, selection=None)])
    else:
        _out = mo.vstack(
            [
                mo.md("**Baseline measurements** (unchanged)"),
                mo.ui.table(report.baseline_rows(result), selection=None),
            ]
        )
    _out
    return


@app.cell(hide_code=True)
def _(mo, report, result):
    mo.md(report.quality_md(result))
    return


@app.cell(hide_code=True)
def _(mo, report, result):
    _rows = report.frontier_rows(result)
    mo.vstack(
        [mo.md("**Other configurations on the measured frontier**"), mo.ui.table(_rows, selection=None)]
    ) if _rows else mo.md("_No other configuration passed every gate._")
    return


@app.cell(hide_code=True)
def _(mo, report, result):
    mo.accordion({"Run details and defaults": mo.md(report.run_details_md(result))})
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## 5. Use the optimized model

        Sera returns loaded models, not configuration files. The wrapper hides
        whether vLLM runs in-process or as a managed server.
        """
    )
    return


@app.cell(hide_code=True)
def _(mo, report, result):
    mo.vstack(
        [
            mo.md("**Copy this to use the result in your own code**"),
            mo.ui.code_editor(report.usage_snippet(result), language="python", disabled=True, show_copy_button=True),
            mo.accordion(
                {
                    "Recommended settings, as data": mo.ui.code_editor(
                        report.config_snippet(result), language="python", disabled=True, show_copy_button=True
                    )
                }
            ),
        ]
    )
    return


@app.cell
def _(mo, result):
    # Fixture-backed models return canned text and say so rather than pretending
    # to serve, which is why this is wrapped.
    try:
        _model = result.models[0]
        _answer = _model.generate("Explain paged attention in simple English.")
        _out = mo.md(f"**`{_model.model_id}`**\n\n> {_answer}")
    except Exception as exc:  # noqa: BLE001 - presentation must not break the notebook
        _out = mo.callout(f"No live engine attached: {exc}", kind="neutral")
    _out
    return


if __name__ == "__main__":
    app.run()
