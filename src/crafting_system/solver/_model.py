"""The solver's input: states, actions with positive costs, outcomes with integer weights."""

import math
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass
from numbers import Integral, Real
from typing import NamedTuple, Protocol


class Outcome[S](NamedTuple):
    """One successor of an action and its integer weight (a plain `(state, weight)` tuple also works)."""

    state: S
    weight: int


@dataclass(frozen=True, slots=True)
class Action[S]:
    """One choice in a state.

    `label` is opaque to the solver: the caller's identity of the action. `cost` is finite and
    positive. `outcomes` carry integer weights (not bool, not negative, total above zero);
    zero-weight outcomes are ignored, repeated successors are merged by summing weights, and an
    outcome may be the state itself. `extra_inputs` lists the states of other items the action
    also consumes (multi-input actions, ADR-0011); v1 does not solve those.
    """

    label: Hashable
    cost: float
    outcomes: tuple[Outcome[S], ...]
    extra_inputs: tuple[S, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "cost", _checked_cost(self.cost))
        object.__setattr__(self, "outcomes", _checked_outcomes(self.outcomes))
        object.__setattr__(self, "extra_inputs", tuple(self.extra_inputs))


@dataclass(frozen=True, slots=True)
class VariantAction[S]:
    """One choice in a state whose successor distribution is picked by nature among `variants`.

    Each variant is an outcome tuple checked like an `Action`'s; there is at least one. `cost`,
    `label` and `extra_inputs` are as in `Action` and common to all variants. A model that offers
    these is read by `solve_variants` as a game (the controller picks the action, nature the
    variant, every time the state is visited) and by `solve_bounds` as a min over the variants on
    its optimistic side and a max on its pessimistic side. `solve` does not accept it.
    """

    label: Hashable
    cost: float
    variants: tuple[tuple[Outcome[S], ...], ...]
    extra_inputs: tuple[S, ...] = ()

    def __post_init__(self) -> None:
        cost = _checked_cost(self.cost)
        variants = tuple(_checked_outcomes(outcomes) for outcomes in self.variants)
        if not variants:
            raise ValueError("a variant action needs at least one variant")
        object.__setattr__(self, "cost", cost)
        object.__setattr__(self, "variants", variants)
        object.__setattr__(self, "extra_inputs", tuple(self.extra_inputs))


def _checked_cost(cost: float) -> float:
    if isinstance(cost, bool) or not isinstance(cost, Real):
        raise ValueError(f"action cost must be a real number, got {cost!r}")
    try:
        found = float(cost)
    except OverflowError:
        raise ValueError("action cost does not fit a float64") from None
    if not math.isfinite(found) or found <= 0.0:
        raise ValueError(f"action cost must be finite and above zero, got {cost!r}")
    return found


def _checked_outcomes[S](outcomes: Iterable[tuple[S, int]]) -> tuple[Outcome[S], ...]:
    found = []
    total = 0
    for state, weight in outcomes:
        if isinstance(weight, bool) or not isinstance(weight, Integral):
            raise ValueError(f"outcome weight must be an integer, got {weight!r}")
        if weight < 0:
            raise ValueError(f"outcome weight must not be negative, got {weight!r}")
        found.append(Outcome(state, int(weight)))
        total += int(weight)
    if total <= 0:
        raise ValueError("an action needs outcomes with a total weight above zero")
    return tuple(found)


class Model[S](Protocol):
    """What the solver asks of a problem."""

    def is_goal(self, state: S) -> bool:
        """Goal states have value 0 and are never expanded."""
        ...

    def actions(self, state: S) -> Iterable[Action[S] | VariantAction[S]]:
        """The actions of a non-goal state; called at most once per state.

        `VariantAction`s may be mixed with `Action`s; only `solve_variants` and `solve_bounds` read them.
        """
        ...


class TabularModel[S]:
    """A small explicit model: goal states and a table from state to its actions.

    A state missing from the table has no actions.
    """

    def __init__(self, goals: Iterable[S], table: Mapping[S, Iterable[Action[S]]]) -> None:
        self._goals = frozenset(goals)
        self._table = {state: tuple(actions) for state, actions in table.items()}

    def is_goal(self, state: S) -> bool:
        return state in self._goals

    def actions(self, state: S) -> tuple[Action[S], ...]:
        return self._table.get(state, ())
