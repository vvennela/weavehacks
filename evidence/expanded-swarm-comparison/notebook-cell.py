def show_sera_expanded_comparison():
    """Read saved Sera results. This cell does not launch inference."""
    import json
    from pathlib import Path
    import marimo

    rows = []
    links = []
    for label, name in (
        ("Astra", "live-astra-expanded-v1"),
        ("Luna repeat", "live-luna-expanded-v2"),
    ):
        path = Path("/marimo/sera-evidence") / name / "result.json"
        if not path.exists():
            rows.append(f"| {label} | Not started | — | — | — | — |")
            continue
        report = json.loads(path.read_text())
        baseline = report.get("baseline") or {}
        trials = [baseline, *report.get("search_trials", [])]
        selected = (report.get("decision") or {}).get("selected")
        winner = next((trial for trial in trials if trial.get("trial_id") == selected), {})
        base_p95 = (baseline.get("reduced") or {}).get("p95_latency_ms")
        winner_p95 = (winner.get("reduced") or {}).get("p95_latency_ms")
        score = (winner.get("task_quality") or {}).get("mean")
        quality = "8/8" if score == 1.0 else "Pending"
        gain = f"{100 * (base_p95 - winner_p95) / base_p95:.2f}%" if base_p95 and winner_p95 else "Pending"
        latency = f"{winner_p95:.2f} ms" if winner_p95 else "Pending"
        changes = {key: value for key, value in (winner.get("runtime") or {}).get("configuration", {}).items()
                   if value != (baseline.get("runtime") or {}).get("configuration", {}).get(key)}
        settings = ", ".join(f"{key}={value}" for key, value in changes.items()) or "Pending"
        state = (report.get("search") or {}).get("stop_reason") if report.get("status") == "closed" else "Running"
        rows.append(f"| {label} | {state} | {quality} | {latency} | {gain} | {settings} |")
        if report.get("weave_url"):
            links.append(f"[{label} Weave trace]({report['weave_url']})")
    return marimo.md(
        "# Sera: two three-investigator swarms\n\n"
        "The agents recommend experiments. Measured answer quality and performance decide what Sera returns.\n\n"
        "| Swarm | Stop/state | Tasks | Winning p95 | Lower than baseline | Winning changes |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        + "\n".join(rows)
        + "\n\n" + " · ".join(links)
        + "\n\nEight candidate options per specialist, not eight GPU trials. "
        "Runs use the same eight questions, 99% quality floor, 5% progress threshold, and concurrency 1/2/4/8. "
        "GPU measurements run sequentially.\n\n"
        "Scope: repeated prompts after warmup. Startup is excluded from request latency. "
        "A stop under the plateau rule does not prove global optimality. "
        "Completed runners were tested after return, then closed to release GPU memory.\n\n"
        "The earlier Luna run found an 18.85% caching gain but lost its controller connection before confirmation. "
        "Its evidence remains saved separately. The Luna repeat also needed a manual controller reconnection; "
        "the agents still chose its experiments. Unattended recovery from a long connection outage is not proven. "
        "Re-run this display cell to refresh an in-progress result."
    )

sera_expanded_comparison = show_sera_expanded_comparison()
sera_expanded_comparison
