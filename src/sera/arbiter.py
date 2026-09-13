"""Spends the trial budget.

Three specialists argue; there are fewer slots than opinions. The arbiter's job is to
decide who gets to be tested, and it has one rule it will not break: a trial changes
exactly one lever group. Merging two proposals into a single config would produce a
faster number and destroy the ability to say which claim produced it — and a result
you cannot attribute teaches the team nothing for the next round.

Combinations are valuable, but they are proposed *explicitly*, after the single-lever
effects are known, and recorded as combination trials.

Ranking weights each specialist by whether its past predictions held. A specialist
that has been right twice gets the next contested slot over one that has been wrong
twice, without anyone hand-tuning a trust score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import InferenceConfig
from .ledger import Ledger
from .specialists.base import Dead, Proposal, Verdict


@dataclass
class Arbitration:
    """What the arbiter decided and why, kept for the trace."""

    selected: list[Proposal]
    declined: list[Proposal] = field(default_factory=list)
    dead_levers: list[Dead] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class Arbiter:
    def __init__(self, ledger: Ledger, slots: int = 3):
        self.ledger = ledger
        self.slots = slots

    def _score(self, p: Proposal) -> float:
        """Rank a proposal by expected value, discounted by the proposer's track record.

        Calibration starts at 0.5 for an untested specialist, so a newcomer competes
        on the strength of its claim rather than being locked out.
        """
        calibration = self.ledger.calibration(p.specialist)
        magnitude = (p.prediction.magnitude_pct or 10.0) / 100.0
        return p.prediction.confidence * magnitude * (0.5 + calibration)

    def arbitrate(self, verdicts: list[Verdict], baseline: InferenceConfig) -> Arbitration:
        """Choose which proposals get trial slots this round."""
        proposals = [v for v in verdicts if isinstance(v, Proposal)]
        dead = [v for v in verdicts if isinstance(v, Dead)]

        notes: list[str] = []
        for d in dead:
            notes.append(f"{d.specialist} declared its lever dead: {d.reason}")

        # Enforce the single-lever rule at selection time. A specialist emitting a
        # cross-lever delta is a bug, and silently trialling it would corrupt
        # attribution for every round that follows.
        legal: list[Proposal] = []
        for p in proposals:
            touched = p.apply_to(baseline).levers_touched(baseline)
            if len(touched) > 1:
                notes.append(
                    f"{p.specialist} proposed a change spanning {sorted(touched)}; "
                    "rejected — one lever group per trial"
                )
                continue
            legal.append(p)

        for p in legal:
            p.priority = self._score(p)
        legal.sort(key=lambda p: p.priority, reverse=True)

        selected = legal[: self.slots]
        declined = legal[self.slots :]

        for p in selected:
            cal = self.ledger.calibration(p.specialist)
            notes.append(
                f"slot -> {p.specialist} ({p.label()}): confidence "
                f"{p.prediction.confidence:.2f}, calibration {cal:.2f}, "
                f"score {p.priority:.3f}"
            )
        for p in declined:
            notes.append(f"no slot for {p.specialist} ({p.label()}): score {p.priority:.3f}")

        return Arbitration(
            selected=selected, declined=declined, dead_levers=dead, notes=notes
        )

    def propose_combination(
        self,
        winners: list[Proposal],
        baseline: InferenceConfig,
    ) -> Proposal | None:
        """Stack the single-lever winners into one explicit combination trial.

        Only called once each constituent lever has been measured alone, so if the
        combination underperforms the sum of its parts we can see that the levers
        interfere rather than guessing at it.
        """
        if len(winners) < 2:
            return None

        merged: dict = {}
        levers: list[str] = []
        for w in winners:
            merged.update(w.delta)
            levers.append(w.lever)

        return Proposal(
            specialist="arbiter",
            lever="combination",  # type: ignore[arg-type]
            delta=merged,
            prediction=winners[0].prediction,
            rationale=(
                "Combination trial stacking the levers that each won alone: "
                + ", ".join(levers)
                + ". Tested now that every constituent has a measured single-lever "
                "effect, so interference between them is observable rather than assumed."
            ),
        )
