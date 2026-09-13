"""Phase 2 — how should the models share the hardware?

Phase 1 asked what makes each model fast and answered it per model, on its own card.
That answer is the wrong shape for this question, and the first thing Phase 2 does is
say so: the fastest config frequently shards across every device available, which is
useless when the goal is to empty one.

So the frontier reader re-reads the Phase 1 ledger with a different objective —
smallest footprint that still clears SLO — and produces new knowledge without running
a single new trial. Then the fit check decides on arithmetic whether co-tenancy is
even conceivable, and only then does a joint trial find out what actually happens.

Memory fit is necessary and nowhere near sufficient. Two models can fit on one card
with room to spare and still ruin each other's tail latency, because they are
contending for device time rather than for bytes. The joint trial is the only thing
that can tell you which.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from . import tracing
from .config import InferenceConfig
from .ledger import Ledger, Measurement, TrialRecord, Verdict
from .quality import full_eval
from .runner.base import Tenant, TrialRunner
from .spec import Spec
from .validator import fits_together


@dataclass
class FrontierEntry:
    """One viable Phase 1 config, re-read for its footprint rather than its speed."""

    model: str
    config: InferenceConfig
    measurement: Measurement
    solo_p95_ms: float
    single_device: bool

    @property
    def footprint_gb(self) -> float:
        return self.measurement.footprint_gb


@dataclass
class ContentionEvidence:
    """What co-tenancy did to one model, relative to running it alone.

    Routed back to the specialists on a failure. The point is to hand them the
    measured delta rather than a theory about it — 'p95 went from 378ms to 1840ms
    under a neighbour doing 94%-prefill traffic' is something a specialist can act
    on; 'contention' is not.
    """

    model: str
    solo_p95_ms: float
    joint_p95_ms: float
    solo_throughput: float
    joint_throughput: float
    neighbour: str
    neighbour_prefill_share: float

    @property
    def p95_inflation_pct(self) -> float:
        if self.solo_p95_ms == 0:
            return 0.0
        return (self.joint_p95_ms - self.solo_p95_ms) / self.solo_p95_ms * 100.0

    def describe(self) -> str:
        return (
            f"{self.model}: p95 {self.solo_p95_ms:.0f}ms solo -> {self.joint_p95_ms:.0f}ms "
            f"co-resident with {self.neighbour} ({self.p95_inflation_pct:+.0f}%), "
            f"throughput {self.solo_throughput:.2f} -> {self.joint_throughput:.2f} rps"
        )


@dataclass
class Phase2Result:
    consolidated: bool
    gpu_freed: str | None
    assignment: dict[str, str]
    configs: dict[str, InferenceConfig]
    joint_measurements: dict[str, Measurement] = field(default_factory=dict)
    evidence: list[ContentionEvidence] = field(default_factory=list)
    reason: str = ""
    fit_detail: dict[str, float] = field(default_factory=dict)
    attempts: int = 0


class Phase2:
    def __init__(self, spec: Spec, runner: TrialRunner, ledger: Ledger, verbose: bool = True):
        self.spec = spec
        self.runner = runner
        self.ledger = ledger
        self.verbose = verbose

    def log(self, msg: str = "") -> None:
        if self.verbose:
            print(msg)

    # -- step 12 -------------------------------------------------------------

    @tracing.op
    def read_frontier(self, model: str) -> list[FrontierEntry]:
        """Re-read Phase 1's history asking for small rather than fast."""
        rows = self.ledger.frontier(model, objective="footprint_gb")
        entries = [
            FrontierEntry(
                model=model,
                config=InferenceConfig(**r.config),
                measurement=r.measurement,  # type: ignore[arg-type]
                solo_p95_ms=r.measurement.p95_latency_ms,  # type: ignore[union-attr]
                single_device=(
                    r.config["tensor_parallel_size"] * r.config["pipeline_parallel_size"] == 1
                ),
            )
            for r in rows
        ]
        return entries

    # -- step 13 -------------------------------------------------------------

    def choose_candidate(self, model: str) -> FrontierEntry | None:
        """Smallest viable config that occupies exactly one device.

        The multi-device configs are dropped here, and that is the whole point of the
        phase: a tp=2 winner cannot participate in freeing a GPU, however fast it was.
        """
        frontier = self.read_frontier(model)
        if not frontier:
            return None

        fastest = min(frontier, key=lambda e: e.solo_p95_ms)
        single = [e for e in frontier if e.single_device]

        self.log(f"\n  [frontier] {model}: {len(frontier)} viable configs from phase 1")
        for e in frontier[:5]:
            tag = "1 device " if e.single_device else f"{e.config.tensor_parallel_size} devices"
            self.log(
                f"      {e.footprint_gb:5.2f}GB  p95={e.solo_p95_ms:7.0f}ms  [{tag}]  "
                f"{e.config.label()}"
            )
        self.log(
            f"      fastest was {fastest.solo_p95_ms:.0f}ms at {fastest.footprint_gb:.2f}GB "
            f"on {fastest.config.tensor_parallel_size} device(s)"
        )

        if not single:
            self.log(f"      no single-device config for {model} — cannot co-locate")
            return None

        pick = min(single, key=lambda e: e.footprint_gb)
        if pick is not fastest:
            self.log(
                f"      -> choosing {pick.footprint_gb:.2f}GB / {pick.solo_p95_ms:.0f}ms instead: "
                "the fastest config occupies every device, which is the opposite of what "
                "consolidation needs"
            )
        return pick

    @tracing.op
    def retune_single_device(self, model: str) -> FrontierEntry | None:
        """Re-run Phase 1 for one model with only one device available.

        This is the loop closing between phases. Phase 1 was never told that a GPU
        might need to be emptied, so it reached for tensor parallelism — a legitimate
        answer to the question it was asked and the wrong answer to this one. The
        constraint goes back to the specialists as a changed fact about the world:
        parallelism's lever is now dead, and quantization and batching have to find
        the SLO on their own.
        """
        from .phase1 import Phase1  # local import: Phase 1 imports nothing from here

        self.log(
            f"\n  [retune] {model} has no single-device config that clears SLO.\n"
            "      Sending the placement constraint back to the specialists and "
            "re-tuning with tp=1."
        )
        constrained = Phase1(
            self.spec, self.runner, self.ledger,
            verbose=self.verbose, available_gpus=1,
        )
        constrained.tune_model(self.spec.model(model))

        frontier = [e for e in self.read_frontier(model) if e.single_device]
        if not frontier:
            self.log(f"      {model} still has no viable single-device config")
            return None
        pick = min(frontier, key=lambda e: e.footprint_gb)
        self.log(
            f"      retune produced {pick.footprint_gb:.2f}GB / {pick.solo_p95_ms:.0f}ms "
            f"on one device: {pick.config.label()}"
        )
        return pick

    # -- steps 14 through 19 -------------------------------------------------

    def _fit_check(self, configs, candidates, gpu):
        """Step 14. Arithmetic only — no GPU is touched."""
        concurrent = {
            n: int(e.measurement.kv_occupancy * 200_000) or 8192
            for n, e in candidates.items()
        }
        fit = fits_together(
            configs, {n: self.spec.model(n) for n in configs}, gpu, concurrent
        )
        self.log("\n  [fit check] arithmetic only, no GPU touched")
        for k, v in (fit.detail or {}).items():
            self.log(f"      {k:26} {v:8.2f}")
        return fit

    def _joint_trial(self, configs, candidates, gpu, attempt):
        """Step 15. The only way to observe contention."""
        self.log(
            f"\n  [joint trial {attempt}] both models on {gpu.id}, "
            "both load generators firing"
        )
        tenants = [
            Tenant(self.spec.model(n), cfg, self.spec.workload(n))
            for n, cfg in configs.items()
        ]
        return self.runner.run(tenants, gpu, seed=self.spec.seed)

    def _evidence(self, outcome, candidates):
        """Step 16. Interference, measured against each model's own solo result."""
        names = list(candidates)
        out = []
        for n in names:
            neighbour = next((m for m in names if m != n), "none")
            nb_wl = self.spec.workload(neighbour) if neighbour != "none" else None
            joint = outcome.measurements[n]
            out.append(
                ContentionEvidence(
                    model=n,
                    solo_p95_ms=candidates[n].solo_p95_ms,
                    joint_p95_ms=joint.p95_latency_ms,
                    solo_throughput=candidates[n].measurement.throughput_rps,
                    joint_throughput=joint.throughput_rps,
                    neighbour=neighbour,
                    neighbour_prefill_share=(
                        nb_wl.input_len_mean
                        / max(nb_wl.input_len_mean + nb_wl.output_len_mean, 1)
                        if nb_wl
                        else 0.0
                    ),
                )
            )
        return out

    def _gates(self, outcome, configs):
        """Step 17. Each model is gated independently — no averaging across tenants."""
        self.log("\n  [per-model gates]")
        failures, failing_models = [], []
        for n in configs:
            joint = outcome.measurements[n]
            slo = self.spec.slo(n)
            quality = full_eval(configs[n], self.spec.quality_floor(n))
            slo_ok = joint.p95_latency_ms <= slo.p95_latency_ms
            if slo.min_throughput_rps is not None:
                slo_ok = slo_ok and joint.throughput_rps >= slo.min_throughput_rps
            ok = slo_ok and quality.passed
            self.log(
                f"      {n:12} p95={joint.p95_latency_ms:8.0f}ms / {slo.p95_latency_ms:.0f}ms  "
                f"tput={joint.throughput_rps:6.2f}  q={quality.score:.3f}  "
                f"[{'PASS' if ok else 'FAIL'}]"
            )
            if not ok:
                failing_models.append(n)
                failures.append(
                    f"{n} breached "
                    + ("SLO" if not slo_ok else "the quality floor")
                    + f" ({joint.p95_latency_ms:.0f}ms vs {slo.p95_latency_ms:.0f}ms)"
                )
        return failures, failing_models

    @tracing.op
    def retune_under_contention(self, model: str, contended, config, allowance: int) -> None:
        """Step 18's revise half — the contention back-edge, spending real trials.

        Phase 1 tuned this model alone, so its proposals answered a question the
        neighbour was not part of. Rather than narrate that, the joint measurement is
        fed back in as the starting evidence: the reducer computes the digest from
        what the model actually experienced while sharing the device, and the
        specialists propose against those numbers.

        The retune still runs solo trials — a solo trial is all Phase 1 can run — so
        what it is really searching for is a configuration with enough headroom to
        survive the inflation already on the record.
        """
        from .phase1 import Phase1

        self.log(
            f"\n  [retune] feeding {model}'s contended measurement back to the reducer "
            f"(p95 {contended.p95_latency_ms:.0f}ms observed while co-resident)"
        )
        Phase1(
            self.spec, self.runner, self.ledger,
            verbose=self.verbose, available_gpus=len(self.spec.gpus),
        ).tune_model(
            self.spec.model(model),
            seed_from=(config, contended),
            label="retuning under measured contention",
            trial_allowance=allowance,
        )

    @tracing.op
    def run(self, target_gpu: str | None = None) -> Phase2Result:
        gpu = self.spec.gpu(target_gpu) if target_gpu else self.spec.gpus[0]
        others = [g for g in self.spec.gpus if g.id != gpu.id]
        max_attempts = max(1, self.spec.budget.phase2_trials)

        self.log(f"\n{'=' * 74}\n  PHASE 2 — joint placement on {gpu.id}\n{'=' * 74}")
        if not others:
            self.log(
                "  One GPU visible. The question is whether both services can share it,\n"
                "  not whether a second card can be freed."
            )

        last: Phase2Result | None = None

        for attempt in range(1, max_attempts + 1):
            candidates: dict[str, FrontierEntry] = {}
            for name in self.spec.model_names:
                pick = self.choose_candidate(name)
                if pick is None and len(self.spec.gpus) > 1:
                    pick = self.retune_single_device(name)
                if pick is None:
                    return Phase2Result(
                        consolidated=False, gpu_freed=None, assignment={}, configs={},
                        reason=f"no viable single-device configuration for {name}",
                    )
                candidates[name] = pick

            configs = {n: e.config for n, e in candidates.items()}

            fit = self._fit_check(configs, candidates, gpu)
            if not fit.ok:
                self.log(f"      DOES NOT FIT — {fit.reason}")
                return Phase2Result(
                    consolidated=False, gpu_freed=None,
                    assignment={n: gpu.id for n in configs}, configs=configs,
                    reason=f"fit check failed: {fit.reason}",
                    fit_detail=fit.detail or {},
                )
            self.log(
                f"      fits with {fit.detail['headroom_gb']:.2f}GB headroom — proceeding. "
                "Fitting is not the same as working."
            )

            outcome = self._joint_trial(configs, candidates, gpu, attempt)
            if not outcome.ok:
                return Phase2Result(
                    consolidated=False, gpu_freed=None,
                    assignment={n: gpu.id for n in configs}, configs=configs,
                    reason=f"joint trial failed: {outcome.error}",
                )

            evidence = self._evidence(outcome, candidates)
            self.log("\n  [interference]")
            for ev in evidence:
                self.log(f"      {ev.describe()}")

            failures, failing = self._gates(outcome, configs)
            names = list(configs)

            self.ledger.append(
                TrialRecord(
                    trial_id=f"p2-joint-{attempt}-{uuid.uuid4().hex[:6]}",
                    phase=2, round=attempt, models=names,
                    config={n: c.as_dict() for n, c in configs.items()},
                    verdict=Verdict.ACCEPTED if not failures else Verdict.REVERTED_SLO,
                    substrate=outcome.substrate,
                    proposing_specialist="frontier_reader", lever="placement",
                    measurement=outcome.measurements[names[0]],
                    quality_score=min(
                        full_eval(configs[n], self.spec.quality_floor(n)).score for n in names
                    ),
                    quality_floor=min(self.spec.quality_floor(n).min_score for n in names),
                    reason="; ".join(failures) if failures else "both models held",
                    gpu_assignment={n: gpu.id for n in names},
                )
            )

            if not failures:
                freed = others[0].id if others else None
                self.log(
                    f"\n  [verdict] CO-RESIDENT — both models hold on {gpu.id}"
                    + (f", {freed} is free" if freed else " sharing one device")
                )
                return Phase2Result(
                    consolidated=True, gpu_freed=freed,
                    assignment={n: gpu.id for n in names}, configs=configs,
                    joint_measurements=outcome.measurements, evidence=evidence,
                    reason="both models held under co-tenancy",
                    fit_detail=fit.detail or {}, attempts=attempt,
                )

            binding = max(evidence, key=lambda e: e.p95_inflation_pct)
            self.log(f"\n  [verdict] attempt {attempt} REVERTED — {'; '.join(failures)}")
            self.log(
                f"      Memory was not the binding constraint: the fit check cleared with "
                f"{fit.detail['headroom_gb']:.2f}GB spare. Device-time contention was — "
                f"{binding.model}'s p95 inflated {binding.p95_inflation_pct:+.0f}% beside "
                f"{binding.neighbour}, whose traffic is "
                f"{binding.neighbour_prefill_share:.0%} prefill."
            )

            last = Phase2Result(
                consolidated=False, gpu_freed=None,
                assignment={n: gpu.id for n in names}, configs=configs,
                joint_measurements=outcome.measurements, evidence=evidence,
                reason="; ".join(failures), fit_detail=fit.detail or {}, attempts=attempt,
            )

            if attempt >= max_attempts:
                self.log(
                    f"      Phase-2 allowance spent ({max_attempts} joint "
                    f"attempt{'s' if max_attempts != 1 else ''})."
                )
                break

            for name in failing:
                self.retune_under_contention(
                    name, outcome.measurements[name], configs[name],
                    allowance=self.spec.budget.phase1_trials,
                )

        assert last is not None
        self.log(
            "\n  [result] no safe joint placement found. The per-model configurations "
            "from phase 1 stand; these two services should not share this device under "
            "these workloads."
        )
        return last
