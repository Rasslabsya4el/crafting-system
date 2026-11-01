"""The veiled orbs, the unveil and the pick (ticket #144, ADR-0026, ADR-0027).

Four actions, one file:

* `VeiledChaosOrb()`: a Chaos Orb reroll that guarantees one generic veiled placeholder (`VeiledPrefix` or `VeiledSuffix`),
  counted inside the drawn total of 4, 5 or 6 mods. The placeholder goes to the only side that has room once the kept mods
  (fractured, or on a locked side) are counted, otherwise to the prefix or the suffix with chance 1/2: **the veil ignores a
  lock with room**. It is refused when a veiled mod would be kept (on a locked side or fractured). The result is a `Mixture` of
  the two sides' pool draws, built on `Outcomes.reroll` with the placeholder as the forced mod (as an essence's).
* `VeiledExaltedOrb()`: removes one mod, uniformly among those not fractured and not on a locked side (crafted mods and
  metamods included; the Attack/Caster metamods protect nothing), then adds a placeholder by the same side rule. It is
  refused on an item that holds a veiled mod: the placeholder, a mod unveiled from the pool, or a bench craft that is the
  craftable version of one. The result is a `Finite`.
* `Unveil()`: draws the offer of the placeholder, the chance node of ADR-0026: up to three mods of the unveiled pool of the
  placeholder's side, by the weight of the base, without replacement, one mod per family, after removing the families of the
  mods on the item. The offer is drawn once and stays on the item (`Item.veil_offer`); there is no offer filter and no item
  level gate. It is free (`unveil.is_free_and_in_place`), so `resources` is empty: the solver's small positive cost is
  the business of the compressed model (ticket #145).
* `Pick(k)`, k = 1 to 3: the choice node. It replaces the placeholder with the k-th mod of the offer in mod id order, at
  its lowest values. There is no decline.

An item with a signature placeholder, or with two, is out of scope (grill B2, `OutOfScopeError`); a jewel has no veiled
pool, so the two orbs refuse it. The kinds are not planner kinds: the placeholder slot and the offer state belong to the
compressed model of ticket #145.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.data import GameData, Mod, conflicts
from crafting_system.items import (
    GENERIC_PLACEHOLDERS as GENERIC_PLACEHOLDER_IDS,
    ExplicitMod,
    Item,
    Rarity,
    Side,
    is_veiled_mod,
    spawn_weight,
    tier_table,
    veiled_placeholder,
)
from crafting_system.items.model import MAX_VEIL_OFFER, UNVEILED_DOMAIN, VEILED_DOMAIN
from crafting_system.rules import Rule, get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .draw import refuse_unmodelled
from .errors import NotApplicableError, OutOfScopeError
from .finite import Finite
from .metamods import kept_by_reroll, locked_sides, on_locked_side
from .mixture import Mixture
from .outcomes import Outcomes

CHAOS_REROLLS_WITH_ONE_VEILED_MOD = get_rule("veiled.chaos_reforge_with_one_veiled_mod")
EXALTED_REMOVES_THEN_ADDS_VEILED = get_rule("veiled.exalted_removes_then_adds_veiled")
GENERIC_POOL_ONLY = get_rule("veiled.orbs_generic_pool_only")
PLAIN_AFFIX_NOT_CRAFTED = get_rule("veiled.mod_is_a_plain_affix_not_crafted")
CHAOS_VEILED_COUNTS_IN_TOTAL = get_rule("veiled.chaos_veiled_counts_in_total")
CHAOS_PLACEMENT_SIDE = get_rule("veiled.chaos_placement_side")
CHAOS_REFUSED_WHEN_KEPT = get_rule("veiled.chaos_refused_when_a_veiled_mod_would_be_kept")
EXALTED_REFUSED_WITH_A_VEILED_MOD = get_rule("veiled.exalted_refused_with_a_veiled_mod")
EXALTED_REFUSED_AFTER_AN_UNVEIL = get_rule("veiled.exalted_refused_after_an_unveil")
EXALTED_REMOVAL = get_rule("veiled.exalted_removal_respects_side_locks_not_attack_caster")
EXALTED_PLACEMENT_SIDE = get_rule("veiled.exalted_placement_side")
PLACEHOLDER_RECORDS = get_rule("veiled.mod_placeholder_records")
REFUSED_ON_CORRUPTED = get_rule("veiled.refused_on_corrupted")
CHAOS_COST = get_rule("veiled.chaos_cost")
EXALTED_COST = get_rule("veiled.exalted_cost")

THREE_OPTIONS = get_rule("unveil.three_options_player_picks")
UNVEIL_IS_FREE = get_rule("unveil.is_free_and_in_place")
OFFER_POOL = get_rule("unveil.offer_pool_is_the_unveiled_domain_by_side")
OFFER_DRAW = get_rule("unveil.offer_draw_three_families_no_repeat")
LEGACY_MODS_WEIGHT_ZERO = get_rule("unveil.legacy_mods_have_weight_zero")
OFFER_DRAWN_ONCE = get_rule("unveil.offer_drawn_once_and_fixed")
NO_OFFER_FILTER = get_rule("unveil.no_offer_filter_no_level_gate")

OWN_CLAIMS = frozenset(value.id for value in tuple(vars().values()) if isinstance(value, Rule))  # every claim of this file: each action names its own

PLACEHOLDER_IDS: Mapping[Side, str] = {Side(side): mod_id for side, mod_id in GENERIC_PLACEHOLDER_IDS.items()}  # the generic ones
GENERIC_PLACEHOLDERS = frozenset(PLACEHOLDER_IDS.values())
ONE = Fraction(1)
NO_VEILED_POOL = "a jewel has no veiled pool (Craft of Exile's veiled groups are the jewellery, body armour, boots, helmets, gloves, one-hand, two-hand and off-hand classes)"

_CACHE_LIMIT = 32
_CACHE: dict[tuple, tuple[GameData, object]] = {}  # (id(data), name, ...) -> (data, value); the entry keeps `data` alive, so its id is not reused


def _cached(data: GameData, key: tuple, build):
    full = (id(data), *key)
    found = _CACHE.get(full)
    if found is not None and found[0] is data:
        return found[1]
    value = build()
    if len(_CACHE) >= _CACHE_LIMIT:
        _CACHE.clear()
    _CACHE[full] = (data, value)
    return value


def unveil_families(data: GameData) -> frozenset[str]:
    """The families of the placeholders and of every mod of the unveiled domain: what an action that tells the veiled mods apart reads."""

    def build() -> frozenset[str]:
        found = {family for mod in data.mods.values() if mod.domain in (VEILED_DOMAIN, UNVEILED_DOMAIN) for family in mod.families}
        return frozenset(found)

    return _cached(data, ("families",), build)


def is_veiled(data: GameData, entry: ExplicitMod) -> bool:
    """Whether the mod counts as a veiled mod for the orbs' refusals: a placeholder, a mod unveiled from the pool, or the craftable version of one."""
    return is_veiled_mod(data, data.mods[entry.mod_id])


def _placeholders(data: GameData, item: Item) -> list[ExplicitMod]:
    return [entry for entry in item.mods if data.mods[entry.mod_id].domain == VEILED_DOMAIN]


def _refuse_out_of_scope_veil(data: GameData, item: Item) -> None:
    """Raise `OutOfScopeError` for an item with a signature placeholder or with two (grill B2: out of v1)."""
    held = _placeholders(data, item)
    if len(held) > 1:
        raise OutOfScopeError("the item holds two veiled placeholders; a start item with a double veil is out of scope (grill B2)")
    if held and held[0].mod_id not in GENERIC_PLACEHOLDERS:
        raise OutOfScopeError(
            f"the item holds the signature placeholder {held[0].mod_id}; only the generic VeiledPrefix and VeiledSuffix are modelled (grill B2)"
        )


def _placeholder_mod(data: GameData, side: Side) -> Mod:
    mod = data.mods.get(PLACEHOLDER_IDS[side])
    if mod is None:
        raise OutOfScopeError(f"the game data has no generic veiled {side.value} placeholder {PLACEHOLDER_IDS[side]}")
    return mod


def _sides_with_room(item: Item, data: GameData) -> list[Side]:
    return [side for side in Side if item.free_slots(data, side) > 0]


@dataclass(frozen=True)
class VeiledChaosOrb(Action):
    """One Veiled Chaos Orb."""

    def label(self, data: GameData | None = None) -> str:
        return "Veiled Chaos Orb"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(CHAOS_COST.value)

    def reads(self, data: GameData) -> Reads:
        # Like a Chaos Orb it erases the junk. The placeholder and the mods unveiled from families that no ordinary pool
        # holds are kinds of their own in a state that keeps the junk (a lock), so the refusal can see a veiled mod it would keep.
        return Reads.nothing()

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        # It puts one of two placeholders on the item, so it names neither; it throws away an offer that was drawn.
        return Adds.erasing(named=None, offer=True)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        rules = (
            CHAOS_REROLLS_WITH_ONE_VEILED_MOD, GENERIC_POOL_ONLY, PLAIN_AFFIX_NOT_CRAFTED, CHAOS_VEILED_COUNTS_IN_TOTAL,
            CHAOS_PLACEMENT_SIDE, CHAOS_REFUSED_WHEN_KEPT, REFUSED_ON_CORRUPTED, PLACEHOLDER_RECORDS, CHAOS_COST,
        )
        return frozenset(rule.id for rule in rules) | (super().claims(data) - OWN_CLAIMS)  # and the claims of the draw it shares with the Chaos Orb

    def outcomes(self, data: GameData, item: Item) -> Mixture:
        """The outcomes of using the orb on `item`: one pool draw per side the veil can take.

        Raises `NotApplicableError` for an item that is not rare or is corrupted, for a veiled mod that the reroll would keep
        (on a locked side, or fractured) and for an item whose every slot is kept; `OutOfScopeError` for a jewel, a signature or
        double veil, and what `Outcomes.reroll` raises (an influenced item of a class with no influence class key). A drawn offer
        goes with the placeholder it belonged to.
        """
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError(f"a Veiled Chaos Orb works on a rare item only, and this item is {item.rarity}")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Veiled Chaos Orb")
        refuse_unmodelled(data, item, NO_VEILED_POOL)
        _refuse_out_of_scope_veil(data, item)
        for entry in kept_by_reroll(data, item):
            if is_veiled(data, entry):
                raise NotApplicableError(
                    f"the reroll would keep the veiled mod {entry.mod_id} (it is fractured or on a locked side), so a Veiled Chaos Orb cannot be used"
                )
        given = item.changed(data, veil_offer=()) if item.veil_offer else item
        kept = given.changed(data, rarity=Rarity.RARE, mods=kept_by_reroll(data, given))
        sides = _sides_with_room(kept, data)
        if not sides:
            raise NotApplicableError("the kept mods fill every prefix and suffix slot, so the veil has no room")
        share = Fraction(1, len(sides))
        return Mixture(
            data,
            tuple((share, Outcomes.reroll(data, given, tag=None, forced=_placeholder_mod(data, side))) for side in sides),
            False,
        )


@dataclass(frozen=True)
class VeiledExaltedOrb(Action):
    """One Veiled Exalted Orb."""

    def label(self, data: GameData | None = None) -> str:
        return "Veiled Exalted Orb"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(EXALTED_COST.value)

    def reads(self, data: GameData) -> Reads:
        # It keeps the junk, removes one of it by side and puts a placeholder on the item; it is refused when a veiled mod is
        # there, so the placeholder and the families of the unveiled pool are told apart. A mod unveiled from a family that
        # an ordinary mod shares (Movement Speed on boots) is not told apart from it by the kind of a slot: ticket #145.
        return Reads(junk=True, families=unveil_families(data))

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=None, draws=False)  # one of two placeholders, so none by name; a crafted mod may be the one removed, so it is not erased

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        rules = (
            EXALTED_REMOVES_THEN_ADDS_VEILED, GENERIC_POOL_ONLY, PLAIN_AFFIX_NOT_CRAFTED, EXALTED_REFUSED_WITH_A_VEILED_MOD,
            EXALTED_REFUSED_AFTER_AN_UNVEIL, EXALTED_REMOVAL, EXALTED_PLACEMENT_SIDE, PLACEHOLDER_RECORDS, REFUSED_ON_CORRUPTED,
            EXALTED_COST,
        )
        return frozenset(rule.id for rule in rules) | frozenset({"metamods.locks_protect_existing_mods"})  # the locks it respects

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The outcomes of using the orb on `item`: one result per mod it can remove and per side the veil can take.

        Raises `NotApplicableError` for an item that is not rare or is corrupted, for one that holds a veiled mod (the
        placeholder, a mod unveiled from the pool, or a bench craft that is the craftable version of one) and for one with
        no mod to remove; `OutOfScopeError` for a jewel and a signature or double veil.
        """
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError(f"a Veiled Exalted Orb works on a rare item only, and this item is {item.rarity}")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Veiled Exalted Orb")
        refuse_unmodelled(data, item, NO_VEILED_POOL)
        _refuse_out_of_scope_veil(data, item)
        for entry in item.mods:
            if is_veiled(data, entry):
                raise NotApplicableError(f"the item holds the veiled mod {entry.mod_id}, so a Veiled Exalted Orb cannot be used")
        locked = locked_sides(data, item)
        removable = [entry for entry in item.mods if not entry.fractured and not on_locked_side(data, entry, locked)]
        if not removable:
            raise NotApplicableError(
                "a Veiled Exalted Orb cannot be used here: every mod is fractured or on a side that a lock protects"
            )
        results = []
        for entry in removable:
            rest = item.remove_mod(data, entry.mod_id)
            sides = _sides_with_room(rest, data)  # the removal frees a slot, so there is one
            share = Fraction(1, len(removable) * len(sides))
            for side in sides:
                results.append((share, rest.add_mod(data, veiled_placeholder(data, PLACEHOLDER_IDS[side]))))
        return Finite(data, item, tuple(results))


def offer_pool(data: GameData, item: Item, placeholder: Mod) -> tuple[tuple[Mod, int], ...]:
    """The mods the unveil of `placeholder` can offer on `item`, with their weights on the base, in data order.

    The mods of the unveiled domain on the side of the placeholder with a spawn weight above 0 on the tags of the base,
    without a mod whose family is on the item (bench crafts included). The item level and the metamods do not filter it.
    """
    tags = data.base_items[item.base_id].tags
    taken = item.families(data)

    def build() -> tuple[tuple[Mod, int], ...]:
        return tuple(
            (mod, weight)
            for mod in data.mods.values()
            if mod.domain == UNVEILED_DOMAIN
            and mod.generation_type == placeholder.generation_type
            and (weight := spawn_weight(mod, tags)) > 0
        )

    side_pool = _cached(data, ("pool", item.base_id, placeholder.generation_type), build)
    return tuple((mod, weight) for mod, weight in side_pool if taken.isdisjoint(mod.families))


def offer_distribution(pool: tuple[tuple[Mod, int], ...]) -> dict[frozenset[str], Fraction]:
    """The exact chance of every offer drawn from `pool`: up to three draws by weight, a picked mod's family leaving the pool.

    An offer is the set of the mod ids shown (the order of the draws does not matter to the player). The sequences are
    enumerated in full, so each chance is a product of the exact fractions `weight / weight left`.

    Every family of a picked mod counts, as `Item.blocks` and the check of an offer on `Item` do: two options that share a
    family (a hybrid mod's second family) are never offered together. The research counted the first family only, which
    gives the wand's Minion attack and cast speed 0.194; with every family it is 0.1996 (`test_actions_veiled_real.py`).
    """
    shown: dict[frozenset[str], Fraction] = {}

    def draw(left: tuple[tuple[Mod, int], ...], chosen: tuple[str, ...], chance: Fraction) -> None:
        if len(chosen) == MAX_VEIL_OFFER or not left:
            key = frozenset(chosen)
            shown[key] = shown.get(key, Fraction(0)) + chance
            return
        total = sum(weight for _, weight in left)
        for mod, weight in left:
            rest = tuple((other, w) for other, w in left if other.id != mod.id and not conflicts(mod, other))
            draw(rest, (*chosen, mod.id), chance * Fraction(weight, total))

    draw(pool, (), ONE)
    return shown


@dataclass(frozen=True)
class Unveil(Action):
    """Unveil the veiled placeholder: draw its offer (the chance node of ADR-0026). Free."""

    def label(self, data: GameData | None = None) -> str:
        return "Unveil"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {}  # unveiling costs nothing (unveil.is_free_and_in_place)

    def reads(self, data: GameData) -> Reads:
        # The offer depends on the families on the item that the unveiled pool holds, and on the placeholder (a mod of the item).
        return Reads(junk=True, families=unveil_families(data), offer=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset(), draws=False, offer=True)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        rules = (THREE_OPTIONS, UNVEIL_IS_FREE, OFFER_POOL, OFFER_DRAW, LEGACY_MODS_WEIGHT_ZERO, OFFER_DRAWN_ONCE, NO_OFFER_FILTER, GENERIC_POOL_ONLY)
        return frozenset(rule.id for rule in rules)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The outcomes of unveiling `item`: one result per possible offer, with the chance the draw gives it.

        Raises `NotApplicableError` when the item holds no placeholder, when its offer is drawn already, and when no mod
        of the pool is left to offer; `OutOfScopeError` for a signature or double veil.
        """
        _refuse_out_of_scope_veil(data, item)
        held = _placeholders(data, item)
        if not held:
            raise NotApplicableError("the item holds no veiled placeholder to unveil")
        if item.veil_offer:
            raise NotApplicableError("the offer of this placeholder is drawn already and stays fixed")
        pool = offer_pool(data, item, data.mods[held[0].mod_id])
        if not pool:
            raise NotApplicableError("no mod of the unveiled pool can be offered: none spawns on this base or every family is on the item")
        shown = offer_distribution(pool)
        return Finite(
            data,
            item,
            tuple((chance, item.changed(data, veil_offer=tuple(sorted(offer)))) for offer, chance in sorted(shown.items(), key=lambda pair: sorted(pair[0]))),
        )


@dataclass(frozen=True)
class Pick(Action):
    """Pick the `index`-th mod (1 to 3, in mod id order) of the offer in place of the placeholder (the choice node of ADR-0026). Free."""

    index: int = 1

    def __post_init__(self) -> None:
        if type(self.index) is not int or not 1 <= self.index <= MAX_VEIL_OFFER:
            raise ValueError(f"a pick is of the 1st to the {MAX_VEIL_OFFER}rd mod of the offer, not {self.index!r}")

    def label(self, data: GameData | None = None) -> str:
        return f"Pick {self.index}"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {}  # unveiling costs nothing (unveil.is_free_and_in_place)

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset(), offer=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=None, draws=False, offer=True)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset(rule.id for rule in (THREE_OPTIONS, UNVEIL_IS_FREE, OFFER_DRAWN_ONCE))

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The outcomes of picking: the placeholder becomes the chosen mod, at its lowest values (fractured if the placeholder was), and the offer is used up.

        Raises `NotApplicableError` when no offer is drawn, when it holds fewer than `index` mods, and when the chosen mod
        shares a family with a mod of the item; `OutOfScopeError` for a signature or double veil.
        """
        _refuse_out_of_scope_veil(data, item)
        if not item.veil_offer:
            raise NotApplicableError("no offer is drawn, so there is nothing to pick")
        if self.index > len(item.veil_offer):
            raise NotApplicableError(f"the offer holds {len(item.veil_offer)} mod(s), so there is no mod number {self.index} to pick")
        (held,) = _placeholders(data, item)  # an offer needs exactly one placeholder (the item checks it)
        chosen = data.mods[item.veil_offer[self.index - 1]]
        rest = tuple(entry for entry in item.mods if entry.mod_id != held.mod_id)
        if any(conflicts(chosen, data.mods[entry.mod_id]) for entry in rest):
            raise NotApplicableError(f"the chosen mod {chosen.id} shares a family with a mod of the item")
        low = tuple(min(stat.min, stat.max) for stat in chosen.stats)
        picked = ExplicitMod(chosen.id, tier_table(data, item.base_id).get(chosen.id, 1), low, fractured=held.fractured)  # a fractured veil stays fractured
        return Finite(data, item, ((ONE, item.changed(data, mods=(*rest, picked))),))  # no placeholder left, so the offer goes


@kind("veiled-chaos-orb", order=76, planner=False, why_not="the placeholder slot and the offer state of the compressed model are ticket #145")
def _veiled_chaos_orb(data: GameData, item: Item):
    if item.rarity is Rarity.RARE:
        yield VeiledChaosOrb()


@kind("veiled-exalted-orb", order=77, planner=False, why_not="the placeholder slot and the offer state of the compressed model are ticket #145")
def _veiled_exalted_orb(data: GameData, item: Item):
    if item.rarity is Rarity.RARE:
        yield VeiledExaltedOrb()


@kind("unveil", order=78, planner=False, why_not="the placeholder slot and the offer state of the compressed model are ticket #145")
def _unveil(data: GameData, item: Item):
    if item.rarity is Rarity.RARE:  # a start item need not hold a placeholder: a veiled orb puts one on it
        yield Unveil()


@kind("pick", order=79, planner=False, why_not="the placeholder slot and the offer state of the compressed model are ticket #145")
def _pick(data: GameData, item: Item):
    if item.rarity is Rarity.RARE:
        for index in range(1, MAX_VEIL_OFFER + 1):
            yield Pick(index)
