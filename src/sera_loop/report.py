"""Presentation logic for a SeraResult.

The notebook is a thin shell over these functions. Keeping the rendering here
rather than in notebook cells means it can be tested without launching marimo,
which is the only way to know the demo works before standing in front of it.

Every function is total: it takes any well-formed SeraResult, including one with
no recommendation, no trials, or missing measurements, and returns something
displayable. A presentation layer that can raise is a presentation layer that can
fail live.
"""

from __future__ import annotations

from typing import Any

from .ledger import Verdict
from .types import RunState, SeraResult, Trial

# Callout styling per terminal state. NO_SAFE_IMPROVEMENT is deliberately "info"
# and not "warn": it is an honest answer, not a malfunction.
STATE_KIND: dict[RunState, str] = {
    RunState.IMPROVED: "success",
    RunState.NO_SAFE_IMPROVEMENT: "info",
    RunState.CANCELLED: "warn",
    RunState.FAILED: "danger",
}


def _fmt(value: float | None, suffix: str = "", digits: int = 0) -> str:
    """Format a number, or say it is unavailable.

    Missing measurements print as "unavailable" rather than 0, matching the
    ledger's rule that an unknown value must never read as a measured zero.
    """
    if value is None:
        return "unavailable"
    return f"{value:.{digits}f}{suffix}"


def state_banner(result: SeraResult) -> tuple[str, str]:
    """The headline and its callout kind."""
    return result.headline, STATE_KIND[result.state]


def progress_rows(result: SeraResult) -> list[dict[str, Any]]:
    """One row per executed trial, in the order Sera ran them.

    Deterministic rejections are excluded here on purpose — they never consumed a
    trial slot, and mixing them in would overstate what the GPU actually did.
    """
    rows: list[dict[str, Any]] = []
    for trial in result.trials:
        if not trial.ran:
            continue
        m = trial.measurement
        rows.append(
            {
                "Trial": trial.trial_id,
                "Phase": trial.phase,
                "Proposed by": trial.specialist or "baseline",
                "Lever": trial.lever or "—",
                "Outcome": trial.label,
                "p95 (ms)": _fmt(m.p95_latency_ms if m else None),
                "Memory (GB)": _fmt(m.footprint_gb if m else None, digits=1),
                "Quality": _fmt(trial.quality.score if trial.quality else None, digits=3),
            }
        )
    return rows


def rejection_rows(result: SeraResult) -> list[dict[str, Any]]:
    """Candidates ruled out on arithmetic, before any GPU time was spent."""
    return [
        {
            "Proposed by": r.specialist or "—",
            "Why it was ruled out": r.reason,
        }
        for r in result.rejected
    ]


def failure_rows(result: SeraResult) -> list[dict[str, Any]]:
    """Trials that ran and did not survive, with the reason in user language.

    Separated from `progress_rows` so the notebook can answer "what went wrong"
    without the reader scanning a table of everything.
    """
    rows: list[dict[str, Any]] = []
    for trial in result.trials:
        if trial.verdict in (Verdict.ACCEPTED, Verdict.REJECTED_PAPER):
            continue
        rows.append(
            {
                "Trial": trial.trial_id,
                "What happened": trial.label,
                "Detail": trial.note or "—",
            }
        )
    return rows


def improvement_rows(result: SeraResult) -> list[dict[str, Any]]:
    """Baseline vs recommended, metric by metric.

    Empty when nothing was recommended; the caller shows baselines instead.
    """
    rec = result.recommended
    if rec is None:
        return []
    return [
        {
            "Metric": "p95 latency",
            "Baseline": _fmt(rec.baseline.p95_latency_ms, " ms"),
            "Optimized": _fmt(rec.optimized.p95_latency_ms, " ms"),
            "Change": f"{rec.latency_change_pct:+.1f}%",
        },
        {
            "Metric": "Median latency",
            "Baseline": _fmt(rec.baseline.p50_latency_ms, " ms"),
            "Optimized": _fmt(rec.optimized.p50_latency_ms, " ms"),
            "Change": "—",
        },
        {
            "Metric": "Throughput",
            "Baseline": _fmt(rec.baseline.throughput_rps, " req/s", 1),
            "Optimized": _fmt(rec.optimized.throughput_rps, " req/s", 1),
            "Change": f"{rec.throughput_change_pct:+.1f}%",
        },
        {
            "Metric": "GPU memory",
            "Baseline": _fmt(rec.baseline.footprint_gb, " GB", 1),
            "Optimized": _fmt(rec.optimized.footprint_gb, " GB", 1),
            "Change": f"{rec.memory_change_pct:+.1f}%",
        },
    ]


def baseline_rows(result: SeraResult) -> list[dict[str, Any]]:
    """Baseline measurements, shown when there is no improvement to compare."""
    return [
        {
            "Model": model_id,
            "p95 latency": _fmt(m.p95_latency_ms, " ms"),
            "Throughput": _fmt(m.throughput_rps, " req/s", 1),
            "GPU memory": _fmt(m.footprint_gb, " GB", 1),
        }
        for model_id, m in result.baselines.items()
    ]


def frontier_rows(result: SeraResult) -> list[dict[str, Any]]:
    """Other configurations worth knowing about."""
    return [
        {
            "Configuration": entry.label or entry.model_id,
            "p95 latency": _fmt(entry.measurement.p95_latency_ms, " ms"),
            "GPU memory": _fmt(entry.measurement.footprint_gb, " GB", 1),
            "Quality": _fmt(entry.quality.score, digits=3),
        }
        for entry in result.frontier
    ]


def recommendation_md(result: SeraResult) -> str:
    """What to change, in the user's terms. Never raises when nothing was found."""
    rec = result.recommended
    if rec is None:
        return (
            "**No change recommended.**\n\n"
            "Sera found no configuration that was both faster and safe, so your "
            "models are returned on their baseline settings. The trials below show "
            "what was tried and why each candidate was rejected."
        )

    lines = [f"**Recommended for `{rec.model_id}`**", ""]
    from .config import InferenceConfig

    diff = InferenceConfig(model=rec.configuration.model).diff(rec.configuration)
    if diff:
        for lever, (was, now) in diff.items():
            lines.append(f"- `{lever}`: `{was}` → `{now}`")
    else:
        lines.append("- Baseline configuration was already the best option measured.")

    if rec.rationale:
        lines += ["", f"_{rec.rationale}_"]
    return "\n".join(lines)


def quality_md(result: SeraResult) -> str:
    """The quality gate's finding, including the quick-mode caveat.

    Quick mode must never read as a claim that task quality was verified.
    """
    rec = result.recommended
    if rec is None:
        failures = [t for t in result.trials if t.verdict is Verdict.REVERTED_QUALITY]
        if not failures:
            return "No candidate reached the quality gate."
        lines = ["**No candidate cleared the quality floor.**", ""]
        for trial in failures:
            q = trial.quality
            if q is not None:
                lines.append(
                    f"- `{trial.trial_id}` scored **{q.score:.3f}** "
                    f"against a floor of **{q.floor:.3f}**"
                )
        return "\n".join(lines)

    q = rec.quality
    verdict = "passed" if q.passed else "failed"
    return (
        f"**{q.method}: {q.score:.3f}** against a floor of **{q.floor:.3f}** — {verdict}.\n\n"
        f"{q.caveat}"
    )


def run_details_md(result: SeraResult) -> str:
    """Defaults and environment, which the spec requires be shown, not hidden."""
    lines = [f"- **Mode**: {result.mode}"]
    for key, value in result.report.items():
        lines.append(f"- **{key}**: {value}")
    if result.weave_url:
        lines.append(f"- **Full trace**: [{result.weave_url}]({result.weave_url})")
    return "\n".join(lines)


def usage_snippet(result: SeraResult) -> str:
    """Copyable code answering "what do I use now?".

    The fourth thing a new user needs to know, and the one a table cannot say.
    Returns a runnable example even when nothing was recommended, because the
    baseline models are still handed back and still usable.
    """
    model_ids = [m.model_id for m in result.models] or ["your/model"]
    quoted = ", ".join(f'"{m}"' for m in model_ids)
    lines = [
        "import sera_loop",
        "",
        "result = sera_loop.optimize(",
        f"    models=[{quoted}],",
        '    prompts=["your representative prompt"],',
        ")",
        "",
    ]
    if len(model_ids) == 1:
        lines += [
            "model = result.models[0]",
            'print(model.generate("your prompt here"))',
        ]
    else:
        names = ", ".join(f"model_{chr(ord('a') + i)}" for i in range(len(model_ids)))
        lines += [
            f"{names} = result.models",
            f'print({names.split(", ")[0]}.generate("your prompt here"))',
        ]
    return "\n".join(lines)


def config_snippet(result: SeraResult) -> str:
    """The recommended settings as copyable data.

    Sera owns model loading, so this is for the reader who wants to know exactly
    what changed, or to reproduce the configuration outside Sera.
    """
    rec = result.recommended
    if rec is None:
        if not result.models:
            return "# No configuration to report."
        cfg = result.models[0].configuration
        header = "# No change was recommended. This is the baseline configuration."
    else:
        cfg = rec.configuration
        header = "# Recommended configuration."

    lines = [header, "{"]
    for key, value in cfg.as_dict().items():
        lines.append(f"    {key!r}: {value!r},")
    lines.append("}")
    return "\n".join(lines)


def counts(result: SeraResult) -> dict[str, int]:
    """Headline numbers for the progress strip."""
    return {
        "trials_run": result.trials_run,
        "accepted": sum(1 for t in result.trials if t.verdict is Verdict.ACCEPTED),
        "rolled_back": sum(
            1
            for t in result.trials
            if t.verdict in (Verdict.REVERTED_SLO, Verdict.REVERTED_QUALITY)
        ),
        "failed": sum(1 for t in result.trials if t.verdict is Verdict.FAILED),
        "ruled_out": len(result.rejected),
    }


def describe_trial(trial: Trial) -> str:
    """One line for a live progress feed."""
    who = trial.specialist or "baseline"
    return f"[{trial.trial_id}] {who}: {trial.label}"
