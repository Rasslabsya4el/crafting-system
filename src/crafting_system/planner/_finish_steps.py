"""The finishes of a plan as steps (#1234): the catalyst quality (`_quality_finish`) and the base implicit's roll (`_implicit_finish`), each a
last step after the mods, with its own small chain, folded into the cost law of the plan.

Each finish is an independent chain that starts on every goal item of the mods (no step of the mods changes the quality or the implicit where it
is a finish, so every goal holds the start item's) and ends at the target: the quality's chain walks the catalyst's gains from the start item's
quality to the percent asked (at most 20 states, `_quality_finish.quality_law`); the implicit's is one state that a Blessed Orb leaves with the
chance `p` of meeting every wish. A finish step holds that chain as `law`: its states in order, each with its outcomes (a chance and the next
state, None for "this finish is done").

`with_finish_chain` hangs the steps after the goals of a policy: a goal of the mods is no goal any more, it takes the first step's action, the
last state of the last step is the goal. The risk evaluated on that chain (`Plan.risk`, `_plan.add_risk`) is then the law of the whole craft,
the mods' cost and the finishes' convolved (the two are independent), and its mean is the mods' mean plus the finishes' means: the result's
mean, percentiles and CVaR, the JSON and the benchmark read the whole craft (#1234 points 2). The page and the text draw each step as the last
rows of the route (`cli._finish_rows`).
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterator, Mapping
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.abstraction import integer_weights
from crafting_system.solver import Action

from ._offers import PricedOffer

QUALITY = "quality"
IMPLICIT = "implicit"


@dataclass(frozen=True)
class FinishStep:
    """One finish drawn as a last step: what it is (`QUALITY`, `IMPLICIT`), the offer it uses, the goal in a player's words, the mean number
    of uses, the chance one use ends it (when that is one chance, the implicit's), and its chain (`law`, the module text)."""

    kind: str
    priced: PricedOffer
    goal: str
    uses: Fraction
    chance: Fraction | None
    law: tuple[tuple[Hashable, tuple[tuple[Fraction, Hashable | None], ...]], ...]
    approximate: str  # why its count is approximate, in a player's words

    @property
    def label(self) -> str:
        return self.priced.label

    @property
    def value(self) -> float:
        """The mean cost of the step in Chaos: its mean number of uses times the price of one."""
        return float(self.uses) * self.priced.cost


@dataclass(frozen=True)
class FinishNode:
    """A state of a finish chain hung after the goals of a policy: the step's place (`step`, `len(steps)` for the finished item) and the
    state of its chain (`key`)."""

    step: int
    key: Hashable


class _Finished(Mapping):
    """A policy with the finish steps hung after its goals (`with_finish_chain`): the goals of the mods take the first step's action."""

    def __init__(self, policy: Mapping, main_goal: Callable[[object], bool], steps: tuple[FinishStep, ...]) -> None:
        self.policy, self.main_goal = policy, main_goal
        self.nodes: dict[FinishNode, Action] = {}
        done = FinishNode(len(steps), None)
        for at, step in enumerate(steps):
            after = FinishNode(at + 1, steps[at + 1].law[0][0]) if at + 1 < len(steps) else done
            for key, outcomes in step.law:
                kernel: dict = {}
                for chance, onto in outcomes:
                    where = after if onto is None else FinishNode(at, onto)
                    kernel[where] = kernel.get(where, Fraction(0)) + Fraction(chance)
                weights = integer_weights(kernel)
                self.nodes[FinishNode(at, key)] = Action(("finish", step.label), step.priced.cost, tuple(weights.items()))
        self.entry = self.nodes[FinishNode(0, steps[0].law[0][0])]
        self.done = done

    def get(self, state, default=None):
        if isinstance(state, FinishNode):
            return self.nodes.get(state, default)
        if self.main_goal(state):
            return self.entry
        return self.policy.get(state, default)

    def __getitem__(self, state):
        found = self.get(state)
        if found is None:
            raise KeyError(state)
        return found

    def __iter__(self) -> Iterator:
        yield from self.policy
        yield from self.nodes

    def __len__(self) -> int:
        return len(self.policy) + len(self.nodes)


def with_finish_chain(
    policy: Mapping, is_goal: Callable[[object], bool], steps: tuple[FinishStep, ...], main_goal: Callable[[object], bool] | None = None
) -> tuple[Mapping, Callable[[object], bool]]:
    """`policy` and its goal test with the finish `steps` hung after the goals (the module text); `main_goal` tells the goals of the target's
    own item among `is_goal`'s (a product with donors, whose donors' goals take no finish), `is_goal` itself by default. No steps: as given."""
    if not steps:
        return policy, is_goal
    main = is_goal if main_goal is None else main_goal
    finished = _Finished(policy, lambda state: not isinstance(state, FinishNode) and main(state), steps)

    def goal(state) -> bool:
        if isinstance(state, FinishNode):
            return state == finished.done
        return is_goal(state) and not main(state)

    return finished, goal
