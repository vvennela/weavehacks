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
    mo.md(
        """
        # Sera Lab

        Pick an open-weight model and press **Run**. Sera's specialist agents propose
        one configuration change at a time, every trial is measured on the GPU, and
        anything that breaks the latency target or the quality floor is reverted and
        recorded as such.

        Attach a GPU first: **notebook specs** in the app header → RTX Pro 6000
        Blackwell. Without one this still runs, on the analytic simulator, and says so.
        """
    )
    return


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
        f"### Environment\n\n**GPU** {GPU[0]}, {GPU[1]} GB VRAM"
        if GPU else
        "### Environment\n\n**No GPU attached.** Use the notebook specs button in the "
        "app header to attach an RTX Pro 6000 Blackwell, then re-run this cell. "
        "Everything below still works on the analytic simulator meanwhile."
    )
    return GPU, PY, subprocess


@app.cell(hide_code=True)
def _(GPU, PY, mo, subprocess):
    # Sera comes from the public repo rather than being vendored, so the notebook
    # tracks whatever is on the branch. vLLM is only worth installing when there is
    # a device to run it on; it is a large wheel.
    setup = mo.ui.run_button(label="⚙  Install Sera" + (" and vLLM" if GPU else ""))
    setup
    return (setup,)


@app.cell(hide_code=True)
def _(GPU, PY, mo, setup, subprocess):
    mo.stop(not setup.value, mo.md("*Install once per session, then press Run below.*"))

    _pkgs = ["git+https://github.com/vvennela/weavehacks.git@test1"]
    if GPU:
        _pkgs.append("vllm")

    _log = []
    with mo.status.spinner(title="Installing…") as _s:
        for _pkg in _pkgs:
            _s.update(title=f"Installing {_pkg.split('/')[-1]}…")
            _r = subprocess.run([PY, "-m", "pip", "install", "-q", _pkg],
                                capture_output=True, text=True)
            _log.append(f"{'ok  ' if _r.returncode == 0 else 'FAIL'} {_pkg}")
            if _r.returncode:
                _log.append(_r.stderr[-1500:])

    mo.callout(mo.md("```\n" + "\n".join(_log) + "\n```"),
               kind="success" if all(l.startswith("ok") for l in _log if l[:2] in ("ok", "FA")) else "danger")
    return


@app.cell(hide_code=True)
def _():
    # Embedded because pip installing the package does not carry specs/*.yaml, and
    # fetching them at run time would be one more thing to fail on stage.
    SPECS = {}
    __EMBEDDED_SPECS__
    return (SPECS,)


@app.cell(hide_code=True)
def _(GPU, mo):
    # Time estimates are for a cold run on one Blackwell: weight download, then a
    # vLLM engine start plus CUDA graph capture per trial. They are honest rather
    # than encouraging.
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
    fetch_button = mo.ui.run_button(label="⬇  Download weights")
    run_button = mo.ui.run_button(label="▶  Run Sera")

    mo.vstack([
        model_select,
        mo.hstack([fetch_button, run_button], justify="start", gap=1),
        mo.md(
            "*Downloading first keeps the transfer out of the timed run.*"
            if GPU else
            "*No GPU attached — Run will use the analytic simulator and finish in seconds.*"
        ),
    ])
    return fetch_button, model_select, run_button


@app.cell(hide_code=True)
def _(PY, fetch_button, mo, model_select, subprocess):
    mo.stop(not fetch_button.value, mo.md(""))
    _key, _hf = model_select.value

    with mo.status.spinner(title=f"Downloading {_hf}…"):
        _r = subprocess.run(
            [PY, "-c",
             "import sys;from huggingface_hub import snapshot_download;"
             "snapshot_download(sys.argv[1])", _hf],
            capture_output=True, text=True,
        )
    mo.callout(
        mo.md(f"Weights for `{_hf}` are local." if _r.returncode == 0
              else f"Download failed:\n\n```\n{_r.stderr[-1500:]}\n```"),
        kind="success" if _r.returncode == 0 else "danger",
    )
    return


@app.cell(hide_code=True)
def _(SPECS, model_select):
    import pathlib, tempfile

    from sera.spec import load_spec

    # load_spec reads a file, which is the real entry point; writing the embedded
    # text out keeps that path rather than constructing Spec objects by hand.
    _key, _hf = model_select.value
    _dir = pathlib.Path(tempfile.mkdtemp())
    _path = _dir / f"{_key}.yaml"
    _path.write_text(SPECS[_key])
    spec = load_spec(str(_path))
    model, gpu_spec = spec.models[0], spec.gpus[0]
    slo, floor = spec.slos[0], spec.quality_floors[0]
    workload = spec.workloads[0]
    return floor, gpu_spec, model, slo, spec, workload


@app.cell(hide_code=True)
def _(floor, gpu_spec, mo, model, slo, workload):
    mo.md(
        f"""
        | | |
        |---|---|
        | **Model** | `{model.hf_id}` |
        | **Size** | {model.params_b}B parameters, {model.num_layers} layers, {model.num_kv_heads} KV heads x {model.head_dim} |
        | **Target device** | {gpu_spec.name}, {gpu_spec.vram_gb:.0f} GB |
        | **Workload** | {workload.request_rate_rps} req/s, {workload.input_len_mean} in / {workload.output_len_mean} out, {workload.duration_s}s |
        | **Latency target** | p95 under {slo.p95_latency_ms:.0f} ms |
        | **Quality floor** | {floor.min_score:.3f} |
        """
    )
    return


@app.cell(hide_code=True)
def _(mo, model_select, run_button):
    mo.stop(
        not run_button.value,
        mo.callout(
            mo.md(f"Press **Run Sera** to tune **{model_select.value[1]}**."),
            kind="neutral",
        ),
    )
    return


@app.cell(hide_code=True)
def _(GPU, mo, spec):
    import pathlib as _pl
    import tempfile as _tf
    import time as _time

    from sera.ledger import Ledger
    from sera.phase1 import Phase1
    from sera.runner.sim_runner import SimRunner

    def _runner():
        """Real vLLM when there is a device, the simulator otherwise. Never silent."""
        if not GPU:
            return SimRunner(), "analytic simulator (no GPU attached)"
        from sera.runner.vllm_runner import VllmRunner
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

    _lines = []

    def _show(record):
        _v = str(getattr(record.verdict, "value", record.verdict))
        _m = record.measurement
        _lines.append(
            f"{len(_lines) + 1:>2}. {record.proposing_specialist or 'baseline':<14} "
            f"{_v:<18} "
            + (f"p95 {_m.p95_latency_ms:>8,.0f} ms   {_m.footprint_gb:>6.2f} GB"
               if _m else "not run")
        )
        mo.output.replace(mo.md("```\n" + "\n".join(_lines) + "\n```"))

    _t0 = _time.time()
    ledger = StreamingLedger(_pl.Path(_tf.mkdtemp()) / "molab.jsonl", _show)
    with mo.status.spinner(title=f"Running on {substrate_label}…"):
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
    return elapsed, ledger, rows, substrate_label


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
def _(floor, mo, rows):
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
        **Quality** {_best.quality_score:.3f} against a {floor.min_score:.3f} floor
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
