"""What a specialist is allowed to say.

A specialist owns one lever group and returns exactly one of two things: a proposal,
or a declaration that its lever is dead for this situation. Both are useful. "Batch
size is not your problem here" saves a trial slot, and a specialist that always finds
something to suggest is not reasoning, it is just emitting.

Each specialist proposes a change to ONE lever group. The arbiter enforces that too,
but the constraint belongs here as well: it is what makes a measured improvement
attributable to a specific claim.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..config import InferenceConfig, Lever
from ..ledger import Ledger, Prediction
from ..reduction import Digest
from ..spec import GpuSpec, ModelSpec


@dataclass
class Proposal:
    """A single-lever change, with a falsifiable claim attached."""

    specialist: str
    lever: Lever
    delta: dict[str, Any]
    prediction: Prediction
    rationale: str
    # Set by the arbiter, not the specialist.
    priority: float = 0.0
    # True when this proposal won its slot by being unexplored rather than by
    # outranking the alternatives. Recorded so the ledger can separate a win the
    # arbiter predicted from one it only found by looking.
    exploration: bool = False

    def apply_to(self, cfg: InferenceConfig) -> InferenceConfig:
        return cfg.with_delta(self.delta)

    def label(self) -> str:
        return ", ".join(f"{k}={v}" for k, v in self.delta.items())


@dataclass
class Dead:
    """This lever is not the bottleneck here, and why."""

    specialist: str
    lever: Lever
    reason: str


Verdict = Proposal | Dead


@dataclass
class Context:
    """Everything a specialist is allowed to look at."""

    digest: Digest
    config: InferenceConfig
    model: ModelSpec
    gpu: GpuSpec
    ledger: Ledger
    available_gpus: int = 1
    round: int = 0
    tried: set[str] = field(default_factory=set)

    def already_tried(self, delta: dict[str, Any]) -> bool:
        """Has this exact change been run before? Re-proposing wastes a slot."""
        return self.config.with_delta(delta).label() in self.tried


class Specialist(ABC):
    """One lever group, up to two opinions."""

    name: str
    lever: Lever

    @abstractmethod
    def propose(self, ctx: Context) -> list[Verdict]:
        """Read the shared digest and return proposals, or a single Dead.

        Returning up to two proposals is deliberate. With one proposal per specialist
        and one slot per specialist, the arbiter never declines anything — ranking has
        no effect and there is nothing left over to explore. More candidates than slots
        is what makes the arbiter's job real.

        A dead lever is returned as a single Dead, never mixed with proposals.
        """

    def __repr__(self) -> str:
        return f"<{self.name}>"
