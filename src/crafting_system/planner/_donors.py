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
different amounts to get, so neither may be dropped for the other. The planner (`make_plan`) does not use the loop yet; it
takes the donors the target names (its isolated feeders, ticket #225) and solves their product per reading of the rule axes with
`risk.solve_readings` (`_plan.solve_each_reading`): with a handful of donors the whole product is small, and the loop here is for many.
"""

import dataclasses
from collections.abc import Callable, Iterable

from crafting_system.abstraction import Abstraction, CompressedState, Status
from crafting_system.actions import Need as ItemNeed, NotApplicableError, OutOfScopeError
from crafting_system.solver import Action, LazySolution, Need, solve_lazily

from ._offers import BuyStartItem, PricedOffer, takes_inputs
from ._plan import offer_action
from ._prune import chosen_offers, solver_actions


def is_feeder(state: CompressedState) -> bool:
    """Whether the item holds nothing but target mods, each at a tier the target accepts (ticket #225): one mod for each requirement it meets.

    Every mod of a state that is not fractured is one of its slots, a target mod among them, so the item is made of target mods exactly when it
    has no fractured mod and as many slots as requirements it meets (a lower tier of a wanted family, or any other mod, is a slot that meets none).
    """
    met = sum(1 for status in state.status if status is Status.PASSING)
    return not state.fractured and len(state.slots) == met


class DonorModel:
    """The solver's view of the compressed states under the offers, donors included (the full model `M`).

    `actions(state)` lists, in the order of `offers`, the actions the offers give there: the input-free ones with equal
    kernels merged (`chosen_offers`, as the planner does) and one candidate for each offer whose action has inputs at that
    item. `needs(state, action)` gives the `Need`s of a candidate on concrete items, as the action asked for them.
    """

    def __init__(
        self,
        abstraction: Abstraction,
        start: CompressedState,
        offers: Iterable[PricedOffer],
        *,
        merge_equal: bool = True,
        feeders_only: bool = False,
    ) -> None:
        self.abstraction = abstraction
        self.feeders_only = feeders_only  # the planner's restriction (#225): only an item of target mods is recombined
        self.merge_equal = merge_equal  # the interval driver matches actions across readings by label, so it asks for no merging
        self.start = start
        self.offers = tuple(offers)
        self._free = tuple(p for p in self.offers if isinstance(p.offer.action, BuyStartItem) or not takes_inputs(p.offer.action))
        self._with = tuple(p for p in self.offers if p not in self._free)
        self._cache: dict = {}
        self._built: dict[CompressedState, tuple[Action[CompressedState], ...]] = {}
        self._needs: dict[tuple[CompressedState, str, tuple], tuple[ItemNeed, ...]] = {}

    def is_goal(self, state: CompressedState) -> bool:
        return self.abstraction.is_goal(state)

    def actions(self, state: CompressedState) -> tuple[Action[CompressedState], ...]:
        built = self._built.get(state)
        if built is None:
            found = solver_actions(self.abstraction, self._free, state, self.start, merge_equal=self.merge_equal, cache=self._cache)
            for priced in self._with:
                candidate = self._candidate(state, priced)
                if candidate is not None:
                    found.append(candidate)
            built = self._built[state] = tuple(found)
        return built

    def needs(self, state: CompressedState, action: Action[CompressedState]) -> tuple[ItemNeed, ...]:
        """The `Need`s of the action `actions(state)` gave, on concrete items (empty for an action without inputs)."""
        return self._needs.get((state, action.label, action.extra_inputs), ())

    def _candidate(self, state: CompressedState, priced: PricedOffer) -> Action[CompressedState] | None:
        """The action of one offer that takes inputs, with its `Need`s over compressed states; None where the game refuses it.

        With `feeders_only` an item in hand that holds anything but target mods at a tier the target accepts is not offered one (`is_feeder`).
        """
        if self.feeders_only and not is_feeder(state):
            return None
        try:
            wanted = self.abstraction.inputs(state, priced.offer.action)
            built = offer_action(self.abstraction, priced, state, self.start)
        except NotApplicableError:  # the game refuses it here
            return None
        except OutOfScopeError as gap:  # the model has no rule for it here: left out, and the answer says so (ticket #506)
            self.abstraction.gaps.note(priced.label, state, gap)
            return None
        if not wanted:
            return built
        compress = self.abstraction.compress
        candidate = dataclasses.replace(built, extra_inputs=tuple(Need(compress(n.start), compress(n.want)) for n in wanted))
        self._needs[(state, candidate.label, candidate.extra_inputs)] = wanted
        return candidate


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
