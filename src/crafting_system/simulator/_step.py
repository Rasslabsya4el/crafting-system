"""What a policy hands the simulator: a step, that is an action and the price of using it once, with the runs it consumes."""

import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from numbers import Real
from typing import Protocol

from crafting_system.data import GameData
from crafting_system.items import Item


class Sampler(Protocol):
    """What an action's `outcomes` returns, as far as the simulator is concerned: it can draw one item."""

    def sample(self, rng: random.Random) -> Item: ...


class Action(Protocol):
    """Anything the simulator can apply to a concrete item.

    The actions of the `actions` module fit (every `actions.Action`): their `outcomes(data, item)`
    returns an object with `sample(rng)`. That is all the simulator takes of the contract, which also
    lets a test pass a fake. A refusal is raised by `outcomes`, never swallowed here.
    """

    def outcomes(self, data: GameData, item: Item) -> Sampler: ...


class DonorMismatchError(ValueError):
    """A nested run ended at a donor that its `Input.matches` refuses: the policy built the wrong item, a bug in the caller."""


@dataclass(frozen=True, slots=True)
class Input:
    """A second item a step consumes (ADR-0022): it is made by a nested run before the action is applied.

    The nested run starts at `start` with `start_cost` paid, is steered by `policy` (the sub-policy from the input's start
    item to its goal, the same kind of function as the main policy) and ends when `is_goal(item)` holds, which is the donor
    reaching its `want`. The run is made afresh on every attempt of the step (a retry pays its inputs again) and its whole
    cost is added to the run that asked. `matches`, when given, is checked on the donor the run made, before the action is
    applied: it is the caller's statement that this donor is the one the action was priced with (that it compresses to
    `want`), and `DonorMismatchError` is raised when it fails. An input may itself be asked for by a step of its own
    policy, to any depth.
    """

    start: Item
    policy: "Policy"
    is_goal: Callable[[Item], bool]
    start_cost: float = 0.0
    matches: Callable[[Item], bool] | None = None

    def __post_init__(self) -> None:
        cost = self.start_cost
        if isinstance(cost, bool) or not isinstance(cost, Real) or not math.isfinite(cost) or cost < 0.0:
            raise ValueError(f"input start_cost must be finite and not negative, got {cost!r}")
        object.__setattr__(self, "start_cost", float(cost))


@dataclass(frozen=True, slots=True)
class Step:
    """One use of `action`, costing `cost` every time it is taken, also when it changes nothing.

    `cost` is finite and not negative; zero is allowed (a free action). Raises `ValueError`
    otherwise, and for an `action` without an `outcomes` method.

    A step with `inputs` first makes each input by a nested run, in order, and adds what the runs cost. Then the action is
    applied to the item in hand: as it is when `bind` is None (it already holds the donor it was priced with, as the
    recombinator does), or, when `bind` is given, as `bind(donors)` returns it, where `donors` are the items the nested
    runs made, in the order of `inputs`. A step with no `inputs` is the ordinary step of before.
    """

    action: Action
    cost: float
    inputs: tuple[Input, ...] = ()
    bind: Callable[[tuple[Item, ...]], Action] | None = None

    def __post_init__(self) -> None:
        if not callable(getattr(self.action, "outcomes", None)):
            raise ValueError(f"a step needs an action with an outcomes(data, item) method, got {self.action!r}")
        object.__setattr__(self, "inputs", tuple(self.inputs))
        if not all(isinstance(entry, Input) for entry in self.inputs):
            raise ValueError(f"the inputs of a step are Input objects, got {self.inputs!r}")
        if self.bind is not None and not callable(self.bind):
            raise ValueError(f"bind must be a function from the donors to an action, got {self.bind!r}")
        if self.bind is not None and not self.inputs:
            raise ValueError("a step with bind needs inputs: there are no donors to bind")
        cost = self.cost
        if isinstance(cost, bool) or not isinstance(cost, Real):
            raise ValueError(f"step cost must be a real number, got {cost!r}")
        try:
            cost = float(cost)
        except OverflowError:
            raise ValueError("step cost does not fit a float64") from None
        if not math.isfinite(cost) or cost < 0.0:
            raise ValueError(f"step cost must be finite and not negative, got {self.cost!r}")
        object.__setattr__(self, "cost", cost)


Policy = Callable[[Item], Step | None]
"""A concrete item to the step to take on it, or None to stop. Called only on items that are not a goal."""
