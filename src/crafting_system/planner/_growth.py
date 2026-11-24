"""Plan-led growth: the methods a round holds, grown from the plan in hand (#1414, #1276; OR-12, OR-13, OR-37, OR-39, OR-55).

The rule of the research note `docs/research/2026-11-22-rounds-design-2.md` (section 4), coded: no route, no guide's set and no method kind is
named here. Every choice is read from what the offers declare (`_offer_kinds._kind_of`, `Action.adds`, `Action.reads`, `Action.rarities`,
`Action.imprint_move`) and from the statuses of the states the plan in hand visits.

* **The table** (`OfferTable`). For each offer, at each shape the offers turn the start item into (one item per rarity, `_offers.reached_by`):
  its kind there, the rarities its outcomes have there, and its chance of making each wanted mod not on the start item PASSING in one use,
  the floors' own number (THE NUMBER pbar of `_offer_kinds`, for that one leaf): 1 for a craft, a veiled choice or a veil that names a mod
  passing the leaf (`finishes`), the declared bound or `reach_bound` for an erasing reroll, `add_bound` (or the declared draw's) for an
  addition, none for any other kind. And what it declares at the start item: that it fractures, makes or restores an imprint, needs a veiled
  placeholder or makes one, needs a crafted mod, adds crafted mods, adds no mod at all (a craft that only removes), and which metamods it adds
  (a lock of a side, a tag kept out of the draws, more crafted mods).
* **Round 0, the seed** (`seed`): per wanted mod not passing at the start, the `PER_ROLE` offers of least cost over chance (any kind, any shape).
* **The diagnosis of a plan in hand** (`Grower.next`). Its steps are its actions by their cost share (expected uses times price, read on the
  plan's lumped chain, `step_shares`); the dearest step `D` not diagnosed yet is read at the states where it acts: `W`, the wanted mods not
  passing there that some outcome of `D` makes pass (what `D` waits for), and `K`, the wanted mods passing there that some outcome of `D` loses
  (what `D` can destroy). The roles named for them:
  - **adders** for each mod of `W`: the `PER_ROLE` offers of least cost over chance on it that keep the mods they are given (an addition, a
    craft, a veiled choice or a veil: not a reroll), at any shape, among the offers the round that made the plan did not hold;
  - **moves**: for an adder whose best shape is not one `D` acts at, the cheapest offer of each step of the rarities between them;
  - **protectors** for each mod of `K`, among the offers that draw no mod (they keep the mods they are given; a reroll that also fractures
    keeps none of them): every one that fractures (when the states hold no fractured mod), the cheapest that adds the lock of the mod's side
    (unless every mod of `W` sits on that side: a step that waits for a mod of the other side still gains it under the lock), and the
    cheapest imprint that can be made at `D`'s shape (its outcomes are read there);
  - **cleaners and narrowers** for the adders: the cheapest craft that adds no mod and needs no crafted one (it removes a mod), the crafts that
    add no mod and need a crafted one when the round holds a crafted mod, and, among the offers that draw no mod, the cheapest that keeps each
    tag out of the draws that no wanted mod the adders must draw carries, and the cheapest of more crafted mods when the round holds two
    crafted mods (#1423). The mods the adders must draw are those of `W`, and the other wanted mods not passing at some state where `D` acts,
    less every one an offer of the round gives by a finishing kind (a bench craft, a veiled choice, a veil: it is not drawn, so a tag it
    carries may be kept out of the draws before it is made); a mod passing at every state where `D` acts is not drawn either (a tag kept out
    removes no mod the item holds). A narrower is a crafted mod held: it counts towards the crafted mods of the two rules after it.
  - **the narrowers of each state** (`Grower.state_narrowers`): at every state where a drawing addition of the plan in hand acts (an
    Exalted Orb and the like), the narrowers of the wanted mods it waits for at that state, by the rule above, with the crafted roles they
    bring. Unlike the step's own reading, which keeps the tags of every wanted mod not passing at some state where it acts, a state keeps
    only the tags of what it waits for there (less what a finishing offer of the round gives). A step read whole waits for the union of its
    states' mods: R04's Exalted Orb waits for the extra Arrow (tagged `attack`) at the states that lack it and for Life and Bow Damage alone
    at the others, where the guide keeps the attack tag out (#1423). A drawing reroll is not read so (only additions are).
  With no plan in hand the same roles are read at the start: `W` the wanted mods whose providers in the round all reroll, `K` every other
  wanted mod when one mod's only provider rerolls.
* **The lock group** (`Grower.lock_group`, #1420, hypothesis H16 of #1434). A step whose `W` holds a prefix and a suffix (`side_of`, read among the mods the item can hold) and
  that can lose nothing (`K` empty: a spam from a bare rare only waits) is read for its locks, as the last resort of the growth: the lock
  of one side lets a reroll make the other while the side already made stays, and with nothing at risk no protector names a lock. The
  lock groups come only when the usual roles name nothing for any step (`Grower.last_lock`): where the growth would go to its later
  group, or a round that did not finish within its share ends the usual growth (`Grower.stop`). So the usual rounds come in main's
  order, each with its share; a lock group has the growth's share like any round (half the time left), and the rounds after the growth
  the other half. Read earlier, before a step's usual roles or right after they were beaten, a lock group took the time a usual round
  needed: on R13 at 600 s 4,346.05 c against main's 2,066.12 c, its Orb of Annulment round two rounds later. On R14 the earlier order
  gave 3,429.31 c at 600 s, a lock group on the Augmentation step that named the Orb of Alteration; here that step's usual roles come
  first (5,897.11 c, then 5,725.49 c in the next round), and no step of those plans that can lose nothing waits on both sides, so no
  lock group is named and R14 stays at main's 5,725.49 c. A step that can lose a mod has its protectors in its usual roles, so it has no lock group. Its round holds the offers the
  next round holds already, the cheapest cleaner, and the lock role (`OfferTable.lock_roles`), alone:
  - for each side, every offer that may add its lock and keeps the mods it is given (`lockers`: no reroll at any shape): the bench lock, and
    what puts it back once a reroll of the other side has taken it off with that side (a beast that draws a metamod keeps the mods);
  - for each waited mod `x` and each side, the `PER_ROLE` rerolls of least cost over chance at the item under that lock (`under_lock`): the
    shape's item with its fractured mods, a mod of each other waited mod of that side and the lock's crafted mod, read on the model of the
    metamods. The chance is that one use leaves `x` and every held waited mod passing (`reach_bound` over them): it counts what the reroll
    keeps, so one that takes the locked side off scores nothing there, and a reroll the lock refuses (an essence) is not ranked. Its cost
    is its price and the cheapest locker's: a reroll under the lock rerolls the other side, and the lock, a crafted mod of that side, goes
    with it, so each use pays a lock again. Read at the bare item the cheap rerolls of the whole item lead instead: on R20 Harvest Reforge
    Fire is 13th there on Burning Damage, first under the suffix lock (#1429); and without the lock's price the Chaos Orb (1 c) leads Harvest
    Reforge Influence (150.65 c) on Concentrated Effect under it, and the set it names plans at 429,990.79 c against the guide's
    206,331.71 c: with it (Matron, 238 c) Influence comes first, (150.65 + 238) / 4.97% against the Chaos Orb's (1 + 238) / 2.02%.
  - for each waited mod, the `PER_ROLE` adders of least cost over chance on it (`step_adders`: they keep the mods they are given), ranked
    only at the shapes where the step acts, among the offers the group and the round that made the plan do not hold yet; nothing else of
    the usual roles comes with them. The usual roles rank their adders at any shape, so the one that adds to the item the step already
    made, under the lock that keeps it, loses there to those that act on a magic item: on R20 Augmentation and Regal, where the Exalted
    Orb acts on the rare. Named in the lock group, it is searched with the locks it works with: on R20 within the hour 115,986.10 c
    against 206,331.71 c without it (H37 of #1434). Ranked so in the usual round instead (H36), it came without its locks, that round
    did not build in its share, and the lock group came sixth: 4,663,549 c.
  A side under whose lock no reroll is ranked names nothing (a lock pays only with a reroll under it). The lock role is never read in
  one round with the usual roles (on R20 that made a round of 15 offers that did not build in its share); a lock group that does not
  finish within its share ends nothing, the next lock group or the later group comes (`Grower.stop`). The plan's steps are read the
  dearest first, and each step, with its `W` and shapes, has one lock group in the run, also when a later plan improves. A lock group
  that improves the plan, before the usual growth ended, lets the usual roles read the new plan. On R20 the usual roles of the essence
  step are beaten (about 120 s), nothing more is named, and its lock group comes: 206,331.71 c within the hour.
* **Dependencies** (`OfferTable.closure`): an offer that needs a veiled placeholder brings every offer that makes one and every other offer that
  needs one (a pick brings the Unveil, the veiled sources and the other picks); an offer that makes a placeholder brings those that need one;
  a restore brings the imprints and an imprint the restores; and an offer that adds the lock of a side and draws nothing (the bench lock)
  brings every offer that may add that lock and keeps the mods (`lockers`, #1513, hypothesis H35 of #1434). The protector rule names the
  lock among the offers that draw no mod, so the Wild Bristle Matron, which draws which metamod it adds, was never named beside the bench
  lock; yet where the item's state leaves it one metamod to add it puts on the same lock, and it may be the cheaper one: on R24's boots,
  whose suffixes are full, the suffix lock is the one metamod with room (238 c against the bench's 353 c), and a plan that relocks at each
  reroll of the prefixes pays it at each use. With the bench lock alone in the group, the plan paid the bench (2,541.56 c within the hour
  against 2,184.44 c with the Matron beside it, proved within 1%). The search reads which metamod it adds at each state, so the group widens
  and nothing is cut (OR-12).
* **The next round** holds the support of the plan in hand (the offers its policy uses), the run's named offers, the named roles and their
  dependencies; never the union of the earlier rounds. A set held by an earlier round names nothing new: the step is marked diagnosed and the
  next dearest is read. When no step names anything new the growth ends, and the rounds of `_rounds.widen` follow with the plan's support as
  their base.
* **The later group** (#1440, hypothesis H11 of #1434). A method one use of which fans out over two random choices, or copies the item, is
  named by no role until a round without it has proved a plan (`OfferTable.held_back`): each state it reaches is two draws deep, or doubled
  by a held copy, so a round that holds it with the rest is a model of every pairing, which on R14 and R04 stopped the build of the round
  that first held the Exalted Orb with its narrower (#1423's hand probe: the guide's own set built in 12 s and 37 s, the same set with one
  such method stopped before a first bound). The class is read from the offer (`Entry.fans`), never from a list of names: it makes,
  replaces or restores an imprint (`Action.imprint_move`); or it is an addition one of whose outcomes at a shape's item lacks a mod the item
  held that was not fractured (it removes a random mod as it adds one: the Beastcraft side swaps, Harvest's add-remove crafts); or the draw
  it declares there (`Action.added_draw`) is over other mods than the item's own pool on the same sides (a pool of its own: the side swaps'
  draw at the beast's level; the beast recipe that adds a mod to an influenced item drew the influence's mods alone until #1538 and now
  draws the item's own pool, as an Exalted Orb). The roles are read as before with these offers held out (the
  next cheapest takes their place), and what they would have named of them is kept. When nothing new is named without them, or a round
  does not finish within its share, one later group runs with a plan in hand: the plan's support, the named offers and the methods of the
  class the roles named, its words naming them (the page shows them). After it nothing is held back; with no plan in hand when nothing new is
  named, they are held back no longer and the start is read again with them (no plan was proved without them). Nothing is dropped (OR-12,
  OR-13): the members the roles named run in that group, and every offer keeps its group in the widening rounds after the growth. A member
  another offer needs (`closure`: a veiled placeholder, the imprint chain) comes in with it, as a dependency is never held back.

* **The full item** (#1567, hypothesis H49 of #1434). The finished shape is the rarity whose item holds the most mods (`OfferTable.finished`);
  a side of it is full when the target asks as many mods of that side as it has room for. On a full side a miss takes a slot the target
  needs, so a player plans how a miss is undone, and two rules read that from the table:
  - **the reroll back** (`rerolls_back`): on a target that fills both sides, an addition the seed ranks first on a wanted mod at a shape
    (an Orb of Augmentation on a magic item) brings the cheapest reroll that keeps that shape on the same mod (the Orb of Alteration:
    alt-aug), with the moves to its shape, when no offer of the seed rerolls the item back there already. Ranked by its own figure the
    Orb of Transmutation, a reroll that does not keep the magic shape, beat the Alteration on R17's Talisman, and the Alteration never
    entered (#1567 fault 2). On a target with room left a miss can stay on the item, and the seed is the ranking alone (the listing of
    the 13 reference crafts: only R17 and R04 fill both sides);
  - **the undo of a miss** (in `roles`): where the roles name a drawing addition at the finished shape for a waited mod of a full side (an
    Exalted Orb on R17's rare Talisman), the cheapest imprint made at that shape comes with it, though nothing is at risk yet and the
    imprints wait for their later group: the imprint before the slam, restored on a miss (#1567 fault 1: the imprint was named only as the
    protector of a step that can lose a wanted mod).

The `PER_ROLE` count orders what is searched first; it cuts nothing (OR-12): every offer keeps its group in the widening rounds after the growth.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction

import numpy as np

from crafting_system.abstraction import Abstraction, CompressedState, Status, add_bound, declared_add_bound, declared_bounds, reach_bound
from crafting_system.actions import BLOCKED_TAG, BLOCKING, LOCKED_SIDE, NotApplicableError, OutOfScopeError, build_pool
from crafting_system.data import GameData
from crafting_system.items import ExplicitMod, Item, Metamod, Rarity, Side
from crafting_system.solver import linear_solve

from ._offer_kinds import ADD, CRAFT, FINISHING, REFUSED, REROLL, RESTART_KIND, _kind_of, finishes
from ._offers import BuyStartItem, PricedOffer, reached_by

GROWS = True  # every run grows its rounds from the plan in hand; the tests of the widening rounds' own mechanism set it off (`_plan.rounds_grower`)
PER_ROLE = 2  # the offers of least cost over chance a wanted mod brings for one role: an order of what is searched first, never a cut (OR-12)
KEEPS_MODS = (ADD, *FINISHING)  # the kinds that keep the mods they are given and add one: what an adder is (a reroll is not)
_LOCKS = {metamod.value: side for metamod, side in LOCKED_SIDE.items()}
_TAGS = {metamod.value: tag for metamod, tag in BLOCKED_TAG.items()}
COPIES = "it copies the item (it makes, replaces or restores an imprint)"  # the three reasons an offer waits for the later group (#1440)
REMOVES_AND_ADDS = "it removes a random mod as it adds a random one"
OWN_POOL = "it adds a mod drawn from a pool of its own"
_SIDES = frozenset({"prefix", "suffix"})  # the sides a rolled mod sits on (`Mod.generation_type`)


@dataclass
class Entry:
    """One offer as the growth reads it (module text)."""

    position: int
    label: str
    cost: float
    kinds: dict[Rarity, str] = field(default_factory=dict)  # its kind at each shape it was read at (`_kind_of`)
    leads: dict[Rarity, frozenset[Rarity]] = field(default_factory=dict)  # the rarities its outcomes have at each shape where it applies
    chance: dict[tuple[Rarity, int], Fraction] = field(default_factory=dict)  # (shape, leaf) -> its chance of making that leaf PASSING in one use
    fractures: bool = False
    draws: bool = True  # it draws mods (a reroll, an addition): it does not only keep the mods it is given, so it protects none of them
    makes_imprint: bool = False
    restores: bool = False
    needs_veiled: bool = False
    veils: bool = False
    needs_crafted: bool = False
    crafted: bool = False  # it adds mods it names as crafted ones
    removes: bool = False  # a craft that adds no mod: it only takes one off
    locks: frozenset = frozenset()  # the sides whose lock it may add
    keeps_out: frozenset[str] = frozenset()  # the tags it may keep out of the draws
    more_crafted: bool = False  # it may add the metamod of more crafted mods
    fans: str = ""  # why one use fans out over two random choices or copies the item (module text, the later group; #1440), or ""
    need: float = 0.0  # what the cheapest offer it needs to act costs (`OfferTable.priced_needs`): ranked with its price

    def acts_at(self, shapes) -> bool:
        """Whether it is read as acting at one of `shapes` (its kind there is not a refusal)."""
        return any(shape in self.kinds and self.kinds[shape] not in (REFUSED, RESTART_KIND) for shape in shapes)

    def ratio(self, leaf: int, shapes: Sequence[Rarity] | None = None) -> tuple[float, Rarity | None]:
        """Its least cost over chance on `leaf` over `shapes` (all its shapes when None), and the shape it is at; infinity when it has none."""
        best, at = math.inf, None
        for (shape, each), chance in self.chance.items():
            if each == leaf and chance > 0 and (shapes is None or shape in shapes):
                ratio = float(Fraction(self.cost + self.need) / chance) if math.isfinite(self.need) else math.inf
                if ratio < best:
                    best, at = ratio, shape
        return best, at


class OfferTable:
    """The offers of a run as the growth reads them (module text): `entries[i]` is the offer at position `i` of `offers`.

    `held_back` are the offers no role names while the methods that fan out wait for their later group (`Grower`)."""

    held_back: frozenset[int] = frozenset()
    views: Mapping[Rarity, Item] = {}  # the item of each shape the offers turn the start item into (`_read_shape`)
    actions: Sequence = ()  # `actions[i]` is the action of the offer at position `i`
    locking: Callable[[], Abstraction] | None = None  # the model the items under a lock are read on (metamods modelled), made when first asked
    under: dict  # (side, shape, leaf, held) -> the rerolls ranked at the item under the lock (`under_lock`), read once each
    named_ids: set[str] | frozenset[str] = frozenset()  # the mods an offer names at the start item or gives by a finishing kind at a shape (`item_mod_ids`)
    _item_ids: frozenset[str] | None = None  # `item_mod_ids`, read once
    _finished: tuple | None = None  # `finished`, read once

    def __init__(self, data: GameData, abstraction: Abstraction, start: CompressedState, item: Item, priced: Sequence[PricedOffer],
                 ask: Callable[[], None] | None = None, locking: Callable[[], Abstraction] | None = None) -> None:  # fmt: skip
        self.data, self.goal = data, abstraction.goal
        self.views, self.actions, self.locking, self.under = {}, [p.offer.action for p in priced], locking, {}
        self.named_ids = set()
        shape = abstraction.compress(item) if getattr(start.flags, "unopened", False) else start
        self.start_rarity = item.rarity
        self.open = tuple(index for index in range(len(self.goal.leaves)) if shape.status[index] is not Status.PASSING)
        self.entries = [Entry(position, p.label, p.cost) for position, p in enumerate(priced)]
        actions = [p.offer.action for p in priced if not isinstance(p.offer.action, BuyStartItem) and not getattr(p.offer.action, "opens_listing", False)]
        items = [item, *(each for each in reached_by(data, item, lambda _item: actions)[1:] if not getattr(abstraction.compress(each).flags, "unopened", False))]
        for view in items:
            self._read_shape(abstraction, view, priced, ask)
        for entry, offer in zip(self.entries, priced):
            self._read_declarations(entry, offer, item)
        self.priced_needs()

    def priced_needs(self) -> None:
        """Each offer's cost as the roles rank it: its price plus the cheapest offer of what it needs to act (`closure`): a veiled choice is
        worth what a veiled placeholder costs to make, a restore what an imprint costs, so a free pick is not ranked as a free adder."""
        veil = min((entry.cost for entry in self.entries if entry.veils), default=math.inf)
        imprint = min((entry.cost for entry in self.entries if entry.makes_imprint), default=math.inf)
        for entry in self.entries:
            entry.need = (veil if entry.needs_veiled else 0.0) + (imprint if entry.restores else 0.0)

    def _read_shape(self, abstraction: Abstraction, view: Item, priced: Sequence[PricedOffer], ask) -> None:
        data, goal, rarity = self.data, self.goal, view.rarity
        self.views.setdefault(rarity, view)
        bare = replace(abstraction.compress(view), slots=())
        held = tuple(entry.mod_id for entry in view.mods)  # the mods this shape's item was given: a state of the shape may hold them (#1506)
        rerolls: dict[type, list[int]] = {}
        for position, offer in enumerate(priced):
            if ask is not None and position % 256 == 0:
                ask()
            entry, action = self.entries[position], offer.offer.action
            try:
                kind, named = _kind_of(data, view, offer)
                entry.kinds[rarity] = kind
                if kind in (RESTART_KIND, REFUSED):
                    continue
                try:  # where its outcomes go from this shape's item (a craft refused on an empty item still has its chance, read below)
                    entry.leads[rarity] = frozenset(action.rarities(data, view))
                except (NotApplicableError, OutOfScopeError, ValueError):
                    pass
                if kind in FINISHING:
                    self.named_ids |= named
                    made = bool(action.adds(data, view).crafted)
                    for leaf in self.open:
                        if finishes(goal.leaves[leaf], named, made):
                            entry.chance[(rarity, leaf)] = Fraction(1)
                elif kind == ADD:
                    if not entry.fans:
                        entry.fans = self._fans_at(action, view)
                    declared = action.added_draw(data, view) is not None
                    for leaf in self.open:
                        chance = (  # the order's figure (#1506): the held mods read per shape, not a bound, and no floor reads `entry.chance`
                            declared_add_bound(abstraction, action, view, (leaf,), ranking=True) if declared else add_bound(abstraction, bare, action, (leaf,), held, ranking=True)
                        )
                        if chance is not None and chance > 0:
                            entry.chance[(rarity, leaf)] = chance
                elif kind == REROLL:
                    adds = action.adds(data, view)
                    if not (adds.fractures or adds.keeps_crafted or action.reads(data).needs_crafted):
                        rerolls.setdefault(type(action), []).append(position)
            except (NotApplicableError, OutOfScopeError, ValueError):  # refused at this shape, or out of the data's scope: nothing read here
                continue
        for positions in rerolls.values():  # a class answers for its own actions at once (`declared_bounds`, #1073), the rest one by one
            if ask is not None:
                ask()
            for leaf in self.open:
                try:
                    found = declared_bounds(abstraction, bare, [priced[position].offer.action for position in positions], (leaf,))
                except (NotApplicableError, OutOfScopeError, ValueError):
                    found = [None] * len(positions)
                for position, bound in zip(positions, found):
                    if bound is None:
                        try:
                            bound = reach_bound(abstraction, bare, priced[position].offer.action, (leaf,))
                        except (NotApplicableError, OutOfScopeError, ValueError):
                            continue
                    if bound is not None and bound > 0:
                        self.entries[position].chance[(rarity, leaf)] = bound

    def _read_declarations(self, entry: Entry, offer: PricedOffer, item: Item) -> None:
        data, action = self.data, offer.offer.action
        if isinstance(action, BuyStartItem) or getattr(action, "opens_listing", False):
            return
        try:
            adds, reads = action.adds(data, item), action.reads(data)
        except (NotApplicableError, OutOfScopeError, ValueError):
            return
        if adds.named:
            self.named_ids |= adds.named
        move = action.imprint_move()
        entry.fractures, entry.draws = bool(adds.fractures), bool(adds.draws)
        entry.makes_imprint = move is not None and not move.restore
        entry.restores = move is not None and move.restore
        if move is not None:
            entry.fans = COPIES
        entry.needs_veiled, entry.veils, entry.needs_crafted = bool(reads.needs_veiled), bool(adds.veils), bool(reads.needs_crafted)
        entry.crafted = bool(adds.crafted) and bool(adds.named)
        entry.removes = adds.named == frozenset() and not adds.draws and CRAFT in entry.kinds.values()
        families: set[str] = set()
        if adds.named:
            families = {family for mod_id in adds.named if mod_id in data.mods for family in data.mods[mod_id].families}
        elif adds.named is None and adds.crafted:
            families = set(reads.families or ())  # a crafted mod it picks among the families it reads
        entry.locks = frozenset(_LOCKS[family] for family in families if family in _LOCKS)
        entry.keeps_out = frozenset(_TAGS[family] for family in families if family in _TAGS)
        entry.more_crafted = Metamod.MULTIPLE_CRAFTED_MODS.value in families

    def _fans_at(self, action, view: Item) -> str:
        """Why an addition at `view`'s shape fans out over two random choices (module text, the later group), or "": one of its outcomes at
        `view` lacks a mod `view` held that was not fractured (it removes a random mod as it adds one), or the draw it declares there
        (`Action.added_draw`) is over other mods than the item's own pool on the same sides (a pool of its own)."""
        data = self.data
        held = {entry.mod_id for entry in view.mods if not entry.fractured}
        try:
            results = getattr(action.outcomes(data, view), "results", None) if held else None
            if results and any(held - {entry.mod_id for entry in after.mods} for _chance, after in results):
                return REMOVES_AND_ADDS
            draw = action.added_draw(data, view)
            if draw is None:
                return ""
            sides = {side for side, room in draw.free.items() if room}
            own = {each.mod.id for family in draw.pool if family.side in sides for each in family.mods}
            return OWN_POOL if own != self.pool_ids(view, sides) else ""
        except (NotApplicableError, OutOfScopeError, ValueError):  # refused or out of the model's scope at this shape: nothing read here
            return ""

    def pool_ids(self, view: Item, sides) -> set[str]:
        """The mods of the item's own pool on `sides` at `view`'s shape (its fractured mods and nothing else)."""
        bare = view.changed(self.data, mods=tuple(entry for entry in view.mods if entry.fractured))
        return {each.mod.id for family in build_pool(self.data, bare) if family.side in sides for each in family.mods}

    def seed(self, per_role: int = PER_ROLE) -> set[int]:
        """Round 0: per wanted mod not passing at the start, the `per_role` offers of least cost over chance on it, any kind, any shape, and
        the reroll back each addition among them needs on a target that fills the finished item (`rerolls_back`, module text)."""
        chosen: set[int] = set()
        for leaf in self.open:
            chosen.update(self._best(leaf, lambda entry: True, per_role))
        return chosen | self.rerolls_back(chosen, per_role)

    def finished(self) -> tuple[Rarity | None, frozenset[str], Entry | None]:
        """The finished shape (the rarity whose item holds the most mods), the sides of it the wanted mods fill (as many wanted mods of that
        side as it has room), and the cheapest imprint made at it (the undo of a miss there), read once (module text, the full item)."""
        if self._finished is None:
            shape, full, undo = None, frozenset(), None
            if self.views:
                shape = max(self.views, key=lambda rarity: sum(self.views[rarity].capacity(self.data).of(side) for side in Side))
                room = self.views[shape].capacity(self.data)
                count: dict[str, int] = {}
                for leaf in range(len(self.goal.leaves)):
                    side = self.side_of(leaf)
                    if side is not None:
                        count[side] = count.get(side, 0) + 1
                full = frozenset(side for side, n in count.items() if n >= room.of(Side(side)) > 0)
                imprints = [entry for entry in self.entries if entry.makes_imprint and not entry.draws and shape in entry.leads]
                undo = min(imprints, key=lambda entry: (entry.cost, entry.position)) if imprints else None
            self._finished = (shape, full, undo)
        return self._finished

    def rerolls_back(self, chosen: set[int], per_role: int = PER_ROLE) -> set[int]:
        """On a target that fills both sides of the finished item: for each addition the seed ranks first on a wanted mod at a shape where no
        offer of `chosen` rerolls the item back to that shape, the cheapest reroll that does (on the same mod), with the moves to its shape
        (module text, the full item: alt-aug)."""
        if self.finished()[1] != _SIDES:
            return set()
        def repeats(entry: Entry, shape: Rarity) -> bool:
            return entry.kinds.get(shape) == REROLL and shape in entry.leads.get(shape, ())
        extra: set[int] = set()
        for leaf in self.open:
            for position in self._best(leaf, lambda entry: True, per_role):
                at = self.entries[position].ratio(leaf)[1]
                if at is None or self.entries[position].kinds.get(at) != ADD or any(repeats(self.entries[each], at) for each in chosen | extra):
                    continue
                for roll in self._best(leaf, lambda entry, at=at: repeats(entry, at), 1, (at,)):
                    extra.add(roll)
                    if at != self.start_rarity:
                        extra |= self.moves(frozenset({self.start_rarity}), at) - self.held_back
        return extra

    def _best(self, leaf: int, allowed: Callable[[Entry], bool], count: int, shapes: Sequence[Rarity] | None = None, held: frozenset[int] = frozenset()) -> list[int]:
        ranked = sorted(
            (ratio, entry.position) for entry in self.entries
            if entry.position not in held and entry.position not in self.held_back and allowed(entry) and math.isfinite(ratio := entry.ratio(leaf, shapes)[0])
        )  # fmt: skip
        return [position for _ratio, position in ranked[:count]]

    def item_mod_ids(self) -> frozenset[str]:
        """The mods this item can hold (#1502): its own pool on both sides at the item of each rarity the offers reach (`views`, `pool_ids`), the mods
        those items hold, and the mods an offer names (`named_ids`: a craft's, an essence's, a veiled choice's). Empty for a table read with no
        item. Read once."""
        if self._item_ids is None:
            found = set(self.named_ids)
            for view in self.views.values():
                found |= {entry.mod_id for entry in view.mods}
                try:
                    found |= self.pool_ids(view, _SIDES)
                except (NotApplicableError, OutOfScopeError, ValueError):  # no pool read at this shape: its offers name the rest
                    continue
            self._item_ids = frozenset(found)
        return self._item_ids

    def side_of(self, leaf: int) -> str | None:
        """The side of the wanted mod `leaf` (#1502): the side of the prefixes and suffixes that pass it among the mods this item can hold
        (`item_mod_ids`), so a requirement written as a stat that other bases' mods carry on the other side (X1's Physical Damage over
        Time Multiplier: a suffix on a wand, a prefix elsewhere) has the side of its own base. None when those mods sit on both sides: the
        item can roll it either as a prefix or as a suffix, so no one side's lock protects it and no step waits for it on one side. When
        the item can hold none of them (a mod the table reads no source of, a table read with no item), every prefix or suffix that passes
        it is read, as before. A unique's or another source's mod that passes it is never rolled on the item and names no side."""
        mods, ids = self.data.mods, self.goal.leaves[leaf].mod_ids
        sides = {mods[mod_id].generation_type for mod_id in ids & self.item_mod_ids() if mod_id in mods} & _SIDES
        if not sides:
            sides = {mods[mod_id].generation_type for mod_id in ids if mod_id in mods} & _SIDES
        return next(iter(sides)) if len(sides) == 1 else None

    def tags_of(self, leaves) -> frozenset[str]:
        """The tags the wanted mods `leaves` carry (any mod that can pass each)."""
        mods = self.data.mods
        return frozenset(tag for leaf in leaves for mod_id in self.goal.leaves[leaf].mod_ids if mod_id in mods for tag in mods[mod_id].implicit_tags)

    def given(self, leaf: int, holding) -> bool:
        """Whether an offer of `holding` gives the wanted mod `leaf` by a finishing kind (a craft, a veiled choice, a veil): it is not drawn."""
        return any(self.entries[position].kinds.get(shape) in FINISHING for position in holding for (shape, each) in self.entries[position].chance if each == leaf)

    def narrowers(self, pending: set[int], holding) -> set[int]:
        """The cheapest offer that draws no mod and keeps each tag out of the draws, for every tag no wanted mod of `pending` the adders must
        draw carries (module text): a mod an offer of `holding` gives by a finishing kind is not drawn, so its tags may be kept out."""
        drawn = {leaf for leaf in pending if not self.given(leaf, holding)}
        kept = self.tags_of(drawn)
        named = set()
        for tag in sorted({tag for entry in self.entries for tag in entry.keeps_out} - kept):
            narrower = self.cheapest(lambda entry, tag=tag: tag in entry.keeps_out and not entry.draws)
            if narrower is not None:
                named.add(narrower)
        return named

    def cheapest(self, allowed: Callable[[Entry], bool], held: frozenset[int] = frozenset()) -> int | None:
        found = [(entry.cost, entry.position) for entry in self.entries if entry.position not in held and entry.position not in self.held_back and allowed(entry)]
        return min(found)[1] if found else None

    def roles(self, waits: set[int], risks: set[int], shapes: frozenset[Rarity], fractured: bool, held: frozenset[int], current: frozenset[int],
              pending: set[int] | None = None) -> set[int]:  # fmt: skip
        """The offers named for a step that waits for `waits` and can lose `risks` at `shapes` (module text). `held` are the offers the round
        that made the plan held (adders are named among the others); `current` the offers the next round already holds; `pending` the wanted
        mods not passing at some state where the step acts (the mods open at the start when None)."""
        named: set[int] = set()
        adders: list[tuple[int, Rarity | None]] = []
        for leaf in sorted(waits):
            for position in self._best(leaf, lambda entry: any(kind in KEEPS_MODS for kind in entry.kinds.values()) and not entry.removes, PER_ROLE, None, held):
                adders.append((position, self.entries[position].ratio(leaf)[1]))
        for position, at in adders:
            named.add(position)
            if at is not None and at not in shapes:
                named.update(self.moves(shapes, at))
        wait_sides = {self.side_of(leaf) for leaf in waits}
        for leaf in sorted(risks):
            if not fractured:
                named.update(entry.position for entry in self.entries if entry.fractures and not entry.draws and entry.acts_at(shapes))
            side = self.side_of(leaf)
            if side is not None and wait_sides != {side}:
                lock = self.cheapest(lambda entry, side=side: not entry.draws and any(getattr(each, "value", each) == side for each in entry.locks))
                if lock is not None:
                    named.add(lock)
            imprint = self.cheapest(lambda entry: entry.makes_imprint and not entry.draws and any(shape in entry.leads for shape in shapes))
            if imprint is not None:
                named.add(imprint)
        shape, full, undo = self.finished()
        if undo is not None and full and any(
            self.entries[position].draws and self.entries[position].kinds.get(shape) == ADD
            and any(self.side_of(leaf) in full and (shape, leaf) in self.entries[position].chance for leaf in waits)
            for position in named
        ):  # fmt: skip
            named.add(undo.position)  # the undo of a miss on a side the target fills: never held back for the later group (module text)
        if adders or any(self.entries[position].crafted for position in current):
            holding = current | named
            cleaner = self.cheapest(lambda entry: entry.removes and not entry.needs_crafted)
            if cleaner is not None:
                named.add(cleaner)
            named |= self.narrowers(set(waits) | set(self.open if pending is None else pending), holding)
            named |= self.crafted_roles(current | named)
        return named

    def step_adders(self, waits: set[int], shapes: frozenset[Rarity], held: frozenset[int]) -> set[int]:
        """The adders a lock group names beside its locks (module text, #1420): for each wanted mod of `waits`, the `PER_ROLE` offers of least
        cost over chance on it that keep the mods they are given, ranked only at `shapes` (the rarities where the step acts), among the offers
        `held` does not hold. An offer with no chance on the mod at those shapes is not ranked."""
        keeps = lambda entry: any(kind in KEEPS_MODS for kind in entry.kinds.values()) and not entry.removes  # noqa: E731
        return {position for leaf in sorted(waits) for position in self._best(leaf, keeps, PER_ROLE, shapes, held)}

    def lockers(self, side: str) -> list[int]:
        """Every offer that may add the lock of `side` and keeps the mods it is given (a reroll at no shape): the bench lock, and what puts
        it back once a reroll of the other side has taken it off (a beast that adds a metamod draws which one, but keeps the mods)."""
        return [
            entry.position for entry in self.entries
            if entry.position not in self.held_back and REROLL not in entry.kinds.values() and any(getattr(each, "value", each) == side for each in entry.locks)
        ]  # fmt: skip

    def lock_roles(self, waits: set[int], shapes: frozenset[Rarity], held: frozenset[int]) -> set[int]:
        """The locks and the rerolls under them for a step that waits for wanted mods on both sides (module text, #1420): for each side,
        every offer that adds its lock (`lockers`), and for each waited mod the `PER_ROLE` rerolls of least cost over chance at the item
        under that lock (`under_lock`), among the offers `held` does not hold."""
        sides = {self.side_of(leaf) for leaf in waits}
        if not _SIDES <= sides:
            return set()
        named: set[int] = set()
        for side in sorted(_SIDES):
            lockers = self.lockers(side)
            if not lockers:
                continue
            rerolls: set[int] = set()
            for shape in sorted(shapes, key=str):
                for leaf in sorted(waits):
                    other = frozenset(each for each in waits if each != leaf and self.side_of(each) == side)
                    ranked = [position for _ratio, position in self.under_lock(side, shape, leaf, other) if position not in held]
                    rerolls.update(ranked[:PER_ROLE])
            if rerolls:  # a lock pays only with a reroll under it: with none ranked there the side names nothing
                named.update(lockers)
                named |= rerolls
        return named

    def under_lock(self, side: str, shape: Rarity, leaf: int, other: frozenset[int]) -> list[tuple[float, int]]:
        """The rerolls at `shape` ranked by cost over chance at the item under the lock of `side` (module text, #1420): the shape's item
        with its fractured mods, a mod of each wanted mod of `other` (the step's other waited mods on that side) and the lock's own mod, read
        on the model of the metamods. The chance is that one use leaves `leaf` and every mod of `other` passing (`reach_bound` over them): it
        counts what the reroll keeps, so a reroll that takes the locked side off scores nothing there. Read once each; empty when the item
        cannot be made (a wanted mod no mod of that side can be, no room, no lock that names its mod)."""
        key = (side, shape, leaf, other)
        if key not in self.under:
            self.under[key] = self._read_under_lock(side, shape, leaf, other)
        return self.under[key]

    def _read_under_lock(self, side: str, shape: Rarity, leaf: int, other: frozenset[int]) -> list[tuple[float, int]]:
        found: list[tuple[float, int]] = []
        view = self.views.get(shape)
        lockers = [self.entries[position] for position in self.lockers(side)]
        if view is None or self.locking is None or not lockers:
            return found
        data = self.data
        lock = min(lockers, key=lambda entry: (entry.draws, entry.cost, entry.position))  # the item is made with a lock that names its mod
        # a reroll under the lock rerolls the other side, and the lock, a crafted mod of that side, goes with it: each use pays a lock again
        relock = min(entry.cost for entry in lockers)
        try:
            item = view.changed(data, mods=tuple(entry for entry in view.mods if entry.fractured))
            for each in sorted(other):
                mod = next((data.mods[mod_id] for mod_id in sorted(self.goal.leaves[each].tier_ok or self.goal.leaves[each].mod_ids)
                            if mod_id in data.mods and data.mods[mod_id].generation_type == side and item.can_add(data, data.mods[mod_id])), None)  # fmt: skip
                if mod is None:
                    return found
                item = item.add_mod(data, ExplicitMod(mod.id, tuple(stat.max for stat in mod.stats)))
            named = self.actions[lock.position].adds(data, item).named or ()
            mod = next((data.mods[mod_id] for mod_id in sorted(named) if mod_id in data.mods and any(getattr(_LOCKS.get(family), "value", None) == side for family in data.mods[mod_id].families)), None)
            if mod is None:
                return found
            item = item.add_mod(data, ExplicitMod(mod.id, tuple(stat.min for stat in mod.stats), crafted=True))
            abstraction = self.locking()
            state = abstraction.compress(item)
        except (NotApplicableError, OutOfScopeError, ValueError):  # the item cannot be made or read on the model: no reroll is read under it
            return found
        leaves = tuple(sorted({*other, leaf}))
        for entry in self.entries:
            if entry.position in self.held_back or entry.kinds.get(shape) != REROLL or not math.isfinite(entry.need):
                continue
            try:
                bound = reach_bound(abstraction, state, self.actions[entry.position], leaves)
            except (NotApplicableError, OutOfScopeError, ValueError):  # refused under the lock (an essence), or out of the model's scope
                continue
            if bound is not None and bound > 0:
                found.append((float(Fraction(entry.cost + entry.need + relock) / bound), entry.position))
        found.sort()
        return found

    def crafted_roles(self, holding) -> set[int]:
        """The crafts that add no mod and need a crafted one when `holding` holds a crafted mod, and the cheapest of more crafted mods when
        it holds two (module text): a narrower counts, it is a crafted mod held."""
        crafted = sum(1 for position in holding if self.entries[position].crafted)
        named = {entry.position for entry in self.entries if entry.removes and entry.needs_crafted} if crafted else set()
        if crafted >= 2:
            more = self.cheapest(lambda entry: entry.more_crafted and not entry.draws)
            if more is not None:
                named.add(more)
        return named

    def moves(self, shapes: frozenset[Rarity], to: Rarity) -> set[int]:
        """The cheapest offer of each step on the cheapest way from `shapes` to the shape `to` (the rarities the offers' outcomes have)."""
        best: dict[Rarity, tuple[float, tuple[int, ...]]] = {shape: (0.0, ()) for shape in shapes}
        frontier = list(shapes)
        while frontier:
            shape = frontier.pop(0)
            cost, path = best[shape]
            for entry in self.entries:
                for lead in entry.leads.get(shape, ()):
                    if lead != shape and (lead not in best or cost + entry.cost < best[lead][0]):
                        best[lead] = (cost + entry.cost, (*path, entry.position))
                        frontier.append(lead)
        return set(best.get(to, (0.0, ()))[1])

    def closure(self, positions: set[int]) -> set[int]:
        """`positions` with what each needs to act, and the lockers of each side a bench lock among them locks (module text, dependencies)."""
        found = set(positions)
        while True:
            more = set()
            chosen = [self.entries[position] for position in found]
            if any(entry.needs_veiled or entry.veils for entry in chosen):
                more.update(entry.position for entry in self.entries if entry.needs_veiled or (entry.veils and any(each.needs_veiled for each in chosen)))
            if any(entry.restores or entry.makes_imprint for entry in chosen):
                more.update(entry.position for entry in self.entries if entry.restores or entry.makes_imprint)
            for side in sorted({getattr(side, "value", side) for entry in chosen if not entry.draws for side in entry.locks}):
                more.update(self.lockers(side))  # where the bench lock of a side is, every offer that may put that lock on is (#1513)
            if more <= found:
                return found
            found |= more


def step_shares(plan) -> list[tuple[str, float, list[tuple[CompressedState, object, float]]]]:
    """The steps of `plan` by their cost share, dearest first: each label with its expected uses times its price, and the states where it acts
    with the action there and their expected visits. Read on the plan's lumped chain (`PackedResult.view`, one shown state per block: the
    numbers are those of the policy), whose visits solve `u = e + P^T u` with each state's self-loop taken out exactly (`P[s, t]` its chance to go
    to `t` given that it leaves, `u` the departures, visits = departures over the chance to leave). Empty when it cannot be read."""
    packed = getattr(plan, "packed", None)
    view = getattr(packed, "view", None) if packed is not None else None
    if not view:
        return []
    states = list(view)
    index = {state: i for i, state in enumerate(states)}
    start = plan.start if plan.start in index else None
    if start is None and packed.risk_policy is not None and packed.risk_start in packed.risk_policy:
        start = states[list(packed.risk_policy).index(packed.risk_start)]
    if start is None:
        return []
    n = len(states)
    rows, cols, chances, leave = [], [], [], np.ones(n)
    for i, state in enumerate(states):
        action = view[state]
        # the weights may be exact integers past float's range (a kernel on one common denominator, #957)
        total = sum(outcome.weight for outcome in action.outcomes)
        self_weight = sum(outcome.weight for outcome in action.outcomes if outcome.state == state)
        if total <= 0 or self_weight >= total:
            return []
        exact = isinstance(total, int) and total.bit_length() > 1000  # past float's range: ratios taken as fractions
        part = (lambda a, b: float(Fraction(a, b))) if exact else (lambda a, b: float(a) / float(b))
        leave[i] = part(total - self_weight, total)
        for outcome in action.outcomes:
            j = index.get(outcome.state)
            if j is not None and j != i:
                rows.append(i)
                cols.append(j)
                chances.append(part(outcome.weight, total - self_weight))
    row, col, chance = np.asarray(rows, dtype=np.int64), np.asarray(cols, dtype=np.int64), np.asarray(chances, dtype=float)

    class _Departures(linear_solve.Terms):
        def __init__(self) -> None:
            self.n = n

        def apply(self, v: np.ndarray) -> np.ndarray:
            return np.bincount(col, weights=chance * v[row], minlength=n)

        def dense(self) -> np.ndarray:
            matrix = np.zeros((n, n))
            np.add.at(matrix, (col, row), chance)
            return matrix

    b = np.zeros(n)
    b[index[start]] = 1.0
    with np.errstate(all="ignore"):
        solved = linear_solve.solve(_Departures(), b)
    if solved.x is None or not np.all(np.isfinite(solved.x)):
        return []
    visits = np.maximum(solved.x, 0.0) / leave
    shares: dict[str, float] = {}
    where: dict[str, list] = {}
    for i, state in enumerate(states):
        action = view[state]
        shares[action.label] = shares.get(action.label, 0.0) + visits[i] * action.cost
        where.setdefault(action.label, []).append((state, action, float(visits[i])))
    return sorted(((label, share, where[label]) for label, share in shares.items()), key=lambda each: (-each[1], str(each[0])))


def read_step(acts: Sequence[tuple[CompressedState, object, float]], leaves: int) -> tuple[set[int], set[int], frozenset[Rarity], bool]:
    """`W`, `K`, the shapes and whether a fractured mod is held, at the states where a step acts (module text), from their statuses and their
    outcomes' statuses."""
    waits, risks, shapes, fractured = set(), set(), set(), False
    for state, action, visits in acts:
        if not visits > 0.0:
            continue
        shapes.add(state.flags.rarity)
        fractured = fractured or bool(state.fractured)
        for outcome in action.outcomes:
            after = outcome.state
            status = getattr(after, "status", None)
            if status is None:
                continue
            for leaf in range(leaves):
                before = state.status[leaf] is Status.PASSING
                now = status[leaf] is Status.PASSING
                if not before and now:
                    waits.add(leaf)
                elif before and not now:
                    risks.add(leaf)
    return waits, risks, frozenset(shapes), fractured


def pending_at(acts: Sequence[tuple[CompressedState, object, float]], leaves: int) -> set[int]:
    """The wanted mods not passing at some state where a step acts (`acts` as `read_step` reads them): a mod passing at every one of them is
    not drawn by the step, so a tag it carries may be kept out of the draws (a tag kept out removes no mod the item holds)."""
    return {leaf for state, _action, visits in acts if visits > 0.0 for leaf in range(leaves) if state.status[leaf] is not Status.PASSING}


class Grower:
    """The growth of the rounds (module text): asked by `_rounds.widen` for the seed, then for the next round's offers after each round.

    `asked` are the positions of the run's named offers (they are in every round); `support(plan)` the positions its policy uses."""

    def __init__(self, table: OfferTable, asked: Sequence[int]) -> None:
        self.table, self.asked = table, frozenset(asked)
        self.tried: list[frozenset[int]] = []
        self.diagnosed: set[str] = set()
        self.plan = None
        self.plan_set: frozenset[int] = frozenset()  # the offers of the round that made the plan in hand
        self.last: frozenset[int] = frozenset()
        self.by_label = {entry.label: entry.position for entry in table.entries}
        # the methods that fan out (module text, the later group): no role names them until a round without them has proved a plan; what the
        # roles would have named of them is kept for that group. An offer the target names is in every round, so it is never held back
        self.later_ones = frozenset(entry.position for entry in table.entries if entry.fans) - self.asked
        self.later_named: set[int] = set()
        self.later_done = not self.later_ones
        self.ended = False
        self.lock_round = False  # the last round named was a lock group (`stop`)
        self.locks_read: set[tuple] = set()  # (step, its W, its shapes) whose lock group was read (module text, the lock group)
        table.held_back = self.later_ones

    def _named_later(self, named: Callable[[], set[int]]) -> None:
        """Keep for the later group what `named()` names of the methods that fan out when no offer is held back."""
        if self.later_done:
            return
        table = self.table
        held, table.held_back = table.held_back, frozenset()
        try:
            self.later_named |= table.closure(set(named())) & self.later_ones
        finally:
            table.held_back = held

    def later(self) -> tuple[tuple[int, ...], str] | None:
        """The later group (module text), once: the plan's support, the named offers and the methods that fan out the roles named, with a
        plan in hand; None when there is none to run. After it no offer is held back."""
        if self.later_done or self.plan is None:
            return None
        self.later_done, self.table.held_back = True, frozenset()
        if not self.later_named:
            return None
        chosen = self.table.closure(set(self.support(self.plan)) | set(self.asked) | self.later_named)
        if not self._new(chosen):
            return None
        return tuple(sorted(chosen)), f"the later group of the methods that fan out over two random choices or copy the item, after a plan proved without them: {self._labels(self.later_named)}"

    def stop(self) -> tuple[tuple[int, ...], str] | None:
        """A growth round did not finish within its share (`_rounds.widen`): the usual growth ends; the lock groups not yet read come, then
        the later group when it is owed. A lock group that did not finish ends nothing (module text)."""
        if self.lock_round:
            return self.next()
        self.ended = True
        return self.last_lock() or self.later()

    def seed(self) -> tuple[tuple[int, ...], str] | None:
        self._named_later(self.table.seed)
        chosen = self.table.closure(self.table.seed() | self.asked)
        if not chosen:
            return None
        return tuple(sorted(chosen)), "the seed: the cheapest methods for each wanted mod, by cost over chance"

    def support(self, plan) -> frozenset[int]:
        if plan is None:
            return frozenset()
        packed = getattr(plan, "packed", None)
        policy = packed.view if packed is not None and packed.view else plan.policy
        labels = {action.label for action in policy.values()}
        return frozenset(self.by_label[label] for label in labels if label in self.by_label)

    def ran(self, positions: Sequence[int], plan_in_hand, improved: bool) -> None:
        """Note a round: its offers, and the plan in hand after it (`improved`: the round made it)."""
        chosen = frozenset(positions)
        self.tried.append(chosen)
        self.last = chosen
        if improved:
            self.plan, self.plan_set, self.diagnosed = plan_in_hand, chosen, set()

    def say(self, text: str) -> None:
        """A line for a measuring script (`_packed.PROGRESS`, never set by the library)."""
        from . import _packed

        if _packed.PROGRESS is not None:
            _packed.PROGRESS(text)

    def _new(self, chosen: set[int]) -> bool:
        return not any(chosen <= tried for tried in self.tried)

    def next(self) -> tuple[tuple[int, ...], str] | None:
        """The next round's offers and the words that say why, or None: nothing new is named for any step (the growth ends). When the
        usual roles name nothing more, the lock groups come (`last_lock`), then the later group of the methods that fan out (module text)."""
        self.lock_round = False
        if not self.ended:
            found = self._next()
            if found is not None:
                return found
            if not self.later_done and self.plan is None:  # no round proved a plan without them: they are held back no longer, and the start is read again with them
                self.later_done, self.table.held_back = True, frozenset()
                return self._next()
        found = self.last_lock()
        if found is not None:
            return found
        if self.ended or self.later_done:
            return self.later()
        return self.later() or self._next()

    def _next(self) -> tuple[tuple[int, ...], str] | None:
        table, plan = self.table, self.plan
        if plan is None:  # no plan in hand: the roles read at the start
            base = set(self.last)
            waits, risks = self._start_reading(base)
            self._named_later(lambda: table.roles(waits, risks, frozenset({table.start_rarity}), False, self.last, frozenset(base)))
            named = table.roles(waits, risks, frozenset({table.start_rarity}), False, self.last, frozenset(base))
            chosen = table.closure(base | named | self.asked)
            if named and self._new(chosen):
                return tuple(sorted(chosen)), f"no plan yet, so methods named at the start item (it waits for {self._names(waits)}; at risk: {self._names(risks)})"
            return None
        support = self.support(plan)
        shares = step_shares(plan)
        at_states = self.waits_at_states(shares)  # read once per plan: it does not depend on the step diagnosed
        for label, share, acts in shares:
            if label in self.diagnosed or label not in self.by_label:
                continue
            waits, risks, shapes, fractured = read_step(acts, len(table.goal.leaves))
            current = frozenset(support | self.asked)
            self.diagnosed.add(label)
            pending = pending_at(acts, len(table.goal.leaves))
            self._named_later(lambda: table.roles(waits, risks, shapes, fractured, self.plan_set, current, pending))
            named = table.roles(waits, risks, shapes, fractured, self.plan_set, current, pending)
            narrowers = self.state_narrowers(shares, current | named, at_states) - current - named
            named |= narrowers | (table.crafted_roles(current | named | narrowers) if narrowers else set())
            chosen = table.closure(set(current) | named)
            if named - current and self._new(chosen):
                also = f"; and, at the states where the plan's drawing additions act, {self._labels(narrowers)}" if narrowers else ""
                return tuple(sorted(chosen)), (
                    f"the plan's dearest step not yet read, {label} ({share:,.2f} Chaos of the plan), waits for {self._names(waits)} and can lose {self._names(risks)}{also}"
                )
        return None

    def last_lock(self) -> tuple[tuple[int, ...], str] | None:
        """The lock groups, the last resort (module text): once the usual roles name nothing for any step, the first lock group not yet
        read among the plan's steps, the dearest first, of a step that can lose nothing; None when there is none."""
        if self.plan is None:
            return None
        current = frozenset(self.support(self.plan) | self.asked)
        for label, share, acts in step_shares(self.plan):
            if label not in self.by_label:
                continue
            waits, risks, shapes, _fractured = read_step(acts, len(self.table.goal.leaves))
            if risks:
                continue
            found = self.lock_group(label, share, waits, shapes, current)
            if found is not None:
                self.lock_round = True
                return found
        return None

    def lock_group(self, label: str, share: float, waits: set[int], shapes: frozenset[Rarity], current: frozenset[int]) -> tuple[tuple[int, ...], str] | None:
        """The lock group of a step that waits on both sides (module text, #1420), once per step, its `W` and its shapes: the offers the next
        round holds already, the lock role (`OfferTable.lock_roles`), the adders ranked where the step acts (`OfferTable.step_adders`) and the
        cheapest cleaner; None when the lock role names nothing new."""
        key = (label, frozenset(waits), shapes)
        if key in self.locks_read:
            return None
        self.locks_read.add(key)
        table = self.table
        named = table.lock_roles(waits, shapes, current | self.plan_set)
        if not named - current:
            return None
        held = current | self.plan_set | named
        self._named_later(lambda: table.step_adders(waits, shapes, held))
        named = named | table.step_adders(waits, shapes, held)
        cleaner = table.cheapest(lambda entry: entry.removes and not entry.needs_crafted)
        chosen = table.closure(set(current) | named | ({cleaner} if cleaner is not None else set()))
        if not self._new(chosen):
            return None
        return tuple(sorted(chosen)), (
            f"the lock group of the plan's dearest step not yet read, {label} ({share:,.2f} Chaos of the plan), which waits for mods on both sides "
            f"({self._names(waits)}): {self._labels(named - current)}"
        )

    def state_narrowers(self, shares, holding, at_states: set[frozenset[int]] | None = None) -> set[int]:
        """The narrowers of each state where a drawing adder of the plan in hand acts (module text, #1423): from the wanted mods it waits for
        at that state, not at the step's other states (R04's Exalted Orb waits for the Arrow at some states, for Life and Bow Damage alone at
        others: there the attack tag may be kept out). `at_states` is `waits_at_states(shares)` when the caller has read it."""
        table = self.table
        named: set[int] = set()
        for waits in self.waits_at_states(shares) if at_states is None else at_states:
            named |= table.narrowers(set(waits), holding)
        return named

    def waits_at_states(self, shares) -> set[frozenset[int]]:
        """The sets of wanted mods a drawing addition of the plan waits for, one per state where it acts (`read_step` at that state)."""
        table, leaves = self.table, len(self.table.goal.leaves)
        drawn: set[frozenset[int]] = set()
        for label, _share, acts in shares:
            position = self.by_label.get(label)
            if position is None:
                continue
            entry = table.entries[position]
            if not (entry.draws and ADD in entry.kinds.values()):
                continue
            for act in acts:
                waits = read_step([act], leaves)[0]
                if waits:
                    drawn.add(frozenset(waits))
        return drawn

    def _labels(self, positions) -> str:
        return ", ".join(sorted(self.table.entries[position].label for position in positions))

    def _start_reading(self, held: set[int]) -> tuple[set[int], set[int]]:
        """`W` and `K` with no plan in hand (module text): the wanted mods whose providers among `held` all reroll, and, when one mod's only
        provider there rerolls, every other wanted mod."""
        table = self.table
        waits, risks = set(), set()
        for leaf in table.open:
            providers = [table.entries[position] for position in held if any(each == leaf for (_shape, each) in table.entries[position].chance)]
            rerolling = [entry for entry in providers if all(kind not in KEEPS_MODS for kind in entry.kinds.values())]
            if not providers or len(rerolling) == len(providers):
                waits.add(leaf)
            if len(providers) == 1 and rerolling:
                risks.update(other for other in table.open if other != leaf)
        return waits, risks

    def _names(self, leaves: set[int]) -> str:
        """The wanted mods `leaves` by a mod each can be (the first of its accepted mods)."""
        if not leaves:
            return "no wanted mod"
        goal, mods = self.table.goal, self.table.data.mods
        names = []
        for leaf in sorted(leaves):
            mod_id = sorted(goal.leaves[leaf].tier_ok or goal.leaves[leaf].mod_ids)[0]
            mod = mods.get(mod_id)
            names.append(" ".join(str(getattr(mod, "text", "") or mod_id).split()))
        return "; ".join(names)


def growth_table(data: GameData, goal, target, priced: Sequence[PricedOffer], listing: Item | None, ask=None) -> OfferTable:
    """The table of `priced` (the rounds' offers, in their order) on the model of every offer (`OfferTable`)."""
    enabled = [p.offer.action for p in priced if (reads := p.offer.action.reads(data)).junk or reads.item_state]
    holds = bool(target.start_item.metamods(data) & BLOCKING)
    abstraction = Abstraction(
        data, goal, target.base_id, target.item_level, enabled, metamods=holds, enchantment=target.start_item.enchantment, allow_inputs=True
    )  # fmt: skip
    start = abstraction.compress(listing or target.start_item)
    made: list[Abstraction] = []

    def locking() -> Abstraction:  # the model of the items under a lock (`OfferTable.under_lock`): the same, with the metamods modelled
        if not made:
            made.append(abstraction if holds else Abstraction(
                data, goal, target.base_id, target.item_level, enabled, metamods=True, enchantment=target.start_item.enchantment, allow_inputs=True
            ))  # fmt: skip
        return made[0]

    return OfferTable(data, abstraction, start, target.start_item, priced, ask, locking)


__all__ = ["Grower", "OfferTable", "PER_ROLE", "growth_table", "pending_at", "read_step", "step_shares"]
