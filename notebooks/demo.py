# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "numpy",
#     "pyyaml",
#     "altair",
#     "pandas",
# ]
# ///
"""Reproducible walkthrough of the two-phase optimization loop.

Runs the real loop — not a recording of one. Every number below is computed when
the cell executes, and re-running with the same spec reproduces it exactly.
"""

import marimo

__generated_with = "0.23.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        # An agentic inference optimization team

        Three specialists tune a model's serving configuration, argue over a bounded
        trial budget, and write every result to a ledger — including the failures.
        A second phase re-reads that ledger asking a *different* question and finds
        out whether two models can share one GPU.

        **Phase 1: how should each model run?**
        **Phase 2: how should they share the hardware?**

        Everything here executes live. Nothing is a recording.
        """
    )
    return


@app.cell
def _():
    # Bootstrap: use the local checkout when running inside the repo, otherwise
    # install the package. molab has no working directory, so it takes the branch.
    import sys
    from pathlib import Path

    _local = Path("../src")
    if _local.exists():
        sys.path.insert(0, str(_local.resolve()))
    elif Path("src").exists():
        sys.path.insert(0, str(Path("src").resolve()))

    try:
        import sera  # noqa: F401

        _source = "local checkout"
    except ImportError:  # pragma: no cover - molab path
        import subprocess

        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q",
             "git+https://github.com/vvennela/sera.git@test1"],
            check=True,
        )
        import sera  # noqa: F401

        _source = "installed from git"

    source = _source
    return (source,)


@app.cell(hide_code=True)
def _(mo, source):
    mo.md(f"*Package loaded from: **{source}***")
    return


@app.cell
def _():
    import altair as alt
    import pandas as pd

    # Validated palette. Categorical slots 1-3 clear every all-pairs gate in both
    # modes; status colors are fixed and always ship beside a text label.
    SERIES_1 = "#2a78d6"   # blue
    SERIES_2 = "#eb6834"   # orange
    SERIES_3 = "#1baf7a"   # aqua
    GOOD = "#0ca30c"
    CRITICAL = "#d03b3b"
    SERIOUS = "#ec835a"
    MUTED = "#898781"
    GRID = "#e1e0d9"

    VERDICT_COLORS = {
        "accepted": GOOD,
        "reverted_slo": CRITICAL,
        "reverted_quality": SERIOUS,
        "rejected_paper": MUTED,
        "failed": MUTED,
    }

    def base_chart(chart, height=260):
        return (
            chart.properties(height=height, width="container")
            .configure_axis(
                grid=True, gridColor=GRID, gridWidth=1,
                domainColor="#c3c2b7", tickColor="#c3c2b7",
                labelColor="#52514e", titleColor="#52514e",
                labelFontSize=11, titleFontSize=11, titleFontWeight="normal",
            )
            .configure_view(strokeWidth=0)
            .configure_legend(
                labelColor="#52514e", titleColor="#52514e",
                labelFontSize=11, titleFontSize=11, titleFontWeight="normal",
                symbolStrokeWidth=0, symbolType="square", symbolSize=110,
            )
        )

    return (
        SERIES_1, SERIES_2, SERIES_3, GOOD, CRITICAL, MUTED,
        VERDICT_COLORS, alt, base_chart, pd,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("## The spec\n\nNothing downstream infers these. If a number matters to a decision, it is declared.")
    return


@app.cell
def _(pd):
    from sera.spec import load_spec

    spec = load_spec("../specs/molab.yaml")

    spec_table = pd.DataFrame(
        [
            {
                "model": m.name,
                "hf_id": m.hf_id,
                "params_B": m.params_b,
                "kv_heads": m.num_kv_heads,
                "rps": spec.workload(m.name).request_rate_rps,
                "input_len": spec.workload(m.name).input_len_mean,
                "output_len": spec.workload(m.name).output_len_mean,
                "p95_SLO_ms": spec.slo(m.name).p95_latency_ms,
                "quality_floor": spec.quality_floor(m.name).min_score,
            }
            for m in spec.models
        ]
    )
    return spec, spec_table


@app.cell(hide_code=True)
def _(mo, spec, spec_table):
    mo.vstack([
        mo.ui.table(spec_table, selection=None),
        mo.md(
            f"**Hardware:** {len(spec.gpus)} x {spec.gpus[0].name}, "
            f"{spec.gpus[0].vram_gb:.0f}GB, {spec.gpus[0].mem_bandwidth_gbs:.0f} GB/s. "
            f"**Budget:** {spec.budget.phase1_trials} phase-1 trials, "
            f"{spec.budget.concurrent_slots} slots per round.\n\n"
            "Note the pairing: **model_a** takes long prompts and short answers "
            "(prefill heavy); **model_b** takes short prompts and long answers "
            "(decode heavy). They stress different parts of the device, which is what "
            "makes the consolidation question interesting rather than obvious."
        ),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## Phase 1 — tune each model alone

        A deterministic reduction turns serving metrics into a shared digest. Three
        specialists read it and each either proposes a single-lever change or declares
        its lever **dead**. The arbiter spends the slots, weighted by whose predictions
        have been holding up. Every outcome is recorded.
        """
    )
    return


@app.cell
def _(spec):
    import tempfile
    from pathlib import Path as _P

    from sera.ledger import Ledger
    from sera.phase1 import Phase1
    from sera.runner.sim_runner import SimRunner

    run_dir = _P(tempfile.mkdtemp(prefix="sera-"))
    runner = SimRunner()
    ledger = Ledger(run_dir / "ledger.jsonl")

    phase1_results = Phase1(spec, runner, ledger, verbose=False).run()
    return Ledger, ledger, phase1_results, run_dir, runner


@app.cell
def _(ledger, pd, spec):
    from sera.config import InferenceConfig

    rows = []
    for _i, _r in enumerate(ledger.all()):
        _m = _r.measurement
        rows.append(
            {
                "n": _i + 1,
                "model": _r.models[0],
                "round": _r.round,
                "proposed_by": _r.proposing_specialist or "baseline",
                "lever": _r.lever or "—",
                "config": InferenceConfig(**_r.config).label().split("[", 1)[1].rstrip("]")
                if isinstance(_r.config.get("model"), str) else "joint",
                "p95_ms": round(_m.p95_latency_ms, 1) if _m else None,
                "footprint_GB": round(_m.footprint_gb, 2) if _m else None,
                "quality": round(_r.quality_score, 4) if _r.quality_score else None,
                "verdict": _r.verdict.value,
                "prediction_held": _r.prediction_held,
                "slo_ms": spec.slo(_r.models[0]).p95_latency_ms,
            }
        )
    ledger_df = pd.DataFrame(rows)
    return (ledger_df,)


@app.cell(hide_code=True)
def _(VERDICT_COLORS, alt, base_chart, ledger_df, mo):
    _d = ledger_df[ledger_df.p95_ms.notna()].copy()

    _bars = (
        alt.Chart(_d)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=26)
        .encode(
            x=alt.X("n:O", title="trial", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("p95_ms:Q", title="p95 latency (ms)", scale=alt.Scale(type="log")),
            color=alt.Color(
                "verdict:N",
                title="verdict",
                scale=alt.Scale(
                    domain=list(VERDICT_COLORS), range=list(VERDICT_COLORS.values())
                ),
            ),
            tooltip=["model", "proposed_by", "lever", "config", "p95_ms",
                     "footprint_GB", "quality", "verdict", "prediction_held"],
        )
    )
    _slo = (
        alt.Chart(_d)
        .mark_rule(strokeDash=[4, 3], strokeWidth=2, color="#52514e")
        .encode(y="slo_ms:Q")
    )
    _chart = (_bars + _slo).facet(
        column=alt.Column("model:N", title=None,
                          header=alt.Header(labelFontSize=12, labelColor="#0b0b0b")),
    ).resolve_scale(x="independent")

    mo.vstack([
        mo.md("**Every trial, including the reverts.** Dashed line is the SLO. Log scale."),
        mo.ui.altair_chart(base_chart(_chart, height=280)),
    ])
    return


@app.cell(hide_code=True)
def _(ledger_df, mo):
    mo.vstack([
        mo.md("Full ledger — the artifact the whole system exists to produce:"),
        mo.ui.table(ledger_df, selection=None, page_size=20),
    ])
    return


@app.cell(hide_code=True)
def _(ledger, mo, phase1_results):
    _lines = []
    for _name, _o in phase1_results.items():
        _lines.append(
            f"- **{_name}**: p95 {_o.baseline.p95_latency_ms:,.0f}ms → "
            f"{_o.best_measurement.p95_latency_ms:,.0f}ms "
            f"({_o.p95_improvement_pct:+.0f}%), footprint "
            f"{_o.baseline.footprint_gb:.2f} → {_o.best_measurement.footprint_gb:.2f}GB  \n"
            f"  `{_o.best_config.label()}`"
        )
    _cal = ledger.summary()["calibration"]
    mo.md(
        "### Phase 1 result\n\n"
        + "\n".join(_lines)
        + "\n\n**Specialist calibration** — the fraction of each agent's predictions "
        "that held, which is what the arbiter weights the next round by:\n\n"
        + "\n".join(f"- `{_k}`: {_v:.2f}" for _k, _v in _cal.items())
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## Phase 2 — can they share a card?

        The frontier reader re-reads the **same ledger** with a different objective:
        not the fastest config, but the smallest one still clearing SLO. That produces
        new knowledge without running a single new trial.
        """
    )
    return


@app.cell
def _(ledger, pd, spec):
    from sera.phase2 import Phase2

    _p2 = Phase2(spec, __import__("sera.runner.sim_runner", fromlist=["SimRunner"]).SimRunner(),
                 ledger, verbose=False)

    frontier_rows = []
    for _name in spec.model_names:
        for _e in _p2.read_frontier(_name):
            frontier_rows.append(
                {
                    "model": _name,
                    "footprint_GB": round(_e.footprint_gb, 2),
                    "p95_ms": round(_e.solo_p95_ms, 1),
                    "devices": _e.config.tensor_parallel_size,
                    "placement": "1 device" if _e.single_device else "2 devices",
                    "config": _e.config.label().split("[", 1)[1].rstrip("]"),
                }
            )
    frontier_df = pd.DataFrame(frontier_rows)
    return Phase2, frontier_df


@app.cell(hide_code=True)
def _(SERIES_1, SERIES_2, alt, base_chart, frontier_df, mo):
    _pts = (
        alt.Chart(frontier_df)
        .mark_point(size=150, filled=True, strokeWidth=2, stroke="#fcfcfb")
        .encode(
            x=alt.X("footprint_GB:Q", title="memory footprint (GB)"),
            y=alt.Y("p95_ms:Q", title="p95 latency (ms)"),
            color=alt.Color(
                "placement:N", title="placement",
                scale=alt.Scale(domain=["1 device", "2 devices"],
                                range=[SERIES_1, SERIES_2]),
            ),
            shape=alt.Shape("placement:N", title="placement"),
            tooltip=["model", "config", "footprint_GB", "p95_ms", "placement"],
        )
    )
    _labels = (
        alt.Chart(frontier_df)
        .mark_text(align="left", dx=10, dy=-6, fontSize=10, color="#52514e")
        .encode(x="footprint_GB:Q", y="p95_ms:Q", text="placement:N")
    )
    _c = (_pts + _labels).facet(
        column=alt.Column("model:N", title=None,
                          header=alt.Header(labelFontSize=12, labelColor="#0b0b0b"))
    ).resolve_scale(x="independent", y="independent")

    mo.vstack([
        mo.md(
            "**The fastest config is the wrong answer here.** Every point cleared SLO "
            "and quality in Phase 1. The ones marked *2 devices* occupy both GPUs — "
            "which is the opposite of what freeing a GPU requires, however fast they are."
        ),
        mo.ui.altair_chart(base_chart(_c, height=280)),
        mo.ui.table(frontier_df, selection=None),
    ])
    return


@app.cell
def _(Phase2, ledger, runner, spec):
    p2_result = Phase2(spec, runner, ledger, verbose=False).run()
    return (p2_result,)


@app.cell
def _(p2_result, pd, spec):
    contention_rows = []
    for _ev in p2_result.evidence:
        contention_rows += [
            {"model": _ev.model, "condition": "alone", "p95_ms": round(_ev.solo_p95_ms, 1),
             "slo_ms": spec.slo(_ev.model).p95_latency_ms},
            {"model": _ev.model, "condition": "sharing a GPU", "p95_ms": round(_ev.joint_p95_ms, 1),
             "slo_ms": spec.slo(_ev.model).p95_latency_ms},
        ]
    contention_df = pd.DataFrame(contention_rows)
    return (contention_df,)


@app.cell(hide_code=True)
def _(SERIES_1, SERIES_2, alt, base_chart, contention_df, mo, p2_result):
    if contention_df.empty:
        _out = mo.md("*No joint trial ran — Phase 2 stopped before contention could be measured.*")
    else:
        _bars = (
            alt.Chart(contention_df)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=44)
            .encode(
                x=alt.X("condition:N", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("p95_ms:Q", title="p95 latency (ms)"),
                color=alt.Color(
                    "condition:N", title="condition",
                    scale=alt.Scale(domain=["alone", "sharing a GPU"],
                                    range=[SERIES_1, SERIES_2]),
                ),
                tooltip=["model", "condition", "p95_ms", "slo_ms"],
            )
        )
        _vals = (
            alt.Chart(contention_df)
            .mark_text(dy=-8, fontSize=11, color="#52514e")
            .encode(x="condition:N", y="p95_ms:Q",
                    text=alt.Text("p95_ms:Q", format=",.0f"))
        )
        _slo = (
            alt.Chart(contention_df)
            .mark_rule(strokeDash=[4, 3], strokeWidth=2, color="#d03b3b")
            .encode(y="slo_ms:Q")
        )
        _c = (_bars + _vals + _slo).facet(
            column=alt.Column("model:N", title=None,
                              header=alt.Header(labelFontSize=12, labelColor="#0b0b0b"))
        ).resolve_scale(y="independent")

        _fit = p2_result.fit_detail
        _out = mo.vstack([
            mo.md(
                f"**The fit check passed with {_fit.get('headroom_gb', 0):.1f}GB to spare.** "
                f"Total {_fit.get('total_gb', 0):.2f}GB against "
                f"{_fit.get('capacity_gb', 0):.1f}GB usable. Memory was never the "
                "question. Red line is the SLO."
            ),
            mo.ui.altair_chart(base_chart(_c, height=290)),
            mo.ui.table(contention_df, selection=None),
        ])
    _out
    return


@app.cell(hide_code=True)
def _(mo, p2_result):
    if p2_result.consolidated:
        _verdict = (
            f"### Verdict: consolidated\n\nBoth models held on one card. "
            f"**{p2_result.gpu_freed} is free.**"
        )
    else:
        _worst = (
            max(p2_result.evidence, key=lambda e: e.p95_inflation_pct)
            if p2_result.evidence else None
        )
        _verdict = f"### Verdict: reverted\n\n{p2_result.reason}\n\n"
        if _worst:
            _verdict += (
                f"**Memory fit was never the binding constraint** — the fit check "
                f"cleared with {p2_result.fit_detail.get('headroom_gb', 0):.1f}GB spare. "
                f"Device-time contention was: `{_worst.model}`'s p95 inflated "
                f"**{_worst.p95_inflation_pct:+.0f}%** beside `{_worst.neighbour}`, "
                f"whose traffic is {_worst.neighbour_prefill_share:.0%} prefill."
            )
    mo.md(_verdict)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## The control arm

        Claiming the agents are better requires something to be better *than*. This
        sweeps the identical lever space, spends the identical budget, and passes the
        identical gates — choosing randomly instead of by reasoning.
        """
    )
    return


@app.cell
def _(Ledger, pd, run_dir, runner, spec):
    import statistics

    from sera.baseline import sweep

    _agent_trials = {}
    for _m in spec.model_names:
        _rows = [r for r in Ledger(run_dir / "ledger.jsonl").for_model(_m) if r.round > 0]
        _agent_trials[_m] = next(
            (i + 1 for i, r in enumerate(_rows) if r.verdict.viable), None
        )

    _cmp = []
    for _m in spec.models:
        _hits = []
        for _s in range(20):
            _sp = spec
            object.__setattr__(_sp, "seed", _s)
            _r = sweep(_sp, _m, runner, Ledger(run_dir / f"b_{_m.name}_{_s}.jsonl"), "random")
            if _r.trials_to_target:
                _hits.append(_r.trials_to_target)
        object.__setattr__(spec, "seed", 7)
        _cmp.append(
            {
                "model": _m.name,
                "agent loop (trials to SLO)": _agent_trials[_m.name],
                "random search — median": statistics.median(_hits) if _hits else None,
                "random search — best": min(_hits) if _hits else None,
                "random search — worst": max(_hits) if _hits else None,
                "seeds where random never reached SLO": 20 - len(_hits),
            }
        )
    comparison_df = pd.DataFrame(_cmp)
    return (comparison_df,)


@app.cell(hide_code=True)
def _(comparison_df, mo):
    mo.vstack([
        mo.ui.table(comparison_df, selection=None),
        mo.md(
            """
            **Random search matches or beats this loop on trials-to-target.**

            The cause is measurable rather than mysterious: at these SLOs, most legal
            configurations already pass, and when most answers are correct, guessing is
            an excellent strategy. This matches the known result that random search is
            very hard to beat in low-dimensional discrete spaces.

            We report this rather than tuning the scenario until the agents win. A
            benchmark adjusted until it flatters the system under test measures nothing.

            **So the claim is not trial efficiency.** It is that Phase 2 is not a search
            problem at all: a sweep has no notion of re-reading its own history under a
            new objective, no fit check, no joint trial, and no way to attribute a
            co-tenancy failure to bandwidth rather than memory.
            """
        ),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## What this demo does not show

        Stated plainly, because a demo that hides its limits is worth less than one
        that names them.

        - **The trials are simulated.** There is no GPU in this run. The simulator models
          continuous batching directly — bandwidth-bound decode, compute-bound prefill,
          KV-capped concurrency, preemption — but it is not a claim to predict absolute
          H100 latency. Every ledger row records which substrate produced it.
        - **The specialists are deterministic heuristics, not LLM agents.** Their
          rationales read well because they were written, not reasoned. Swapping in
          LLM-backed specialists is a drop-in at `Specialist.propose`.
        - **The quality gate is a lookup table.** Accuracy is a function of dtype only,
          so "int4 breaks the floor" is arithmetic rather than a discovery. On real
          hardware this is a real eval.
        - **Co-tenant step times are summed.** Two tenants therefore cost roughly 2x,
          so the direction and mechanism of the contention finding are trustworthy while
          its magnitude is structural.
        """
    )
    return


if __name__ == "__main__":
    app.run()
