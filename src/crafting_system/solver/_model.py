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
    also consumes (multi-input actions, ADR-0011, ADR-0022): the value of an input state, what it
    costs to obtain that item, is paid on every attempt, a self-loop retry included. A repeated
    state means that many copies. An action whose own state is one of its inputs needs a copy of
    itself to make one and is dropped, like an action that can never leave its state.
    """

    label: Hashable
    cost: float
    outcomes: tuple[Outcome[S], ...]
    extra_inputs: tuple[S, ...] = ()

    def __post_init__(self) -> None:
        cost = self.cost
        if isinstance(cost, bool) or not isinstance(cost, Real):
            raise ValueError(f"action cost must be a real number, got {cost!r}")
        try:
            cost = float(cost)
        except OverflowError:
            raise ValueError("action cost does not fit a float64") from None
        if not math.isfinite(cost) or cost <= 0.0:
            raise ValueError(f"action cost must be finite and above zero, got {self.cost!r}")
        outcomes = []
        total = 0
        for state, weight in self.outcomes:
            if isinstance(weight, bool) or not isinstance(weight, Integral):
                raise ValueError(f"outcome weight must be an integer, got {weight!r}")
            if weight < 0:
                raise ValueError(f"outcome weight must not be negative, got {weight!r}")
            outcomes.append(Outcome(state, int(weight)))
            total += int(weight)
        if total <= 0:
            raise ValueError("an action needs outcomes with a total weight above zero")
        object.__setattr__(self, "cost", cost)
        object.__setattr__(self, "outcomes", tuple(outcomes))
        object.__setattr__(self, "extra_inputs", tuple(self.extra_inputs))


class Model[S](Protocol):
    """What the solver asks of a problem."""

    def is_goal(self, state: S) -> bool:
        """Goal states have value 0 and are never expanded."""
        ...

    def actions(self, state: S) -> Iterable[Action[S]]:
        """The actions of a non-goal state; called at most once per state."""
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
