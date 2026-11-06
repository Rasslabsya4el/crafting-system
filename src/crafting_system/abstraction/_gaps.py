"""The model gaps an abstraction met while it was walked (ticket #506, OR-13, OR-23).

A refusal of an action is one of two things. The game refuses (`NotApplicableError`): the plan is exact under it and nothing is said.
The model has no rule (`OutOfScopeError`): the action may be fine in the game, but the plan cannot use it there, and the answer has to say so.
`ModelGaps` is where the walk and the solve write the second kind: for each action (by its label in the offers) the states where it was
left out and the cause of the first refusal. The planner reads it at the end of the plan (`cli._plan.model_gap_limits`).

One `Abstraction` owns one `ModelGaps` (`Abstraction.gaps`); the walks of one plan share the abstraction, so they share the record. A state
that is met again (the bound pruning solves the same states again) counts once.
"""

from collections.abc import Hashable
from dataclasses import dataclass

from crafting_system.actions import ConsumesInputsError, OutOfScopeError

__all__ = ["PRUNED_CORRUPTING", "PRUNED_QUALITY", "Gap", "ModelGaps", "Prunings"]


@dataclass(frozen=True)
class Gap:
    """One action the model could not apply: how many states, the cause of the first refusal, and whether the cause is that it consumes other items (G6)."""

    label: str
    states: int
    cause: str
    consumes_inputs: bool
    blocks: bool = False  # `states` counts the blocks of a coarse level (groups of states), not item states


class ModelGaps:
    """The record of the model gaps met by one abstraction, by action label (see the module text)."""

    def __init__(self) -> None:
        self._states: dict[tuple[str, bool], set[Hashable]] = {}
        self._cause: dict[tuple[str, bool], tuple[str, bool]] = {}

    def note(self, label: str, state: Hashable, refusal: OutOfScopeError, *, block: bool = False) -> None:
        """Write that the model had no rule for the action `label` in `state`; with `block` the state is a block of a coarse level."""
        key = (label, block)
        self._states.setdefault(key, set()).add(state)
        self._cause.setdefault(key, (str(refusal), isinstance(refusal, ConsumesInputsError)))

    def __bool__(self) -> bool:
        return bool(self._states)

    def entries(self) -> tuple[Gap, ...]:
        """One `Gap` per action, in the order the actions first met a gap."""
        return tuple(Gap(label, len(states), *self._cause[(label, block)], block) for (label, block), states in self._states.items())


PRUNED_CORRUPTING = "corrupting"
PRUNED_QUALITY = "quality"


class Prunings:
    """The offers the planner left out of some states because they cannot be used there, by the reason (K13, ticket #506).

    Unlike a model gap this is exact: a corrupting action that keeps the mods (`Adds.corrupts`) is an action of a state only when the
    target's other requirements are met there (ADR-0036), and an action that only sets the quality only when everything else is (ADR-0029).
    The answer says which offers were left out and why, so that nothing the planner does to the offers is unsaid (OR-13).
    """

    def __init__(self) -> None:
        self._labels: dict[str, dict[str, None]] = {}

    def note(self, label: str, why: str) -> None:
        """Write that the offer `label` was left out of a state for the reason `why` (`PRUNED_CORRUPTING` or `PRUNED_QUALITY`)."""
        self._labels.setdefault(why, {})[label] = None

    def labels(self, why: str) -> tuple[str, ...]:
        """The offers left out of some state for the reason `why`, in the order they were first left out."""
        return tuple(self._labels.get(why, ()))
