"""The acquisition adapter (ADR-0022): a base model whose actions need other items, as a product.

A `Need(start, want)` in the `extra_inputs` of a base action asks for one more item: it begins in
base state `start` and must reach base state `want`. `Acquisition` wraps the base model into a
product model over states `('in', want, s)`, where `want` is `MAIN` for the main target and
otherwise a wanted base state, and `s` is the base state the item is in now. The product has
(G+1) x S states for G distinct wanted items over S base states. The solver explores it lazily,
so only the copies that are reachable get built. A base model with no `Need` gives a product that
is the base model under the `MAIN` tag, with the same values as without the wrapper.
"""

import operator
from collections.abc import Callable
from dataclasses import dataclass, replace

from ._model import Action, Model, Outcome


@dataclass(frozen=True, slots=True)
class Need[S]:
    """An item that begins in base state `start` and must reach `want`."""

    start: S
    want: S


class _Main:
    """The sentinel `want` of the main target: one object, `MAIN`, which copies return as itself."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "MAIN"

    def __copy__(self) -> "_Main":
        return self

    def __deepcopy__(self, memo: dict) -> "_Main":
        return self

    def __reduce__(self) -> str:
        return "MAIN"


MAIN = _Main()


class Acquisition[S]:
    """A base model with `Need`s in its extra inputs, as a product model the solver can run.

    A product state is the plain tuple `('in', want, s)`: the item wanted (`MAIN` or a base state)
    and the base state `s` the item is in. The main target is `start(state)`, which is
    `('in', MAIN, state)`. Outcomes stay in their `want`. A `Need(start, w2)` among the extra
    inputs of an action becomes the product state `('in', w2, start)`, so a Need nests: the
    inputs of an acquisition process are again Needs. Labels and costs are kept; a repeated Need
    stays repeated, as copies.

    A product state is a goal when `s` reaches `want`. For `MAIN` that is `base.is_goal(s)`.
    Otherwise it is `reaches(s, want)`, and the default `reaches` is `s == want`. `reaches` is the
    want predicate for dominance: a state that dominates the wanted one (has everything `want`
    has) may end the acquisition early, so `reaches` may be wider than equality.

    Starts of `solve` must be product states, made by `start(state)`; a plain base state is not
    one and is not checked.

    An extra input that is not a `Need` raises `TypeError`, so a base model cannot mix plain and
    acquired inputs without notice. The product's actions are built on each call and not cached,
    as the solver calls them once per product state.
    """

    def __init__(
        self, base: Model[S], *, reaches: Callable[[S, S], bool] | None = None
    ) -> None:
        self._base = base
        self._reaches = reaches if reaches is not None else operator.eq

    def start(self, state: S) -> tuple:
        return ("in", MAIN, state)

    def is_goal(self, product: tuple) -> bool:
        _, want, state = product
        if want is MAIN:
            return self._base.is_goal(state)
        return self._reaches(state, want)

    def actions(self, product: tuple) -> tuple[Action, ...]:
        _, want, state = product
        result = []
        for action in self._base.actions(state):
            outcomes = tuple(Outcome(("in", want, t), w) for t, w in action.outcomes)
            extra_inputs = []
            for entry in action.extra_inputs:
                if not isinstance(entry, Need):
                    raise TypeError(
                        f"extra input {entry!r} of an action in base state {state!r} "
                        f"(wanted {want!r}) is not a Need: a base model whose actions have "
                        "extra inputs must write every one as Need(start, want)"
                    )
                extra_inputs.append(("in", entry.want, entry.start))
            result.append(
                replace(action, outcomes=outcomes, extra_inputs=tuple(extra_inputs))
            )
        return tuple(result)
