"""The actions the planner may use, what one use of each takes, and what that costs at today's prices.

An `Offer` pairs an action of `actions` with the resources one use consumes, by their price-file
names. `offers_for` lists what the model offers for one target: a Chaos Orb, the Harvest reforge of
Lightning, every essence the item class takes, Remove Crafted Mods and the bench crafts whose mod
counts toward a requirement. Prices come from the price file (hand overrides on top); an offer with a
missing price is dropped and reported (ADR-0007), never guessed.
"""

import random
from collections import Counter, defaultdict
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass, replace
from itertools import combinations

from crafting_system.abstraction import Goal, Status, status_of
from crafting_system.actions import Action, Axis, ListingGap, Need, NotApplicableError, OutOfScopeError, Reads, StrandUse, UnmodelledBase, base_refusal, catalog, catalog_kinds, default_actions, drawable_mod_ids, holds_placeholder, kinds, open_listing, unveil_pool_families
from crafting_system.actions import without_ranges  # noqa: F401  (the report reads it from here)
from crafting_system.data import GameData
from crafting_system.items import ExplicitMod, Item, ItemError, Rarity, spawn_weight
from crafting_system.prices import CHAOS_ORB, DIVINE_ORB, PriceFile, planned_price, standing_defaults
from crafting_system.prices.price_source import DEFAULT_PRICE_SOURCE

from . import _limits
from ._limits import Limit, claim, kind_title

RESTART = "restart"
UNVEIL_KIND = "unveil"  # the catalog kind whose offer a bench craft can block (ADR-0026)
LOCK_KIND = "hinekora-lock"  # the name a target's `actions:` gives Hinekora's Lock, on by default (`_foresight`, ticket #296)
FREE_ACTION_SHARE = 1e-6  # what an action that consumes nothing costs, as a share of the cheapest offer that costs something (ADR-0026)
# What the draw of a bought item's mods costs (ADR-0064), as a share of the cheapest offer that costs something. It is not free like an unveil
# because it lies on every cycle of a restart: the certified error of a component is about (m + 2) * epsilon * value / g for its smallest constant
# term g (`solver/_certify.py`), and a draw at 1e-6 of the cheapest orb gave R13 an error of 8.7e-4 and at 1e-2 of 1.3e-6, past the 1e-6 the
# solvers accept. At 0.1 it is about 1.3e-7, and a plan's mean moves by 0.1 of the cheapest orb per draw (R13: 0.0016 Chaos of 6,568, 2.4e-7 of
# it), which is inside the tolerance the solvers accept. The start price is the listing's price and is not changed.
DRAW_COST_SHARE = 0.1


@dataclass(frozen=True)
class Offer:
    """One action and what a use of it consumes.

    `resources` maps a price-file name to how many of it one use takes. `tag` is the guaranteed mod
    tag of a Harvest reforge and None for any other action. `inputs` are the other items one use consumes on the
    start item (`Action.inputs`, ADR-0022) and `axes` the rule axes the action reads (`Action.rule_axes`, ADR-0033);
    both are empty for an action that has neither, which is every action of batches B1 and B2. The inputs of other
    states are asked of the action there (`Abstraction.inputs`).
    """

    label: str
    action: object
    resources: Mapping[str, int]
    tag: str | None = None
    shares: bool = True  # whether the report quotes a single-draw weight share (a Chaos Orb, a Harvest reforge)
    inputs: tuple[Need, ...] = ()
    axes: tuple[Axis, ...] = ()
    kind: str = ""  # the name of the catalog kind that lists the action ("" for an offer made by hand); the unpriced limit groups by it (#487)


@dataclass(frozen=True)
class PricedOffer:
    """An offer with the price of one use, in Chaos Orbs, and where each resource price came from."""

    offer: Offer
    cost: float
    parts: tuple[tuple[str, int, float, str], ...]  # (resource, count, chaos for all of them, source)
    marks: tuple[tuple[str, str], ...] = ()  # (resource, mark) of the parts whose price is a thin market's (OR-8); empty when none is marked

    @property
    def label(self) -> str:
        return self.offer.label


@dataclass(frozen=True)
class DroppedOffer:
    """An offer left out because some resource has no price."""

    label: str
    missing: tuple[str, ...]
    kind: str = ""


def offer_of(action: Action, label: str, data: GameData | None = None, item: Item | None = None, kind: str = "", *, shares: bool | None = None) -> Offer:
    """The offer of `action` under `label`: its resources, and whether the report quotes a single-draw share (with its tag).

    `data` and `item` only matter to an action whose resources or additions depend on them (an essence, a bench craft).
    """
    adds = action.adds(data, item)
    inputs = action.inputs(data, item) if data is not None else ()
    axes = action.rule_axes(data) if data is not None else ()
    return Offer(label, action, dict(action.resources(data)), tag=adds.tag, shares=adds.single_draw if shares is None else shares, inputs=inputs, axes=axes, kind=kind)


RECOMBINATOR_KIND = "recombinator"


def takes_inputs(action: Action) -> bool:
    """Whether the action's kind answers `inputs` itself: false for the base class's empty answer, so it is cheap to ask."""
    return type(action).inputs is not Action.inputs


def isolated_feeders(data: GameData, goal: Goal, start_item: Item) -> tuple[Item, ...]:
    """The donors a recombinator is offered with (ADR-0062 decision 4, ticket #225): every item made only of the target's own mods.

    One mod stands for each leaf of the goal: of the mods the leaf accepts (at a tier it accepts), the one the base rolls most often (the cheapest feeder to make;
    ties by id), and a leaf whose mods the base never rolls has none. A donor is any non-empty set of those mods of distinct families that fits
    the base (magic with at most one mod a side, rare otherwise), at the start item's base, item level and influences. These are the feeders
    the guides build (R25's A, B and AB; R28's single-mod feeders and their pairs); a donor that holds any other mod is not offered, and the
    answer says so (`_limits.FEEDER_DONORS`).
    """
    tags = data.base_items[start_item.base_id].tags
    picked: dict[str, None] = {}
    rolled_high: set[str] = set()  # mods whose leaf limits the roll: the feeder holds them at the top of their range, which every limit accepts
    for leaf in goal.leaves:
        accepted = leaf.tier_ok if leaf.tier_ok is not None else leaf.mod_ids  # a tier the leaf accepts (OR-1: the top tier when none is written)
        rolled = [(spawn_weight(data.mods[mod_id], tags), mod_id) for mod_id in accepted if mod_id in data.mods]
        rolled = [(weight, mod_id) for weight, mod_id in rolled if weight > 0]
        if rolled:
            chosen_mod = min(rolled, key=lambda pair: (-pair[0], pair[1]))[1]
            picked.setdefault(chosen_mod, None)
            if leaf.has_roll_limit:
                rolled_high.add(chosen_mod)
    found: list[Item] = []
    seen: set[Item] = set()
    chosen = sorted(picked)
    for size in range(1, len(chosen) + 1):
        for group in combinations(chosen, size):
            families = [family for mod_id in group for family in data.mods[mod_id].families]
            if len(families) != len(set(families)):
                continue
            per_side = Counter(data.mods[mod_id].generation_type for mod_id in group)
            rarity = Rarity.MAGIC if max(per_side.values()) <= 1 else Rarity.RARE
            mods = tuple(
                ExplicitMod(mod_id, tuple((max if mod_id in rolled_high else min)(stat.min, stat.max) for stat in data.mods[mod_id].stats))
                for mod_id in group
            )
            try:
                item = Item.build(
                    data, base_id=start_item.base_id, item_level=start_item.item_level, rarity=rarity, mods=mods, influences=start_item.influences
                )
            except ItemError:  # more mods on a side than the base holds
                continue
            if item not in seen:
                seen.add(item)
                found.append(item)
    return tuple(found)


def _with_feeder_donors(data: GameData, goal: Goal, start_item: Item, kind_of: dict[Action, str]) -> dict[Action, str]:
    """`kind_of` with the recombinators the catalog listed for the start item replaced by one for each of the target's isolated feeders.

    The catalog's own donors (a copy of the item in hand and a donor of other mods) are a contract fixture, not the planner's choice; the
    planner's donors come from the target (ADR-0062 decision 4). The price follows whether the item in hand carries an influence.
    """
    kept = {action: kind for action, kind in kind_of.items() if kind != RECOMBINATOR_KIND}
    feeders = isolated_feeders(data, goal, start_item)
    if not feeders:
        return kept
    # the kind's first action for an item of the target's mods is the plain one (no junk craft), priced for the influences of the item in hand
    # (the feeders carry the start item's); every feeder is that action with its own donor (`with_inputs`)
    listed = catalog_kinds(data, feeders[0], planner_only=True, names=frozenset({RECOMBINATOR_KIND}))
    template = next(iter(listed), None)
    if template is None:
        return kept
    for donor in feeders:
        kept[template.with_inputs((donor,))] = RECOMBINATOR_KIND
    return kept


def isolated_feeder(goal: Goal) -> Callable[[Need], bool]:
    """The seed of the lazy offer loop (ADR-0062 decision 4): a `Need` whose donor holds only mods the goal names.

    The loop starts by offering the actions whose donors are made of the target's own mods, "isolated feeders" (for a
    recombinator the single target mods and their pairs). Any seed ends at the same value; this one saves rounds.
    The test is on concrete items: a mod counts when a leaf of the goal lists it (`Wanted.mod_ids`).
    """
    named = frozenset(mod_id for leaf in goal.leaves for mod_id in leaf.mod_ids)
    return lambda need: all(entry.mod_id in named for entry in need.want.mods)


def default_offers() -> tuple[Offer, ...]:
    """The two rerolls that need no game data: a Chaos Orb and the Harvest reforge of Lightning."""
    return tuple(offer_of(action, action.label()) for action in default_actions())


def price_offers(
    offers: Iterable[Offer], prices: PriceFile, price_source: str = DEFAULT_PRICE_SOURCE
) -> tuple[tuple[PricedOffer, ...], tuple[DroppedOffer, ...]]:
    """The offers whose resources all have a price, and those that do not (with the names missing).

    A Chaos Orb is worth 1 Chaos whether or not the file lists it, and a Divine Orb the file's `chaos_per_divine` when
    it lists no price for it (a Divine Orb is the unit of that rate, ticket #71). A resource is read by `planned_price` under the
    profile's `price_source`: a thin trade market is priced by OR-8 and its mark goes in `PricedOffer.marks`, beside the part.

    An action that consumes nothing (an unveil, a pick: `unveil.is_free_and_in_place`), or only resources priced at 0 (a use of the
    Locus of Corruption at its standing default, ADR-0038, which a price file that lacks it prices too: `standing_defaults`), costs `FREE_ACTION_SHARE` of the cheapest
    offer that costs something, because the solver needs a positive cost on every action (ADR-0026, ticket #145). The share is a
    compromise: a use must stay negligible next to the value of a route (a route of a million Chaos is moved by a Chaos at most),
    yet a cycle of free steps and paid steps (veil, unveil, pick, veil again) lies in one component of the solver, whose certified
    error is about `epsilon * value / g` for the smallest constant term `g` of the component, here the free step's cost. With a
    share of 1e-6 a route of a few thousand Chaos is certified to about 1e-9 (`tests/test_cli_free_actions.py`).
    """
    priced: list[PricedOffer] = []
    dropped: list[DroppedOffer] = []
    for offer in offers:
        parts = []
        marks = []
        missing = []
        for name, count in offer.resources.items():
            if name == CHAOS_ORB:
                parts.append((name, count, float(count), "fixed"))
            elif (planned := planned_price(prices, name, price_source)) is not None:
                parts.append((name, count, count * planned.chaos, planned.source))
                if planned.mark is not None:
                    marks.append((name, planned.mark))
            elif name == DIVINE_ORB:
                parts.append((name, count, count * prices.chaos_per_divine, "rate"))
            elif (standing := standing_defaults().get(name)) is not None:  # a use of the Locus: 0 Chaos unless the file or an override names it (ADR-0038)
                parts.append((name, count, count * standing.chaos, standing.source))
            else:
                missing.append(name)
        if missing:
            dropped.append(DroppedOffer(offer.label, tuple(sorted(missing)), offer.kind))
        else:
            priced.append(PricedOffer(offer, sum(part[2] for part in parts), tuple(parts), tuple(marks)))
    if any(_costs_nothing(entry) for entry in priced):
        paid = [entry.cost for entry in priced if entry.cost > 0]
        free_cost = FREE_ACTION_SHARE * min(paid) if paid else FREE_ACTION_SHARE
        priced = [replace(entry, cost=free_cost) if _costs_nothing(entry) else entry for entry in priced]
    return tuple(priced), tuple(dropped)


def _costs_nothing(entry: PricedOffer) -> bool:
    """Whether a use consumes nothing, or only resources priced at 0 (a use of the Locus at its default, ADR-0038): `price_offers` charges it the free share."""
    return not entry.offer.resources or (bool(entry.parts) and all(part[2] == 0 for part in entry.parts))


def listing_draw(data: GameData, listing: Item, rarity: Rarity, priced: Iterable[PricedOffer]) -> PricedOffer:
    """The draw that opens the bought listing `listing` (ADR-0064), priced as every action that consumes nothing is: the listing's price is the start price."""
    action = open_listing(rarity)
    paid = [entry.cost for entry in priced if entry.offer.resources and entry.cost > 0]  # the actions that cost something, not the free ones
    free_cost = DRAW_COST_SHARE * min(paid) if paid else FREE_ACTION_SHARE
    return PricedOffer(offer_of(action, action.label(data), data, listing, shares=False), free_cost, ())


def free_action_cost(priced: Iterable[PricedOffer]) -> float | None:
    """What `price_offers` charged the actions that consume nothing, or `None` when the offers hold none (ticket #349)."""
    costs = [entry.cost for entry in priced if _costs_nothing(entry)]
    return max(costs) if costs else None


# --- what the model offers for one target ------------------------------------------------------------


@dataclass(frozen=True)
class OfferSet:
    """The offers for one target and the limits of that choice: every kind or action left out on purpose, each with what the plan still guarantees."""

    offers: tuple[Offer, ...]
    limits: tuple[Limit, ...]


@dataclass(frozen=True)
class BuyStartItem(Action):
    """Buy the start item again: the item comes back as the target's start item, whatever it was.

    It is the restart of ADR-0011's buy action. It meets the contract only as far as the simulator and
    the planner need (`outcomes(data, item).sample(rng)`, the label, and that it reads nothing of the
    item, which it replaces); the planner gives it the start state and prices it with the start item.
    """

    item: Item

    def label(self, data: GameData | None = None) -> str:
        return RESTART

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {}

    def reads(self, data: GameData) -> Reads:
        return Reads.nothing()

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        # ADR-0041: it replaces the item, so it is no craft: nothing is cut or spent, and the strands of the item that comes back are the
        # start item's own (what a stranded buy costs is ADR-0043's). It is declared so that the guard does not refuse a restart from a stranded item.
        return StrandUse.untouched()

    def outcomes(self, data: GameData, item: Item) -> "BuyStartItem":  # type: ignore[override]
        return self

    def sample(self, rng: random.Random) -> Item:
        return self.item


def _allowing(data: GameData, start_item: Item, action: Action) -> Action:
    """`action` as a target that only allows a corrupted item uses it: `Action.for_allowed_corruption` for a corrupting one, the action itself otherwise."""
    return action.for_allowed_corruption(data) if action.adds(data, start_item).corrupts else action


def offers_for(
    data: GameData, goal: Goal, base_id: str, start_item: Item, kinds_named: Collection[str] | None = None
) -> OfferSet:
    """The actions the model offers for a target on `base_id`: the planner kinds of the catalog, then the filters below.

    Every action of the `planner` kinds of `actions.catalog` that can apply to the start item is offered
    (a Chaos Orb, the Harvest reforge of Lightning, every essence the item class takes, the bench), under
    its `label`; two with one label are told apart by their `variant`. A new method registered in the
    catalog is offered with no edit here. The filters, each over what an action declares (`Action.adds`,
    `Action.reads`):

    * An action that only adds named crafted mods (a bench craft) is offered ONLY WHEN A MOD IT ADDS
      COUNTS TOWARD ONE OF THE GOAL'S REQUIREMENTS (a leaf names it and does not refuse a crafted mod,
      `not_crafted`). While EVERY OTHER OFFERED ACTION ERASES THE CRAFTED MODS (declares
      `Adds.keeps_crafted` False; the default True keeps every craft in play, so an action that keeps
      them needs no edit here) this is exact: every other action (Chaos Orb, Harvest reforge, an
      essence, Remove Crafted Mods) removes the crafted mods, and without the multimod an item holds one crafted
      mod, so a craft that gives the goal nothing only takes a slot and costs currency; it can never
      lower the mean. Leaving it out keeps the state space small: each craft that
      clashes with a family makes that family its own kind, so all 141 ring crafts would grow R05 from
      76 to 13,172 states (ticket #60, PR #79). When an offered action keeps the crafted mod (Augmentation
      and Regal Orb, #66) a craft that counts for nothing could still pay off: it takes a slot or clears a
      family out of the pool before the next orb. It is left out all the same, because every belt craft in
      the model is 100 offers and the states grow past what a plan can hold; the plan is then the cheapest
      among the offered crafts, not a proof against the rest (the report says so). REVISIT with the
      Exalted Orb and Annulment Orb (#67) and the metamods and the multimod (#68). The crafts left out are reported.
    * An UNVEIL BLOCK is the exception (ADR-0026, ticket #146): when the unveil kind is offered, a craft whose mod's family is in the
      unveiled pool of the base (`unveil_pool_families`, either side, weight above 0 on the base) is offered even though it counts toward
      no requirement, because explicit mods, crafts included, take their families out of the next offer. Crafts of one family give one
      kernel, so the solver keeps the cheapest of them at each state (ADR-0031, equal kernels).
    * With `kinds_named` (the target's `actions:` key) only the kinds of those names are listed at all and the filters
      below see only them. That is the target's choice, not a proof: the plan is the cheapest among the named kinds,
      and the kinds not named are a `Limit` of the answer (`_limits`). A name may also be the label of ONE action (`Essence of
      Insanity`, `Bench craft Cannot roll Attack Modifiers`): that action is offered whatever the filters below say
      (a metamod craft counts toward no requirement and would be left out), and only the actions named that way are
      listed of a kind that is not named as a whole. An `opt_in` kind (Exalted Orb, Annulment, Fracturing
      Orb) is offered only when named, as a kind or by its label (ticket #70).
    * An action that adds named mods only for a target that wants them (`Adds.wanted_only`, an aspect beast, #147) is
      offered only when a mod it adds is named by a requirement of the goal, whatever the other actions do to crafted mods.
      It is left out and reported like a craft that counts for nothing.
    * An action that needs a crafted mod to be used on (`Reads.needs_crafted`, Remove Crafted Mods) is
      offered only when the start item holds one or another offered action adds one. An action that needs a veiled placeholder
      (`Reads.needs_veiled`, an Unveil, a Pick) likewise, when the start item holds one or another offered action may put one there
      (`Adds.veils`, the veiled orbs); otherwise it could never be used (#848). Both are said in the answer (`unusable_limits`).
    * THE KIND-LEVEL RELEVANCE TEST (#848, decided in #637), before the walk and before the bound is built: an action that the model refuses
      on every item of the target's base (`UnmodelledBase`, asked by `base_refusal`: the Harvest crafts and the veiled orbs on a jewel) is
      left out of the offers, and the answer says it as a model gap of the listing (#511), kind by kind when the whole kind goes. Both this
      cut and the one above are exact: such an action could never be used at any state, so no mean changes, while its reads would split the
      states the walk keeps (J01 with the resistance swaps: 236 states for the 8 of the Chaos Orb alone) and every state would ask it.
    * An action that only changes rolled values (`Adds.needs_roll_limit`, a Divine Orb, #71) is offered only when the goal has a
      roll limit (a leaf with a `min_roll` that asks for some value) on a mod that can occur on the item: the start item
      holds it, a draw of its pool can give it, or another candidate adds it by name. Without such a limit no value
      matters to the goal, so the orb would only cost currency. It is left out; the report names it only when the goal has a
      roll limit and every one is on a mod that cannot occur (a target without a roll limit needs no word about it).
    * An action that corrupts the item (`Adds.corrupts`, a Vaal Orb, the Locus) is offered only when the goal asks for a corrupted
      implicit or allows a corrupted item (`Goal.takes_corrupted`): an item never arrives corrupted unasked (ADR-0036). For any
      other target it is absent from the offers and the answer carries a `Limit` that names it. Which states offer it, for a target that
      asks, is `solver_actions`' business (`_prune.py`). One that also declares `Adds.asked_only` (a fossil set with the Bloodstained
      Fossil: its reroll exists without the corruption) is offered only when the goal asks for a corrupted implicit, not when it
      merely allows a corrupted item (ADR-0038). For a target that only allows a corrupted item (and asks for no corrupted implicit) a
      corrupting action is offered as `Action.for_allowed_corruption` gives it: the Vaal Orb whose brick is a full fill (ticket #260).
    """
    goal = goal.resolved(data, start_item.base_id, start_item.item_level)  # a leaf built by hand with a `min_tier` reads it from the data
    counting = {mod_id for leaf in goal.leaves for mod_id in leaf.mod_ids if _counts_as_crafted(data, leaf, mod_id)}
    kind_names, label_names = _split_names(data, start_item, kinds_named)
    named = {mod_id for leaf in goal.leaves for mod_id in leaf.mod_ids}  # a `wanted_only` mod is no crafted one, so `not_crafted` does not hide it
    candidates = []
    left_out_unwanted: list[str] = []
    listing_gaps: list[ListingGap] = []
    kind_of = _listed(data, start_item, kind_names, label_names, listing_gaps)
    if kind_names is not None and RECOMBINATOR_KIND in kind_names:
        kind_of = _with_feeder_donors(data, goal, start_item, kind_of)
        # a donor is made from a normal item of the base (the recombinator's `inputs`): the actions that apply to one are offered too
        bare = Item.build(data, base_id=start_item.base_id, item_level=start_item.item_level, rarity=Rarity.NORMAL, influences=start_item.influences)
        for action, kind in _listed(data, bare, kind_names, label_names).items():  # its gaps are the start item's to say, once
            if kind != RECOMBINATOR_KIND:
                kind_of.setdefault(action, kind)
    if goal.allow_corrupted and not goal.asks_corrupted:  # a target that only allows corruption gets each corrupting action as it uses it (ADR-0037)
        kind_of = {_allowing(data, start_item, action): kind for action, kind in kind_of.items()}
    listed = list(kind_of)
    label_count = Counter(action.label(data) for action in listed)

    def told_apart(action: Action) -> str:
        """The label a limit names a left-out action by: the label alone, and for one that shares it with others the label and its variant (as the offers do)."""
        label = action.label(data)
        return label if label_count[label] == 1 or not action.variant else f"{label} [{action.variant}]"

    refused = base_refused(data, start_item, listed)  # the kind-level relevance test (#848): no item of this base can take these
    listing_gaps.extend(refusal_gaps(refused, kind_of, listed, told_apart))
    listed = [action for action in listed if action not in refused]

    roll_matters = _roll_limit_can_matter(data, goal, start_item, listed)
    left_out_rolls: list[str] = []
    left_out_corrupting: list[str] = []  # the target takes no corrupted item
    left_out_asked: list[str] = []  # the target allows a corrupted item but asks for no corrupted implicit, and the set is offered only to one that does (ADR-0038)
    for action in listed:
        adds = action.adds(data, start_item)
        if adds.corrupts and (not goal.takes_corrupted or (adds.asked_only and not goal.asks_corrupted)):
            (left_out_asked if goal.takes_corrupted else left_out_corrupting).append(told_apart(action))  # an item never arrives corrupted unasked
            continue
        if adds.wanted_only and not (adds.named or frozenset()) & named and action.label(data) not in label_names:
            left_out_unwanted.append(told_apart(action))
        elif adds.needs_roll_limit and not roll_matters:
            left_out_rolls.append(told_apart(action))
        else:
            candidates.append(action)
    # a craft that gives the goal nothing is useless while every other action erases the crafted mod
    erased_by_all = not any(
        action.adds(data, start_item).keeps_crafted for action in candidates if not _only_crafts(data, start_item, action)
    )
    blocks = _unveil_blocks(data, base_id, candidates, kind_of)
    chosen: list[Action] = []
    left_out_crafts: list[str] = []
    for action in candidates:
        if (
            _only_crafts(data, start_item, action)
            and not action.adds(data, start_item).named & counting
            and action.label(data) not in label_names
            and not _families_of(data, action.adds(data, start_item).named) & blocks
        ):
            left_out_crafts.append(told_apart(action))
            continue
        chosen.append(action)
    chosen, unusable = split_usable(data, start_item, chosen)

    groups: dict[str, list[Action]] = defaultdict(list)
    for action in chosen:
        groups[action.label(data)].append(action)
    offers = []
    for label, actions in groups.items():
        variants = [action.variant for action in actions]
        if len(set(variants)) != len(variants) or "" in variants:
            variants = [str(number) for number in range(1, len(actions) + 1)]
        for action, variant in zip(actions, variants):
            offers.append(offer_of(action, label if len(actions) == 1 else f"{label} [{variant}]", data, start_item, kind_of.get(action, "")))

    limits = _kind_limits(kinds_named, kind_names, goal, start_item, listing_gaps)
    unlisted = (
        tuple(kind_title(entry.name) for entry in kinds(planner_only=True) if entry.corrupting and entry.name not in kind_names)
        if kind_names is not None and not goal.takes_corrupted
        else ()
    )
    if left_out_corrupting or unlisted:
        limits += (
            Limit(
                _limits.CORRUPTING,
                "Not offered",
                "the target takes no corrupted item, so these would only corrupt it",
                "The plan is unaffected: nothing here could be used for this target.",
                tuple(dict.fromkeys((*unlisted, *left_out_corrupting))),
            ),
        )
    if left_out_asked:
        limits += (
            Limit(
                _limits.CORRUPT_ASKED,
                "Not offered",
                "each of these corrupts the item, and it is offered only to a target that asks for a corrupted implicit; this target allows a corrupted item but asks for none",
                labels=tuple(left_out_asked),
                **claim("the kinds offered"),
            ),
        )
    if left_out_crafts:
        why = (
            "its mod counts toward no requirement, so the craft only takes a slot and costs currency"
            if erased_by_all
            else "its mod counts toward no requirement; an offered action keeps crafted mods, so a craft could still "
            "pay off by clearing a family from the pool"
        )
        guarantee = (
            claim("all the offered methods", "Such a craft cannot lower the cost, because every other offered action erases crafted mods.")
            if erased_by_all
            else claim("the offered crafts only", "A craft left out could still pay off, and that is not checked.")
        )
        limits += (Limit(_limits.CRAFTS, "Not offered", why, labels=tuple(left_out_crafts), **guarantee),)
    if left_out_rolls and any(leaf.has_roll_limit for leaf in goal.leaves):  # a target without a roll limit needs no word about it
        limits += (
            Limit(
                _limits.ROLLS,
                "Not offered",
                "it only changes rolled values and the roll limit of the target is on a mod that cannot occur on the item, "
                "so it would only cost currency",
                "The plan is unaffected: no roll can matter for this target.",
                tuple(left_out_rolls),
            ),
        )
    if left_out_unwanted:
        limits += (
            Limit(
                _limits.FIXED_MOD,
                "Not offered",
                "it adds one fixed mod and the target wants none of those, so it only takes a slot and costs currency",
                "The plan is unaffected: such an action cannot help this target.",
                tuple(left_out_unwanted),
            ),
        )
    if unusable:
        limits += unusable_limits(data, ((told_apart(action), action) for action in unusable))
    return OfferSet(tuple(offers), limits)


def _probe_items(data: GameData, start_item: Item) -> tuple[Item, ...]:
    """The items `base_refusal` asks: the start item, then an empty item of its base and level at each rarity (one may be refused by the game
    where another reaches the base's verdict: a Harvest swap refuses a normal item before it looks at the base)."""
    found = [start_item]
    for rarity in (Rarity.RARE, Rarity.MAGIC, Rarity.NORMAL):
        try:
            found.append(Item.build(data, base_id=start_item.base_id, item_level=start_item.item_level, rarity=rarity))
        except ItemError:  # a base the item model refuses at that rarity: the start item is asked all the same
            continue
    return tuple(found)


def base_refused(data: GameData, start_item: Item, actions: Iterable[Action]) -> dict[Action, UnmodelledBase]:
    """The actions of `actions` that the model refuses on every item of the start item's base, each with its refusal (#848).

    `base_refusal` proves it from the base alone (`draw.refuse_unmodelled`), so leaving them out changes no mean: no state could use them.
    """
    items = _probe_items(data, start_item)
    found = {}
    for action in actions:
        refusal = base_refusal(data, action, items)
        if refusal is not None:
            found[action] = refusal
    return found


def refusal_gaps(
    refused: Mapping[Action, UnmodelledBase], kind_of: Mapping[Action, str], listed: Iterable[Action], told_apart: Callable[[Action], str]
) -> list[ListingGap]:
    """The base refusals as model gaps of the listing (#511): one per kind when every listed action of the kind is refused, else one per action."""
    listed_of = Counter(kind_of.get(action, "") for action in listed)
    refused_of = Counter(kind_of.get(action, "") for action in refused)
    gaps: list[ListingGap] = []
    for action, refusal in refused.items():
        kind = kind_of.get(action, "")
        whole = refused_of[kind] == listed_of[kind]
        gap = ListingGap(kind, "" if whole else told_apart(action), refusal.player, refusal.detail)
        if gap not in gaps:
            gaps.append(gap)
    return gaps


def _kind_limits(
    kinds_named: Collection[str] | None,
    kind_names: frozenset[str] | None,
    goal: Goal,
    start_item: Item,
    listing_gaps: Collection[ListingGap] = (),
) -> tuple[Limit, ...]:
    """The kinds of the catalog that no plan for this target offers, each group with its reason: not named, opt-in, not built (K1, K2, K4),
    and what the listed kinds left out because the model has no rule for the start item (`listing_gaps`, #511).

    A kind that only corrupts is the corrupting limit's when the target takes no corrupted item, and a kind that needs Memory
    Strands, while the start item has none, is the strands limit's (`make_plan`): neither is named here.
    """
    strands = _strand_kinds_absent(start_item)
    found: tuple[Limit, ...] = ()
    if kinds_named is not None:
        not_named = tuple(
            kind_title(entry.name)
            for entry in kinds(planner_only=True)
            if entry.name not in (kind_names or ()) and not (entry.corrupting and not goal.takes_corrupted) and entry.name not in strands
        )
        if not_named:
            found += (
                Limit(
                    _limits.NOT_NAMED,
                    "Not offered",
                    "kinds this target does not name",
                    labels=not_named,
                    **claim("the kinds offered"),
                ),
            )
    else:
        opt_in = tuple(kind_title(entry.name) for entry in kinds(planner_only=True) if entry.opt_in and entry.name not in strands)
        if opt_in:
            found += (
                Limit(
                    _limits.OPT_IN,
                    "Not offered",
                    "kinds that are offered only when a target names them",
                    labels=opt_in,
                    **claim("the kinds offered", "A kind left out could be cheaper."),
                ),
            )
    found += listing_gap_limits(listing_gaps, goal)
    not_built = tuple(kind_title(entry.name) for entry in kinds() if not entry.planner)
    if not_built:
        found += (
            Limit(
                _limits.NOT_BUILT,
                "Not offered",
                "methods the planner cannot use yet",
                labels=not_built,
                **claim("the methods the planner can use"),
            ),
        )
    return found


def listing_gap_limits(gaps: Collection[ListingGap], goal: Goal) -> tuple[Limit, ...]:
    """The limit of the actions the listing of their kind left out because the model has no rule for the start item (#511, OR-13).

    Each label is the kind, or the kind and what it left out ("Fossil sets: Hollow Fossil with Glyphic Fossil"); the causes are named once
    each. A gap of a kind that only corrupts is left out when the target takes no corrupted item: the kind would not be offered anyway (the
    corrupting limit's). A game refusal while listing writes no gap, so it is not here.
    """
    corrupting = {entry.name for entry in kinds() if entry.corrupting}
    shown = [gap for gap in gaps if goal.takes_corrupted or gap.kind not in corrupting]
    if not shown:
        return ()
    labels = tuple(dict.fromkeys(kind_title(gap.kind) + (f": {gap.subject}" if gap.subject else "") for gap in shown))
    detail_of: dict[str, str] = {}
    for gap in shown:
        detail_of.setdefault(gap.cause, gap.detail or gap.cause)
    causes = tuple(detail_of)
    rest = (f"{len(causes) - _limits.SHOWN_CAUSES} more causes",) if len(causes) > _limits.SHOWN_CAUSES else ()  # as the model gaps of the walk
    return (
        Limit(
            _limits.LISTING_GAP,
            "Not offered",
            "the model has no rule for them on this item: {names}",
            labels=labels,
            names=causes[: _limits.SHOWN_CAUSES] + rest,
            detail=tuple(detail_of[cause] for cause in causes[: _limits.SHOWN_CAUSES]) + rest,  # one for one with `names`, the count of the rest last
            **claim("the actions the model can list for this item", "An action the model has no rule for could make it cheaper."),
        ),
    )


def crafted_mods_limit(labels: tuple[str, ...]) -> Limit:
    """The limit of an action that needs a crafted mod to act on, dropped because no crafted mod can exist in the plan."""
    return Limit(
        _limits.CRAFTED_MODS,
        "Not offered",
        "no crafted mod can exist in this plan, so there is nothing to remove",
        "The plan is unaffected: the action would have nothing to act on.",
        labels,
    )


def veiled_mod_limit(labels: tuple[str, ...]) -> Limit:
    """The limit of an action that needs a veiled mod on the item, dropped because neither the start item nor any offered action gives one (#848)."""
    return Limit(
        _limits.NO_VEIL,
        "Not offered",
        "each of these needs a veiled mod on the item, and neither the start item nor any offered action puts one there",
        "The plan is unaffected: these could never be used for this target.",
        labels,
    )


def unusable_limits(data: GameData, removed: Iterable[tuple[str, Action]]) -> tuple[Limit, ...]:
    """The limits of the actions `split_usable` removed, by label: those that need a crafted mod, and those that need a veiled one."""
    crafted, veiled = [], []
    for label, action in removed:
        (veiled if action.reads(data).needs_veiled else crafted).append(label)
    return (
        *((crafted_mods_limit(tuple(crafted)),) if crafted else ()),
        *((veiled_mod_limit(tuple(veiled)),) if veiled else ()),
    )


def _strand_kinds_absent(start_item: Item) -> frozenset[str]:
    """The kinds that exist only in a plan that considers Memory Strands, when `start_item` has none (as `catalog` lists them)."""
    if start_item.memory_strands >= 1:
        return frozenset()
    return frozenset(entry.name for entry in kinds() if entry.needs_strands)


def _split_names(data: GameData, start_item: Item, names: Collection[str] | None) -> tuple[frozenset[str] | None, frozenset[str]]:
    """The names of a target's `actions:` as (kinds, labels): a name is a kind of the catalog, else the label of one action.

    No names (`None`) is every kind offered by default and no label. A name that is neither is an error, as is a
    kind the planner cannot use yet.
    """
    if names is None:
        return None, frozenset()
    names = [name for name in names if name != LOCK_KIND]  # Hinekora's Lock is no action of the catalog: the plan offers it as a Peek (`_foresight`)
    usable = {entry.name for entry in kinds(planner_only=True)}
    exist = {entry.name for entry in kinds()}
    kind_names = {name for name in names if name in exist}
    absent = _strand_kinds_absent(start_item)  # a kind that needs Memory Strands is no kind of this item's catalog until the planner passes `strands` (#277)
    unready = sorted((kind_names - usable) | (kind_names & absent))
    labels = {action.label(data) for action in catalog(data, start_item, planner_only=True, names=usable)}
    unknown = sorted(name for name in names if name not in exist and name not in labels)
    problems = []
    if unknown:
        problems.append(f"unknown action kind(s) or action label(s) {', '.join(unknown)}")
    if unready:
        problems.append(f"action kind(s) {', '.join(unready)} cannot be used by the planner yet")
    if problems:
        raise ValueError("; ".join(problems) + f"; the kinds the planner can use are {', '.join(sorted((usable - absent) | {LOCK_KIND}))}")
    return frozenset(kind_names), frozenset(name for name in names if name not in exist)


def _listed(
    data: GameData, start_item: Item, kind_names: frozenset[str] | None, label_names: frozenset[str], gaps: list[ListingGap] | None = None
) -> dict[Action, str]:
    """The planner actions of the kinds named, plus those named by label (any planner kind, default or not), each with its kind.

    With `gaps`, the model gaps the kinds named meet while they list are added to it (`catalog_kinds`); a kind searched only for a label
    adds none, as it is not offered as a kind.
    """
    found = catalog_kinds(data, start_item, planner_only=True, names=kind_names, gaps=gaps)
    if label_names:
        usable = {entry.name for entry in kinds(planner_only=True)}
        extra = {a: k for a, k in catalog_kinds(data, start_item, planner_only=True, names=usable).items() if a.label(data) in label_names}
        found.update({a: k for a, k in extra.items() if a not in found})
    return found


def _roll_limit_can_matter(data: GameData, goal: Goal, start_item: Item, listed: Iterable[Action]) -> bool:
    """Whether a roll limit of the goal is on a mod that can occur: held by the start item, drawable on it, or added by name."""
    limited = {mod_id for leaf in goal.leaves if leaf.has_roll_limit for mod_id in leaf.mod_ids}
    if not limited:
        return False
    if limited & {entry.mod_id for entry in start_item.mods}:
        return True
    if any(limited & (action.adds(data, start_item).named or frozenset()) for action in listed):
        return True
    try:
        return bool(limited & drawable_mod_ids(data, start_item))
    except (NotApplicableError, OutOfScopeError):  # either: a pool that cannot be built is no proof the mod is out of reach, so the orb stays (nothing is left out)
        return True


def _counts_as_crafted(data: GameData, leaf, mod_id: str) -> bool:
    """Whether the mod `mod_id`, added as a crafted mod at its highest roll, passes the leaf by the one judgement (`status_of`).

    A bench craft has no natural tier (OR-1, OR-2), so a leaf with a tier limit counts it only when `mod:` names it; a leaf with
    `not_crafted` never counts it.
    """
    mod = data.mods.get(mod_id)
    if mod is None:
        return False
    values = tuple(max(stat.min, stat.max) for stat in mod.stats)
    return status_of(leaf, mod_id, values, True) is Status.PASSING


def _unveil_blocks(data: GameData, base_id: str, candidates: Iterable[Action], kind_of: Mapping[Action, str]) -> frozenset[str]:
    """The families a bench craft blocks an unveil offer by, when an unveil is offered: those of the base's unveiled pool, else none (ADR-0026)."""
    if not any(kind_of.get(action) == UNVEIL_KIND for action in candidates):
        return frozenset()
    return unveil_pool_families(data, base_id)


def _families_of(data: GameData, mod_ids: Iterable[str] | None) -> frozenset[str]:
    """The families of the mods `mod_ids` (none for `None`)."""
    return frozenset(family for mod_id in mod_ids or () if mod_id in data.mods for family in data.mods[mod_id].families)


def _only_crafts(data: GameData, item: Item, action: Action) -> bool:
    """Whether the action only adds mods it names, as crafted mods (a bench craft)."""
    adds = action.adds(data, item)
    return adds.crafted and not adds.draws and adds.named is not None


def split_usable(data: GameData, start_item: Item, actions: Iterable[Action]) -> tuple[list[Action], list[Action]]:
    """(`actions` without those that can never be used, those removed): an action that needs a crafted mod when neither the start item
    nor another of them gives one, and one that needs a veiled placeholder when the start item holds none and no other of them may put
    one there (`Adds.veils`, #848); an imprint of the start item that holds one counts, as a Restore brings it back. Both are exact: no state
    the plan reaches can hold what the action needs."""
    actions = list(actions)
    crafted = bool(start_item.crafted_mods) or any(action.adds(data, start_item).crafted for action in actions)
    veiled = any(holds_placeholder(data, held) for held in (start_item, *start_item.imprints))  # a Restore may bring an imprint's back
    veiled = veiled or any(action.adds(data, start_item).veils for action in actions)

    def never(action: Action) -> bool:
        reads = action.reads(data)
        return (reads.needs_crafted and not crafted) or (reads.needs_veiled and not veiled)

    return [action for action in actions if not never(action)], [action for action in actions if never(action)]


def usable_actions(data: GameData, start_item: Item, actions: Iterable[Action]) -> list[Action]:
    """`actions` without those that need a crafted mod when neither the start item nor another of them gives one."""
    return split_usable(data, start_item, actions)[0]
