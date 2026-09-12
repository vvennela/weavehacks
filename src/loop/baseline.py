"""A conventional tuner, run as a control arm.

Claiming the agent team is better requires something to be better *than*, and the
honest comparison is not "our best config is fast." Any search finds a fast config
eventually. The comparison that means something is how many trials it took, because
trials are the expensive thing — each one deploys a model and drives real traffic.

So this sweeps the identical lever space, spends the identical budget, and passes
through the identical validator and gates. The only difference is how it chooses what
to try next: random or grid order, with no notion of which lever is currently dead.

Two failure modes this guards against. If the sweep matches the loop, the agents are
decoration and we should say so. If the sweep never reaches the target, the lever
space was too easy and the comparison proves nothing.
"""

from __future__ import annotations

import itertools
import random
import uuid
from dataclasses import dataclass

from .config import InferenceConfig, baseline_config
from .ledger import Ledger, Measurement, TrialRecord, Verdict
from .quality import full_eval, smoke_check
from .runner.base import Tenant, TrialRunner
from .spec import ModelSpec, Spec
from .validator import validate

# The same space the three specialists can reach, enumerated.
LEVER_SPACE: dict[str, list] = {
    "weight_dtype": ["bf16", "fp8", "int8", "int4"],
    "kv_cache_dtype": ["bf16", "fp8"],
    "max_num_seqs": [64, 256, 512],
    "max_num_batched_tokens": [1024, 2048, 8192],
    "enable_chunked_prefill": [False, True],
    "tensor_parallel_size": [1, 2],
}


@dataclass
class BaselineResult:
    strategy: str
    model: str
    trials_run: int
    paper_rejections: int
    trials_to_target: int | None       # None means it never got there
    best_p99_ms: float
    best_config: InferenceConfig | None
    target_p99_ms: float

    def describe(self) -> str:
        reached = (
            f"reached SLO on trial {self.trials_to_target}"
            if self.trials_to_target is not None
            else f"never reached SLO in {self.trials_run} trials"
        )
        return (
            f"{self.strategy:14} {self.model:10} {reached}, "
            f"best p99 {self.best_p99_ms:.0f}ms"
        )


def _all_configs(model: ModelSpec) -> list[InferenceConfig]:
    base = baseline_config(model)
    keys = list(LEVER_SPACE)
    out = []
    for values in itertools.product(*(LEVER_SPACE[k] for k in keys)):
        out.append(base.with_delta(dict(zip(keys, values))))
    return out


def sweep(
    spec: Spec,
    model: ModelSpec,
    runner: TrialRunner,
    ledger: Ledger,
    strategy: str = "random",
    budget: int | None = None,
) -> BaselineResult:
    """Spend the trial budget without any notion of which lever is live."""
    gpu = spec.gpus[0]
    slo = spec.slo(model.name)
    floor = spec.quality_floor(model.name)
    budget = budget or spec.budget.phase1_trials

    candidates = _all_configs(model)
    if strategy == "random":
        random.Random(spec.seed).shuffle(candidates)
    # "grid" keeps itertools order, which is the other thing people actually do.

    trials = 0
    paper_rejections = 0
    best_p99 = float("inf")
    best_cfg: InferenceConfig | None = None
    trials_to_target: int | None = None

    for cfg in candidates:
        if trials >= budget:
            break

        check = validate(cfg, model, gpu, available_gpus=len(spec.gpus))
        if not check.ok:
            # Free, exactly as it is for the agent loop — the comparison would be
            # rigged if one arm paid for arithmetic errors and the other did not.
            paper_rejections += 1
            ledger.append(TrialRecord(
                trial_id=f"base-{strategy}-{uuid.uuid4().hex[:6]}", phase=1, round=0,
                models=[model.name], config=cfg.as_dict(),
                verdict=Verdict.REJECTED_PAPER, substrate=runner.substrate,
                proposing_specialist=f"baseline_{strategy}", reason=check.reason,
            ))
            continue

        if not smoke_check(cfg, floor).passed:
            trials += 1
            continue

        outcome = runner.run([Tenant(model, cfg, spec.workload(model.name))], gpu,
                             seed=spec.seed)
        trials += 1
        if not outcome.ok:
            continue

        meas: Measurement = outcome.measurements[model.name]
        quality = full_eval(cfg, floor)

        slo_ok = meas.p99_latency_ms <= slo.p99_latency_ms
        if slo.min_throughput_rps is not None:
            slo_ok = slo_ok and meas.throughput_rps >= slo.min_throughput_rps

        verdict = (
            Verdict.ACCEPTED if slo_ok and quality.passed
            else Verdict.REVERTED_QUALITY if slo_ok
            else Verdict.REVERTED_SLO
        )
        ledger.append(TrialRecord(
            trial_id=f"base-{strategy}-{uuid.uuid4().hex[:6]}", phase=1, round=0,
            models=[model.name], config=cfg.as_dict(), verdict=verdict,
            substrate=outcome.substrate, proposing_specialist=f"baseline_{strategy}",
            measurement=meas, quality_score=quality.score, quality_floor=quality.floor,
        ))

        if verdict is Verdict.ACCEPTED:
            if trials_to_target is None:
                trials_to_target = trials
            if meas.p99_latency_ms < best_p99:
                best_p99, best_cfg = meas.p99_latency_ms, cfg

    return BaselineResult(
        strategy=strategy, model=model.name, trials_run=trials,
        paper_rejections=paper_rejections, trials_to_target=trials_to_target,
        best_p99_ms=best_p99, best_config=best_cfg,
        target_p99_ms=slo.p99_latency_ms,
    )


def compare(spec: Spec, runner: TrialRunner, ledger_dir, verbose: bool = True) -> dict:
    """Run both sweeps against every model and report trials-to-target."""
    from pathlib import Path

    ledger_dir = Path(ledger_dir)
    results: dict[str, list[BaselineResult]] = {}
    for strategy in ("random", "grid"):
        led = Ledger(ledger_dir / f"baseline_{strategy}.jsonl")
        for model in spec.models:
            res = sweep(spec, model, runner, led, strategy=strategy)
            results.setdefault(strategy, []).append(res)
            if verbose:
                print(f"  {res.describe()}")
    return results
