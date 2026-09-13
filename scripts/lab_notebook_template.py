import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium", app_title="Sera Lab")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _():
    # Captured runs, embedded so the exported notebook is self-contained and needs
    # no network call in the browser. Regenerate with scripts/build_lab_data.py.
    import json

    LAB = json.loads(r"""__LAB_DATA__""")
    MODELS = {m["key"]: m for m in LAB["models"]}
    return LAB, MODELS


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        # Sera Lab

        Pick an open-weight model and press **Run**. Sera's specialist agents
        propose one configuration change at a time, each trial is measured, and
        anything that breaks the latency target or the quality floor is reverted
        and recorded as such.

        The code below is the code that runs. Nothing here is a mockup.
        """
    )
    return


@app.cell(hide_code=True)
def _(LAB, mo):
    model_select = mo.ui.dropdown(
        options={m["label"]: m["key"] for m in LAB["models"]},
        value=LAB["models"][0]["label"],
        label="Model",
    )
    run_button = mo.ui.run_button(label="▶  Run Sera")
    mo.hstack([model_select, run_button], justify="start", gap=1.5)
    return model_select, run_button


@app.cell(hide_code=True)
def _(MODELS, mo, model_select):
    m = MODELS[model_select.value]
    w = m["workload"]

    _kv = f'{m["num_kv_heads"]} KV heads x {m["head_dim"]}'
    mo.md(
        f"""
        | | |
        |---|---|
        | **Model** | `{m["hf_id"]}` |
        | **Vendor** | {m["vendor"]} |
        | **Size** | {m["params_b"]}B parameters, {m["num_layers"]} layers, {_kv} |
        | **Device** | {m["gpu"]}, {m["vram_gb"]:.0f} GB |
        | **Workload** | {w["request_rate_rps"]} req/s, {w["input_len_mean"]} in / {w["output_len_mean"]} out, {w["duration_s"]}s |
        | **Latency target** | p95 under {m["slo_p95_ms"]:.0f} ms |
        | **Quality floor** | {m["quality_floor"]:.3f} |
        """
    )
    return (m,)


@app.cell(hide_code=True)
def _(m, mo):
    mo.accordion(
        {
            "Show the code this runs": mo.md(
                f"""
        ```bash
        python -m sera --spec {m["spec_file"]} --phase 1 \\
            --ledger runs/lab/{m["key"]}.jsonl --fresh
        ```

        which is this loop, from `src/sera/phase1.py`:

        ```python
        for rnd in range(1, budget.max_rounds + 1):
            digest = reduce_metrics(best_measurement, config, model, gpu, workload)
            proposals = [p for s in ALL_SPECIALISTS for p in s().propose(context)]
            decision = Arbiter().arbitrate(proposals, best_config, remaining_budget)

            for proposal in decision.selected:
                candidate = best_config.with_delta(proposal.delta)
                if not validator.validate(candidate, model, gpu):
                    ledger.append(rejected_on_paper(candidate))   # costs no trial
                    continue
                measurement = runner.run(candidate)               # the only source of numbers
                if measurement.p95_latency_ms > slo.p95_latency_ms:
                    ledger.append(reverted(candidate, Verdict.REVERTED_SLO))
                elif full_eval(candidate) < quality_floor.min_score:
                    ledger.append(reverted(candidate, Verdict.REVERTED_QUALITY))
                else:
                    ledger.append(accepted(candidate, measurement))
        ```
        """
            )
        }
    )
    return


@app.cell(hide_code=True)
def _(m, mo, run_button):
    mo.stop(
        not run_button.value,
        mo.callout(
            mo.md(f"Press **Run Sera** to replay the measured run for **{m['label']}**."),
            kind="neutral",
        ),
    )
    return


@app.cell(hide_code=True)
def _(m, mo):
    VERDICT_LABEL = {
        "accepted": "ACCEPTED",
        "reverted_slo": "REVERTED — latency",
        "reverted_quality": "REVERTED — quality",
        "rejected_paper": "REJECTED — on paper",
        "failed": "FAILED",
    }

    def _fmt(v, digits=0, dash="—"):
        return dash if v is None else f"{v:,.{digits}f}"

    _rows = []
    for t in m["trials"]:
        lever = "baseline" if not t["specialist"] else ", ".join(
            f"{k}={v}" for k, v in t["changed"].items()
        ) or t["lever"]
        held = {True: "held", False: "missed", None: "—"}[t["prediction_held"]]
        _rows.append(
            f'| {t["round"]} | {t["specialist"] or "—"} | `{lever}` | '
            f'{_fmt(t["p95_ms"])} | {_fmt(t["footprint_gb"], 2)} | '
            f'{_fmt(t["quality_score"], 3)} | {VERDICT_LABEL.get(t["verdict"], t["verdict"])} | {held} |'
        )

    mo.md(
        "### Every trial, including the reverts\n\n"
        "| Round | Specialist | Change | p95 (ms) | Memory (GB) | Quality | Verdict | Prediction |\n"
        "|---|---|---|---|---|---|---|---|\n" + "\n".join(_rows)
    )
    return


@app.cell(hide_code=True)
def _(m, mo):
    # Inline SVG rather than a plotting library: this notebook runs under Pyodide
    # in the browser, and a chart that cannot fail to import is worth more here
    # than one with nicer defaults.
    _measured = [t for t in m["trials"] if t["p95_ms"] is not None]
    _slo = m["slo_p95_ms"]
    _top = max([t["p95_ms"] for t in _measured] + [_slo]) * 1.15
    _W, _H, _L, _R, _T, _B = 720, 260, 58, 16, 18, 46

    def _x(i):
        return _L + i * (_W - _L - _R) / max(len(_measured) - 1, 1)

    def _y(v):
        return _H - _B - (v / _top) * (_H - _T - _B)

    _parts = [
        f'<svg viewBox="0 0 {_W} {_H}" role="img" '
        f'aria-label="p95 latency for each trial against the {_slo:.0f} millisecond target">',
        '<style>text{font:11px system-ui;fill:#62716a}</style>',
    ]
    for _i in range(5):
        _v = _top * _i / 4
        _parts.append(
            f'<line x1="{_L}" x2="{_W-_R}" y1="{_y(_v):.1f}" y2="{_y(_v):.1f}" stroke="#dce2d9"/>'
            f'<text x="{_L-8}" y="{_y(_v)+4:.1f}" text-anchor="end">{_v/1000:.1f}s</text>'
        )
    _parts.append(
        f'<line x1="{_L}" x2="{_W-_R}" y1="{_y(_slo):.1f}" y2="{_y(_slo):.1f}" '
        f'stroke="#795889" stroke-width="2" stroke-dasharray="6 4"/>'
        f'<text x="{_W-_R}" y="{_y(_slo)-7:.1f}" text-anchor="end" fill="#795889">'
        f'target {_slo:.0f} ms</text>'
    )
    _pts = " ".join(f"{_x(i):.1f},{_y(t['p95_ms']):.1f}" for i, t in enumerate(_measured))
    _parts.append(f'<polyline fill="none" stroke="#286555" stroke-width="2" points="{_pts}"/>')
    for _i, _t in enumerate(_measured):
        _fill = "#286555" if _t["verdict"] == "accepted" else "#b0553f"
        _lab = "baseline" if not _t["specialist"] else (
            ", ".join(f"{k}={v}" for k, v in _t["changed"].items()) or _t["lever"] or ""
        )
        _parts.append(
            f'<circle cx="{_x(_i):.1f}" cy="{_y(_t["p95_ms"]):.1f}" r="5" fill="{_fill}">'
            f'<title>{_lab} · {_t["p95_ms"]:,.0f} ms · {_t["verdict"]}</title></circle>'
            f'<text x="{_x(_i):.1f}" y="{_H-_B+16:.1f}" text-anchor="middle">{_i}</text>'
        )
    _parts.append(
        f'<text x="{_L}" y="{_H-6}">trial index · green accepted, red reverted</text></svg>'
    )

    mo.md("### Latency across the run\n\n" + "".join(_parts))
    return


@app.cell(hide_code=True)
def _(m, mo):
    _accepted = [t for t in m["trials"] if t["verdict"] == "accepted" and t["p95_ms"]]
    _baseline = m["trials"][0]
    mo.stop(
        not _accepted,
        mo.callout(
            mo.md(
                f"**No safe improvement.** Every candidate for {m['label']} either "
                "missed the latency target or fell through the quality floor, so the "
                "baseline configuration stands."
            ),
            kind="warn",
        ),
    )

    _best = min(_accepted, key=lambda t: t["p95_ms"])
    _lat = (_baseline["p95_ms"] - _best["p95_ms"]) / _baseline["p95_ms"] * 100
    _mem = (_baseline["footprint_gb"] - _best["footprint_gb"]) / _baseline["footprint_gb"] * 100
    _levers = "\n".join(f"- `{k}` → **{v}**" for k, v in _best["changed"].items())
    _reverted = [t for t in m["trials"] if t["verdict"] == "reverted_quality"]
    _note = ""
    if _reverted:
        _r = _reverted[0]
        _note = (
            f"\n\nA faster candidate existed and was rejected: "
            f"`{', '.join(f'{k}={v}' for k, v in _r['changed'].items())}` reached "
            f"{_r['p95_ms']:,.0f} ms but scored {_r['quality_score']:.3f} against a "
            f"{_r['quality_floor']:.3f} floor, so it was reverted."
        )

    mo.callout(
        mo.md(
            f"""
        ### Recommended configuration

        {_levers}

        **p95 latency** {_baseline["p95_ms"]:,.0f} → **{_best["p95_ms"]:,.0f} ms**  ({_lat:.0f}% faster)
        **Memory** {_baseline["footprint_gb"]:.2f} → **{_best["footprint_gb"]:.2f} GB**  ({_mem:.0f}% smaller)
        **Quality** {_best["quality_score"]:.3f} against a {_best["quality_floor"]:.3f} floor{_note}
        """
        ),
        kind="success",
    )
    return


@app.cell(hide_code=True)
def _(m, mo):
    _sub = {
        "sim": (
            "**Analytic simulator.** These numbers come from Sera's continuous-batching "
            "model, not from a GPU. It models the mechanism — weight bytes read per decode "
            "step, prefill FLOPs, cache occupancy — and is deterministic, so the run "
            "reproduces exactly. It is not a hardware benchmark."
        ),
        "vllm": (
            "**Measured on vLLM.** Every number was produced by a real vLLM server on the "
            "device named above, with warm-up requests excluded from the measurement."
        ),
        "fake_vllm": (
            "**Fake vLLM server.** The real vLLM HTTP client and Prometheus parsing ran "
            "against a local stand-in, so the code path is real and the numbers are not."
        ),
    }.get(m["substrate"], f"Substrate: {m['substrate']}.")

    _extra = ""
    if m["key"] == "moonlight_16b":
        _extra = (
            "\n\nThis model uses Multi-head Latent Attention and a mixture of experts. "
            "Its KV cache is modelled with the effective head geometry that reproduces "
            "MLA's true bytes per token, and its compute is modelled across all 15.3B "
            "parameters rather than the ~2.2B active per token, which makes its latency "
            "figures conservative. See `specs/lab_moonlight_16b.yaml` for the arithmetic."
        )

    mo.accordion({"Where these numbers come from": mo.md(_sub + _extra)})
    return


if __name__ == "__main__":
    app.run()
