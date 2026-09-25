import json

from sera.kernel_search import KernelCandidate
from sera.kernel_specialists import KernelSpecialistTeam, route_specialists


PROFILE = dict(tags=["gemm", "memory", "packing", "registers", "simd"],
               capabilities=["cpu", "arm64", "neon", "sme", "single-thread"])


def test_experimental_kernel_api_is_exported():
    import sera
    assert sera.KernelSpecialistTeam is KernelSpecialistTeam
    assert callable(sera.optimize_kernel)


def test_router_selects_relevant_bounded_stable_team():
    roles = route_specialists(PROFILE, {}, limit=3)
    assert len(roles) == 3
    assert roles == route_specialists(PROFILE, {}, limit=3)
    assert all(role.id not in {"threading_numa", "model_precision", "operator_fusion"} for role in roles)


def test_m4_profile_routes_exact_relevant_first_team():
    profile = dict(capabilities=["cpu", "arm64", "neon", "simd", "sme", "single-thread"],
                   tags=["gemm", "sme", "packing", "registers", "memory", "simd", "reuse"])
    assert [role.id for role in route_specialists(profile, {}, limit=3)] == [
        "sme_tiles", "register_tiling", "packing_layout"]


def test_sme_specialist_requires_sme_capability():
    profile = dict(tags=["sme", "gemm"], capabilities=["cpu", "x86_64"])
    assert "sme_tiles" not in {role.id for role in route_specialists(profile, {}, limit=3)}


def test_fair_rotation_does_not_call_all_specialists():
    first = route_specialists(PROFILE, {}, limit=3)
    calls = {role.id: 1 for role in first}
    second = route_specialists(PROFILE, calls, limit=3)
    assert {role.id for role in first} != {role.id for role in second}


def test_team_queues_each_unique_source_and_enforces_call_cap(tmp_path):
    calls = []
    def factory(*, role, **kwargs):
        class Agent:
            def propose(self, history, *, timeout):
                calls.append(role.id)
                return KernelCandidate(role.id, "source-" + role.id, "test")
        return Agent()
    team = KernelSpecialistTeam(work_dir=tmp_path / "team", profile=PROFILE,
        task="test", max_calls=3, agent_factory=factory)
    candidates = [team.propose([], timeout=10) for _ in range(3)]
    assert len(calls) == 3
    assert len({item.source for item in candidates}) == 3
    assert team.propose([], timeout=10) is None
    assert len(calls) == 3


def test_only_measured_outcomes_become_specialist_memory(tmp_path):
    team = KernelSpecialistTeam(work_dir=tmp_path / "team", profile=PROFILE, task="test", max_calls=0)
    history = [dict(specialist_id="packing_layout", source_hash="abc", status="passed",
                    scores=[100, 102, 101], control_scores=[90, 89, 91], promoted=True,
                    reports=["signed.json"], comparison_identity={"tree_hash": "frozen"}),
               dict(specialist_id="packing_layout", source_hash="def", status="running",
                    scores=[], reports=[])]
    assert team.propose(history, timeout=10) is None
    memory = json.loads((tmp_path / "team/state.json").read_text())["memory"]
    assert len(memory["packing_layout"]) == 1
    assert memory["packing_layout"][0]["source_hash"] == "abc"


def test_duplicate_source_does_not_reach_evaluator_queue(tmp_path):
    def factory(**kwargs):
        class Agent:
            def propose(self, history, *, timeout):
                return KernelCandidate("duplicate", "same", "test")
        return Agent()
    team = KernelSpecialistTeam(work_dir=tmp_path / "team", profile=PROFILE,
        task="test", max_calls=3, agent_factory=factory)
    assert team.propose([], timeout=10).source == "same"
    assert team.propose([], timeout=10) is None


def test_team_uses_luna_for_codex_specialists(tmp_path, monkeypatch):
    models = []
    class Agent:
        def __init__(self, **kwargs):
            models.append(kwargs["model"])
        def propose(self, history, *, timeout):
            return None
    monkeypatch.setattr("sera.kernel_specialists.CodexKernelProposer", Agent)
    team = KernelSpecialistTeam(work_dir=tmp_path / "team", profile=PROFILE,
                               task="test", max_calls=3)
    assert team.propose([], timeout=10) is None
    assert models == ["gpt-6-luna"] * 3
