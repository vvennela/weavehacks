"""Bounded Codex specialist dispatch, without all-to-all agent discussion."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import heapq
import json
from pathlib import Path
import time

from .kernel_search import KernelCandidate
from .kernel_tools import DEFAULT_KERNEL_MODEL, CodexKernelProposer
from .storage import content_hash, save_json


@dataclass(frozen=True)
class KernelSpecialist:
    id: str
    description: str
    tags: frozenset[str]
    requires: frozenset[str] = frozenset({"cpu"})


def _role(name, description, tags, requires="cpu"):
    return KernelSpecialist(name, description, frozenset(tags.split()), frozenset(requires.split()))


SPECIALISTS = (
    _role("register_tiling", "Improve register tiles and accumulation layout; account for register pressure.", "gemm registers reuse"),
    _role("cache_blocking", "Improve cache tiles and loop order; keep all packing inside the timed call.", "gemm cache reuse"),
    _role("packing_layout", "Reduce input packing and transpose cost; compare its full cost with reuse savings.", "gemm packing memory"),
    _role("sme_tiles", "Optimize Arm SME tile operations, streaming transitions, and ZA data movement; keep valid tails.", "gemm sme registers simd", "cpu arm64 sme"),
    _role("simd_vectorization", "Improve supported vector arithmetic and loads/stores without unproved alignment.", "simd compiler dtype", "cpu simd"),
    _role("instruction_schedule", "Reduce dependency chains, address calculations, and loop overhead within one thread.", "registers codegen latency gemm"),
    _role("memory_traffic", "Remove redundant reads, writes, and allocations while preserving complete output semantics.", "memory dtype gemm"),
    _role("compiler_codegen", "Improve source patterns for the fixed compiler; do not change compiler flags.", "compiler codegen simd"),
    _role("alignment_tails", "Improve general tail and alignment paths while preserving arbitrary supported dimensions.", "abi tails alignment"),
    _role("numerical_semantics", "Keep reduction order and precision inside the frozen numerical tolerance; never relax it.", "correctness dtype reduction"),
    _role("prefetch_tlb", "Explore bounded prefetch and access locality; do not claim cache-counter evidence absent from records.", "cache tlb memory"),
    _role("allocation_lifetime", "Reduce scratch allocation and initialization per call; never cache answers across calls.", "allocation packing memory"),
    _role("threading_numa", "Partition authorized CPU workers and memory locality; preserve declared thread limits.", "parallel numa scaling", "cpu parallel-allowed"),
    _role("operator_fusion", "Fuse only caller-authorized adjacent model operators with an independent graph reference.", "graph fusion intermediates", "cpu graph-adapter"),
    _role("model_precision", "Change only adapter-supported model storage precision under a fixed quality contract.", "model precision capacity", "cpu precision-adapter"),
)


def route_specialists(profile, calls, *, limit=3):
    """O(N log k) selection; catalog growth does not add peer messages."""
    if type(limit) is not int or not 1 <= limit <= 3:
        raise ValueError("Select one to three active specialists")
    tags, capabilities = set(profile["tags"]), set(profile["capabilities"])
    eligible = [role for role in SPECIALISTS
                if role.requires <= capabilities and role.tags & tags]

    def score(role):
        # Try relevant uncalled specialties before paying for repeated guesses.
        return (4 * len(role.tags & tags) - 8 * calls.get(role.id, 0), role.id)

    return heapq.nlargest(limit, eligible, key=score)


class KernelSpecialistTeam:
    """Route at most three independent Codex calls, then queue unique sources.

    History is supplied by kernel_search after evaluator verification. Never
    load agent-authored or arbitrary external history as trusted outcomes.
    Memory is scoped to this run and identity; it contains observations, not
    agent-written policy or explanations asserted as fact.
    """

    def __init__(self, *, work_dir, profile, task, max_calls=12, active=3,
                 timeout=180, model=None, agent_factory=None):
        if type(max_calls) is not int or not 0 <= max_calls <= 100:
            raise ValueError("max_calls must be an integer from 0 to 100")
        route_specialists(profile, {}, limit=active)
        self.folder = Path(work_dir).resolve()
        self.folder.mkdir(parents=True, exist_ok=False)
        self.profile = json.loads(json.dumps(profile))
        self.profile_key = content_hash(self.profile)
        self.task, self.max_calls, self.active = task, max_calls, active
        self.timeout = timeout
        self.model = DEFAULT_KERNEL_MODEL if model is None else model
        self.factory = agent_factory or self._codex_agent
        self.calls, self.memory, self.records, self.queue = {}, {}, [], []
        self.observed, self.proposed = set(), set()
        self.identity = None
        self._save()

    def _save(self):
        save_json(self.folder / "state.json", dict(schema_version="sera-kernel-specialists-v1",
            profile=self.profile, profile_key=self.profile_key, calls=self.calls,
            memory=self.memory, dispatches=self.records, max_calls=self.max_calls,
            max_active=self.active, pending=len(self.queue)))

    def _observe(self, history):
        ids = {role.id for role in SPECIALISTS}
        for trial in history:
            role = trial.get("specialist_id")
            if role not in ids or trial.get("status") not in {"passed", "rejected"}:
                continue
            identity = trial.get("comparison_identity")
            if not identity or not trial.get("reports"):
                continue
            if self.identity is not None and identity != self.identity:
                raise ValueError("Specialist memory comparison identity changed")
            self.identity = identity
            key = (role, trial["source_hash"])
            if key in self.observed:
                continue
            self.observed.add(key)
            memory = self.memory.setdefault(role, [])
            memory.append({name: trial.get(name) for name in
                           ("source_hash", "status", "scores", "control_scores", "promoted", "reports")}
                          | dict(comparison_identity=identity, confidence="single-trial-observation"))
            del memory[:-8]
        self._save()

    def _codex_agent(self, *, role, work_dir, task):
        return CodexKernelProposer(work_dir=work_dir, task=task, model=self.model, timeout=self.timeout)

    def _dispatch(self, role, history, timeout, call_id):
        task = (self.task + "\n\nYour specialist role: " + role.id + ". " + role.description
                + "\nYour scope does not permit changing the evaluator, budget, hardware, "
                  "thread limit, or correctness contract. Reflect on your measured outcomes "
                  "when choosing a new hypothesis; do not turn a causal guess into a fact."
                + "\nYour bounded outcome memory:\n" + json.dumps(self.memory.get(role.id, [])))
        agent = self.factory(role=role, work_dir=self.folder / f"call-{call_id:03d}-{role.id}", task=task)
        candidate = agent.propose(history, timeout=min(timeout, self.timeout))
        if candidate is None:
            return None
        return KernelCandidate(candidate.name, candidate.source, candidate.hypothesis,
                               specialist_id=role.id)

    def propose(self, history, *, timeout):
        deadline = time.monotonic() + timeout
        self._observe(history)
        self.proposed.update(trial["source_hash"] for trial in history)
        if self.queue:
            return self.queue.pop(0)
        remaining_calls = self.max_calls - sum(self.calls.values())
        if remaining_calls <= 0:
            return None
        roles = route_specialists(self.profile, self.calls, limit=min(self.active, remaining_calls))
        dispatches = []
        for role in roles:
            self.calls[role.id] = self.calls.get(role.id, 0) + 1
            record = dict(call_id=len(self.records) + 1, specialist_id=role.id, status="requested")
            self.records.append(record)
            dispatches.append((role, record))
        self._save()  # Intent persists before any Codex call.
        with ThreadPoolExecutor(max_workers=self.active) as executor:
            futures = [(record, executor.submit(self._dispatch, role, history,
                        max(0.001, deadline - time.monotonic()), record["call_id"]))
                       for role, record in dispatches]
            # Keep routing order, independent of network completion order.
            for record, future in futures:
                try:
                    candidate = future.result()
                    if candidate is None:
                        record["status"] = "abstained"
                    else:
                        source_hash = hashlib.sha256(candidate.source.encode()).hexdigest()
                        record["source_hash"] = source_hash
                        if source_hash in self.proposed:
                            record["status"] = "duplicate"
                        else:
                            self.proposed.add(source_hash)
                            self.queue.append(candidate)
                            record["status"] = "queued"
                except Exception as error:
                    record.update(status="failed", error=type(error).__name__)
                self._save()
        if time.monotonic() >= deadline:
            raise TimeoutError("Specialist team deadline reached")
        return self.queue.pop(0) if self.queue else None
