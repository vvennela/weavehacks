# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo==0.24.0"]
# ///

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    from pathlib import Path

    import marimo as mo
    return Path, json, mo


@app.cell
def _(Path, json):
    # Run from the repository root. This view never starts a GPU or calls an LM.
    sera_large_fit_result = json.loads(Path("evidence/large-fit-v1/result.json").read_text())
    return (sera_large_fit_result,)


@app.cell
def _(mo, sera_large_fit_result):
    _trial = sera_large_fit_result['candidate_trial']
    _metrics = _trial['reduced']
    _runtime = _trial['runtime']
    _plan = sera_large_fit_result['fit_plan']
    _rows = [
        {'Plan': item['plan_id'], 'Estimated GiB': round(item['estimated_peak_bytes'] / 1024**3, 2),
         'Estimated fit': item['estimated_fit']}
        for item in _plan['plans']
    ]
    mo.vstack([
        mo.md("# Sera: a large model that fits\n\nRecorded GPU run — not live inference. Qwen2.5-72B, one RTX PRO 6000."),
        mo.md("BF16 cannot fit → agent selects FP8 weights → online quantization → task gate → usable runner."),
        mo.ui.table(_rows, selection=None, pagination=False),
        mo.md(f"**8/8 tasks passed.** p95: {_metrics['p95_latency_ms']:.0f} ms · output throughput: {_metrics['output_tokens_per_second']:.2f} tokens/s · peak GPU memory: {_runtime['sampled_peak_memory_mib']/1024:.2f} GiB.\n\nFresh returned-runner request passed. Startup: {_runtime['startup_seconds']:.1f} s after download. Runner closed; cleanup passed."),
        mo.md(f"[Inspect the real Weave trace]({sera_large_fit_result['weave_url']})\n\nOne feasible candidate proves deployment, not best-plan search or speedup. Memory estimates are not hard caps. The original final-agent review had an ambiguous prediction contract; its raw result is preserved.")
    ])
    return


@app.cell
def _(json, mo, sera_large_fit_result):
    _outputs = sera_large_fit_result['candidate_trial']['quality']
    _checks = sera_large_fit_result['candidate_trial']['task_quality']['per_prompt']
    mo.ui.table([
        {'Task': case['id'], 'Expected': json.dumps(case['expected']), 'Raw output': output['text'], 'Passed': check['score'] == 1.0}
        for case, output, check in zip(sera_large_fit_result['evaluation_cases'], _outputs, _checks, strict=True)
    ], selection=None, pagination=False, label='Saved task acceptance — no output repair')
    return


@app.cell
def _(Path, json, mo):
    _review = json.loads(Path("evidence/large-fit-review-v2/result.json").read_text())
    mo.md(
        "## Corrected agent review\n\n"
        + _review["agent_final"]["reason"]
        + "\n\nThis is a separate LM review of the saved GPU evidence, not a new GPU run. "
        + f"[Review trace]({_review['weave_url']})."
    )
    return


if __name__ == "__main__":
    app.run()
