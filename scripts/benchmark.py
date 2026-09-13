"""Run Sera against its controls on one trial budget, and write the dataset the
benchmark view reads.

Why this exists as a separate harness rather than a flag on the loop: the controls
must not share state with Sera. Each arm gets its own ledger file, so nothing one arm
learned can leak into another, and every curve in the output is reconstructed from
recorded trials rather than from a summary the arm reported about itself.

Four arms, all spending the same budget through the same validator, runner and gates:

    sera     the agent loop
    grid     fixed-order sweep of the identical lever space
    random   the same sweep, shuffled, over N seeds
    oracle   exhaustive — every legal config measured, no budget

Plus two ablations of Sera itself, each removing one input and nothing else:

    no telemetry feedback   specialists keep seeing the baseline measurement, so a
                            trial's result never reaches the next proposal
    no calibration history  the arbiter ranks proposals without knowing whose past
                            predictions held

Run it:

    PYTHONPATH=src python scripts/benchmark.py --spec specs/tight.yaml

Output lands in runs/benchmark.json and is committed, so the notebook renders the
charts with no GPU and no rerun.
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from sera_loop import baseline
from sera_loop.arbiter import Arbiter
from sera_loop.config import InferenceConfig, baseline_config
from sera_loop.ledger import Ledger, TrialRecord, Verdict
from sera_loop.phase1 import Phase1
from sera_loop.quality import full_eval, smoke_check
from sera_loop.runner.base import Tenant, TrialRunner
from sera_loop.runner.sim_runner import SimRunner
from sera_loop.spec import ModelSpec, Spec, load_spec

SCHEMA_VERSION = 1

# A config within this much of the oracle is "as good as the best available". Tuning
# past it is not a difference a user would notice, and holding every arm to the exact
# oracle would reward luck on the last decimal.
NEAR_ORACLE_TOLERANCE = 1.05


# ----------------------------------------------------------------- curve building


def _curve(records: list[TrialRecord]) -> list[dict[str, Any]]:
    """Best valid p95 after each executed trial, in the order the arm ran them.

    Paper rejections are excluded because they cost no trial — counting them would
    flatter whichever arm proposed the most illegal configs. They are reported
    separately instead.
    """
    rows: list[dict[str, Any]] = []
    best: float | None = None

    for n, rec in enumerate((r for r in records if r.verdict.ran), start=1):
        p95 = rec.measurement.p95_latency_ms if rec.measurement else None
        if rec.verdict is Verdict.ACCEPTED and p95 is not None:
            best = p95 if best is None else min(best, p95)
        rows.append(
            {
                "trial": n,
                "p95_ms": p95,
                "best_valid_p95_ms": best,
                "verdict": rec.verdict.value,
                "quality_failed": rec.verdict is Verdict.REVERTED_QUALITY,
                "lever": rec.lever,
                "specialist": rec.proposing_specialist,
            }
        )
    return rows


def _trials_to(curve: list[dict[str, Any]], threshold: float) -> int | None:
    """First trial whose best-valid p95 is at or under the threshold. None means never."""
    for row in curve:
        best = row["best_valid_p95_ms"]
        if best is not None and best <= threshold:
            return row["trial"]
    return None


def _arm(records: list[TrialRecord], near_oracle_ms: float, slo_ms: float) -> dict[str, Any]:
    curve = _curve(records)
    best = next(
        (r["best_valid_p95_ms"] for r in reversed(curve) if r["best_valid_p95_ms"] is not None),
        None,
    )
    return {
        "curve": curve,
        "trials_run": len(curve),
        "paper_rejections": sum(1 for r in records if r.verdict is Verdict.REJECTED_PAPER),
        "quality_failures": sum(1 for r in curve if r["quality_failed"]),
        "best_valid_p95_ms": best,
        "trials_to_slo": _trials_to(curve, slo_ms),
        "trials_to_near_oracle": _trials_to(curve, near_oracle_ms),
        "reached_slo": best is not None and best <= slo_ms,
    }


# ----------------------------------------------------------------------- the arms


def _fresh(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    return path


@contextmanager
def _frozen_telemetry() -> Iterator[None]:
    """Freeze each model's digest at its baseline measurement.

    Specialists still see the live config, the model and the GPU — only the measured
    consequence of the last trial is withheld. That isolates the feedback loop rather
    than lobotomising the specialists, which would prove nothing.
    """
    from sera_loop import phase1 as phase1_module

    real = phase1_module.reduce_metrics
    first: dict[str, Any] = {}

    def frozen(measurement, cfg, model, gpu, workload, slo, available_gpus=1):  # noqa: ANN001
        first.setdefault(model.name, measurement)
        return real(
            first[model.name], cfg, model, gpu, workload, slo, available_gpus=available_gpus
        )

    phase1_module.reduce_metrics = frozen
    try:
        yield
    finally:
        phase1_module.reduce_metrics = real


def run_sera(
    spec: Spec,
    runner: TrialRunner,
    ledger_path: Path,
    *,
    telemetry: bool = True,
    calibration: bool = True,
) -> Ledger:
    """Phase 1 over every model in the spec, into a ledger of its own."""
    ledger = Ledger(_fresh(ledger_path))
    loop = Phase1(spec, runner, ledger, verbose=False)

    if not calibration:
        # A ledger the arbiter reads but nothing writes to: every specialist stays at
        # the 0.5 default forever, so ranking cannot use a track record.
        blind = Ledger(_fresh(ledger_path.with_name(ledger_path.stem + "_blind.jsonl")))
        loop.arbiter = Arbiter(blind, slots=spec.budget.concurrent_slots)

    if telemetry:
        loop.run()
    else:
        with _frozen_telemetry():
            loop.run()
    return ledger


def run_sweep(
    spec: Spec,
    runner: TrialRunner,
    ledger_path: Path,
    strategy: str,
    order_seed: int | None = None,
) -> Ledger:
    ledger = Ledger(_fresh(ledger_path))
    for model in spec.models:
        baseline.sweep(spec, model, runner, ledger, strategy=strategy, order_seed=order_seed)
    return ledger


def oracle(spec: Spec, model: ModelSpec, runner: TrialRunner) -> dict[str, Any]:
    """Measure every legal configuration. No budget — this is the number to beat.

    Exhaustive search is what none of the arms can afford; running it here is how we
    know whether a budgeted arm found the good region or merely a mediocre one.
    """
    gpu = spec.gpus[0]
    slo = spec.slo(model.name)
    floor = spec.quality_floor(model.name)
    configs = baseline._all_configs(model)

    legal = 0
    qualifying: list[tuple[float, InferenceConfig]] = []

    for cfg in configs:
        from sera_loop.validator import validate

        if not validate(cfg, model, gpu, available_gpus=len(spec.gpus)).ok:
            continue
        legal += 1
        if not smoke_check(cfg, floor).passed:
            continue
        outcome = runner.run([Tenant(model, cfg, spec.workload(model.name))], gpu, seed=spec.seed)
        if not outcome.ok:
            continue
        meas = outcome.measurements[model.name]
        if meas.p95_latency_ms > slo.p95_latency_ms:
            continue
        if slo.min_throughput_rps is not None and meas.throughput_rps < slo.min_throughput_rps:
            continue
        if not full_eval(cfg, floor).passed:
            continue
        qualifying.append((meas.p95_latency_ms, cfg))

    qualifying.sort(key=lambda pair: pair[0])
    best_p95, best_cfg = qualifying[0] if qualifying else (None, None)

    return {
        "p95_ms": best_p95,
        "config": best_cfg.as_dict() if best_cfg else None,
        "enumerated_configs": len(configs),
        "legal_configs": legal,
        "qualifying_configs": len(qualifying),
        "qualifying_pct": round(100.0 * len(qualifying) / max(len(configs), 1), 1),
    }


# -------------------------------------------------------------------- the dataset


def build(spec_path: str, seeds: int, out_path: Path) -> dict[str, Any]:
    spec = load_spec(spec_path)
    runner = SimRunner()
    work = out_path.parent / "benchmark_arms"
    if work.exists():
        shutil.rmtree(work)

    started = time.time()

    print(f"  oracle       exhaustive over the lever space, {len(spec.models)} models")
    oracles = {m.name: oracle(spec, m, runner) for m in spec.models}
    for name, o in oracles.items():
        print(
            f"    {name:10} best valid p95 {o['p95_ms']:.0f}ms  "
            f"({o['qualifying_configs']}/{o['enumerated_configs']} configs qualify, "
            f"{o['qualifying_pct']}%)"
        )

    print("  sera         the agent loop")
    sera_led = run_sera(spec, runner, work / "sera_loop.jsonl")

    print("  grid         fixed-order sweep")
    grid_led = run_sweep(spec, runner, work / "grid.jsonl", "grid")

    print(f"  random       shuffled sweep, {seeds} seeds")
    # Only the order varies. The measurement seed stays at spec.seed for every arm,
    # so the oracle remains an upper bound that none of them can accidentally beat.
    random_leds = [
        run_sweep(spec, runner, work / f"random_{s}.jsonl", "random", order_seed=s)
        for s in range(seeds)
    ]

    print("  ablation     no telemetry feedback")
    no_tel_led = run_sera(spec, runner, work / "no_telemetry.jsonl", telemetry=False)

    print("  ablation     no calibration history")
    no_cal_led = run_sera(spec, runner, work / "no_calibration.jsonl", calibration=False)

    models: dict[str, Any] = {}
    for model in spec.models:
        name = model.name
        slo = spec.slo(name)
        o = oracles[name]
        near = (o["p95_ms"] or float("inf")) * NEAR_ORACLE_TOLERANCE

        base_cfg = baseline_config(model)
        base_out = runner.run(
            [Tenant(model, base_cfg, spec.workload(name))], spec.gpus[0], seed=spec.seed
        )
        base_p95 = base_out.measurements[name].p95_latency_ms if base_out.ok else None

        seed_arms = [
            {"seed": s, **_arm(led.for_model(name), near, slo.p95_latency_ms)}
            for s, led in enumerate(random_leds)
        ]
        reached = [a["trials_to_near_oracle"] for a in seed_arms if a["trials_to_near_oracle"]]

        models[name] = {
            "hf_id": model.hf_id,
            "slo_p95_ms": slo.p95_latency_ms,
            "quality_floor": spec.quality_floor(name).min_score,
            "baseline_p95_ms": base_p95,
            "oracle": o,
            "near_oracle_p95_ms": near if o["p95_ms"] else None,
            "arms": {
                "sera": _arm(sera_led.for_model(name), near, slo.p95_latency_ms),
                "grid": _arm(grid_led.for_model(name), near, slo.p95_latency_ms),
            },
            "random": {
                "seeds": seed_arms,
                "seed_count": len(seed_arms),
                "reached_near_oracle": len(reached),
                # Two different failures, kept apart. Missing the SLO means the seed
                # found nothing usable at all; missing near-oracle means it found
                # something usable but never the good region inside the budget.
                "missed_near_oracle": len(seed_arms) - len(reached),
                "missed_slo": sum(1 for a in seed_arms if not a["reached_slo"]),
                "median_trials_to_near_oracle": statistics.median(reached) if reached else None,
            },
            "ablations": {
                "no_telemetry": _arm(no_tel_led.for_model(name), near, slo.p95_latency_ms),
                "no_calibration": _arm(no_cal_led.for_model(name), near, slo.p95_latency_ms),
            },
        }

    data = {
        "schema_version": SCHEMA_VERSION,
        "spec": spec_path,
        "spec_name": spec.meta.get("name", spec_path) if isinstance(spec.meta, dict) else spec_path,
        "substrate": runner.substrate.value,
        "budget_trials": spec.budget.phase1_trials,
        "near_oracle_tolerance": NEAR_ORACLE_TOLERANCE,
        "random_seeds": seeds,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wall_clock_s": round(time.time() - started, 1),
        "models": models,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2) + "\n")
    shutil.rmtree(work, ignore_errors=True)
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="benchmark", description=__doc__)
    ap.add_argument("--spec", default="specs/tight.yaml")
    ap.add_argument("--seeds", type=int, default=30, help="random-search seeds")
    ap.add_argument("--out", default="runs/benchmark.json")
    args = ap.parse_args(argv)

    print(f"  spec         {args.spec}")
    data = build(args.spec, args.seeds, Path(args.out))

    print(f"\n  wrote {args.out} in {data['wall_clock_s']}s\n")
    for name, m in data["models"].items():
        sera_n = m["arms"]["sera"]["trials_to_near_oracle"]
        grid_n = m["arms"]["grid"]["trials_to_near_oracle"]
        rnd = m["random"]
        print(
            f"    {name:10} oracle {m['oracle']['p95_ms']:.0f}ms   "
            f"sera {sera_n or 'never'}   grid {grid_n or 'never'}   "
            f"random median {rnd['median_trials_to_near_oracle'] or 'never'} "
            f"(misses near-oracle in {rnd['missed_near_oracle']}/{rnd['seed_count']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
