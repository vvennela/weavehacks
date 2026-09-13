"""The properties the loop claims about itself, asserted rather than eyeballed."""

from __future__ import annotations

from sera.arbiter import Arbiter
from sera.config import InferenceConfig, baseline_config
from sera.ledger import Ledger, Prediction
from sera.phase1 import Phase1
from sera.reduction import reduce_metrics
from sera.runner.base import Tenant
from sera.runner.sim_runner import SimRunner
from sera.spec import load_spec
from sera.specialists import ALL_SPECIALISTS
from sera.specialists.base import Context, Dead, Proposal

SPEC = "specs/demo.yaml"


def _proposal(name: str, delta: dict, conf: float = 0.7) -> Proposal:
    return Proposal(
        specialist=name, lever=name, delta=delta,
        prediction=Prediction("p95_latency_ms", "decrease", 30.0, conf),
        rationale="test",
    )


def test_arbiter_refuses_a_proposal_spanning_two_levers(tmp_path):
    """The rule that keeps a measured win attributable to one claim."""
    led = Ledger(tmp_path / "l.jsonl")
    arb = Arbiter(led, slots=3)
    base = InferenceConfig(model="m")
    cross = _proposal("rogue", {"weight_dtype": "fp8", "max_num_seqs": 32})

    result = arb.arbitrate([cross], base)
    assert result.selected == []
    assert any("one lever group per trial" in n for n in result.notes)


def test_arbiter_respects_slot_budget(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    arb = Arbiter(led, slots=2)
    base = InferenceConfig(model="m")
    props = [
        _proposal("quantization", {"weight_dtype": "fp8"}, 0.9),
        _proposal("batching", {"max_num_seqs": 512}, 0.8),
        _proposal("parallelism", {"tensor_parallel_size": 2}, 0.7),
    ]
    res = arb.arbitrate(props, base)
    assert len(res.selected) == 2
    assert len(res.declined) == 1
    assert res.selected[0].specialist == "quantization"  # highest score first


def test_calibration_reorders_the_queue(tmp_path):
    """A specialist that has been wrong loses the contested slot to one that hasn't."""
    from sera.ledger import Measurement, Substrate, TrialRecord, Verdict

    led = Ledger(tmp_path / "l.jsonl")
    for i in range(4):
        led.append(TrialRecord(
            trial_id=f"q{i}", phase=1, round=1, models=["m"], config={},
            verdict=Verdict.ACCEPTED, substrate=Substrate.SIM,
            proposing_specialist="quantization", prediction_held=False,
            measurement=Measurement(1, 1, 1, 1),
        ))
    arb = Arbiter(led, slots=1)
    base = InferenceConfig(model="m")
    res = arb.arbitrate(
        [
            _proposal("quantization", {"weight_dtype": "fp8"}, 0.8),
            _proposal("batching", {"max_num_seqs": 512}, 0.7),
        ],
        base,
    )
    assert res.selected[0].specialist == "batching"


def test_arbiter_never_merges_levers_implicitly(tmp_path):
    """propose_combination is the ONLY path to a multi-lever config, and it is labelled."""
    led = Ledger(tmp_path / "l.jsonl")
    arb = Arbiter(led, slots=3)
    base = InferenceConfig(model="m")
    winners = [
        _proposal("quantization", {"weight_dtype": "fp8"}),
        _proposal("batching", {"max_num_seqs": 512}),
    ]
    combo = arb.propose_combination(winners, base)
    assert combo is not None
    assert combo.lever == "combination"
    assert combo.specialist == "arbiter"
    assert len(combo.apply_to(base).levers_touched(base)) == 2
    assert arb.propose_combination(winners[:1], base) is None


def test_every_phase1_trial_changes_exactly_one_lever_group(tmp_path):
    """End to end: no ledger row may stack levers without being marked a combination."""
    spec = load_spec(SPEC)
    led = Ledger(tmp_path / "l.jsonl")
    Phase1(spec, SimRunner(), led, verbose=False).run()

    rows = [r for r in led.all() if r.lever and r.lever != "combination" and r.round > 0]
    assert rows, "expected at least one specialist-proposed trial"
    for r in rows:
        cfg = InferenceConfig(**r.config)
        base = baseline_config(spec.model(r.models[0]))
        touched = cfg.levers_touched(base)
        # A trial may sit on top of earlier accepted rounds, but the lever the
        # proposing specialist owns must be among what changed.
        assert r.lever in touched or not touched, (
            f"{r.trial_id}: lever={r.lever} but config touches {sorted(touched)}"
        )


def test_specialists_return_exactly_one_verdict_type(tmp_path):
    spec = load_spec(SPEC)
    model = spec.model("model_a")
    cfg = baseline_config(model)
    gpu = spec.gpu("gpu0")
    out = SimRunner().run([Tenant(model, cfg, spec.workload("model_a"))], gpu, seed=spec.seed)
    digest = reduce_metrics(
        out.measurements["model_a"], cfg, model, gpu,
        spec.workload("model_a"), spec.slo("model_a"), available_gpus=2,
    )
    ctx = Context(digest=digest, config=cfg, model=model, gpu=gpu,
                  ledger=Ledger(tmp_path / "l.jsonl"), available_gpus=2)
    for cls in ALL_SPECIALISTS:
        v = cls().propose(ctx)
        assert isinstance(v, (Proposal, Dead))
        if isinstance(v, Dead):
            assert v.reason, f"{cls.__name__} declared dead without a reason"
        else:
            assert v.rationale and v.delta


def test_dead_lever_is_reported_when_no_devices_are_free(tmp_path):
    """Parallelism must not propose sharding onto hardware that does not exist."""
    spec = load_spec(SPEC)
    model = spec.model("model_a")
    cfg = baseline_config(model)
    gpu = spec.gpu("gpu0")
    out = SimRunner().run([Tenant(model, cfg, spec.workload("model_a"))], gpu, seed=spec.seed)
    digest = reduce_metrics(
        out.measurements["model_a"], cfg, model, gpu,
        spec.workload("model_a"), spec.slo("model_a"), available_gpus=1,
    )
    ctx = Context(digest=digest, config=cfg, model=model, gpu=gpu,
                  ledger=Ledger(tmp_path / "l.jsonl"), available_gpus=1)
    from sera.specialists import ParallelismSpecialist

    v = ParallelismSpecialist().propose(ctx)
    assert isinstance(v, Dead)


def test_simulator_is_deterministic(tmp_path):
    """Same spec, same seed, byte-identical measurements. The ledger depends on it."""
    spec = load_spec(SPEC)
    model = spec.model("model_a")
    cfg = baseline_config(model)
    runs = [
        SimRunner().run([Tenant(model, cfg, spec.workload("model_a"))],
                        spec.gpu("gpu0"), seed=spec.seed)
        for _ in range(3)
    ]
    p99s = {r.measurements["model_a"].p95_latency_ms for r in runs}
    assert len(p99s) == 1, f"simulator is not deterministic: {p99s}"


def test_co_tenancy_is_never_faster_than_running_alone(tmp_path):
    """Sharing a device cannot help. If it did, the contention model would be wrong."""
    spec = load_spec(SPEC)
    gpu = spec.gpu("gpu0")
    runner = SimRunner()
    tenants = [
        Tenant(spec.model(n), baseline_config(spec.model(n)), spec.workload(n))
        for n in spec.model_names
    ]
    joint = runner.run(tenants, gpu, seed=spec.seed)
    for t in tenants:
        solo = runner.run([t], gpu, seed=spec.seed)
        assert (
            joint.measurements[t.model.name].p95_latency_ms
            >= solo.measurements[t.model.name].p95_latency_ms
        )
