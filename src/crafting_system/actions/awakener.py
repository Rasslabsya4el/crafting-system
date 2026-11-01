"""The Awakener's Orb as an exact two-input action (ADR-0032, ticket #213).

The item in hand is the **receiver**; the **donor** is an input (a `Need`, ADR-0022), a rare item of one other influence that
holds the influenced mod the route wants carried over and is destroyed. The result is a rare receiver with both influences. Of
the receiver's influenced mods one is kept, and the donor's mod; if the receiver holds several, the pair is drawn **uniformly
among the valid pairs** (receiver mod, donor mod), valid meaning two different mods (`awakener.pair_choice_uniform`; the pairs
of Craft of Exile are the same, because the two influences differ). A kept mod keeps its tier and its value is rolled afresh
(`Outcomes.rerolled`). Every other mod goes, the crafted ones and the metamods too (`awakener.ignores_metamods`), and the rest
is rerolled as a Chaos Orb rerolls a rare: a total of 4, 5 or 6 mods (8:3:1) **minus the kept mods that remain**, which count
inside the total (`awakener.kept_mods_count_in_total`, approximate), drawn by the shared draw from the pool of the item with
both influences (`Outcomes`, `outcomes.py`).

Two kept mods of one mod group (a shared family of the data, `awakener.same_mod_group_keeps_one`) are a **group conflict**, and
the sources disagree on which survives. That is the rule axis `awakener.group_conflict` of two readings: `receiver` (the plan,
Craft of Exile keeps the receiver's mod; `awakener.survivor_coe`) and `donor` (the other end of the interval,
`awakener.survivor_wiki`); the other influence is added in both, and one mod remains in the total. A pair without a conflict is
the same under both readings.

Refusals (`NotApplicableError`): the item is corrupted, normal, holds no influence or more than one, has the donor's influence,
is below item level 68, holds no influenced mod, or no pair of different mods can be made. `OutOfScopeError`: a fractured mod
(in 3.29 a fractured item cannot carry an influence, the planner refuses the case, ADR-0032), an item class with no influence
class key, a jewel, or a donor mod that is no influence mod of the donor's influence on this base. The game's refusal of a
mirrored or synthesised item is not modelled: an `Item` has neither flag.

Limit: a kept mod's value is rerolled, but the compressed state keeps the contribution of its old roll, so under a goal with a roll
limit the kernel raises `OutOfScopeError` (`abstraction._kernel._split`). The donor's own mod is a new mod to the kernel, so a
roll limit on it is refused there as for any forced mod.

The catalog lists the kind only for a receiver with one influence; it is not a planner kind until the solver prices donors
(#211, #212) and the interval driver exists (#220).

Memory Strands (ADR-0041, ticket #289, B5-11f). The orb cuts and spends: the draw of the rerolled mods takes `self.cut_of(data, item)` and
the count after the craft is `max(0, s - x)` for `x` uniform on 0 to 100, the wiki's "Awakener's Orb - 0-100"
(`memory_strands.spend_ranges_special_orbs`; the cut follows the emulator's spend table, which has an Awakener's Orb row,
`memory_strands.cut_follows_spend_table`). The two kept mods keep their tier, so they are not cut; the donor is destroyed, so its count
is gone and is not modelled. Both readings of the group conflict cut and spend alike. The strand claims are `strand_claims`, not `claims`.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction

from crafting_system.data import GameData, conflicts
from crafting_system.items import ExplicitMod, Influence, Item, Rarity, Side
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Axis, Need, Reading, Reads
from .draw import refuse_unmodelled
from .errors import NotApplicableError, OutOfScopeError
from .mixture import Mixture
from .outcomes import Outcomes
from .pool import build_pool, influence_spawn_test, tiers_of
from .strand_use import CUT_FOLLOWS_SPEND_TABLE, SPEND_SPECIAL_ORBS, SpendLaw, StrandUse

TWO_ITEMS_SAME_CLASS = get_rule("awakener.two_items_same_class")
REROLLED_AS_RARE_WITH_BOTH_INFLUENCES = get_rule("awakener.receiver_reforged_rare_both_influences")
ONE_INFLUENCE_EACH = get_rule("awakener.one_influence_each_and_different")
REFUSED_ON_CORRUPTED = get_rule("awakener.refused_on_corrupted")
KEEPS_BASE_LEVEL_QUALITY_ENCHANTMENT = get_rule("awakener.keeps_base_level_sockets_quality_enchants")
ONE_MOD_PER_INPUT = get_rule("awakener.one_influenced_mod_per_input_kept")
UNIFORM_PAIR = get_rule("awakener.pair_choice_uniform")
GROUP_CONFLICT = get_rule("awakener.same_mod_group_keeps_one")
SURVIVOR_WIKI = get_rule("awakener.survivor_wiki")
SURVIVOR_COE = get_rule("awakener.survivor_coe")
REST_LIKE_CHAOS = get_rule("awakener.rest_rerolled_like_chaos")
KEPT_MODS_COUNT_IN_TOTAL = get_rule("awakener.kept_mods_count_in_total")
IGNORES_METAMODS = get_rule("awakener.ignores_metamods")
COST = get_rule("awakener.cost")
MINIMUM_ITEM_LEVEL = get_rule("awakener.refused_below_item_level_68")
REFUSED_WITHOUT_INFLUENCED_MODS = get_rule("awakener.refused_without_influenced_mods")
INFLUENCED_MOD_IS_INFLUENCE_SPAWN = get_rule("awakener.influenced_mod_is_influence_spawn")

RECEIVER, DONOR = "receiver", "donor"
GROUP_CONFLICT_AXIS = Axis("awakener.group_conflict", (RECEIVER, DONOR), RECEIVER)
"""Which of two kept mods of one mod group survives: the receiver's (the plan, Craft of Exile) or the donor's."""

__all__ = ["AwakenersOrb"]

WHY_NOT_PLANNER = "the solver takes no donors yet (#211, #212) and the interval over its rule axis does not exist (#220)"

_DONORS_LIMIT = 64
# (id(data), base, item level, donor influence, donor mod) -> (data, the donor as bought, the donor as wanted, its mod as kept).
_DONORS: dict[tuple, tuple[GameData, Item, Item, ExplicitMod]] = {}
_MODS_LIMIT = 64
# (id(data), base, item level, influence) -> (data, ids of the influence mods of that influence a donor of that base can hold).
_INFLUENCE_MODS: dict[tuple, tuple[GameData, tuple[str, ...]]] = {}


def _low_values(data: GameData, mod_id: str) -> tuple[int, ...]:
    return tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats)


def influence_mods(data: GameData, base_id: str, item_level: int, influence: Influence) -> tuple[str, ...]:
    """The ids of the mods a donor of `influence` on `base_id` can hold as its influenced mod, in data order.

    The mods of the base's domain, prefix or suffix, whose required level is at most `item_level` and that are influence mods
    of `influence` (`influence_spawn_test`), whatever their weight. Raises what `item_tags` raises for a class with no
    influence class key (`OutOfScopeError`) and `UnknownBaseError`.
    """
    key = (id(data), base_id, item_level, influence)
    hit = _INFLUENCE_MODS.get(key)
    if hit is not None and hit[0] is data:
        return hit[1]
    bare = Item.build(data, base_id=base_id, item_level=item_level, rarity=Rarity.NORMAL, influences=frozenset({influence}))
    is_influence_mod = influence_spawn_test(data, bare)
    domain = data.base_items[base_id].domain
    found = tuple(
        mod.id
        for mod in data.mods.values()
        if mod.domain == domain and mod.generation_type in Side and mod.required_level <= item_level and is_influence_mod(mod)
    )
    if len(_INFLUENCE_MODS) >= _MODS_LIMIT:
        _INFLUENCE_MODS.clear()
    _INFLUENCE_MODS[key] = (data, found)
    return found


@dataclass(frozen=True)
class AwakenersOrb(Action):
    """One Awakener's Orb used on the item in hand, with a donor of `donor_influence` that holds the influence mod `donor_mod`.

    `donor_base` and `donor_level` are the base and the item level the donor is acquired as (the receiver's, which a plan
    never changes); they let `inputs` answer without an item.
    """

    donor_base: str
    donor_level: int
    donor_influence: Influence
    donor_mod: str

    @property
    def variant(self) -> str:
        return f"{self.donor_influence.value} {self.donor_mod}"

    def label(self, data: GameData | None = None) -> str:
        if data is None:
            raise ValueError("an Awakener's Orb is named by the mod of its donor, so it needs the data")
        mod = data.mods.get(self.donor_mod)
        if mod is None:
            raise ValueError(f"the orb names a donor mod ({self.donor_mod}) that is not in the game data")
        return f"Awakener's Orb with a {self.donor_influence.value} donor of {' '.join((mod.text or mod.name or mod.id).split())}"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def reads(self, data: GameData) -> Reads:
        """It keeps the receiver's influenced mods (the junk, every family) and the donor's mod; the rest of the junk goes."""
        return Reads(junk=True, families=None, input_mods=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        """The donor's mod and a draw; every crafted mod goes. Implicits, quality and the offer stay as they were."""
        return Adds.erasing()

    def rule_axes(self, data: GameData) -> tuple[Axis, ...]:
        return (GROUP_CONFLICT_AXIS,)

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        # ADR-0041, #289: the rerolled mods are cut (the two kept mods keep their tier) and it spends 0 to 100; the donor's count is gone
        return StrandUse.cutting(SpendLaw.uniform(SPEND_SPECIAL_ORBS.value["awakeners"]), SPEND_SPECIAL_ORBS, CUT_FOLLOWS_SPEND_TABLE)

    def inputs(self, data: GameData, item: Item | None = None) -> tuple[Need, ...]:
        """The donor: it starts as a bare item of the donor's influence and must become a rare one that holds `donor_mod` alone.

        Nothing else of the donor matters to the result; which compressed state stands for it is decided where the planner
        builds donors (#211).
        """
        start, want, _ = self._donor(data)
        return (Need(start, want),)

    def _donor(self, data: GameData) -> tuple[Item, Item, ExplicitMod]:
        """The donor as bought, as wanted, and its mod as it is kept (its tier on the donor, low values: `sample` rolls it)."""
        key = (id(data), self.donor_base, self.donor_level, self.donor_influence, self.donor_mod)
        hit = _DONORS.get(key)
        if hit is not None and hit[0] is data:
            return hit[1:]
        influences = frozenset({self.donor_influence})
        start = Item.build(data, base_id=self.donor_base, item_level=self.donor_level, rarity=Rarity.NORMAL, influences=influences)
        mod = data.mods.get(self.donor_mod)
        if mod is None or self.donor_mod not in influence_mods(data, self.donor_base, self.donor_level, self.donor_influence):
            raise OutOfScopeError(
                f"{self.donor_mod} is not an influence mod of {self.donor_influence.value} that a donor on {self.donor_base} "
                f"of item level {self.donor_level} can hold"
            )
        entry = ExplicitMod(mod.id, tiers_of(data, start).get(mod.id, 1), _low_values(data, mod.id))
        want = Item.build(
            data, base_id=self.donor_base, item_level=self.donor_level, rarity=Rarity.RARE, mods=(entry,), influences=influences
        )
        if len(_DONORS) >= _DONORS_LIMIT:
            _DONORS.clear()
        _DONORS[key] = (data, start, want, entry)
        return start, want, entry

    def outcomes(self, data: GameData, item: Item, reading: Reading | None = None) -> Mixture:
        """The outcomes of using the orb on `item`, at the reading of the group conflict (the plan's when None).

        A mixture of pool draws, one per kept pair (pairs that leave the same mods are one part): each is the item with both
        influences holding only the kept mods, drawn up to the total of 4, 5 or 6 mods minus the kept ones.
        """
        conflict = (reading if reading is not None else Reading()).get(GROUP_CONFLICT_AXIS.name, GROUP_CONFLICT_AXIS.plan)
        if conflict not in GROUP_CONFLICT_AXIS.readings:
            raise ValueError(f"{conflict!r} is not a reading of {GROUP_CONFLICT_AXIS.name}: {GROUP_CONFLICT_AXIS.readings!r}")
        self._check(data, item)
        refuse_unmodelled(data, item)
        is_influence_mod = influence_spawn_test(data, item)
        held = [entry for entry in item.mods if is_influence_mod(data.mods[entry.mod_id])]
        _, _, donor = self._donor(data)
        if not held:
            raise NotApplicableError("the item holds no influenced mod, so there is nothing to merge with the donor's")
        pairs = [entry for entry in held if entry.mod_id != donor.mod_id]
        if not pairs:
            raise NotApplicableError("no pair of different influenced mods can be made")
        donor_mod = data.mods[donor.mod_id]
        influences = frozenset({*item.influences, self.donor_influence})
        share = Fraction(1, len(pairs))
        cut = self.cut_of(data, item)  # the count of `retained` is that of `item`; the kept mods are fixed, so only the rerolled ones are cut
        parts: dict[tuple[str, ...], tuple[Fraction, Outcomes]] = {}
        for entry in pairs:
            mine = replace(entry, values=_low_values(data, entry.mod_id))
            if not conflicts(data.mods[entry.mod_id], donor_mod):
                kept = (mine, donor)
            else:
                kept = (mine,) if conflict == RECEIVER else (donor,)
            ids = tuple(sorted(mod.mod_id for mod in kept))
            if ids in parts:
                parts[ids] = (parts[ids][0] + share, parts[ids][1])
                continue
            retained = item.changed(data, rarity=Rarity.RARE, influences=influences, mods=kept)
            drawn = Outcomes.over(data, retained, build_pool(data, retained, cut=cut), None, None, rerolled=frozenset(ids))
            parts[ids] = (share, drawn)
        return Mixture(data, tuple(parts.values()), False)

    def _check(self, data: GameData, item: Item) -> None:
        """Raise the refusal of the game or of the admitted rules for `item` as the receiver."""
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and an Awakener's Orb works on an uncorrupted item")
        if item.rarity is Rarity.NORMAL:
            raise NotApplicableError("an Awakener's Orb works on a magic or rare item, and this item is normal")
        if len(item.influences) != 1:
            raise NotApplicableError(
                f"an Awakener's Orb needs an item with exactly one influence, and this one has {len(item.influences)}"
            )
        if self.donor_influence in item.influences:
            raise NotApplicableError("the two items have the same influence")
        if item.item_level < MINIMUM_ITEM_LEVEL.value:
            raise NotApplicableError(f"an Awakener's Orb needs item level {MINIMUM_ITEM_LEVEL.value}, and this item has {item.item_level}")
        if any(entry.fractured for entry in item.mods):
            raise OutOfScopeError(
                "the item holds a fractured mod; in 3.29 a fractured item cannot carry an influence, so the Awakener's Orb "
                "does not model it (ADR-0032)"
            )


@kind("awakeners-orb", order=88, planner=False, why_not=WHY_NOT_PLANNER)
def _awakeners_orb(data: GameData, item: Item):
    """One orb for each influence mod of each other influence that a donor on the item's base could hold."""
    if item.corrupted or len(item.influences) != 1 or item.item_level < MINIMUM_ITEM_LEVEL.value:
        return
    (own,) = item.influences
    for influence in Influence:
        if influence is own:
            continue
        try:
            mod_ids = influence_mods(data, item.base_id, item.item_level, influence)
        except OutOfScopeError:  # an item class with no influence class key
            return
        for mod_id in mod_ids:
            yield AwakenersOrb(item.base_id, item.item_level, influence, mod_id)
