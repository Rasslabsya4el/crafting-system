"""Leave out the offers that cannot be the best choice anywhere, and prove it (ticket #118, piece E).

`solve_pruned` solves the plan on a small set S of the offers and then shows, with a certificate, that
the offers left out cannot improve any value of the solve. Everything is a filter over what an action
declares (`reads`, `adds`, `twin_key`) and over `reach_bound`; no action class is named here.

TWINS. Offers with an equal, non-None `Action.twin_key(data, item)` give equal outcomes in every state:
only the cheapest of a group (the earliest on a tie) is kept. Exact: swapping a dearer twin for the
cheaper one in any policy lowers or keeps its cost and changes nothing else.

THE NUMBER pbar. Let U be a set of NECESSARY goal leaves (a leaf is necessary when it sits directly under
the requirements, or only under `AtLeast` nodes with k equal to the number of members; U is the necessary
leaves that are not PASSING at the start, less the ones a bench craft can finish when something is left).
Let E be "every leaf of U is PASSING". The goal implies E, and the start is outside E. For an offer x,
pbar(x) is a number such that one use of x, from ANY state outside E that has the flags and the fractured
mods of the start, lands in E with chance at most pbar(x):
  * `restart` lands on the start, outside E: pbar = 0.
  * an erasing reroll (it does not read the junk, erases the crafted mods, does not fracture, keeps the
    flags and the fractured mods of the item): its result does not depend on the state but through the
    flags and the fractured mods, so the exact chance at one state is the chance at every such state.
    Level 0 is pbar = 1, level 1 is `reach_bound` (an upper bound from the pool), level 2 is the exact
    chance (`reach_bound(..., exact=True)`). All are read on the BARE item of the start's shape (no mods
    but the fractured ones): a reroll refused there is refused wherever the shape holds (it reads
    nothing else), so it is set aside as inapplicable.
  * a bench craft (reads the junk, adds a named mod, draws nothing, does not fracture): it only adds a
    mod, so it makes a leaf of U PASSING only if the mod is one of that leaf's: pbar = 1 if its named
    mods meet the mods of a leaf of U, else 0. It stays in the model.
  * anything else (it fractures, changes the flags, draws and reads the junk, has no bound, is unknown):
    TERMINAL, pbar = 1, and the argument below is cut at its first use.

THE LOWER BOUND rho. rho = min over the offers of cost / pbar (an offer with pbar = 0 counts for infinity);
it is found best first, so that the dear bounds are computed only where they matter: a heap on cost / pbar
with every reroll at level 0; pop the smallest; if it is a reroll below level 2, raise its level and push
it back; stop when the smallest is at level 2 or is not a reroll. Raising a level only lowers pbar, so the
ratios only grow, and the one that stops the loop is the least ratio of all. Claim (Wald): V*(s) >= rho for
every state s outside E with the flags and the fractured mods of the start, in the FULL model.
Proof. A policy from s that reaches the goal almost surely enters E (the goal implies E) at a first time T.
Let tau be the first use of a terminal action and N = min(T, tau). Until N every action used is one of
`restart`, a bench craft or an erasing reroll, none of which moves the flags and the fractured mods, so
the state keeps the shape of the start and, given the history, the chance of entering E at step t is at
most pbar(a_t). With probability 1 either E is entered at a step before tau, or a terminal action is used
(and the first one is at step tau). So 1 <= sum over t <= N of E[w(a_t)] with w = pbar for the others and
w = 1 for a terminal action, and the cost of the policy is at least E[sum over t <= N of cost(a_t)] >=
rho * E[sum w(a_t)] >= rho, since cost(a) >= rho * w(a) for every offer a.

THE CERTIFICATE. S starts as the `restart`, the bench crafts and the K = 8 rerolls of least cost / pbar (a terminal
offer is not in it: it enters S only when it fails the test below, so that a Fractured set dearer than the plan
never moves the item to another shape). Each
round solves the model on S (the solver of the plan, equal kernels merged per state), then, with J the
largest finite value over the reachable non-goal states and T = J (1 + error bound) + a hair, tests every
offer a outside S: LBQ(a) = cost(a) + (1 - pbar(a)) * rho (a terminal offer has pbar = 1, so LBQ = cost).
If LBQ(a) > T, a is PROVED NOT NEEDED. The offers that fail the test are brought level by level to their
exact pbar (levels 1 and 2) and tested again; those that still fail join S (the 16 of least LBQ, or all on
the last round), and the next round solves again. When no offer outside S fails, the final J is the optimal
value of the full model at every reachable state. Proof. J >= V* because S is a subset of the offers.
Say a* is optimal for V* at a reachable state s0 of the model on S. If a* is outside S, then V*(s0) =
Q*(s0, a*) >= LBQ(a*) > T >= J(s0) >= V*(s0): the successors of a* outside E (all but a chance pbar of
them, and the shape is the start's because the model on S never leaves it, which is checked) have V* >= rho
by the claim, the others >= 0; a terminal a* costs at least cost(a*). A contradiction, so a* is in S at
every reachable state. Let D be the largest J - V* over the reachable states and suppose D > 0 at s0.
The optimal a* is in S, so J(s0) <= Q_J(s0, a*) and V*(s0) = Q*(s0, a*) >= Q_J(s0, a*) - D * P(a* leaves
the goal) >= J(s0) - D P(leaves). With J(s0) - V*(s0) = D this forces P(leaves) = 1, and every successor
is a maximiser again (J - V* = D) with Q_J = J. The stationary optimal policy of the full model then
stays among the maximisers for ever and never reaches the goal, which contradicts its being proper.
So D = 0: J = V* at every reachable state, and the policy of the last solve is optimal.

WHAT THE ARGUMENT NEEDS, and what is checked. (1) Every reachable non-goal state of the model on S has
the flags and the fractured mods of the start; if not (a terminal offer in S moved the item), or if a
value is infinite and no offer is left to add, or the solver cannot certify its values, the bound is dropped:
S becomes all the offers that remain after the twins, which are exact on their own ("fell back"). An infinite
value with offers left makes the next round add the cheapest ones instead. (2) An offer that the game refuses on the bare item of
the start's shape never applies at a state of that shape (a reroll reads nothing of the item that the
shape does not hold; a crafted mod can only add refusals). This is an assumption on the contract of
`Reads`, not a check. (3) An erasing reroll keeps the shape, which `keeps_shape` checks at the bare item.
(4) The bound of `reach_bound` is a proof by its own tests. Floats: rho is lowered by 1e-12 of itself and
LBQ compared after the same factor; J is raised by its certified error bound.
"""

import heapq
import math
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction

from crafting_system import parallel
from crafting_system.abstraction import (
    Abstraction,
    AtLeast,
    CompressedState,
    Status,
    Wanted,
    keeps_shape,
    reach_bound,
)
from crafting_system.actions import ActionError
from crafting_system.data import GameData
from crafting_system.items import Item
from crafting_system.solver import ConvergenceError, Solution, solve

from ._offers import BuyStartItem, PricedOffer

ZERO, ONE = Fraction(0), Fraction(1)

SMALL_START = 8  # the rerolls of least cost / pbar that the first round holds
PER_ROUND = 16  # the offers that fail the test and join S in one round
SLACK = 1e-12  # float slack on rho and on the test
HUGE = 1e300  # stands for an infinite rho (nothing can reach E): keeps 0 * rho at 0

PROGRESS: Callable[[str], None] | None = None  # a measuring script sets it to see each phase as it ends (never set by the library)

RESTART_KIND, CRAFT, REROLL, TERMINAL, REFUSED = "restart", "craft", "reroll", "terminal", "refused"


@dataclass(frozen=True)
class Pruned:
    """What `solve_pruned` found: the solution on the offers it kept, and how it got there."""

    solution: Solution[CompressedState]
    used: tuple[PricedOffer, ...]  # the offers of the last solve
    twins: tuple[tuple[str, str], ...]  # (dropped label, kept label)
    bounded: tuple[str, ...]  # labels proved not needed
    rounds: int  # solves made
    rho: float
    j_max: float
    fell_back: bool
    why: str = ""
    inapplicable: tuple[str, ...] = ()  # labels the game refuses on the bare item of the start's shape
    phases: tuple[tuple[str, float], ...] = field(default=(), compare=False)  # (phase, seconds), for the measure


@dataclass
class _Entry:
    """One offer after the twins: what kind it is, the level of its bound, and its pbar."""

    index: int
    priced: PricedOffer
    kind: str
    level: int = 0
    pbar: Fraction = ONE

    @property
    def cost(self) -> float:
        return self.priced.cost

    @property
    def ratio(self) -> float:
        """cost / pbar as a float; infinity for a pbar of 0."""
        return math.inf if self.pbar == 0 else float(Fraction(self.cost) / self.pbar)


def necessary_leaves(goal) -> tuple[int, ...]:
    """The indexes (into `goal.leaves`) of the leaves every goal state must have PASSING.

    A leaf sits directly under the requirements, or only under `AtLeast` nodes whose k is their number of members.
    """
    found: list[int] = []

    def walk(node, position: int, necessary: bool) -> int:
        if isinstance(node, Wanted):
            if necessary:
                found.append(position)
            return position + 1
        keep = necessary and node.k == len(node.members)
        for member in node.members:
            position = walk(member, position, keep)
        return position

    position = 0
    for node in goal.requirements:
        position = walk(node, position, True)
    return tuple(found)


def goal_set(goal, start: CompressedState, finished_by_crafts: frozenset[str]) -> tuple[int, ...]:
    """U: the necessary leaves not PASSING at the start, less those a bench craft can finish (if any remain).

    `finished_by_crafts` are the mod ids that offered crafts add by name.
    """
    open_leaves = [index for index in necessary_leaves(goal) if start.status[index] is not Status.PASSING]
    kept = [index for index in open_leaves if not goal.leaves[index].mod_ids & finished_by_crafts]
    return tuple(kept or open_leaves)


def merge_twins(
    data: GameData, item: Item, priced: Sequence[PricedOffer]
) -> tuple[list[PricedOffer], list[tuple[str, str]]]:
    """`priced` without the offers that have a cheaper twin (equal non-None `twin_key` on `item`), and the (dropped, kept) labels.

    Exact (see TWINS above). `restart` has no twin. Used by the solve and by the forecast of a plan with a budget, which
    must not pay for 10,000 fossil sets that fall into a few thousand classes.
    """
    first_of: dict[object, int] = {}  # twin key -> position of the cheapest offer so far
    twins: list[tuple[str, str]] = []
    dropped: set[int] = set()
    for position, offer in enumerate(priced):
        if isinstance(offer.offer.action, BuyStartItem):
            continue
        key = offer.offer.action.twin_key(data, item)
        if key is None:
            continue
        kept = first_of.get(key)
        if kept is None:
            first_of[key] = position
        elif offer.cost < priced[kept].cost:
            twins.append((priced[kept].label, offer.label))
            dropped.add(kept)
            first_of[key] = position
        else:
            twins.append((offer.label, priced[kept].label))
            dropped.add(position)
    return [offer for position, offer in enumerate(priced) if position not in dropped], twins


def solve_pruned(
    abstraction: Abstraction,
    start: CompressedState,
    priced: Sequence[PricedOffer],
    item: Item,
    *,
    rounds: int = 8,
    min_offers: int = 40,
) -> Pruned:
    """Solve the plan of `priced` from `start` on as few offers as the certificate allows; see the module text.

    `item` is the start item (the twin key is read on it). With fewer than `min_offers` offers nothing is
    left out but the twins (there is nothing to gain). Raises what `solve` raises when even the fallback fails.
    """
    found = _run(abstraction, start, priced, item, rounds, min_offers, False)
    assert isinstance(found, Pruned)
    return found


def starting_offers(
    abstraction: Abstraction, start: CompressedState, priced: Sequence[PricedOffer], item: Item, *, min_offers: int = 40
) -> list[PricedOffer]:
    """The offers `solve_pruned` solves first: the twins merged, then `restart`, the crafts and the best rerolls.

    The size of the exact run is forecast on these (the rounds that follow add a few offers each), so that a plan with a
    budget does not pay for a pilot over thousands of fossil sets that the certificate then proves not needed.
    With fewer than `min_offers` offers it is all of them.
    """
    found = _run(abstraction, start, priced, item, 0, min_offers, True)
    assert not isinstance(found, Pruned)
    return found


def _run(
    abstraction: Abstraction,
    start: CompressedState,
    priced: Sequence[PricedOffer],
    item: Item,
    rounds: int,
    min_offers: int,
    start_set_only: bool,
) -> "Pruned | list[PricedOffer]":
    from ._plan import _Model  # _plan imports this module

    if len(priced) < min_offers and start_set_only:
        return list(priced)
    if len(priced) < min_offers:
        everything = solve(_Model(abstraction, start, priced), [start])
        return Pruned(everything, tuple(priced), (), (), 1, 0.0, _largest(everything, abstraction), True, f"fewer than {min_offers} offers: nothing to gain")
    data = abstraction.data
    phases: list[tuple[str, float]] = []
    clock = time.perf_counter()

    def mark(name: str) -> None:
        nonlocal clock
        now = time.perf_counter()
        phases.append((name, now - clock))
        if PROGRESS is not None:
            PROGRESS(f"{name}: {now - clock:.1f} s")
        clock = now

    # 1. twins
    remaining, twins = merge_twins(data, item, priced)
    mark("twins")

    cache: dict = {}

    def solve_on(offers: Iterable[PricedOffer]) -> Solution[CompressedState]:
        return solve(_Model(abstraction, start, offers, cache), [start])

    def fallback(why: str, spent: int) -> Pruned:
        solution = solve_on(remaining)
        mark("fallback solve")
        return Pruned(
            solution, tuple(remaining), tuple(twins), (), spent + 1, 0.0, _largest(solution, abstraction), True,
            why, (), tuple(phases),
        )

    # 2. classify
    goal = abstraction.goal
    crafts = frozenset()
    kinds: dict[int, tuple[str, frozenset[str]]] = {}
    for index, offer in enumerate(remaining):
        kind, named = _kind_of(data, item, offer)
        kinds[index] = (kind, named)
        if kind == CRAFT:
            crafts |= named
    chosen = goal_set(goal, start, crafts)
    u_mods = frozenset().union(*(goal.leaves[index].mod_ids for index in chosen)) if chosen else frozenset()
    entries: list[_Entry] = []
    for index, offer in enumerate(remaining):
        kind, named = kinds[index]
        pbar = ONE
        if kind == RESTART_KIND:
            pbar = ZERO
        elif kind == CRAFT:
            pbar = ONE if named & u_mods else ZERO
        entries.append(_Entry(index, offer, kind, 0, pbar))
    bare = replace(start, slots=())
    mark("classify")

    def raise_level(entry: _Entry, level: int) -> None:
        """Bring a reroll to `level` (1: the loose bound, 2: the exact chance).

        It becomes refused when the game refuses it on the bare item, and terminal when it fractures, keeps
        the crafted mods, needs one, moves the flags or the fractured mods, or `reach_bound` has no bound.
        """
        entry.kind, entry.pbar, entry.level = _raised(
            abstraction, bare, item, chosen, entry.priced.offer.action, entry.kind, entry.level, entry.pbar, level
        )

    def raise_together(batch: list[tuple[_Entry, int]]) -> None:
        """`raise_level` for each (entry, level) of the batch, side by side in a process pool when `CRAFTING_WORKERS` allows (#250).

        The bounds of different offers read nothing of each other, so each entry ends in the state its own `raise_level` gives.
        """
        if len(batch) >= 2 and parallel.worker_count() >= 2 and parallel.can_inherit():
            jobs = [(entry.priced.offer.action, entry.kind, entry.level, entry.pbar, level) for entry, level in batch]
            try:
                with parallel.WorkerPool(_hold, (abstraction, bare, item, chosen, jobs), workers=min(parallel.worker_count(), len(jobs))) as pool:
                    results = pool.map(_raise_job, range(len(jobs)), chunk=1)  # one at a time: the exact bounds differ in cost by orders of magnitude
            except Exception:  # a worker failed: raise them here, as a serial run does
                results = None
            if results is not None:
                for (entry, _), (kind, pbar, reached) in zip(batch, results):
                    entry.kind, entry.pbar, entry.level = kind, pbar, reached
                return
        for entry, level in batch:
            raise_level(entry, level)

    # 3. rho, best first
    rho = best_first_rho(entries, raise_level) if chosen else 0.0
    mark("bounds (rho)")

    # 4. rounds
    inside = {entry.index for entry in entries if entry.kind in (RESTART_KIND, CRAFT)}
    rerolls = sorted((entry for entry in entries if entry.kind == REROLL), key=lambda entry: (entry.ratio, entry.index))
    inside.update(entry.index for entry in rerolls[:SMALL_START])
    if not inside:  # nothing to start from: the cheapest offers
        inside.update(entry.index for entry in sorted(entries, key=lambda entry: (entry.cost, entry.index))[:SMALL_START])
    if start_set_only:
        return [entry.priced for entry in entries if entry.index in inside]
    spent = 0
    while spent < rounds:
        spent += 1
        offers = [entry.priced for entry in entries if entry.index in inside]
        try:
            solution = solve_on(offers)
        except ConvergenceError as problem:
            mark(f"solve {spent}")
            return fallback(f"the solver could not converge on the reduced model ({problem})", spent)
        mark(f"solve {spent} ({len(offers)} offers, {len(solution.values)} states)")
        non_goal = [state for state in solution.values if not abstraction.is_goal(state)]
        moved = [state for state in non_goal if state.flags != start.flags or state.fractured != start.fractured]
        if moved:
            return fallback("an offer moves the item to another shape (flags or fractured mods)", spent)
        if not _finite(solution.error_bound):
            return fallback("the solver could not certify its values", spent)
        infinite = any(not _finite(solution.values[state]) for state in non_goal)
        j_max = max((solution.values[s] for s in non_goal if _finite(solution.values[s])), default=0.0)
        bound = j_max * (1 + max(solution.error_bound, 1e-9)) + 1e-9
        failing: list[tuple[float, _Entry]] = []
        if not infinite and parallel.worker_count() >= 2 and parallel.can_inherit():  # the loop below raises each offer one level at a time; the offers' raises are independent, so do a level for all of them at once (with one worker the loop is the old one)
            for level in (1, 2):
                raise_together([
                    (entry, level)
                    for entry in entries
                    if entry.index not in inside and entry.kind == REROLL and entry.level < level
                    and _lower(entry, rho) * (1 - SLACK) <= bound
                ])  # fmt: skip
        for entry in entries:
            if entry.index in inside or entry.kind == REFUSED:
                continue
            if infinite:  # the model on S lacks a proper policy somewhere: it needs more offers, whatever they bound
                failing.append((entry.cost, entry))
                continue
            for level in (0, 1, 2):
                if level and entry.kind == REROLL and entry.level < level:
                    raise_level(entry, level)
                if entry.kind == REFUSED:
                    break
                if _lower(entry, rho) * (1 - SLACK) > bound:
                    break
                if entry.kind != REROLL or entry.level >= 2:
                    failing.append((_lower(entry, rho), entry))
                    break
        mark(f"test {spent}")
        if not failing and not infinite:
            outside = [entry for entry in entries if entry.index not in inside]
            bounded = tuple(entry.priced.label for entry in outside if entry.kind != REFUSED)
            refused = tuple(entry.priced.label for entry in outside if entry.kind == REFUSED)
            return Pruned(
                solution, tuple(offers), tuple(twins), bounded, spent, rho, j_max, False, "", refused, tuple(phases)
            )
        if not failing:  # an infinite value with every offer already in S: the full model has the same dead state
            return fallback("a reachable state has no proper policy", spent)
        failing.sort(key=lambda pair: (pair[0], pair[1].index))
        last = spent == rounds - 1
        inside.update(entry.index for _, entry in (failing if last else failing[:PER_ROUND]))
    return fallback(f"the certificate did not close within {rounds} rounds", spent)


def _raised(abstraction, bare, item, chosen, action, kind: str, level: int, pbar: Fraction, target: int) -> tuple[str, Fraction, int]:
    """The `(kind, pbar, level)` of a reroll brought to `target` (see `raise_level`); a function of its arguments alone."""
    data = abstraction.data
    if level == 0:
        try:
            same_shape = keeps_shape(abstraction, bare, action)
        except ActionError:
            return REFUSED, ONE, level
        adds = action.adds(data, item)
        if not same_shape or adds.fractures or adds.keeps_crafted or action.reads(data).needs_crafted:
            return TERMINAL, ONE, level
        level = 1
        found = reach_bound(abstraction, bare, action, chosen) if chosen else ZERO
        if found is None:
            return TERMINAL, ONE, level
        pbar = found
    if target >= 2 and level < 2 and kind == REROLL:
        level = 2
        exact = reach_bound(abstraction, bare, action, chosen, exact=True) if chosen else ZERO
        if exact is not None and exact < pbar:
            pbar = exact
    return kind, pbar, level


def _hold(abstraction, bare, item, chosen, jobs: list) -> tuple:
    return abstraction, bare, item, chosen, jobs


def _raise_job(index: int) -> tuple[str, Fraction, int]:
    abstraction, bare, item, chosen, jobs = parallel.context()
    action, kind, level, pbar, target = jobs[index]
    return _raised(abstraction, bare, item, chosen, action, kind, level, pbar, target)


def best_first_rho(entries: Sequence[_Entry], raise_level: Callable[[_Entry, int], None]) -> float:
    """The least cost / pbar over the entries, found best first so that the dear bounds are computed only where needed.

    A heap on cost / pbar holds every entry at its current level. Pop the smallest; a reroll below
    level 2 is brought one level up (`raise_level`, which only lowers its pbar, so its ratio only grows)
    and pushed back; the loop stops at the first pop that is not a reroll or is at level 2. Every other
    entry has a current ratio at least as large and a true ratio at least as large as its current one,
    so the popped ratio is the least of all. Returns it, lowered by `SLACK` of itself.
    """
    heap = [(entry.ratio, entry.index) for entry in entries]
    heapq.heapify(heap)
    while heap:
        ratio, index = heapq.heappop(heap)
        entry = entries[index]
        if entry.kind == REFUSED:
            continue
        if entry.kind != REROLL or entry.level >= 2:
            return min(ratio, HUGE) * (1 - SLACK)
        raise_level(entry, entry.level + 1)
        heapq.heappush(heap, (entry.ratio, index))
    return 0.0


def _lower(entry: _Entry, rho: float) -> float:
    """LBQ: a lower bound on the cost-to-go of using the offer once: its cost plus, off E, rho."""
    return entry.cost + float(1 - entry.pbar) * rho


def _finite(value: float) -> bool:
    return value == value and value != math.inf


def _largest(solution: Solution[CompressedState], abstraction: Abstraction) -> float:
    values = [v for s, v in solution.values.items() if not abstraction.is_goal(s) and _finite(v)]
    return max(values, default=0.0)


def _kind_of(data, item: Item, offer: PricedOffer) -> tuple[str, frozenset[str]]:
    """The kind of an offer from what its action declares, and (for a craft) the mods it adds by name.

    An action that does not read the junk starts as a reroll; whether it is refused, terminal or bounded
    is found when its bound is first needed (`raise_level`), because that needs the bare item.
    """
    action = offer.offer.action
    if isinstance(action, BuyStartItem):
        return RESTART_KIND, frozenset()
    reads = action.reads(data)
    if reads.item_state:
        return TERMINAL, frozenset()  # its result depends on the implicits, the quality or the offer, which the bound read at one state does not hold fixed
    if not reads.junk:
        return REROLL, frozenset()
    adds = action.adds(data, item)
    if not adds.fractures and not adds.draws and adds.named is not None:
        return CRAFT, frozenset(adds.named)
    return TERMINAL, frozenset()
