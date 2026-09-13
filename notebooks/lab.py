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

    LAB = json.loads(r"""{"models":[{"key":"qwen3_8b","label":"Qwen3-8B","vendor":"Alibaba","hf_id":"Qwen/Qwen3-8B","params_b":8.2,"num_layers":36,"num_kv_heads":8,"head_dim":128,"spec_file":"specs/lab_qwen3_8b.yaml","slo_p95_ms":2800.0,"slo_min_throughput_rps":0.8,"quality_floor":0.975,"workload":{"request_rate_rps":1.0,"input_len_mean":1024,"output_len_mean":128,"duration_s":45},"gpu":"RTX PRO 6000 Blackwell","vram_gb":96.0,"substrate":"sim","trials":[{"trial_id":"p1-qwen3_8b-r0-2a0d41","round":0,"verdict":"reverted_slo","specialist":null,"lever":null,"changed":{},"config":{"model":"qwen3_8b","weight_dtype":"bf16","kv_cache_dtype":"bf16","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":3679.7089636710894,"p50_ms":2688.310485460008,"throughput_rps":0.9163969068949795,"footprint_gb":16.848642580725635,"quality_score":1.0,"quality_floor":0.975,"reason":"p95 3680ms vs SLO 2800ms, throughput 0.92 rps","rationale":null,"predicted_pct":null,"confidence":null,"prediction_held":null,"substrate":"sim"},{"trial_id":"p1-qwen3_8b-r1-e8325e","round":1,"verdict":"accepted","specialist":"quantization","lever":"quantization","changed":{"weight_dtype":"fp8"},"config":{"model":"qwen3_8b","weight_dtype":"fp8","kv_cache_dtype":"bf16","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":1585.509749374488,"p50_ms":1126.8218321405393,"throughput_rps":0.9393825203356937,"footprint_gb":8.500521413802435,"quality_score":0.996,"quality_floor":0.975,"reason":"","rationale":"bandwidth at fp8","predicted_pct":45.0,"confidence":0.75,"prediction_held":true,"substrate":"sim"},{"trial_id":"p1-qwen3_8b-r1-0d0da3","round":1,"verdict":"reverted_slo","specialist":"batching","lever":"batching","changed":{"max_num_batched_tokens":1024,"enable_chunked_prefill":true},"config":{"model":"qwen3_8b","weight_dtype":"bf16","kv_cache_dtype":"bf16","max_num_seqs":256,"max_num_batched_tokens":1024,"enable_chunked_prefill":true,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":3681.1970929568024,"p50_ms":2699.2841718885857,"throughput_rps":0.9161735451663553,"footprint_gb":16.847055834763633,"quality_score":1.0,"quality_floor":0.975,"reason":"p95 3681ms vs SLO 2800ms, throughput 0.92 rps","rationale":"chunked prefill stops long prompts from monopolizing steps","predicted_pct":35.0,"confidence":0.65,"prediction_held":false,"substrate":"sim"},{"trial_id":"p1-qwen3_8b-r2-741d9b","round":2,"verdict":"accepted","specialist":"quantization","lever":"quantization","changed":{"weight_dtype":"int8"},"config":{"model":"qwen3_8b","weight_dtype":"int8","kv_cache_dtype":"bf16","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":1691.208361934942,"p50_ms":1179.5139038163356,"throughput_rps":0.9385884837956804,"footprint_gb":8.507208749837538,"quality_score":0.988,"quality_floor":0.975,"reason":"","rationale":"bandwidth at int8","predicted_pct":45.0,"confidence":0.75,"prediction_held":false,"substrate":"sim"},{"trial_id":"p1-qwen3_8b-r2-98e498","round":2,"verdict":"accepted","specialist":"quantization","lever":"quantization","changed":{"weight_dtype":"fp8","kv_cache_dtype":"fp8"},"config":{"model":"qwen3_8b","weight_dtype":"fp8","kv_cache_dtype":"fp8","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":1556.4911918690973,"p50_ms":1064.949288332354,"throughput_rps":0.9398608822045654,"footprint_gb":8.349512487232063,"quality_score":0.994,"quality_floor":0.975,"reason":"","rationale":"KV at 0%; halving cache element size","predicted_pct":40.0,"confidence":0.7,"prediction_held":false,"substrate":"sim"},{"trial_id":"p1-qwen3_8b-r2-fe76fb","round":2,"verdict":"accepted","specialist":"arbiter","lever":"combination","changed":{"weight_dtype":"int8","kv_cache_dtype":"fp8"},"config":{"model":"qwen3_8b","weight_dtype":"int8","kv_cache_dtype":"fp8","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":1655.7810862633442,"p50_ms":1161.935752744867,"throughput_rps":0.938948748607853,"footprint_gb":8.352788510117646,"quality_score":0.986,"quality_floor":0.975,"reason":"","rationale":"bandwidth at int8","predicted_pct":45.0,"confidence":0.75,"prediction_held":false,"substrate":"sim"},{"trial_id":"p1-qwen3_8b-r3-782167","round":3,"verdict":"reverted_quality","specialist":"quantization","lever":"quantization","changed":{"weight_dtype":"int4","kv_cache_dtype":"fp8"},"config":{"model":"qwen3_8b","weight_dtype":"int4","kv_cache_dtype":"fp8","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":1790.3434533897487,"p50_ms":988.4839175478248,"throughput_rps":0.9423432233648777,"footprint_gb":4.250901737368242,"quality_score":0.943,"quality_floor":0.975,"reason":"0.9430 is below the 0.9750 floor \u2014 reverting despite the latency win","rationale":"bandwidth at int4","predicted_pct":45.0,"confidence":0.75,"prediction_held":false,"substrate":"sim"}]},{"key":"deepseek_r1_14b","label":"DeepSeek-R1-Distill-Qwen-14B","vendor":"DeepSeek","hf_id":"deepseek-ai/DeepSeek-R1-Distill-Qwen-14B","params_b":14.8,"num_layers":48,"num_kv_heads":8,"head_dim":128,"spec_file":"specs/lab_deepseek_r1_14b.yaml","slo_p95_ms":4000.0,"slo_min_throughput_rps":0.5,"quality_floor":0.975,"workload":{"request_rate_rps":0.8,"input_len_mean":512,"output_len_mean":160,"duration_s":45},"gpu":"RTX PRO 6000 Blackwell","vram_gb":96.0,"substrate":"sim","trials":[{"trial_id":"p1-deepseek_r1_14b-r0-7d04dd","round":0,"verdict":"reverted_slo","specialist":null,"lever":null,"changed":{},"config":{"model":"deepseek_r1_14b","weight_dtype":"bf16","kv_cache_dtype":"bf16","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":5485.885544244606,"p50_ms":4113.015613855572,"throughput_rps":0.5770795156429239,"footprint_gb":29.870250038613335,"quality_score":1.0,"quality_floor":0.975,"reason":"p95 5486ms vs SLO 4000ms, throughput 0.58 rps","rationale":null,"predicted_pct":null,"confidence":null,"prediction_held":null,"substrate":"sim"},{"trial_id":"p1-deepseek_r1_14b-r1-8c659b","round":1,"verdict":"accepted","specialist":"quantization","lever":"quantization","changed":{"weight_dtype":"fp8"},"config":{"model":"deepseek_r1_14b","weight_dtype":"fp8","kv_cache_dtype":"bf16","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":2449.777347216993,"p50_ms":1968.5873866901647,"throughput_rps":0.6028087294352318,"footprint_gb":14.9696835613535,"quality_score":0.996,"quality_floor":0.975,"reason":"","rationale":"bandwidth at fp8","predicted_pct":45.0,"confidence":0.75,"prediction_held":true,"substrate":"sim"},{"trial_id":"p1-deepseek_r1_14b-r1-618d1f","round":1,"verdict":"reverted_slo","specialist":"batching","lever":"batching","changed":{"max_num_batched_tokens":1024,"enable_chunked_prefill":true},"config":{"model":"deepseek_r1_14b","weight_dtype":"bf16","kv_cache_dtype":"bf16","max_num_seqs":256,"max_num_batched_tokens":1024,"enable_chunked_prefill":true,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":5512.901967244617,"p50_ms":4124.937647900916,"throughput_rps":0.5768340491408841,"footprint_gb":29.868897703743965,"quality_score":1.0,"quality_floor":0.975,"reason":"p95 5513ms vs SLO 4000ms, throughput 0.58 rps","rationale":"chunked prefill stops long prompts from monopolizing steps","predicted_pct":35.0,"confidence":0.65,"prediction_held":false,"substrate":"sim"},{"trial_id":"p1-deepseek_r1_14b-r2-51b0cd","round":2,"verdict":"accepted","specialist":"quantization","lever":"quantization","changed":{"weight_dtype":"int8"},"config":{"model":"deepseek_r1_14b","weight_dtype":"int8","kv_cache_dtype":"bf16","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":2527.4619912858616,"p50_ms":2001.2473517932244,"throughput_rps":0.6025999057810806,"footprint_gb":14.971670199299645,"quality_score":0.988,"quality_floor":0.975,"reason":"","rationale":"bandwidth at int8","predicted_pct":45.0,"confidence":0.75,"prediction_held":false,"substrate":"sim"},{"trial_id":"p1-deepseek_r1_14b-r2-11b7b7","round":2,"verdict":"accepted","specialist":"quantization","lever":"quantization","changed":{"weight_dtype":"fp8","kv_cache_dtype":"fp8"},"config":{"model":"deepseek_r1_14b","weight_dtype":"fp8","kv_cache_dtype":"fp8","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":2420.8551946912185,"p50_ms":1959.4119045473058,"throughput_rps":0.6028997939426695,"footprint_gb":14.884485935254641,"quality_score":0.994,"quality_floor":0.975,"reason":"","rationale":"KV at 0%; halving cache element size","predicted_pct":40.0,"confidence":0.7,"prediction_held":false,"substrate":"sim"},{"trial_id":"p1-deepseek_r1_14b-r2-cd666f","round":2,"verdict":"accepted","specialist":"arbiter","lever":"combination","changed":{"weight_dtype":"int8","kv_cache_dtype":"fp8"},"config":{"model":"deepseek_r1_14b","weight_dtype":"int8","kv_cache_dtype":"fp8","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":2495.8548909287147,"p50_ms":1992.2299062962702,"throughput_rps":0.6026909072019574,"footprint_gb":14.885531521634043,"quality_score":0.986,"quality_floor":0.975,"reason":"","rationale":"bandwidth at int8","predicted_pct":45.0,"confidence":0.75,"prediction_held":false,"substrate":"sim"},{"trial_id":"p1-deepseek_r1_14b-r3-1bf0d7","round":3,"verdict":"reverted_quality","specialist":"quantization","lever":"quantization","changed":{"weight_dtype":"int4","kv_cache_dtype":"fp8"},"config":{"model":"deepseek_r1_14b","weight_dtype":"int4","kv_cache_dtype":"fp8","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":1757.168082276009,"p50_ms":1175.619863754413,"throughput_rps":0.6145137453287214,"footprint_gb":7.467777902767147,"quality_score":0.943,"quality_floor":0.975,"reason":"0.9430 is below the 0.9750 floor \u2014 reverting despite the latency win","rationale":"bandwidth at int4","predicted_pct":45.0,"confidence":0.75,"prediction_held":true,"substrate":"sim"}]},{"key":"moonlight_16b","label":"Moonlight-16B-A3B","vendor":"Moonshot AI (Kimi)","hf_id":"moonshotai/Moonlight-16B-A3B-Instruct","params_b":15.3,"num_layers":27,"num_kv_heads":1,"head_dim":288,"spec_file":"specs/lab_moonlight_16b.yaml","slo_p95_ms":4800.0,"slo_min_throughput_rps":0.7,"quality_floor":0.975,"workload":{"request_rate_rps":0.8,"input_len_mean":768,"output_len_mean":128,"duration_s":45},"gpu":"RTX PRO 6000 Blackwell","vram_gb":96.0,"substrate":"sim","trials":[{"trial_id":"p1-moonlight_16b-r0-adba39","round":0,"verdict":"reverted_slo","specialist":null,"lever":null,"changed":{},"config":{"model":"moonlight_16b","weight_dtype":"bf16","kv_cache_dtype":"bf16","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":6545.908597985535,"p50_ms":4919.744799208938,"throughput_rps":0.8315764221796333,"footprint_gb":30.70977900421773,"quality_score":1.0,"quality_floor":0.975,"reason":"p95 6546ms vs SLO 4800ms, throughput 0.83 rps","rationale":null,"predicted_pct":null,"confidence":null,"prediction_held":null,"substrate":"sim"},{"trial_id":"p1-moonlight_16b-r1-f330ac","round":1,"verdict":"accepted","specialist":"quantization","lever":"quantization","changed":{"weight_dtype":"fp8"},"config":{"model":"moonlight_16b","weight_dtype":"fp8","kv_cache_dtype":"bf16","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":2779.749560006543,"p50_ms":1974.3182387610264,"throughput_rps":0.869194028764789,"footprint_gb":15.356943660726678,"quality_score":0.996,"quality_floor":0.975,"reason":"","rationale":"bandwidth at fp8","predicted_pct":45.0,"confidence":0.75,"prediction_held":true,"substrate":"sim"},{"trial_id":"p1-moonlight_16b-r1-a5f884","round":1,"verdict":"reverted_slo","specialist":"batching","lever":"batching","changed":{"max_num_batched_tokens":1024,"enable_chunked_prefill":true},"config":{"model":"moonlight_16b","weight_dtype":"bf16","kv_cache_dtype":"bf16","max_num_seqs":256,"max_num_batched_tokens":1024,"enable_chunked_prefill":true,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":6567.170041289109,"p50_ms":4994.580967601799,"throughput_rps":0.830800284733721,"footprint_gb":30.710072339511573,"quality_score":1.0,"quality_floor":0.975,"reason":"p95 6567ms vs SLO 4800ms, throughput 0.83 rps","rationale":"chunked prefill stops long prompts from monopolizing steps","predicted_pct":35.0,"confidence":0.65,"prediction_held":false,"substrate":"sim"},{"trial_id":"p1-moonlight_16b-r2-e2730b","round":2,"verdict":"accepted","specialist":"quantization","lever":"quantization","changed":{"weight_dtype":"int8"},"config":{"model":"moonlight_16b","weight_dtype":"int8","kv_cache_dtype":"bf16","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":2944.559476017172,"p50_ms":2064.5897381780533,"throughput_rps":0.8683774009780354,"footprint_gb":15.35881790053232,"quality_score":0.988,"quality_floor":0.975,"reason":"","rationale":"bandwidth at int8","predicted_pct":45.0,"confidence":0.75,"prediction_held":false,"substrate":"sim"},{"trial_id":"p1-moonlight_16b-r2-8e2df4","round":2,"verdict":"accepted","specialist":"quantization","lever":"quantization","changed":{"weight_dtype":"fp8","kv_cache_dtype":"fp8"},"config":{"model":"moonlight_16b","weight_dtype":"fp8","kv_cache_dtype":"fp8","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":2773.5630197520695,"p50_ms":1974.041666752105,"throughput_rps":0.8692346301010422,"footprint_gb":15.328448581834833,"quality_score":0.994,"quality_floor":0.975,"reason":"","rationale":"KV at 0%; halving cache element size","predicted_pct":40.0,"confidence":0.7,"prediction_held":false,"substrate":"sim"},{"trial_id":"p1-moonlight_16b-r2-1fb770","round":2,"verdict":"accepted","specialist":"arbiter","lever":"combination","changed":{"weight_dtype":"int8","kv_cache_dtype":"fp8"},"config":{"model":"moonlight_16b","weight_dtype":"int8","kv_cache_dtype":"fp8","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":2938.1678182693954,"p50_ms":2062.942855921913,"throughput_rps":0.86841792605657,"footprint_gb":15.329359407993252,"quality_score":0.986,"quality_floor":0.975,"reason":"","rationale":"bandwidth at int8","predicted_pct":45.0,"confidence":0.75,"prediction_held":false,"substrate":"sim"},{"trial_id":"p1-moonlight_16b-r3-87aacd","round":3,"verdict":"reverted_quality","specialist":"quantization","lever":"quantization","changed":{"weight_dtype":"int4","kv_cache_dtype":"fp8"},"config":{"model":"moonlight_16b","weight_dtype":"int4","kv_cache_dtype":"fp8","max_num_seqs":256,"max_num_batched_tokens":8192,"enable_chunked_prefill":false,"tensor_parallel_size":1,"pipeline_parallel_size":1,"gpu_memory_utilization":0.9},"p95_ms":2927.3903197481,"p50_ms":1602.3081934920588,"throughput_rps":0.8811399982197522,"footprint_gb":7.676794061214975,"quality_score":0.943,"quality_floor":0.975,"reason":"0.9430 is below the 0.9750 floor \u2014 reverting despite the latency win","rationale":"bandwidth at int4","predicted_pct":45.0,"confidence":0.75,"prediction_held":false,"substrate":"sim"}]}]}""")
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
