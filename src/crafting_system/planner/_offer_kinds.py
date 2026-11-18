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
    leaves the shape: a MOVE_ADD into a shape the floors know, THE SHAPES, #973) and a Harvest add/remove (it also removes a mod: not one
    drawn mod added to the mods kept) are of this kind but get no bound of their own, so the second stays TERMINAL (#1084). Its
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

THE SHAPES (#973). The claim above is for the start's shape, and an offer that leaves it is cut there at its price. Once the Orb of Scouring is
offered that cut set rho to its price (0.35 Chaos on R05, R10 and R12, whose fractured Rare start it leaves Magic; R05's floor fell from the
essence's 118.36), and a Regal Orb back from the Magic item would have cut it again. So the floors are stated for every shape the priced offers
turn the start item into (`_offers.reached_by`: one item per rarity, its flags and fractured mods; the start's is shape 0), each with its own
bare item, its offers' kinds read at its item (`_kind_of`), its pbars read at its bare item, and its floor rho_S:
  * DEAD LEAVES. D_S is U less (a) every leaf a use that lands in S may leave PASSING: from another shape, an erasing reroll (kind REROLL, no
    fracture, no kept crafted mod, no need of one) whose rarities there (`Action.rarities`) hold S's, those its `reach_bound` for the leaf alone
    at that shape's bare item does not prove 0 (its outcome does not depend on the state); any other offer whose rarities may hold S's empties
    D_S (it keeps mods of the state it was used at); the restart lands in the start's shape only; and (b) every leaf an offer of S may make
    PASSING: an erasing reroll whose rarities hold S's (`reach_bound` for the leaf alone), an addition (`add_bound`, or the declared draw's, for
    the leaf alone: over every state of S), a craft, a veiled choice or a veil (`finishes`). D_0 is empty. The claim C_S of a shape is: V*(s) >=
    rho_S at every state s of S outside E that holds no leaf of D_S PASSING. From such a state, every state reached before the first terminal
    offer or move holds none either (an erasing reroll's outcome holds only leaves of (b), an addition, a craft or a veiled choice adds one mod to
    the mods kept, a removal adds none, an implicit change touches no leaf of U), so the pbars below hold along the whole argument.
  * The pbars of S. An erasing reroll, an implicit change, a restart's: as above, at S's bare item. An addition, and a craft, a veiled choice or a
    veil, add one mod (a placeholder for a veil) to the mods kept: from a state of C_S outside E they land in E only if that mod passes every dead
    leaf (all open there, all needed by E). So a craft's pbar is 1 when one mod it may add passes every leaf of D_S (some leaf of U when D_S is
    empty), else 0, and an addition's is the least of its bound over U and its bound for each dead leaf alone (`_least`).
  * MOVES. An erasing reroll whose outcomes at S's bare item leave S, every one for a shape the floors know (`ShapeView.dests`), is a MOVE: its
    outcomes are those at the bare item from every state of S, so it lands in E with chance at most its pbar (the levels of a reroll's) and
    else in a shape d it names, at a state of C_d (the leaves it may leave PASSING are out of D_d by (a)). An addition whose outcome at the bare
    item leaves S for known shapes (a Regal Orb on the Magic item) is a MOVE_ADD, with an addition's pbar; it lands in a shape whose D (a) leaves
    empty. A restart from a shape other than the start's is a move into the start's shape, with the restart's pbar and draw (`through_listing`).
    A reroll whose outcomes fracture or fall in a shape the floors do not know stays TERMINAL.
  * THE SYSTEM. Let x_S be the infimum of V* over the states of C_S outside E, and F_S(y) = min(W_S, min over the moves m of S of c_m +
    (1 - pbar_m) min_{d of m} y_d), W_S the least cost / pbar over the other offers of S (a terminal offer at its cost). Then x >= F(x): from a
    state of C_S outside E, let N be the first time E is entered, a terminal offer is used or a move is used. Until N the state stays in C_S and
    the Wald argument above runs with w(m) = 1 for a move, and a move's use costs, beyond its price, V* of where it lands: given the history, it
    lands outside E with chance at least 1 - pbar_m, in a shape d whose V* there is at least x_d. Every offer a then has c'(a) >= F_S(x) w(a)
    (c' its price, plus (1 - pbar_m) min x_d for a move), so V*(s) >= F_S(x). F is monotone on [0, inf]^n, so by Knaster-Tarski x is at least the
    least fixed point of F, and `shape_rhos` gives the least fixed point of a G <= F (each move's term taken as min(c + (1 - pbar) y, c / pbar)),
    found best first; so rho_S <= x_S, and rho = rho_0 is the floor of the start's shape as before. On R05: rho 118.36 again (the Scouring
    move costs 0.35 + rho_Magic, and from the Magic item E needs the essence-only Strength mod, which no offer there gives: D_Magic holds it, so
    the Alterations and the Regal Orb have pbar 0, and every way out of Magic goes back to the start's shape).
  * A move's floor in the start's shape (`_offer_floor.OfferFloors.lower`) is its price plus (1 - pbar) the least floor of the shapes it lands
    in (`beyond`), not plus rho: the shape it lands in may be cheaper to finish from than the start's.

WHAT THE CLAIM NEEDS, and what is checked. (1) An offer that the game refuses on the bare item of the start's shape never applies at a state
of that shape (a reroll reads nothing of the item that the shape does not hold; a crafted mod can only add refusals). This is an assumption on
the contract of `Reads`, not a check. (2) An erasing reroll keeps the shape, which `keeps_shape` checks at the bare item. (3) The bound of
`reach_bound` is a proof by its own tests. (4) An addition draws at every state of the shape as it does at the bare item (one mod from the
pool less the families held and the tags a metamod blocks, on a side with room): the contract of `Reads.pool_weight`, not a check; its shape
and its single draw are checked at the bare item, and `add_bound` against every member of hand-worked pools by its tests. (5) An addition whose
class declares its draw (`Action.added_draw`) draws at every state of the shape as declared and keeps the shape: the declaration's, compared with
the built outcomes by the contract suite and at every member of a hand-worked shape (`tests/test_fine_group_floors.py`). (6) A veil adds no mod
but a placeholder, and an implicit change no explicit mod and no flag: the contracts of `Adds.veils` and `Adds.implicits`, not a check (an
implicit change's shape is checked at the bare item). (7) THE SHAPES take on the contracts, not a check: a craft, a veiled choice, a veil
and an implicit change keep the rarity (a bench craft is refused on a Normal item); `Action.rarities`, asked of the shape's item and then of its
bare item, gives the rarities of every state of the shape where the offer applies; an addition that keeps every mod (`Reads.variants`) and that
the bare item refuses is refused at every state of the shape (the bare item has the most room and holds the fewest families; what refuses it
there is the rarity or the class, a Regal Orb on a Rare item, an Exalted Orb on a Magic one) (one that both refuse leaves none, as `_offers.reached_items`
reads it); an erasing reroll's `Fixed` result (an Orb of Scouring) keeps of the state only what a reroll's kept mods are (`reach_bound` reads
it at the bare item as it reads a reroll's kept mods); an addition that leaves the shape draws as one that keeps it does (the contract of
`Reads.pool_weight`, read by `add_bound` at the bare item). Floats: rho is lowered by 1e-12 of itself.
"""

import heapq
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
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
MOVE, MOVE_ADD = "move", "move-add"  # a reroll and an addition that leave the shape for shapes the floors know (THE SHAPES, #973)
NAMING = (CRAFT, VEILED)  # the kinds that make the goal set U (a leaf they can pass leaves it) and that the bound's model starts with
FINISHING = (*NAMING, VEIL)  # the kinds whose pbar is read from the mods they may add (`finishes`)
TOP_LEVEL = {REROLL: 2, ADD: 1, IMPLICIT: 1, MOVE: 2, MOVE_ADD: 1}  # the highest level of the bound of each kind that has levels (see THE NUMBER pbar); every other kind has none


@dataclass
class _Entry:
    """One offer after the twins: what kind it is, the level of its bound, and its pbar."""

    index: int
    priced: PricedOffer
    kind: str
    level: int = 0
    pbar: Fraction = ONE
    extra: float = 0.0  # a cost that every use of the offer is followed by: the draw after a restart into an unopened listing (`through_listing`)
    dests: frozenset[int] = frozenset()  # the shapes a move lands in (THE SHAPES): empty for an offer whose use keeps the shape or is cut there

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


@dataclass
class ShapeView:
    """One shape the floors are stated for (THE SHAPES): its bare item (`bare`: the shape's flags and fractured mods, nothing else), an item of it
    (`item`), the leaves of U (`chosen`), the leaves of U no state of its claim holds PASSING (`dead`), and the index of every shape the floors
    know, by its flags and fractured mods (`known`)."""

    abstraction: Abstraction
    bare: CompressedState
    item: Item
    chosen: tuple[int, ...]
    dead: tuple[int, ...] = ()
    known: Mapping[tuple, int] = field(default_factory=dict)

    def dests(self, action) -> frozenset[int] | None:
        """The shapes the outcomes of `action` at the bare item fall in, or None when one is of a shape the floors do not know or it fractures.
        Raises what the action raises there."""
        ab = self.abstraction
        prepared = ab._prepared(self.bare, action)
        if prepared.outcomes.fractures:
            return None
        found: set[int] = set()
        for split in ab._splits_of(prepared):
            index = self.known.get((split.flags, split.fractured))
            if index is None:
                return None
            found.add(index)
        return frozenset(found)


def _raised(view: ShapeView, action, kind: str, level: int, pbar: Fraction, target: int, dests: frozenset[int] = frozenset()) -> tuple[str, Fraction, int, frozenset[int]]:
    """The `(kind, pbar, level, dests)` of a reroll, an addition, an implicit change or a move of the shape `view` brought to `target` (see
    `raise_level`); a function of its arguments alone. A reroll whose outcomes at the bare item leave the shape for shapes the floors know is a
    MOVE (THE SHAPES), its pbar the same bounds of the chance of landing in E, read at the bare item as a reroll's."""
    abstraction, bare, item, chosen = view.abstraction, view.bare, view.item, view.chosen
    data = abstraction.data
    if kind in (ADD, MOVE_ADD):
        return _raised_add(view, action, kind, level, pbar, dests)
    if kind == IMPLICIT:
        return (*_raised_implicit(abstraction, bare, action, level), frozenset())
    if level == 0:
        try:
            same_shape = keeps_shape(abstraction, bare, action)
        except NotApplicableError:
            return REFUSED, ONE, level, frozenset()
        except OutOfScopeError:  # no rule for the bare item proves nothing for the states: the offer stays in the search, and the walk writes its gap (ticket #506)
            return TERMINAL, ONE, level, frozenset()
        adds = action.adds(data, item)
        if adds.fractures or adds.keeps_crafted or action.reads(data).needs_crafted:
            return TERMINAL, ONE, level, frozenset()
        if not same_shape:
            dests = view.dests(action) or frozenset()  # cached: `keeps_shape` prepared the same outcomes
            if not dests:
                return TERMINAL, ONE, level, frozenset()
            kind = MOVE
        level = 1
        found = reach_bound(abstraction, bare, action, chosen) if chosen else ZERO
        if found is None:
            return TERMINAL, ONE, level, frozenset()
        pbar = min(pbar, found)  # pbar at level 0 is 1 or the declared bound (`declared_pbars`): both bound the same chance
    if target >= 2 and level < 2 and kind in (REROLL, MOVE):
        level = 2
        exact = reach_bound(abstraction, bare, action, chosen, exact=True) if chosen else ZERO
        if exact is not None and exact < pbar:
            pbar = exact
    return kind, pbar, level, dests


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


def _raised_add(view: ShapeView, action, kind: str, level: int, pbar: Fraction, dests: frozenset[int] = frozenset()) -> tuple[str, Fraction, int, frozenset[int]]:
    """The `(kind, pbar, level, dests)` of an addition brought to level 1: its chance of landing in E from any state of the shape's claim (see THE
    NUMBER pbar, and THE SHAPES for the dead leaves and the additions that leave the shape: a Regal Orb on a Magic item, a MOVE_ADD).

    Unlike a reroll's, a refusal at the bare item proves nothing (the addition reads the mods the item holds: an Exalted Orb on a full side,
    a Harvest add/remove with nothing to remove), so the offer stays in the argument as a terminal one, and so does one whose result at the bare
    item leaves for a shape the floors do not know or is not one drawn mod (`add_bound` None).
    """
    if level >= 1:
        return kind, pbar, level, dests
    abstraction, bare, item = view.abstraction, view.bare, view.item
    if item is not None and action.added_draw(abstraction.data, item) is not None:  # the class declares the draw of the shape (#1074)
        try:
            found = _least(view, lambda leaves: declared_add_bound(abstraction, action, item, leaves))
        except OutOfScopeError:
            return TERMINAL, ONE, 1, frozenset()
        return (TERMINAL, ONE, 1, frozenset()) if found is None else (ADD, found, 1, frozenset())
    try:
        same_shape = keeps_shape(abstraction, bare, action)
        dests = frozenset() if same_shape else (view.dests(action) or frozenset())
        if not same_shape and not dests:
            return TERMINAL, ONE, 1, frozenset()
        found = _least(view, lambda leaves: add_bound(abstraction, bare, action, leaves))
    except NotApplicableError:
        # An addition that keeps every mod (`Reads.variants`: an Exalted, a Regal, an Augmentation) refused at the bare item, which has the most
        # room and holds the fewest families of the shape, is refused at every state of the shape (a Regal Orb on the Rare start, offered for the
        # Magic item a Scouring leaves, #973; assumption (7)). Any other (a Harvest add/remove, which needs a mod to remove) proves nothing there
        # for the states that hold more mods.
        return (REFUSED if abstraction.data is not None and action.reads(abstraction.data).variants else TERMINAL), ONE, 1, frozenset()
    except OutOfScopeError:
        return TERMINAL, ONE, 1, frozenset()
    if found is None:
        return TERMINAL, ONE, 1, frozenset()
    return (ADD if same_shape else MOVE_ADD), found, 1, dests


def _least(view: ShapeView, bound: Callable[[tuple[int, ...]], Fraction | None]) -> Fraction | None:
    """The least of the bounds of one added mod (`add_bound`, `declared_add_bound`) over U and over each dead leaf of the shape alone; None when
    the bound over U is None. Over U it bounds the chance that the added mod passes a leaf of U that is not PASSING; over a dead leaf, the chance
    that it passes that leaf, which every state of the claim holds open and E needs (THE SHAPES)."""
    if not view.chosen:
        return ZERO
    found = bound(view.chosen)
    if found is None:
        return None
    for leaf in view.dead:
        alone = bound((leaf,))
        if alone is not None and alone < found:
            found = alone
    return found


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


def beyond(entry: _Entry, rest: float, rho_of: Callable[[int], float]) -> float:
    """`(1 - pbar) R`: the least an offer costs after its use beyond its price, where R is `rest` (the floor of the shape it keeps) for an offer of
    the shape and the least floor of the shapes it lands in for a move. 0 for an offer that lands in E for sure, also when R is infinite (nothing
    else enters E: UNREACHABLE), where float arithmetic would make it 0 * inf, not a number."""
    if entry.pbar == ONE:
        return 0.0
    after = min(rho_of(shape) for shape in entry.dests) if entry.dests else rest
    return float(1 - entry.pbar) * after


def shape_rhos(entries: Sequence[Sequence[_Entry]], raise_level: Callable[[int, _Entry, int], None], until: int | None = 0) -> tuple[list[float | None], float]:
    """The floor rho_S of every shape S (`entries[S]` its offers), found best first as `best_first_rho` is, over the system of THE SHAPES.

    A heap holds, for every offer of every shape, its own key (cost / pbar: for an offer of the shape its Wald ratio, for a move the cost of using
    it until it lands in E, c / p), and, for a move once a shape it lands in is settled, the key through it (c + (1 - p) rho of that shape). Pop the
    least; an offer below its top level is brought one level up (`raise_level(shape, entry, level)`, which only lowers its pbar, so both its keys
    only grow) and its keys pushed again; a key that grew since it was pushed is pushed again at its new value; else the popped key settles its
    shape, and every move into that shape pushes its key through it. Every key is at most the value it reaches at the top level, and a key through a
    shape settled later is at least the least of that shape's floor and the move's own key (c + (1 - p) R >= R when R <= c / p, and >= c / p when
    R > c / p), so the keys settle in order and each shape's settled key is the least fixed point of the system with each move's c + (1 - p) R taken
    as min(c + (1 - p) R, c / p): a lower bound of the least fixed point of THE SHAPES's system, so of every true floor (Knaster-Tarski: the true
    floors x satisfy x >= F(x), and F is monotone). Settling stops once the shape `until` is settled (None: when the heap is empty).

    Returns the settled floors, lowered by `SLACK` of themselves (None for a shape not settled when it stopped; infinity for one never settled when
    the heap ran out: no way into E from it, UNREACHABLE), and the last key settled, which no shape left unsettled has a floor below.
    """
    count = len(entries)
    settled: list[float | None] = [None] * count
    into: list[list[tuple[int, int]]] = [[] for _ in range(count)]  # the moves (shape, position) that land in each shape
    heap: list[tuple[float, int, int, bool]] = []  # (key, shape, position, through a settled shape)

    def through(entry: _Entry) -> float | None:
        known = [settled[shape] for shape in entry.dests if settled[shape] is not None]
        if not known:
            return None
        return entry.cost + (0.0 if entry.pbar == ONE else float(1 - entry.pbar) * min(known))

    def push(shape: int, position: int) -> None:
        entry = entries[shape][position]
        heapq.heappush(heap, (entry.ratio, shape, position, False))
        if entry.dests and (key := through(entry)) is not None:
            heapq.heappush(heap, (key, shape, position, True))

    for shape, offers in enumerate(entries):
        for position, entry in enumerate(offers):
            if entry.dests:
                for target in entry.dests:
                    into[target].append((shape, position))
            push(shape, position)
    last = 0.0
    while heap:
        key, shape, position, via = heapq.heappop(heap)
        if settled[shape] is not None:
            continue
        entry = entries[shape][position]
        if entry.kind == REFUSED:
            continue
        if raisable(entry.kind, entry.level):
            had = entry.dests
            raise_level(shape, entry, entry.level + 1)
            for target in entry.dests - had:
                into[target].append((shape, position))
            push(shape, position)
            continue
        now = through(entry) if via else entry.ratio
        if now is None or now > key:  # stale: the offer was raised since this key was pushed
            if now is not None:
                heapq.heappush(heap, (now, shape, position, via))
            continue
        settled[shape] = last = key * (1 - SLACK)
        if shape == until:
            return settled, last
        for source, at in into[shape]:
            if settled[source] is None and (found := through(entries[source][at])) is not None:
                heapq.heappush(heap, (found, source, at, True))
    return [math.inf if value is None else value for value in settled], math.inf


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
