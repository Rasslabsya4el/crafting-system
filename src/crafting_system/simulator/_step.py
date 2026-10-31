"""What a policy hands the simulator: a step, that is an action and the price of using it once."""

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


@dataclass(frozen=True, slots=True)
class Step:
    """One use of `action`, costing `cost` every time it is taken, also when it changes nothing.

    `cost` is finite and not negative; zero is allowed (a free action). Raises `ValueError`
    otherwise, and for an `action` without an `outcomes` method.
    """

    action: Action
    cost: float

    def __post_init__(self) -> None:
        if not callable(getattr(self.action, "outcomes", None)):
            raise ValueError(f"a step needs an action with an outcomes(data, item) method, got {self.action!r}")
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
