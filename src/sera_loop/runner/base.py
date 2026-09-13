"""The substrate seam.

Everything above this interface — specialists, arbiter, gates, both phases — is
identical whether a trial runs on a real H100 or in the analytic model. That is what
lets the loop be developed and demonstrated without hardware and then moved onto
hardware without touching the logic that judges care about.

Every result carries the substrate that produced it, and the ledger records it, so a
simulated row and a measured row are never silently compared.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..config import InferenceConfig
from ..ledger import Measurement, Substrate
from ..spec import GpuSpec, ModelSpec, Workload


@dataclass
class Tenant:
    """One model to be served, with its config and the traffic aimed at it."""

    model: ModelSpec
    config: InferenceConfig
    workload: Workload


@dataclass
class TrialOutcome:
    """Result of running one or more tenants on one device."""

    measurements: dict[str, Measurement]  # keyed by model name
    substrate: Substrate
    ok: bool = True
    error: str = ""
    notes: dict[str, str] = field(default_factory=dict)


class TrialRunner(ABC):
    """Deploy, warm, load-test, measure, tear down."""

    substrate: Substrate

    @abstractmethod
    def run(self, tenants: list[Tenant], gpu: GpuSpec, seed: int = 0) -> TrialOutcome:
        """Serve every tenant on `gpu` simultaneously and measure each one.

        A single-element list is a Phase 1 trial. Two or more is a Phase 2 joint
        trial, and the co-tenancy effects must be real consequences of sharing the
        device rather than a penalty applied afterwards.
        """

    @abstractmethod
    def available(self) -> bool:
        """Can this runner actually execute right now?"""
