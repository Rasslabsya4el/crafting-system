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


@dataclass(frozen=True, slots=True)
class Peek[S]:
    """A look-then-choose action: pay `cost`, throw the dice of every option at once, then take the best result.

    The solver's kind for Hinekora's Lock (ADR-0054), and generic like `Action`: it knows nothing of the game. At a
    state `s` the value of a Peek is `cost + E[min(min_a(c_a + V(o_a)), F)]`, where each option `a` is an `Action`
    (its price `c_a` and its kernel), the `o_a` are drawn independently from the options' kernels, and `F` is the
    value of the best `fallback` action, the way to give the Peek up (a plain action of the state, or a burn). With
    no fallback the player must take a result. Looking is free: only the option that is taken pays its price.

    `Action(label, cost, outcomes)` cannot carry this: there the choice is made before the dice are thrown.

    An option never carries `extra_inputs`; the fallback may. `fallback` may be one `Action`, an iterable of
    them or `None`. A state offers at most one `Peek`. `solve` does not accept it: `solve_peek` does.
    """

    label: Hashable
    cost: float
    options: tuple[Action[S], ...]
    fallback: tuple[Action[S], ...] = ()

    def __post_init__(self) -> None:
        cost = _checked_cost(self.cost)
        options = tuple(self.options)
        if not options:
            raise ValueError("a peek needs at least one option")
        fallback = self.fallback
        if fallback is None:
            fallback = ()
        elif isinstance(fallback, Action):
            fallback = (fallback,)
        else:
            fallback = tuple(fallback)
        for option in options:
            if not isinstance(option, Action):
                raise TypeError(f"a peek option must be an Action, got {option!r}")
            if option.extra_inputs:
                raise ValueError(f"a peek option never has extra inputs: {option.label!r}")
        for action in fallback:
            if not isinstance(action, Action):
                raise TypeError(f"a peek fallback must be Actions, got {action!r}")
        object.__setattr__(self, "cost", cost)
        object.__setattr__(self, "options", options)
        object.__setattr__(self, "fallback", fallback)


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

    def actions(self, state: S) -> Iterable[Action[S] | VariantAction[S] | Peek[S]]:
        """The actions of a non-goal state; called at most once per state (once per round under `solve_peek`).

        `VariantAction`s may be mixed with `Action`s; only `solve_variants` and `solve_bounds` read them. A `Peek`
        may be mixed in too (at most one per state); only `solve_peek` reads it.
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
