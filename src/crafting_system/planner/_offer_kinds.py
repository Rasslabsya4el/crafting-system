"""What each offer can cost at least, from what its action declares: the twins, the kinds, `pbar` and the floor `rho` (tickets #118, #626, #829).

The bound pruning that used to solve the plan on a few offers and certify the rest (`solve_pruned`, retired with the 40-offer switch, #829)
was built on these pieces; the offers' floors of the bound and of the envelope search (`_offer_floor`) are what is left of it. Everything is a
filter over what an action declares (`reads`, `adds`, `twin_key`, `reach_batch`) and over `reach_bound`; no action class is named here.

TWINS. Offers with an equal, non-None `Action.twin_key(data, item)` give equal outcomes in every state:
only the cheapest of a group (the earliest on a tie) is kept. Exact: swapping a dearer twin for the
cheaper one in any policy lowers or keeps its cost and changes nothing else.

THE NUMBER pbar. Let U be a set of NECESSARY goal leaves (a leaf is necessary when it sits directly under
the requirements, or only under `AtLeast` nodes with k equal to the number of members; U is the necessary
leaves that are not PASSING at the start, less the ones a bench craft or a veiled choice can finish when something is left: one a mod
it adds can pass, by the leaf's tier limit and its refusal of crafted mods, `finishes`, #1112, #1074).
Let E be "every leaf of U is PASSING". The goal implies E, and the start is outside E. For an offer x,
pbar(x) is a number such that one use of x, from ANY state outside E that has the flags and the fractured
mods of the start, lands in E with chance at most pbar(x):
  * `restart` lands on the start, outside E: pbar = 0. When the start is an unopened listing (ADR-0064) the restart lands
    there instead, a state of another shape where only the draw that opens it works, and the draw can land in E. A restart
    is then counted with the draw that must follow it (`through_listing`): one use of cost c(restart) + c(draw), with
    pbar = the chance that the draw from the listing does not land outside E in the shape (the claim below holds because
    from a state of the shape the listing is entered only by a restart, so each draw used follows a restart of its own).
  * an erasing reroll (it does not read the junk, erases the crafted mods, does not fracture, keeps the
    flags and the fractured mods of the item): its result does not depend on the state but through the
    flags and the fractured mods, so the exact chance at one state is the chance at every such state.
    Level 0 is pbar = 1, or the bound its class declares without building an outcome when it declares one
    (`declared_pbars`, #1073: `Action.reach_batch` for every offer of the class at once, through
    `declared_bounds`; only for an action that declares it keeps the flags and the fractured mods, and that
    declares no fracture, no kept crafted mod and no need of one, the conditions of level 1 that `adds` and
    `reads` answer); level 1 is `reach_bound` (an upper bound from the pool), kept at the declared bound when
    that is lower, level 2 is the exact chance (`reach_bound(..., exact=True)`). Each level is an upper bound
    on the same chance, so a level reached lowers pbar or keeps it, and the least of two is one. A declared
    bound of 0 (no mod that can pass a leaf of U has weight in the set's pool, and none is forced: R05's
    `StrengthEssence7_`, an essence-only mod) is exact, so the offer's ratio is infinite and it is never raised.
    That the action keeps the shape is then the class's declaration, not `keeps_shape`'s check; the contract
    tests of the class compare the two. All are read on the BARE item of the start's shape (no mods
    but the fractured ones): a reroll refused there is refused wherever the shape holds (it reads
    nothing else), so it is set aside as inapplicable.
  * a bench craft (reads the junk, adds a named mod, draws nothing, does not fracture): it only adds a
    mod, so it makes a leaf of U PASSING only if the mod can pass that leaf (`finishes`: one of its mods the
    tier limit accepts, and not crafted where the leaf refuses crafted mods): pbar = 1 if one of its named
    mods can pass a leaf of U, else 0. It stays in the model.
  * a veiled choice (#1074: an action that needs the veiled placeholder, `Reads.needs_veiled`, an Unveil or a Pick, offered to a start item
    that holds no placeholder; it draws no mod, fractures nothing and changes no implicit, quality, corruption, imprint or veil): it acts only
    on the placeholder, and the mod it may put on the item is one it names, or (a pick, which names none) a mod of the unveiled pool of the base
    (`unveil_pool_mods`): the placeholder gives way to that mod, and a mod the action removes passes no leaf. So, like a craft, pbar = 1 if
    one of those mods can pass a leaf of U (`finishes`), else 0; the Unveil names no mod (it only draws the offer): pbar = 0. Before #1074 they
    were TERMINAL (they read the offer, `Reads.item_state`), and as free actions (ADR-0026, a price of about 1e-8) they set rho to their price
    in every search that offered them: the floor of every key outside the model was then about 0 (#1112's single search over R05's offers).
    Its use keeps the shape: the placeholder of a state of the start's shape is never fractured (the start holds none, and only a terminal
    offer fractures), so the picked mod is not, and the flags stay (that an action that needs the placeholder changes no flag but by what
    `Adds` declares is the contract of `Reads.needs_veiled`, not a check). A start item that holds a placeholder keeps them TERMINAL.
  * an addition (#1072): it keeps the mods and adds one mod drawn from the pool less the families on the item
    (`Reads.pool_weight` with `variants` or `draw_tags`: an Exalted Orb, an Eldritch Exalted Orb, an Orb of Augmentation;
    it draws, names no mod, fractures nothing, reads no roll, input or influence). A Regal Orb (it changes the rarity, so it
    leaves the shape) and a Harvest add/remove (it also removes a mod: not one drawn mod added to the mods kept) are of this
    kind but get no bound, so they stay TERMINAL (#1084). Its
    chance depends on the families the item holds, so it cannot be read at one state: pbar is the largest chance,
    over every state of the start's shape at which a leaf of U is not PASSING, that the one added mod passes that
    leaf (`add_bound`: the most favourable weight share of the free families, every set of families held and
    every room left; the argument is in `abstraction/_bound.py`, "One added mod"). From a state outside E, E is
    entered only if a leaf of U that is not PASSING becomes PASSING, which only the added mod can do (a mod the
    action removes passes no leaf), so the chance is at most pbar. Level 0 is pbar = 1, level 1 that bound. It is
    raised only where the bare item of the shape takes it, keeps the shape, and gives one draw; anywhere else
    (refused there, which proves nothing for a state holding more mods; another shape; not one draw) it is TERMINAL.
    An action whose class declares its one added mod for the shape (`Action.added_draw`, #1074) is an addition too, whatever it reads: the
    Beastcraft side swap (one mod drawn on its side at the beast level, then a mod of the other side removed: the bare item refuses it, having
    nothing to remove) and the Eldritch Exalted Orb (the ordinary draw on the dominant side: the implicits pick the side, and the bound ranges over
    every side alone). Its bound is `declared_add_bound`, the same bound read from the declared pool; that the action keeps the shape is the
    declaration's, which the contract suite compares with the built outcomes.
  * an implicit change (#1074: it changes the implicits, `Adds.implicits`, and puts no explicit mod on: `Adds.named` empty, no draw, no fracture,
    corruption, quality, offer, imprint or veil; an Ember, an Ichor, an Orb of Conflict, a Blessed Orb): E reads the explicit leaves only (the
    implicits wanted are not leaves of U), and no explicit mod changes, so one use never lands in E: pbar 0, once its use at the bare item keeps
    the shape (level 1; refused there or leaving it: TERMINAL, so an Orb of Conflict, which needs both Eldritch implicits, stays TERMINAL
    from a start that holds fewer). That the states it leads to differ in their implicits changes no other pbar: no
    offer of the other kinds reads the implicits, but an addition whose class declares its draw, whose bound ranges over every side. Before
    #1074 they were TERMINAL (they read the implicits), and a Lesser Eldritch Ember set rho at its price (R10 and R11's single search: 0.2432).
  * a veil (#1074: it puts a veiled placeholder on, `Adds.veils`, names no mod and draws none, reads the junk and needs no placeholder: a
    Veiled Exalted Orb, which removes a mod and puts a placeholder in its place): the one mod it adds is a placeholder (`placeholder_mods`; an
    action that declares a veil and no draw adds no other: the contract of `Adds.veils`, not a check), which passes no leaf, so pbar = 1 if a
    placeholder can pass a leaf of U (`finishes`), else 0. The placeholder is not fractured (only a terminal offer fractures), so the veiled
    choices that follow keep the shape. It is not in the bound's starting model (`NAMING`): it names no goal mod.
  * a restore of an imprint (#1074: `Action.imprint_move()` restores), offered to a start item that holds no imprint: an imprint is made only by
    an offer that reads and changes the imprints (`Reads.item_state`), a TERMINAL one, so no state before the first terminal use holds one, and
    the restore is never used there: it is set aside as REFUSED (it is free, ADR-0026, so as a TERMINAL offer it set rho to its price, about
    1e-8, in every search that offered it: #1112's single search over R05's offers, once the veiled choices no longer did). A state that holds an
    imprint is then of another shape (`_offer_floor.OfferFloors.klass`): from there a restore may bring back a state in E for that price.
  * anything else (it fractures, changes the flags, draws and reads the junk otherwise, has no bound, is unknown):
    TERMINAL, pbar = 1, and the argument below is cut at its first use. A Fracturing Orb (and a Beastcraft talisman fracture) is TERMINAL for
    good: it lands in E with chance 0, but it changes the fractured mods, the shape every reroll's pbar is read at, and a fractured mod that
    passes a leaf of U raises the chance of a reroll after it (fracture, then reroll: the route a player takes), so no pbar read at the start's
    shape bounds the uses that follow it. Its floor is its price, the floor of this argument; a floor past it needs a rho per fractured shape.

THE LOWER BOUND rho. rho = min over the offers of cost / pbar (an offer with pbar = 0 counts for infinity);
it is found best first, so that the dear bounds are computed only where they matter: a heap on cost / pbar
with every reroll at level 0; pop the smallest; if it is a reroll below level 2, raise its level and push
it back (an addition is brought from level 0 to level 1 the same way); stop when the smallest has no higher level. Raising a level only lowers pbar, so the
ratios only grow, and the one that stops the loop is the least ratio of all. Claim (Wald): V*(s) >= rho for
every state s outside E with the flags and the fractured mods of the start, in the FULL model.
Proof. A policy from s that reaches the goal almost surely enters E (the goal implies E) at a first time T.
Let tau be the first use of a terminal action and N = min(T, tau). Until N every action used is one of
`restart`, a bench craft, a veiled choice, a veil, an erasing reroll, an addition or an implicit change, none of which moves the flags and the
fractured mods, so
the state keeps the shape of the start and, given the history, the chance of entering E at step t is at
most pbar(a_t). With probability 1 either E is entered at a step before tau, or a terminal action is used
(and the first one is at step tau). So 1 <= sum over t <= N of E[w(a_t)] with w = pbar for the others and
w = 1 for a terminal action, and the cost of the policy is at least E[sum over t <= N of cost(a_t)] >=
rho * E[sum w(a_t)] >= rho, since cost(a) >= rho * w(a) for every offer a.
UNREACHABLE. When every offer that is not refused has pbar = 0 and none is terminal, rho is infinite, and it is kept so (#1190): no policy from a
state of the start's shape outside E ever enters E, so V* is infinite there. A finite stand-in (it was 1e300) is no bound a search can use: it
reached the envelope search as a cost, the solver's residuals near it overflowed, and the answer printed it as a lower figure in Chaos. The
floors' arithmetic keeps an infinite rho honest (`after_leaving`: an offer that never leaves E costs nothing more, never 0 * inf), the bound's
model has no floor action at an infinite floor (`_pattern_bound._floor_of`), and the search drops an infinite candidate and proves no plan of
its offers reaches the goal.

WHAT THE CLAIM NEEDS, and what is checked. (1) An offer that the game refuses on the bare item of the start's shape never applies at a state
of that shape (a reroll reads nothing of the item that the shape does not hold; a crafted mod can only add refusals). This is an assumption on
the contract of `Reads`, not a check. (2) An erasing reroll keeps the shape, which `keeps_shape` checks at the bare item. (3) The bound of
`reach_bound` is a proof by its own tests. (4) An addition draws at every state of the shape as it does at the bare item (one mod from the
pool less the families held and the tags a metamod blocks, on a side with room): the contract of `Reads.pool_weight`, not a check; its shape
and its single draw are checked at the bare item, and `add_bound` against every member of hand-worked pools by its tests. (5) An addition whose
class declares its draw (`Action.added_draw`) draws at every state of the shape as declared and keeps the shape: the declaration's, compared with
the built outcomes by the contract suite and at every member of a hand-worked shape (`tests/test_fine_group_floors.py`). (6) A veil adds no mod
but a placeholder, and an implicit change no explicit mod and no flag: the contracts of `Adds.veils` and `Adds.implicits`, not a check (an
implicit change's shape is checked at the bare item). Floats: rho is
lowered by 1e-12 of itself.
"""

import heapq
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.abstraction import (
    Abstraction,
    add_bound,
    declared_add_bound,
    CompressedState,
    Status,
    Wanted,
    keeps_shape,
    declared_bounds,
    reach_bound,
)
from crafting_system.actions import NotApplicableError, OutOfScopeError, holds_placeholder, placeholder_mods, unveil_pool_mods
from crafting_system.data import GameData
from crafting_system.items import Item

from ._offers import BuyStartItem, PricedOffer

ZERO, ONE = Fraction(0), Fraction(1)

SMALL_START = 8  # the rerolls of least cost / pbar that the bound's model starts with (`_offer_floor.OfferFloors.initial`)
SLACK = 1e-12  # float slack on rho and on the floors' test

RESTART_KIND, CRAFT, VEILED, REROLL, ADD, TERMINAL, REFUSED = "restart", "craft", "veiled", "reroll", "add", "terminal", "refused"
VEIL, IMPLICIT = "veil", "implicit"  # a Veiled Exalted Orb's kind (it adds a placeholder), and an implicit change's (an Ember, an Ichor; #1074)
NAMING = (CRAFT, VEILED)  # the kinds that make the goal set U (a leaf they can pass leaves it) and that the bound's model starts with
FINISHING = (*NAMING, VEIL)  # the kinds whose pbar is read from the mods they may add (`finishes`)
TOP_LEVEL = {REROLL: 2, ADD: 1, IMPLICIT: 1}  # the highest level of the bound of each kind that has levels (see THE NUMBER pbar); every other kind has none


@dataclass
class _Entry:
    """One offer after the twins: what kind it is, the level of its bound, and its pbar."""

    index: int
    priced: PricedOffer
    kind: str
    level: int = 0
    pbar: Fraction = ONE
    extra: float = 0.0  # a cost that every use of the offer is followed by: the draw after a restart into an unopened listing (`through_listing`)

    @property
    def cost(self) -> float:
        return self.priced.cost + self.extra

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


def goal_set(goal, start: CompressedState, crafts: Sequence[tuple[frozenset[str], bool]]) -> tuple[int, ...]:
    """U: the necessary leaves not PASSING at the start, less those a bench craft or a veiled choice can finish (if any remain).

    `crafts` are, for each offered craft or veiled choice, the mod ids it may add and whether it adds them crafted (`Adds.crafted`). A craft finishes a leaf
    only when a mod it adds can pass it (`finishes`): a leaf that refuses crafted mods, or whose tier limit accepts none of them, stays in U (#1112:
    R05's tier 1 Life left U for the bench Life, so the Wald floor of the bound fell from the essence's chance of tier 1 Life to the essence's price).
    """
    open_leaves = [index for index in necessary_leaves(goal) if start.status[index] is not Status.PASSING]
    kept = [index for index in open_leaves if not any(finishes(goal.leaves[index], named, crafted) for named, crafted in crafts)]
    return tuple(kept or open_leaves)


def finishes(leaf, named: frozenset[str], crafted: bool) -> bool:
    """Whether a mod of `named`, added (as a crafted mod when `crafted`), can make `leaf` PASSING (`status_of`): one of the leaf's mods that its
    tier limit accepts (`tier_ok`), and not a crafted one where the leaf refuses crafted mods. A roll limit is not read: such a mod may pass it."""
    if crafted and leaf.not_crafted:
        return False
    return bool(named & (leaf.mod_ids if leaf.tier_ok is None else leaf.tier_ok))


def merge_twins(
    data: GameData, item: Item, priced: Sequence[PricedOffer]
) -> tuple[list[PricedOffer], list[tuple[str, str]]]:
    """`priced` without the offers that have a cheaper twin (equal non-None `twin_key` on `item`), and the (dropped, kept) labels.

    Exact (see TWINS above). `restart` has no twin. Used by the search and the walk with many offers (`_pattern_bound.MIN_OFFERS`),
    which must not pay for 10,000 fossil sets that fall into a few thousand classes.
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


def through_listing(abstraction: Abstraction, start: CompressedState, shape: CompressedState, chosen: Sequence[int], entries: Sequence[_Entry]) -> None:
    """Count each restart with the draw that follows it when the start is an unopened listing (ADR-0064; see the module text, pbar).

    The restart buys the listing, where only a draw works, so a policy that restarts pays a draw too and lands in E with that draw's chance: the
    least cost of the draws offered and the largest of their chances bound every one of them. A draw outcome of another shape counts as landing (the
    argument is cut there, as at a terminal offer). No draw offered, or a listing that is a goal, leaves the restart as it was.
    """
    if not getattr(start.flags, "unopened", False) or abstraction.is_goal(start):  # the light tests' states carry plain flags
        return
    draws = [entry for entry in entries if getattr(entry.priced.offer.action, "opens_listing", False)]
    if not draws:
        return
    held = (shape.flags, shape.fractured)

    def outside(state: CompressedState) -> bool:  # outside E, with the shape: where the claim's rho holds again
        return (
            not abstraction.is_goal(state)
            and (state.flags, state.fractured) == held
            and not all(state.status[index] is Status.PASSING for index in chosen)
        )

    landing = ZERO
    for draw in draws:
        try:
            outcomes = abstraction.kernel(start, draw.priced.offer.action)
        except NotApplicableError:
            continue  # refused at the listing: never used after a restart
        except OutOfScopeError:  # no rule for it proves no chance: counted as landing, the argument cut there as at a terminal offer
            landing = ONE
            continue
        landing = max(landing, ONE - sum((chance for state, chance in outcomes.items() if outside(state)), ZERO))
    cheapest = min(draw.priced.cost for draw in draws)
    for entry in entries:
        if isinstance(entry.priced.offer.action, BuyStartItem):
            entry.pbar, entry.extra = landing, cheapest


def declared_pbars(abstraction: Abstraction, bare: CompressedState, item: Item, chosen: Sequence[int], entries: Sequence[_Entry], ask: Callable[[], None]) -> None:
    """Lower the pbar of every reroll at level 0 to the bound its class declares, for all the offers of a class at once (see THE NUMBER pbar, #1073).

    Only a reroll whose action declares no fracture, no kept crafted mod and no need of one (what level 1 asks of `adds` and `reads`); the class
    answers for the rest (`declared_bounds`: None for an action that may leave the shape or that it gives no bound). `ask` is the net, asked once
    per class. The offers are grouped by their action's class, which the planner does not name: a class answers for its own actions.
    """
    data = abstraction.data
    groups: dict[type, list[_Entry]] = {}
    for entry in entries:
        if entry.kind != REROLL or entry.level != 0:
            continue
        action = entry.priced.offer.action
        adds = action.adds(data, item)
        if adds.fractures or adds.keeps_crafted or action.reads(data).needs_crafted:
            continue
        groups.setdefault(type(action), []).append(entry)
    for members in groups.values():
        ask()
        for entry, bound in zip(members, declared_bounds(abstraction, bare, [entry.priced.offer.action for entry in members], chosen)):
            if bound is not None and bound < entry.pbar:
                entry.pbar = bound


def raisable(kind: str, level: int) -> bool:
    """Whether an offer of `kind` whose bound is at `level` has a higher level to be brought to."""
    return level < TOP_LEVEL.get(kind, 0)


def _raised(abstraction, bare, item, chosen, action, kind: str, level: int, pbar: Fraction, target: int) -> tuple[str, Fraction, int]:
    """The `(kind, pbar, level)` of a reroll or an addition brought to `target` (see `raise_level`); a function of its arguments alone."""
    data = abstraction.data
    if kind == ADD:
        return _raised_add(abstraction, bare, chosen, action, level, pbar, item)
    if kind == IMPLICIT:
        return _raised_implicit(abstraction, bare, action, level)
    if level == 0:
        try:
            same_shape = keeps_shape(abstraction, bare, action)
        except NotApplicableError:
            return REFUSED, ONE, level
        except OutOfScopeError:  # no rule for the bare item proves nothing for the states: the offer stays in the search, and the walk writes its gap (ticket #506)
            return TERMINAL, ONE, level
        adds = action.adds(data, item)
        if not same_shape or adds.fractures or adds.keeps_crafted or action.reads(data).needs_crafted:
            return TERMINAL, ONE, level
        level = 1
        found = reach_bound(abstraction, bare, action, chosen) if chosen else ZERO
        if found is None:
            return TERMINAL, ONE, level
        pbar = min(pbar, found)  # pbar at level 0 is 1 or the declared bound (`declared_pbars`): both bound the same chance
    if target >= 2 and level < 2 and kind == REROLL:
        level = 2
        exact = reach_bound(abstraction, bare, action, chosen, exact=True) if chosen else ZERO
        if exact is not None and exact < pbar:
            pbar = exact
    return kind, pbar, level


def _raised_implicit(abstraction, bare, action, level: int) -> tuple[str, Fraction, int]:
    """The `(kind, pbar, level)` of an implicit change brought to level 1 (see THE NUMBER pbar): pbar 0 when it keeps the shape at the bare item,
    TERMINAL when it does not or when the bare item refuses it (which, unlike a reroll's refusal, is not read as a proof for the states)."""
    if level >= 1:
        return IMPLICIT, ZERO, level
    try:
        same_shape = keeps_shape(abstraction, bare, action)
    except (NotApplicableError, OutOfScopeError):
        return TERMINAL, ONE, 1
    return (IMPLICIT, ZERO, 1) if same_shape else (TERMINAL, ONE, 1)


def _raised_add(abstraction, bare, chosen, action, level: int, pbar: Fraction, item: Item | None = None) -> tuple[str, Fraction, int]:
    """The `(kind, pbar, level)` of an addition brought to level 1: its chance of landing in E from any state of the shape (see THE NUMBER pbar).

    Unlike a reroll's, a refusal at the bare item proves nothing (the addition reads the mods the item holds: an Exalted Orb on a full side,
    a Harvest add/remove with nothing to remove), so the offer stays in the argument as a terminal one, and so does one whose result at the bare
    item leaves the shape or is not one drawn mod (`add_bound` None).
    """
    if level >= 1:
        return ADD, pbar, level
    if item is not None and action.added_draw(abstraction.data, item) is not None:  # the class declares the draw of the shape (#1074)
        try:
            found = declared_add_bound(abstraction, action, item, chosen) if chosen else ZERO
        except OutOfScopeError:
            return TERMINAL, ONE, 1
        return (TERMINAL, ONE, 1) if found is None else (ADD, found, 1)
    try:
        same_shape = keeps_shape(abstraction, bare, action)
        found = add_bound(abstraction, bare, action, chosen) if same_shape and chosen else (ZERO if same_shape else None)
    except (NotApplicableError, OutOfScopeError):
        return TERMINAL, ONE, 1
    if found is None:
        return TERMINAL, ONE, 1
    return ADD, found, 1


def best_first_rho(entries: Sequence[_Entry], raise_level: Callable[[_Entry, int], None]) -> float:
    """The least cost / pbar over the entries, found best first so that the dear bounds are computed only where needed.

    A heap on cost / pbar holds every entry at its current level. Pop the smallest; a reroll below
    level 2 is brought one level up (`raise_level`, which only lowers its pbar, so its ratio only grows)
    and pushed back; the loop stops at the first pop that is not a reroll or is at level 2. Every other
    entry has a current ratio at least as large and a true ratio at least as large as its current one,
    so the popped ratio is the least of all. Returns it, lowered by `SLACK` of itself: infinity when no offer can enter E.
    """
    heap = [(entry.ratio, entry.index) for entry in entries]
    heapq.heapify(heap)
    while heap:
        ratio, index = heapq.heappop(heap)
        entry = entries[index]
        if entry.kind == REFUSED:
            continue
        if not raisable(entry.kind, entry.level):
            return ratio * (1 - SLACK)  # infinite when no offer can enter E (UNREACHABLE)
        raise_level(entry, entry.level + 1)
        heapq.heappush(heap, (entry.ratio, index))
    return 0.0


def _kind_of(data, item: Item, offer: PricedOffer) -> tuple[str, frozenset[str]]:
    """The kind of an offer from what its action declares, and (for a craft or a veiled choice) the mods it may add.

    An action that does not read the junk starts as a reroll; whether it is refused, terminal or bounded
    is found when its bound is first needed (`raise_level`), because that needs the bare item.
    """
    action = offer.offer.action
    if isinstance(action, BuyStartItem) or getattr(action, "opens_listing", False):  # both are always in the solve: the draw is the one action of the unopened start (ADR-0064)
        return RESTART_KIND, frozenset()
    move = action.imprint_move()
    if move is not None and move.restore and not item.imprints:  # a restore with no imprint before the first terminal use (see THE NUMBER pbar)
        return REFUSED, frozenset()
    reads = action.reads(data)
    if action.added_draw(data, item) is not None:  # one drawn mod its class declares for the shape (a Beastcraft side swap, an Eldritch Exalted Orb)
        return ADD, frozenset()
    if reads.needs_veiled and not holds_placeholder(data, item):  # a veiled choice (see THE NUMBER pbar, #1074)
        adds = action.adds(data, item)
        if not (adds.draws or adds.fractures or adds.implicits or adds.quality or adds.corrupts or adds.imprints or adds.veils or adds.enchantment):
            return VEILED, frozenset(adds.named) if adds.named is not None else unveil_pool_mods(data, item.base_id)
    if not (reads.offer or reads.imprints or reads.needs_veiled):
        adds = action.adds(data, item)
        if (
            adds.implicits
            and adds.named == frozenset()
            and not (adds.draws or adds.fractures or adds.quality or adds.offer or adds.corrupts or adds.imprints or adds.veils)
        ):
            return IMPLICIT, frozenset()  # it changes the implicits and puts no explicit mod on (see THE NUMBER pbar)
    if reads.item_state:
        return TERMINAL, frozenset()  # its result depends on the implicits, the quality or the offer, which the bound read at one state does not hold fixed
    adds = action.adds(data, item)
    if not reads.junk:
        return (TERMINAL if adds.imprints else REROLL), frozenset()  # an imprint made before the first terminal use would void the restores' set-aside
    if adds.veils and adds.named is None and not reads.needs_veiled and not (
        adds.draws or adds.fractures or adds.implicits or adds.quality or adds.offer or adds.corrupts or adds.imprints or adds.enchantment
    ):
        return VEIL, placeholder_mods()  # it adds no mod but a placeholder (a Veiled Exalted Orb; see THE NUMBER pbar)
    if not adds.fractures and not adds.draws and adds.named is not None and not adds.imprints:
        return CRAFT, frozenset(adds.named)
    if (
        reads.pool_weight
        and (reads.variants or reads.draw_tags)
        and not (reads.fractures or reads.draw_levels or reads.rerolls_values or reads.input_mods or reads.input_classes or reads.influenced)
        and adds.draws
        and not adds.named
        and not (adds.fractures or adds.corrupts or adds.veils or adds.imprints)
    ):
        return ADD, frozenset()  # one drawn mod added to the mods kept (see THE NUMBER pbar); what it does at the bare item is checked when it is raised
    return TERMINAL, frozenset()
