# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "numpy",
#     "pyyaml",
# ]
# ///

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium", app_title="Sera Lab")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _():
    # Sera's own source, unpacked into the browser's filesystem. The notebook runs
    # the real package: the cells below import it and call Phase1.run(), rather
    # than replaying numbers captured somewhere else.
    # Underscore-prefixed so marimo treats these as cell-local; the same module
    # imported in two cells is a MultipleDefinitionError.
    import base64 as _b64, io as _io, os as _os, sys as _sys
    import tempfile as _tf, zipfile as _zf

    # A temp dir rather than a fixed absolute path: Pyodide would allow "/sera",
    # but the same notebook has to run under a normal interpreter too, where the
    # filesystem root is not writable.
    SERA_ROOT = _os.path.join(_tf.gettempdir(), "sera-lab-src")
    if SERA_ROOT not in _sys.path:
        _zf.ZipFile(
            _io.BytesIO(_b64.b64decode("__SERA_BUNDLE__"))
        ).extractall(SERA_ROOT)
        _sys.path.insert(0, SERA_ROOT)

    import sera
    from sera.ledger import Ledger
    from sera.phase1 import Phase1
    from sera.runner.sim_runner import SimRunner
    from sera.spec import load_spec
    return Ledger, Phase1, SERA_ROOT, SimRunner, load_spec, sera


@app.cell(hide_code=True)
def _(mo, sera):
    mo.md(
        f"""
        # Sera Lab

        Pick an open-weight model and press **Run**. Sera's specialist agents
        propose one configuration change at a time, every trial is measured, and
        anything that breaks the latency target or the quality floor is reverted
        and recorded as such.

        This executes `sera` **{sera.__version__}** in your browser. Nothing below
        is replayed — pressing Run calls `Phase1.run()` and the tables are built
        from the ledger it writes.
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    # Display order is ascending weight size, so the selector reads as a progression.
    CATALOG = {
        "Qwen3-8B": ("lab_qwen3_8b", "Alibaba"),
        "DeepSeek-R1-Distill-Qwen-14B": ("lab_deepseek_r1_14b", "DeepSeek"),
        "Moonlight-16B-A3B": ("lab_moonlight_16b", "Moonshot AI (Kimi)"),
    }
    model_select = mo.ui.dropdown(
        options={k: v[0] for k, v in CATALOG.items()},
        value="Qwen3-8B",
        label="Model",
    )
    run_button = mo.ui.run_button(label="▶  Run Sera")
    mo.hstack([model_select, run_button], justify="start", gap=1.5)
    return CATALOG, model_select, run_button


@app.cell(hide_code=True)
def _(CATALOG, SERA_ROOT, load_spec, mo, model_select):
    spec = load_spec(f"{SERA_ROOT}/specs/{model_select.value}.yaml")
    model, gpu = spec.models[0], spec.gpus[0]
    workload, slo = spec.workloads[0], spec.slos[0]
    floor = spec.quality_floors[0]
    vendor = next(v for _, (k, v) in CATALOG.items() if k == model_select.value)

    mo.md(
        f"""
        | | |
        |---|---|
        | **Model** | `{model.hf_id}` |
        | **Vendor** | {vendor} |
        | **Size** | {model.params_b}B parameters, {model.num_layers} layers, {model.num_kv_heads} KV heads x {model.head_dim} |
        | **Device** | {gpu.name}, {gpu.vram_gb:.0f} GB |
        | **Workload** | {workload.request_rate_rps} req/s, {workload.input_len_mean} in / {workload.output_len_mean} out, {workload.duration_s}s |
        | **Latency target** | p95 under {slo.p95_latency_ms:.0f} ms |
        | **Quality floor** | {floor.min_score:.3f} |
        """
    )
    return floor, gpu, model, slo, spec, workload


@app.cell(hide_code=True)
def _(Phase1, mo):
    import inspect

    # Read off the class that is about to run, so this can never drift from it.
    mo.accordion(
        {
            "Show the code this runs": mo.md(
                "This is `Phase1.tune_model`, read from the module loaded in this "
                "browser with `inspect.getsource` — the function the Run button calls.\n\n"
                "```python\n" + inspect.getsource(Phase1.tune_model) + "\n```"
            )
        }
    )
    return


@app.cell(hide_code=True)
def _(mo, model_select, run_button):
    mo.stop(
        not run_button.value,
        mo.callout(
            mo.md(f"Press **Run Sera** to tune **{model_select.value}** now."),
            kind="neutral",
        ),
    )
    return


@app.cell(hide_code=True)
def _(Ledger, Phase1, SimRunner, mo, spec):
    import tempfile, time
    from pathlib import Path as _Path

    # The actual run. Nothing is cached and nothing is replayed: a fresh ledger
    # every time, so re-running genuinely re-measures.
    _t0 = time.time()
    ledger = Ledger(_Path(tempfile.mkdtemp()) / "lab.jsonl")
    outcomes = Phase1(spec, SimRunner(), ledger, verbose=False).run()
    elapsed = time.time() - _t0
    rows = ledger.all()

    mo.callout(
        mo.md(
            f"Ran **{len(rows)} trials** in **{elapsed:.2f}s**, in this browser. "
            f"Ledger written to `{ledger.path.name}`."
        ),
        kind="info",
    )
    return elapsed, ledger, outcomes, rows


@app.cell(hide_code=True)
def _(mo, rows):
    LABEL = {
        "accepted": "ACCEPTED",
        "reverted_slo": "REVERTED — latency",
        "reverted_quality": "REVERTED — quality",
        "rejected_paper": "REJECTED — on paper",
        "failed": "FAILED",
    }

    def _n(v, d=0):
        return "—" if v is None else f"{v:,.{d}f}"

    _base = rows[0].config
    _out = []
    for _r in rows:
        _m = _r.measurement
        # TrialRecord.config is a plain dict, as stored in the ledger.
        _changed = ", ".join(
            f"{k}={v}" for k, v in _r.config.items()
            if k != "model" and _base.get(k) != v
        ) or "baseline"
        _held = {True: "held", False: "missed", None: "—"}[_r.prediction_held]
        _v = _r.verdict.value if hasattr(_r.verdict, "value") else str(_r.verdict)
        _out.append(
            f"| {_r.round} | {_r.proposing_specialist or '—'} | `{_changed}` | "
            f"{_n(_m.p95_latency_ms) if _m else '—'} | "
            f"{_n(_m.footprint_gb, 2) if _m else '—'} | "
            f"{_n(_r.quality_score, 3)} | {LABEL.get(_v, _v)} | {_held} |"
        )

    mo.md(
        "### Every trial, including the reverts\n\n"
        "| Round | Specialist | Change | p95 (ms) | Memory (GB) | Quality | Verdict | Prediction |\n"
        "|---|---|---|---|---|---|---|---|\n" + "\n".join(_out)
    )
    return


@app.cell(hide_code=True)
def _(mo, rows, slo):
    # Inline SVG rather than a plotting library: one less thing to resolve in the
    # browser, and it cannot fail to import.
    _pts = [r for r in rows if r.measurement]
    _slo = slo.p95_latency_ms
    _top = max([r.measurement.p95_latency_ms for r in _pts] + [_slo]) * 1.15
    _W, _H, _L, _R, _T, _B = 720, 260, 58, 16, 18, 46
    _x = lambda i: _L + i * (_W - _L - _R) / max(len(_pts) - 1, 1)
    _y = lambda v: _H - _B - (v / _top) * (_H - _T - _B)

    _s = [
        f'<svg viewBox="0 0 {_W} {_H}" role="img" aria-label="p95 latency per trial '
        f'against the {_slo:.0f} millisecond target">',
        "<style>text{font:11px system-ui;fill:#62716a}</style>",
    ]
    for _i in range(5):
        _v = _top * _i / 4
        _s.append(
            f'<line x1="{_L}" x2="{_W-_R}" y1="{_y(_v):.1f}" y2="{_y(_v):.1f}" stroke="#dce2d9"/>'
            f'<text x="{_L-8}" y="{_y(_v)+4:.1f}" text-anchor="end">{_v/1000:.1f}s</text>'
        )
    _s.append(
        f'<line x1="{_L}" x2="{_W-_R}" y1="{_y(_slo):.1f}" y2="{_y(_slo):.1f}" '
        f'stroke="#795889" stroke-width="2" stroke-dasharray="6 4"/>'
        f'<text x="{_W-_R}" y="{_y(_slo)-7:.1f}" text-anchor="end" fill="#795889">'
        f"target {_slo:.0f} ms</text>"
    )
    _s.append(
        '<polyline fill="none" stroke="#286555" stroke-width="2" points="'
        + " ".join(f"{_x(i):.1f},{_y(r.measurement.p95_latency_ms):.1f}" for i, r in enumerate(_pts))
        + '"/>'
    )
    for _i, _r in enumerate(_pts):
        _v = _r.verdict.value if hasattr(_r.verdict, "value") else str(_r.verdict)
        _s.append(
            f'<circle cx="{_x(_i):.1f}" cy="{_y(_r.measurement.p95_latency_ms):.1f}" r="5" '
            f'fill="{"#286555" if _v == "accepted" else "#b0553f"}">'
            f"<title>{_r.trial_id} · {_r.measurement.p95_latency_ms:,.0f} ms · {_v}</title></circle>"
            f'<text x="{_x(_i):.1f}" y="{_H-_B+16:.1f}" text-anchor="middle">{_i}</text>'
        )
    _s.append(f'<text x="{_L}" y="{_H-6}">trial index · green accepted, red reverted</text></svg>')

    mo.md("### Latency across the run\n\n" + "".join(_s))
    return


@app.cell(hide_code=True)
def _(floor, mo, rows):
    _ok = [r for r in rows if str(getattr(r.verdict, "value", r.verdict)) == "accepted" and r.measurement]
    _base = rows[0]
    mo.stop(
        not _ok,
        mo.callout(
            mo.md(
                "**No safe improvement.** Every candidate either missed the latency "
                "target or fell through the quality floor, so the baseline stands."
            ),
            kind="warn",
        ),
    )

    _best = min(_ok, key=lambda r: r.measurement.p95_latency_ms)
    _lat = (_base.measurement.p95_latency_ms - _best.measurement.p95_latency_ms) / _base.measurement.p95_latency_ms * 100
    _mem = (_base.measurement.footprint_gb - _best.measurement.footprint_gb) / _base.measurement.footprint_gb * 100
    _levers = "\n".join(
        f"- `{k}` → **{v}**  (was {_base.config.get(k)})"
        for k, v in _best.config.items()
        if k != "model" and _base.config.get(k) != v
    )
    _q = [r for r in rows if str(getattr(r.verdict, "value", r.verdict)) == "reverted_quality"]
    _note = ""
    if _q:
        _r = _q[0]
        _note = (
            f"\n\nA faster candidate existed and was rejected: it reached "
            f"{_r.measurement.p95_latency_ms:,.0f} ms but scored "
            f"{_r.quality_score:.3f} against a {floor.min_score:.3f} floor."
        )

    mo.callout(
        mo.md(
            f"""
        ### Recommended configuration

        {_levers}

        **p95 latency** {_base.measurement.p95_latency_ms:,.0f} → **{_best.measurement.p95_latency_ms:,.0f} ms**  ({_lat:.0f}% faster)
        **Memory** {_base.measurement.footprint_gb:.2f} → **{_best.measurement.footprint_gb:.2f} GB**  ({_mem:.0f}% smaller)
        **Quality** {_best.quality_score:.3f} against a {floor.min_score:.3f} floor{_note}
        """
        ),
        kind="success",
    )
    return


@app.cell(hide_code=True)
def _(mo, model_select, rows):
    _sub = sorted({str(getattr(r.substrate, "value", r.substrate)) for r in rows})
    _extra = ""
    if model_select.value == "lab_moonlight_16b":
        _extra = (
            "\n\nThis model uses Multi-head Latent Attention and a mixture of experts. "
            "Its KV cache is modelled with the effective head geometry that reproduces "
            "MLA's true bytes per token, and its compute is modelled across all 15.3B "
            "parameters rather than the ~2.2B active per token, which makes its latency "
            "figures conservative. See `specs/lab_moonlight_16b.yaml` for the arithmetic."
        )
    mo.accordion(
        {
            "Where these numbers come from": mo.md(
                f"Substrate: **{', '.join(_sub)}**. A browser cannot reach a GPU, so this "
                "runs Sera's analytic simulator — it models the mechanism (weight bytes "
                "read per decode step, prefill FLOPs, cache occupancy) and is "
                "deterministic, so a re-run reproduces exactly. The loop, the specialists, "
                "the arbiter and the gates are the real ones; the substrate underneath "
                "them is a model rather than hardware. For measured numbers, run "
                "`python -m sera --spec <spec> --vllm` on a GPU node." + _extra
            )
        }
    )
    return


if __name__ == "__main__":
    app.run()
