# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "numpy",
#     "pyyaml",
# ]
# ///

"""Sera Lab, on molab.

Runs the real optimization loop against real vLLM on molab's RTX Pro 6000
Blackwell. Attach the GPU with the notebook specs button in the app header before
pressing Run; without one the notebook still works and says it is simulating.

Two controls, deliberately: pick a model, press Run. Installing Sera and vLLM and
pulling the weights used to be separate buttons pressed in the right order. They
are stages of the run now — the run cell does them in order and says which stage
it is on, so there is nothing to get wrong on stage.
"""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium", app_title="Sera Lab — molab")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    import shutil, subprocess, sys

    def _gpu():
        """Read the device from nvidia-smi. Returns (name, vram_gb) or None."""
        if not shutil.which("nvidia-smi"):
            return None
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=20, check=True,
            ).stdout.strip().splitlines()
        except (subprocess.SubprocessError, OSError):
            return None
        if not out:
            return None
        name, mib = (part.strip() for part in out[0].split(",")[:2])
        return name, round(int(mib) / 1024, 1)

    GPU = _gpu()
    PY = sys.executable

    mo.md(
        f"**{GPU[0]}, {GPU[1]} GB** attached — trials are measured on real vLLM."
        if GPU else
        "**No GPU attached.** Use the *notebook specs* button in the app header to "
        "attach an RTX Pro 6000 Blackwell, then re-run this cell. Run still works "
        "meanwhile, on the analytic simulator, and says so in the results."
    )
    return GPU, PY, subprocess


@app.cell(hide_code=True)
def _():
    # Embedded because pip installing the package does not carry specs/*.yaml, and
    # fetching them at run time would be one more thing to fail on stage.
    SPECS = {}
    __EMBEDDED_SPECS__
    return (SPECS,)


@app.cell(hide_code=True)
def _(GPU, mo):
    # Time estimates are for a cold run on one Blackwell: install, weight download,
    # then a vLLM engine start plus CUDA graph capture per trial. They are honest
    # rather than encouraging.
    CATALOG = {
        "Qwen3-8B  ·  16GB  ·  ~15-20 min": ("lab_qwen3_8b", "Qwen/Qwen3-8B"),
        "DeepSeek-R1-Distill-Qwen-14B  ·  30GB  ·  ~25-35 min": (
            "lab_deepseek_r1_14b", "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B"),
        "Moonlight-16B-A3B (Kimi)  ·  31GB  ·  ~25-35 min": (
            "lab_moonlight_16b", "moonshotai/Moonlight-16B-A3B-Instruct"),
    }
    model_select = mo.ui.dropdown(
        options=CATALOG, value=list(CATALOG)[0], label="Model",
    )
    run_button = mo.ui.run_button(label="▶  Run Sera")

    mo.vstack([
        mo.hstack([model_select, run_button], justify="start", gap=1.5),
        mo.md(
            "*Run installs Sera and vLLM, pulls the weights, then tunes. Each stage "
            "reports itself; the timings above are for all three from cold.*"
            if GPU else
            "*No GPU attached — Run will use the analytic simulator and finish in "
            "seconds.*"
        ),
    ])
    return CATALOG, model_select, run_button


@app.cell(hide_code=True)
def _(SPECS, mo, model_select):
    import yaml as _yaml

    # Read straight from the embedded YAML rather than through sera_loop: this has
    # to render before Run, and Sera is not installed until Run installs it.
    SPEC_KEY, HF_ID = model_select.value
    _s = _yaml.safe_load(SPECS[SPEC_KEY])
    _m, _g = _s["models"][0], _s["gpus"][0]
    _w, _slo = _s["workloads"][0], _s["slos"][0]
    _floor = _s["quality_floors"][0]

    mo.md(
        f"""
        | | |
        |---|---|
        | **Model** | `{_m['hf_id']}` |
        | **Size** | {_m['params_b']}B parameters, {_m['num_layers']} layers, {_m['num_kv_heads']} KV heads x {_m.get('head_dim_override', _m['hidden_size'] // _m['num_attn_heads'])} |
        | **Target device** | {_g['name']}, {_g['vram_gb']:.0f} GB |
        | **Workload** | {_w['request_rate_rps']} req/s, {_w['input_len_mean']} in / {_w['output_len_mean']} out, {_w['duration_s']}s |
        | **Latency target** | p95 under {_slo['p95_latency_ms']:.0f} ms |
        | **Quality floor** | {_floor['min_score']:.3f} |
        """
    )
    return HF_ID, SPEC_KEY


@app.cell(hide_code=True)
def _(GPU, HF_ID, PY, SPEC_KEY, SPECS, mo, run_button, subprocess):
    import importlib
    import pathlib as _pl
    import tempfile as _tf
    import time as _time

    # One button, three stages. The gate lives in this cell rather than a cell of
    # its own because marimo stops a cell's descendants, and descendants are found
    # through variables — a gate cell that defines nothing has none. Reading
    # run_button here is also what makes pressing the button re-run this, and what
    # makes changing the model clear the results rather than silently keep stale
    # ones: `run_button.value` has reset to False by then.
    mo.stop(
        not run_button.value,
        mo.callout(
            mo.md(f"Press **Run Sera** to tune `{HF_ID}`."),
            kind="neutral",
        ),
    )

    def _have(module):
        try:
            importlib.import_module(module)
            return True
        except ImportError:
            return False

    _t0 = _time.time()
    _lines = []

    def _log(line):
        _lines.append(line)
        mo.output.replace(mo.md("```\n" + "\n".join(_lines) + "\n```"))

    with mo.status.spinner(title="Installing Sera…") as _spin:
        # Stage 1: install. Skipped outright on a warm session, so pressing Run a
        # second time goes straight to the tuning.
        _pkgs = []
        if not _have("sera_loop"):
            _pkgs.append("git+https://github.com/vvennela/weavehacks.git@test1")
        if GPU and not _have("vllm"):
            _pkgs.append("vllm")
        if not _pkgs:
            _log("ok   Sera" + (" and vLLM" if GPU else "") + " already installed")
        for _pkg in _pkgs:
            _spin.update(title=f"Installing {_pkg.split('/')[-1]}…")
            _r = subprocess.run([PY, "-m", "pip", "install", "-q", _pkg],
                                capture_output=True, text=True)
            _log(f"{'ok  ' if _r.returncode == 0 else 'FAIL'} {_pkg}")
            if _r.returncode:
                _log(_r.stderr[-1500:])
                raise RuntimeError(f"pip install {_pkg} failed")
        importlib.invalidate_caches()

        # Stage 2: weights. Only worth doing when there is a device to serve them
        # from, and kept ahead of the loop so the transfer stays out of the
        # measured trials.
        if GPU:
            _spin.update(title=f"Downloading {HF_ID}…")
            _r = subprocess.run(
                [PY, "-c",
                 "import sys;from huggingface_hub import snapshot_download;"
                 "snapshot_download(sys.argv[1])", HF_ID],
                capture_output=True, text=True,
            )
            if _r.returncode:
                _log(f"FAIL weights for {HF_ID}")
                _log(_r.stderr[-1500:])
                raise RuntimeError(f"downloading {HF_ID} failed")
            _log(f"ok   weights for {HF_ID} are local")

        # Stage 3: the loop itself.
        from sera_loop.ledger import Ledger
        from sera_loop.phase1 import Phase1
        from sera_loop.runner.sim_runner import SimRunner
        from sera_loop.spec import load_spec

        # load_spec reads a file, which is the real entry point; writing the
        # embedded text out keeps that path rather than building Spec objects.
        _dir = _pl.Path(_tf.mkdtemp())
        _path = _dir / f"{SPEC_KEY}.yaml"
        _path.write_text(SPECS[SPEC_KEY])
        spec = load_spec(str(_path))

        def _runner():
            """Real vLLM when there is a device, the simulator otherwise. Never silent."""
            if not GPU:
                return SimRunner(), "analytic simulator (no GPU attached)"
            from sera_loop.runner.vllm_runner import VllmRunner
            r = VllmRunner()
            if not r.available():
                return SimRunner(), "analytic simulator (vLLM not runnable here)"
            return r, f"vLLM on {GPU[0]}"

        runner, substrate_label = _runner()

        class StreamingLedger(Ledger):
            """Render each trial the moment it lands, so a long run stays watchable."""

            def __init__(self, path, on_append):
                super().__init__(path)
                self._on_append = on_append

            def append(self, record):
                record = super().append(record)
                self._on_append(record)
                return record

        _trials = []

        def _show(record):
            _v = str(getattr(record.verdict, "value", record.verdict))
            _m = record.measurement
            _trials.append(
                f"{len(_trials) + 1:>2}. {record.proposing_specialist or 'baseline':<14} "
                f"{_v:<18} "
                + (f"p95 {_m.p95_latency_ms:>8,.0f} ms   {_m.footprint_gb:>6.2f} GB"
                   if _m else "not run")
            )
            mo.output.replace(mo.md("```\n" + "\n".join(_lines + [""] + _trials) + "\n```"))

        _spin.update(title=f"Running on {substrate_label}…")
        ledger = StreamingLedger(_dir / "molab.jsonl", _show)
        Phase1(spec, runner, ledger, verbose=False).run()

    elapsed = _time.time() - _t0
    rows = ledger.all()

    mo.output.replace(
        mo.callout(
            mo.md(f"Ran **{len(rows)} trials** in **{elapsed / 60:.1f} min** "
                  f"on **{substrate_label}**."),
            kind="info",
        )
    )
    return elapsed, ledger, rows, spec, substrate_label


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
        _changed = ", ".join(
            f"{k}={v}" for k, v in _r.config.items()
            if k != "model" and _base.get(k) != v
        ) or "baseline"
        _held = {True: "held", False: "missed", None: "—"}[_r.prediction_held]
        _v = str(getattr(_r.verdict, "value", _r.verdict))
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
def _(mo, rows, spec):
    _floor = spec.quality_floors[0]
    _ok = [r for r in rows
           if str(getattr(r.verdict, "value", r.verdict)) == "accepted" and r.measurement]
    _base = rows[0]
    mo.stop(
        not _ok,
        mo.callout(
            mo.md("**No safe improvement.** Every candidate either missed the latency "
                  "target or fell through the quality floor, so the baseline stands."),
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

    mo.callout(
        mo.md(
            f"""
        ### Recommended configuration

        {_levers}

        **p95 latency** {_base.measurement.p95_latency_ms:,.0f} → **{_best.measurement.p95_latency_ms:,.0f} ms**  ({_lat:.0f}% faster)
        **Memory** {_base.measurement.footprint_gb:.2f} → **{_best.measurement.footprint_gb:.2f} GB**  ({_mem:.0f}% smaller)
        **Quality** {_best.quality_score:.3f} against a {_floor.min_score:.3f} floor
        """
        ),
        kind="success",
    )
    return


@app.cell(hide_code=True)
def _(mo, rows, substrate_label):
    _subs = sorted({str(getattr(r.substrate, "value", r.substrate)) for r in rows})
    mo.accordion(
        {
            "Where these numbers come from": mo.md(
                f"Substrate recorded in the ledger: **{', '.join(_subs)}** "
                f"({substrate_label}).\n\n"
                "`vllm` means each row was produced by a real vLLM server on this "
                "device, with warm-up requests excluded from the measurement. `sim` "
                "means Sera's analytic model produced them — deterministic, and not a "
                "hardware benchmark. The loop, the specialists, the arbiter and the "
                "gates are identical either way; only the thing being measured changes."
            )
        }
    )
    return


if __name__ == "__main__":
    app.run()
