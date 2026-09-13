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


# Below this many remaining trials, stop exploring and spend what is left on the
# strongest known direction.
EXPLORATION_MIN_BUDGET = 3


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

    def arbitrate(
        self,
        verdicts: list[Verdict],
        baseline: InferenceConfig,
        remaining_budget: int | None = None,
    ) -> Arbitration:
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

        # Exploration. Ranking alone is pure exploitation: the highest-scoring lever
        # keeps winning, its calibration keeps rising, and the arbiter stops learning
        # anything about the levers it never spends a slot on.
        #
        # So when the budget can afford it, one slot is reserved for the best proposal
        # from a lever group that ranking did NOT already select. It is spent only when
        # at least EXPLORATION_MIN_BUDGET trials remain, so exploring never consumes
        # the last trials that should be closing out a known-good direction.
        #
        # MEASURED CAVEAT: with three lever groups and two-to-three slots, this branch
        # does not fire in any shipped scenario — the selected set almost always already
        # covers every live lever, so there is no unselected lever to promote. It is
        # unit-tested and correct when it triggers, and it is inert in practice today.
        # What actually improved search was letting a specialist offer two candidates
        # instead of one. Do not cite this as a working mechanism until a scenario
        # exists where `grep 'exploration slot'` finds something.
        if remaining_budget is not None and remaining_budget >= EXPLORATION_MIN_BUDGET:
            chosen_levers = {p.lever for p in selected}
            candidates = [p for p in declined if p.lever not in chosen_levers]
            if candidates and selected:
                explorer = candidates[0]
                displaced = selected[-1]
                selected = selected[:-1] + [explorer]
                declined = [p for p in declined if p is not explorer] + [displaced]
                explorer.exploration = True
                notes.append(
                    f"exploration slot -> {explorer.specialist} ({explorer.label()}): "
                    f"score {explorer.priority:.3f} is below "
                    f"{displaced.specialist}'s {displaced.priority:.3f}, but "
                    f"{displaced.lever} is already being tested this round and "
                    f"{explorer.lever} has not been. {remaining_budget} trials remain."
                )

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
