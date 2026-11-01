"""The planner's actions as a model with donors, solved by the lazy offer loop (ticket #212, ADR-0062).

`DonorModel` is the full model `M` of `solver.solve_lazily` for an abstraction and priced offers: at a state every offer the
game allows is an action; an offer whose action consumes other items (`Action.inputs`, ADR-0022) is a candidate, an action
with `extra_inputs=(Need(start, want), ...)` over compressed states, and the solver offers the candidates as the solve needs
them. `solve_with_donors` is the whole step: it builds the model and hands it to the loop.

Seams, for the tickets that fill them in:

* **What a want is** (ADR-0062 decision 1). Here a `Need` is the compressed state of the donor the action names, and the
  acquisition ends at that exact state (`reaches` equality). The projection the consuming action reads (the Awakener's
  influence and influenced mods, the recombinator's compressed donor) is the action's to declare (tickets #214, #217): it
  changes `reaches`, which `solve_with_donors` passes on, and nothing else here.
* **Which donors exist.** A candidate per offer and state is what the catalog lists for the item in hand; a kind that offers
  donors of its own (ticket #217) lists them in its `members`, and each is one more offer.
* **The seed** (decision 4): `seed` takes the `Need` of the action on concrete items, `isolated_feeder` in `_offers` is the
  one ADR-0062 names. A route's donors are another.

Equal-kernel merging (`chosen_offers`) applies to the actions that take no input only: two donors with one kernel cost
different amounts to get, so neither may be dropped for the other. The planner (`make_plan`) does not use this yet; it
still refuses an action with inputs (`Abstraction(allow_inputs=False)`), until the report and the risk run read policies with inputs.
"""

import dataclasses
from collections.abc import Callable, Iterable

from crafting_system.abstraction import Abstraction, CompressedState
from crafting_system.actions import Action as GameAction
from crafting_system.actions import ActionError, Need as ItemNeed
from crafting_system.solver import Action, LazySolution, Need, solve_lazily

from ._offers import BuyStartItem, PricedOffer
from ._plan import offer_action
from ._prune import chosen_offers, solver_actions


def takes_inputs(action: GameAction) -> bool:
    """Whether the action's kind answers `inputs` itself: false for the base class's empty answer, so it is cheap to ask."""
    return type(action).inputs is not GameAction.inputs


class DonorModel:
    """The solver's view of the compressed states under the offers, donors included (the full model `M`).

    `actions(state)` lists, in the order of `offers`, the actions the offers give there: the input-free ones with equal
    kernels merged (`chosen_offers`, as the planner does) and one candidate for each offer whose action has inputs at that
    item. `needs(state, action)` gives the `Need`s of a candidate on concrete items, as the action asked for them.
    """

    def __init__(self, abstraction: Abstraction, start: CompressedState, offers: Iterable[PricedOffer]) -> None:
        self.abstraction = abstraction
        self.start = start
        self.offers = tuple(offers)
        self._free = tuple(p for p in self.offers if isinstance(p.offer.action, BuyStartItem) or not takes_inputs(p.offer.action))
        self._with = tuple(p for p in self.offers if p not in self._free)
        self._cache: dict = {}
        self._built: dict[CompressedState, tuple[Action[CompressedState], ...]] = {}
        self._needs: dict[tuple[CompressedState, str], tuple[ItemNeed, ...]] = {}

    def is_goal(self, state: CompressedState) -> bool:
        return self.abstraction.is_goal(state)

    def actions(self, state: CompressedState) -> tuple[Action[CompressedState], ...]:
        built = self._built.get(state)
        if built is None:
            found = solver_actions(self.abstraction, self._free, state, self.start, cache=self._cache)
            for priced in self._with:
                candidate = self._candidate(state, priced)
                if candidate is not None:
                    found.append(candidate)
            built = self._built[state] = tuple(found)
        return built

    def needs(self, state: CompressedState, action: Action[CompressedState]) -> tuple[ItemNeed, ...]:
        """The `Need`s of the action `actions(state)` gave, on concrete items (empty for an action without inputs)."""
        return self._needs.get((state, action.label), ())

    def _candidate(self, state: CompressedState, priced: PricedOffer) -> Action[CompressedState] | None:
        """The action of one offer that takes inputs, with its `Need`s over compressed states; None where the game refuses it."""
        try:
            wanted = self.abstraction.inputs(state, priced.offer.action)
            built = offer_action(self.abstraction, priced, state, self.start)
        except ActionError:  # the game refuses it here, or no admitted rule covers it
            return None
        if not wanted:
            return built
        self._needs[(state, priced.label)] = wanted
        compress = self.abstraction.compress
        return dataclasses.replace(built, extra_inputs=tuple(Need(compress(n.start), compress(n.want)) for n in wanted))


def solve_with_donors(
    abstraction: Abstraction,
    start: CompressedState,
    offers: Iterable[PricedOffer],
    *,
    seed: Callable[[ItemNeed], bool] | None = None,
    reaches: Callable[[CompressedState, CompressedState], bool] | None = None,
    **options,
) -> LazySolution[CompressedState]:
    """Solve the target from `start` with `offers`, taking the donors of the actions that need them lazily (ADR-0062).

    The abstraction must allow inputs (`allow_inputs=True`, its default). `seed(need)` says whether a donor is offered from
    the start: a candidate is seeded when it has inputs and the seed accepts every one of them. `reaches` is the want
    predicate for the acquisition processes (default: the donor's exact compressed state). `options` go to `solve_lazily`.
    """
    model = DonorModel(abstraction, start, offers)
    chosen = None
    if seed is not None:

        def chosen(state: CompressedState, action: Action[CompressedState]) -> bool:
            needs = model.needs(state, action)
            return bool(needs) and all(seed(need) for need in needs)

    return solve_lazily(model, start, reaches=reaches, seed=chosen, **options)
