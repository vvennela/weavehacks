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
def _(Path, mo):
    from experiments.investigation_demo import load_investigation_demo

    _view = load_investigation_demo(Path('.'))
    _content = [
        mo.md('# Sera: agents investigate a real workload\n\n' + _view['banner']),
        mo.md('Proposal → arbiter choice → measurement → review → next decision.\n\n' + _view['scope']),
    ]
    if _view['rows']:
        _content.append(mo.ui.table(_view['rows'], selection=None, pagination=False,
                                    label='Saved investigation — proposals are not approvals'))
    _content.append(mo.md(_view['runner'] + '\n\nCandidate trials used: ' + _view['budget']
                         + '. p95 is the time covering 95% of measured requests.\n\n' + _view['limits']))
    if _view['source']:
        _content.append(mo.md(f"Evidence: `{_view['source']}`"))
    if _view['trace_url']:
        _content.append(mo.md(f"[Inspect the real agent trace]({_view['trace_url']})"))
    mo.vstack(_content)
    return


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
        mo.md("## Earlier proof: a large model that fits\n\nRecorded GPU run — not live inference. Qwen2.5-72B, one RTX PRO 6000."),
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




@app.cell
def _(Path, json, mo):
    _comparison = json.loads(Path("evidence/large-batch-comparison-v1/result.json").read_text())
    _rows = []
    for _baseline, _candidate in zip(_comparison['baseline']['loads'], _comparison['candidate_trial']['loads'], strict=True):
        _rows.append({
            'Concurrent requests': _baseline['concurrency'],
            '4096 batch p95 (ms)': round(_baseline['reduced']['p95_latency_ms'], 2),
            '2048 batch p95 (ms)': round(_candidate['reduced']['p95_latency_ms'], 2),
            '4096 output tokens/s': round(_baseline['reduced']['output_tokens_per_second'], 2),
            '2048 output tokens/s': round(_candidate['reduced']['output_tokens_per_second'], 2),
        })
    mo.vstack([
        mo.md("## Two working plans compared\n\nBoth passed all eight tasks. Sera kept batch 4096 because the alternative's throughput gain was only 0.024%, below the 5% requirement. The agent agreed; the returned runner worked."),
        mo.ui.table(_rows, selection=None, pagination=False),
        mo.md(f"Recorded comparison, not live inference or a grid-search win. [Trace]({_comparison['weave_url']}).\n\n**Two-model placement is unfinished:** under the new structured-output profile, GLM passed 8/8 tasks and Qwen0.6B passed 7/8. Qwen still failed filtering, so the pair does not pass the unchanged 99% floor. These isolated results do not replace the earlier failures. No joint run was started. The successful Qwen72B demo remains available.")
    ])
    return

if __name__ == "__main__":
    app.run()
