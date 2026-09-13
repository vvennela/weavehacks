"""Phase 1 — how should each model run on its own?

Baseline, then rounds of: reduce the measurements to a shared digest, ask three
specialists what they make of it, let the arbiter spend the slots, reject what fails
on paper, run what survives, gate it on latency and then on quality, and write every
outcome down including the reverts.

The rounds are not a fixed script. What the specialists say in round two depends on
what round one measured, and which of them gets the contested slot depends on whose
predictions have been holding up.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from . import tracing
from .arbiter import Arbiter
from .config import InferenceConfig, baseline_config
from .ledger import (
    Ledger,
    Measurement,
    Substrate,
    TrialRecord,
    Verdict,
)
from .quality import full_eval, smoke_check
from .reduction import Digest, reduce_metrics
from .runner.base import Tenant, TrialRunner
from .spec import ModelSpec, Spec
from .specialists import ALL_SPECIALISTS
from .specialists.base import Context, Dead, Proposal
from .validator import validate


@dataclass
class ModelOutcome:
    model: str
    baseline: Measurement
    best_config: InferenceConfig
    best_measurement: Measurement
    trials_run: int = 0
    rounds: int = 0
    accepted: list[TrialRecord] = field(default_factory=list)
    reverted: list[TrialRecord] = field(default_factory=list)

    @property
    def p95_improvement_pct(self) -> float:
        if self.baseline.p95_latency_ms == 0:
            return 0.0
        return (
            (self.baseline.p95_latency_ms - self.best_measurement.p95_latency_ms)
            / self.baseline.p95_latency_ms
            * 100.0
        )


class Phase1:
    def __init__(
        self,
        spec: Spec,
        runner: TrialRunner,
        ledger: Ledger,
        verbose: bool = True,
        available_gpus: int | None = None,
    ):
        self.spec = spec
        self.runner = runner
        self.ledger = ledger
        self.verbose = verbose
        # Phase 2 retunes under a placement constraint by lowering this to 1, which
        # makes the parallelism specialist declare its lever dead and forces the other
        # two to carry the requirement on a single device.
        self.available_gpus = available_gpus or len(spec.gpus)
        self.arbiter = Arbiter(ledger, slots=spec.budget.concurrent_slots)
        self.trials_spent = 0

    def log(self, msg: str = "") -> None:
        if self.verbose:
            print(msg)

    # -- one trial -----------------------------------------------------------

    @tracing.op
    def _run_trial(
        self,
        model: ModelSpec,
        cfg: InferenceConfig,
        round_no: int,
        proposal: Proposal | None,
        baseline_meas: Measurement | None,
    ) -> TrialRecord:
        """Validate on paper, run if legal, gate on latency then quality, record."""
        gpu = self.spec.gpus[0]
        trial_id = f"p1-{model.name}-r{round_no}-{uuid.uuid4().hex[:6]}"

        check = validate(cfg, model, gpu, available_gpus=self.available_gpus)
        if not check.ok:
            self.log(f"      REJECTED ON PAPER  {check.reason}")
            return self.ledger.append(
                TrialRecord(
                    trial_id=trial_id, phase=1, round=round_no, models=[model.name],
                    config=cfg.as_dict(), verdict=Verdict.REJECTED_PAPER,
                    substrate=self.runner.substrate,
                    proposing_specialist=proposal.specialist if proposal else None,
                    lever=proposal.lever if proposal else None,
                    prediction=proposal.prediction if proposal else None,
                    reason=check.reason,
                )
            )

        # Cheap sanity gate before spending the trial.
        floor = self.spec.quality_floor(model.name)
        smoke = smoke_check(cfg, floor)
        if not smoke.passed:
            self.log(f"      SMOKE FAILED  {smoke.detail}")
            self.trials_spent += 1
            return self.ledger.append(
                TrialRecord(
                    trial_id=trial_id, phase=1, round=round_no, models=[model.name],
                    config=cfg.as_dict(), verdict=Verdict.REVERTED_QUALITY,
                    substrate=self.runner.substrate,
                    proposing_specialist=proposal.specialist if proposal else None,
                    lever=proposal.lever if proposal else None,
                    prediction=proposal.prediction if proposal else None,
                    quality_score=smoke.score, quality_floor=smoke.floor,
                    reason=f"smoke check: {smoke.detail}",
                )
            )

        outcome = self.runner.run(
            [Tenant(model, cfg, self.spec.workload(model.name))], gpu, seed=self.spec.seed
        )
        self.trials_spent += 1

        if not outcome.ok:
            self.log(f"      TRIAL FAILED  {outcome.error}")
            return self.ledger.append(
                TrialRecord(
                    trial_id=trial_id, phase=1, round=round_no, models=[model.name],
                    config=cfg.as_dict(), verdict=Verdict.FAILED,
                    substrate=outcome.substrate,
                    proposing_specialist=proposal.specialist if proposal else None,
                    lever=proposal.lever if proposal else None,
                    reason=outcome.error,
                )
            )

        meas = outcome.measurements[model.name]
        slo = self.spec.slo(model.name)

        slo_ok = meas.p95_latency_ms <= slo.p95_latency_ms
        if slo.min_throughput_rps is not None:
            slo_ok = slo_ok and meas.throughput_rps >= slo.min_throughput_rps

        quality = full_eval(cfg, floor)

        if not slo_ok:
            verdict, reason = Verdict.REVERTED_SLO, (
                f"p95 {meas.p95_latency_ms:.0f}ms vs SLO {slo.p95_latency_ms:.0f}ms, "
                f"throughput {meas.throughput_rps:.2f} rps"
            )
        elif not quality.passed:
            verdict, reason = Verdict.REVERTED_QUALITY, quality.detail
        else:
            verdict, reason = Verdict.ACCEPTED, ""

        # Did the proposing specialist's claim hold? Computed, never asserted.
        held = None
        if proposal and baseline_meas is not None:
            before = getattr(baseline_meas, proposal.prediction.metric, None)
            after = getattr(meas, proposal.prediction.metric, None)
            if before is not None and after is not None:
                held = proposal.prediction.held(before, after)

        mark = {
            Verdict.ACCEPTED: "ACCEPTED",
            Verdict.REVERTED_SLO: "REVERTED (slo)",
            Verdict.REVERTED_QUALITY: "REVERTED (quality)",
        }.get(verdict, verdict.value)
        self.log(
            f"      {mark:20} p95={meas.p95_latency_ms:8.0f}ms  "
            f"tput={meas.throughput_rps:5.2f}  fp={meas.footprint_gb:5.2f}GB  "
            f"q={quality.score:.3f}"
            + (f"  prediction {'HELD' if held else 'MISSED'}" if held is not None else "")
        )
        if reason:
            self.log(f"        -> {reason}")

        return self.ledger.append(
            TrialRecord(
                trial_id=trial_id, phase=1, round=round_no, models=[model.name],
                config=cfg.as_dict(), verdict=verdict, substrate=outcome.substrate,
                proposing_specialist=proposal.specialist if proposal else None,
                lever=proposal.lever if proposal else None,
                prediction=proposal.prediction if proposal else None,
                measurement=meas, baseline_measurement=baseline_meas,
                quality_score=quality.score, quality_floor=quality.floor,
                prediction_held=held, reason=reason,
                gpu_assignment={model.name: gpu.id},
            )
        )

    # -- one model -----------------------------------------------------------

    @tracing.op
    def tune_model(
        self,
        model: ModelSpec,
        seed_from: tuple[InferenceConfig, Measurement] | None = None,
        label: str = "",
        trial_allowance: int | None = None,
    ) -> ModelOutcome:
        """Tune one model.

        Normally this starts by measuring a stock baseline. `seed_from` replaces that
        with a configuration and a measurement taken elsewhere — specifically, Phase 2
        passes the measurement a model produced while sharing a GPU. The specialists
        then reduce over what the model actually experienced under contention rather
        than over its solo numbers, which is the only way their proposals can respond
        to a neighbour they cannot see.
        """
        gpu = self.spec.gpus[0]
        budget = self.spec.budget
        allowance = trial_allowance if trial_allowance is not None else budget.phase1_trials

        header = f"{model.name}  ({model.hf_id})"
        if label:
            header += f"  — {label}"
        self.log(f"\n{'=' * 74}\n  {header}\n{'=' * 74}")

        if seed_from is not None:
            base_cfg, base_meas = seed_from
            self.log(
                f"\n  [seeded] starting from measured state "
                f"p95={base_meas.p95_latency_ms:.0f}ms, no fresh baseline trial"
            )
            base_rec = None
        else:
            base_cfg = baseline_config(model)
            self.log("\n  [baseline]")
            base_rec = self._run_trial(model, base_cfg, 0, None, None)
            if base_rec.measurement is None:
                raise RuntimeError(f"baseline failed for {model.name}: {base_rec.reason}")
            base_meas = base_rec.measurement

        best_cfg, best_meas = base_cfg, base_meas
        outcome = ModelOutcome(
            model=model.name, baseline=base_meas,
            best_config=base_cfg, best_measurement=base_meas,
        )
        if base_rec is not None and base_rec.verdict.viable:
            outcome.accepted.append(base_rec)

        tried: set[str] = {base_cfg.label()}
        round_winners: list[Proposal] = []

        for rnd in range(1, budget.max_rounds + 1):
            if self.trials_spent >= allowance:
                self.log(f"\n  [budget] trial allowance spent ({self.trials_spent}/{allowance})")
                break

            self.log(f"\n  [round {rnd}]")
            digest = reduce_metrics(
                best_meas, best_cfg, model, gpu,
                self.spec.workload(model.name), self.spec.slo(model.name),
                available_gpus=self.available_gpus,
            )
            for line in digest.interpret():
                self.log(f"    . {line}")

            ctx = Context(
                digest=digest, config=best_cfg, model=model, gpu=gpu,
                ledger=self.ledger, available_gpus=self.available_gpus,
                round=rnd, tried=tried,
            )
            verdicts = [v for s in ALL_SPECIALISTS for v in s().propose(ctx)]

            self.log("")
            for v in verdicts:
                if isinstance(v, Dead):
                    self.log(f"    {v.specialist:14} LEVER DEAD — {v.reason}")
                else:
                    self.log(f"    {v.specialist:14} proposes {v.label()}")
                    self.log(f"                   {v.rationale}")

            arb = self.arbiter.arbitrate(
                verdicts, best_cfg, remaining_budget=allowance - self.trials_spent
            )
            if not arb.selected:
                self.log("\n    every lever is dead or already spent — stopping early")
                break

            self.log("\n    [arbiter]")
            for note in arb.notes:
                if note.startswith(("slot", "no slot")):
                    self.log(f"      {note}")

            self.log("")
            round_winners = []
            # Every trial this round is measured against the SAME reference config.
            # Applying each proposal to a running best would silently stack levers —
            # trial two would carry trial one's change and no measured delta could be
            # attributed to the specialist that asked for it.
            round_base, round_base_meas = best_cfg, best_meas
            round_best_cfg, round_best_meas = best_cfg, best_meas

            for prop in arb.selected:
                if self.trials_spent >= allowance:
                    break
                cand = prop.apply_to(round_base)
                tried.add(cand.label())
                self.log(f"    [trial] {prop.specialist}: {prop.label()}")
                rec = self._run_trial(model, cand, rnd, prop, round_base_meas)
                if rec.verdict.viable and rec.measurement is not None:
                    outcome.accepted.append(rec)
                    round_winners.append(prop)
                elif rec.verdict.name.startswith("REVERTED"):
                    outcome.reverted.append(rec)

                # Clearing every gate and being the best place to tune from are
                # different things. A config that cut p95 by 60% but is still over
                # SLO has not earned the frontier, yet abandoning it would strand the
                # loop at a baseline it already knows how to beat — and the next
                # round would recompute an identical digest and propose nothing.
                # A quality failure is different: it is numerically wrong, so it is
                # never a base for further work.
                if (
                    rec.measurement is not None
                    and rec.verdict is not Verdict.REVERTED_QUALITY
                    and rec.measurement.p95_latency_ms < round_best_meas.p95_latency_ms
                ):
                    round_best_cfg, round_best_meas = cand, rec.measurement
                    if not rec.verdict.viable:
                        self.log(
                            f"        kept as working point: {round_base_meas.p95_latency_ms:.0f}"
                            f" -> {rec.measurement.p95_latency_ms:.0f}ms, still over SLO"
                        )

            # Single-lever effects are known now, so a combination becomes readable.
            if len(round_winners) >= 2 and self.trials_spent < allowance:
                combo = self.arbiter.propose_combination(round_winners, round_base)
                if combo is not None:
                    cand = combo.apply_to(round_base)
                    if cand.label() not in tried:
                        tried.add(cand.label())
                        self.log(f"\n    [combination] {combo.label()}")
                        self.log(f"      {combo.rationale}")
                        rec = self._run_trial(model, cand, rnd, combo, round_base_meas)
                        if rec.verdict.viable and rec.measurement is not None:
                            outcome.accepted.append(rec)
                        elif rec.verdict.name.startswith("REVERTED"):
                            outcome.reverted.append(rec)
                        if (
                            rec.measurement is not None
                            and rec.verdict is not Verdict.REVERTED_QUALITY
                            and rec.measurement.p95_latency_ms < round_best_meas.p95_latency_ms
                        ):
                            round_best_cfg, round_best_meas = cand, rec.measurement

            # The round's winner becomes the next round's starting point.
            best_cfg, best_meas = round_best_cfg, round_best_meas
            outcome.rounds = rnd

        outcome.best_config, outcome.best_measurement = best_cfg, best_meas
        outcome.trials_run = self.trials_spent

        self.log(
            f"\n  [result] {model.name}: p95 {base_meas.p95_latency_ms:.0f}ms -> "
            f"{best_meas.p95_latency_ms:.0f}ms ({outcome.p95_improvement_pct:+.1f}%), "
            f"footprint {base_meas.footprint_gb:.2f} -> {best_meas.footprint_gb:.2f}GB"
        )
        self.log(f"           best config: {best_cfg.label()}")
        return outcome

    # -- all models ----------------------------------------------------------

    def run(self) -> dict[str, ModelOutcome]:
        results: dict[str, ModelOutcome] = {}
        for model in self.spec.models:
            self.trials_spent = 0  # budget is per model
            results[model.name] = self.tune_model(model)
        return results
