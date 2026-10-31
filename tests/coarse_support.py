"""The committed fixture of the coarse state tests (ticket #125): a small pool, a hybrid craft, prices, and the brute force.

The pool is `abstraction_pool.SMALL` (three prefix families, four suffix families) plus synthetic crafted
mods and bench options, so that nothing here needs the real dump and no build takes long:

* `HYBRID_CRAFT`, a suffix craft of the two families `ColdResistance` and `FireResistance`; the goal asks
  for it, and the two resistances give the goal nothing. They are the zero-contribution families that block
  a goal-relevant craft, so they are never pooled by default but can be pooled on purpose to see the gap;
* `MANA_CRAFT` and `LIGHTNING_CRAFT`, suffix crafts that clash with `ManaLeech` and `LightningResistance`,
  and `DAMAGE_CRAFT`, a prefix craft that clashes with `LightningDamage`: crafts that give the goal nothing,
  so the families they tell apart are irrelevant;
* `HYBRID_JUNK`, a suffix junk mod of two families (`ColdResistance` and `ManaLeech`) that no pool draws.

`PRICES` is the price fixture: the cost in Chaos of each offer, by label. The brute force at the bottom lists
concrete items from the data, compresses them with the exact abstraction and groups them by block, which is
what the invariance tests compare the coarse kernels with. Nothing here imports `Coarsening`.
"""

import dataclasses
from collections import defaultdict
from collections.abc import Iterable, Iterator
from fractions import Fraction
from itertools import combinations

import pytest

from abstraction_pool import COLD_RESIST, LEVEL, LIVES, SMALL
from items_support import AMULET

from crafting_system.abstraction import Abstraction, CompressedState, Goal, Wanted, integer_weights
from crafting_system.actions import (
    Action,
    ActionError,
    BenchCraft,
    ChaosOrb,
    RemoveCraftedMods,
)
from crafting_system.data import BaseItem
from crafting_system.items import ExplicitMod, Item, Rarity, tier_table
from crafting_system.solver import Action as SolverAction
from crafting_system.solver import Outcome

HYBRID_CRAFT = "TestCraftColdAndFire"
MANA_CRAFT = "TestCraftMana"
LIGHTNING_CRAFT = "TestCraftLightningResist"
DAMAGE_CRAFT = "TestCraftLightningDamage"
HYBRID_JUNK = "TestJunkColdAndMana"
CURRENCY = "Metadata/Items/Currency/CurrencyRerollMagic"

COLD, FIRE, MANA = "ColdResistance", "FireResistance", "ManaLeech"
LIGHTNING_RESIST, LIGHTNING_DAMAGE = "LightningResistance", "LightningDamage"

_TEMPLATE_CRAFT = "EinharMasterWeaponElementalDamage1_"  # a crafted prefix mod of the fixture, copied below


def _data():
    from items_support import DATA

    template = DATA.mods[_TEMPLATE_CRAFT]
    mods = dict(SMALL.mods)
    for mod_id, side, families in (
        (HYBRID_CRAFT, "suffix", (COLD, FIRE)),
        (MANA_CRAFT, "suffix", (MANA,)),
        (LIGHTNING_CRAFT, "suffix", (LIGHTNING_RESIST,)),
        (DAMAGE_CRAFT, "prefix", (LIGHTNING_DAMAGE,)),
    ):
        mods[mod_id] = dataclasses.replace(template, id=mod_id, type=mod_id, text=f"Test {mod_id}", families=families, generation_type=side)
    mods[HYBRID_JUNK] = dataclasses.replace(
        SMALL.mods[COLD_RESIST], id=HYBRID_JUNK, families=(COLD, MANA), spawn_weights=(), generation_weights=()
    )
    template_option = next(o for o in DATA.bench_options if o.actions.add_explicit_mod == _TEMPLATE_CRAFT)
    remove_option = next(o for o in DATA.bench_options if o.actions.remove_crafted_mods)
    options = [remove_option]
    for mod_id in (HYBRID_CRAFT, MANA_CRAFT, LIGHTNING_CRAFT, DAMAGE_CRAFT):
        actions = dataclasses.replace(template_option.actions, add_explicit_mod=mod_id)
        options.append(dataclasses.replace(template_option, actions=actions, item_classes=("Amulet",)))
    bases = dict(SMALL.base_items)
    for option in options:
        for entry in option.cost:
            bases.setdefault(
                entry.item_id,
                BaseItem(entry.item_id, entry.item_id.rsplit("/", 1)[-1], "StackableCurrency", "currency", 1, (), (), "released"),
            )
    return dataclasses.replace(SMALL, mods=mods, base_items=bases, bench_options=tuple(options))


DATA = _data()
TIERS = tier_table(DATA, AMULET)
GOAL = Goal((Wanted(frozenset({HYBRID_CRAFT})), Wanted(LIVES)))
CHAOS = ChaosOrb()
CRAFTS = tuple(BenchCraft(mod_id) for mod_id in (HYBRID_CRAFT, MANA_CRAFT, LIGHTNING_CRAFT, DAMAGE_CRAFT))
REMOVE = RemoveCraftedMods()
ENABLED = (*CRAFTS, REMOVE)
OFFERS: tuple[Action, ...] = (CHAOS, *CRAFTS, REMOVE)
PRICES = {  # Chaos Orbs
    CHAOS.label(DATA): 1.0,
    CRAFTS[0].label(DATA): 3.0,
    CRAFTS[1].label(DATA): 1.0,
    CRAFTS[2].label(DATA): 1.0,
    CRAFTS[3].label(DATA): 1.0,
    REMOVE.label(DATA): 0.5,
}


def roll(mod_id: str, *, fractured: bool = False, crafted: bool = False) -> ExplicitMod:
    mod = DATA.mods[mod_id]
    values = tuple(min(stat.min, stat.max) for stat in mod.stats)
    return ExplicitMod(mod_id, TIERS.get(mod_id, 1), values, fractured=fractured, crafted=crafted)


def item(*mods: ExplicitMod, rarity: Rarity = Rarity.RARE) -> Item:
    return Item.build(DATA, base_id=AMULET, item_level=LEVEL, rarity=rarity, mods=mods)


def abstraction(goal: Goal = GOAL, actions: Iterable[Action] = ENABLED) -> Abstraction:
    return Abstraction(DATA, goal, AMULET, LEVEL, tuple(actions))


# --- the solver's view -------------------------------------------------------------------------------


class ExactModel:
    """The exact compressed states under `OFFERS`, priced by `PRICES`."""

    def __init__(self, ab: Abstraction, offers: Iterable[Action] = OFFERS):
        self.ab, self.offers = ab, tuple(offers)

    def is_goal(self, state: CompressedState) -> bool:
        return self.ab.is_goal(state)

    def actions(self, state: CompressedState) -> list[SolverAction]:
        found = []
        for offer in self.offers:
            try:
                weights = integer_weights(self.ab.kernel(state, offer))
            except ActionError:
                continue
            found.append(SolverAction(offer.label(DATA), PRICES[offer.label(DATA)], tuple(Outcome(s, w) for s, w in weights.items())))
        return found


class CoarseModel:
    """The blocks of a `Coarsening` under `OFFERS` in the model of `bound`: "lower" is optimistic, "upper" pessimistic."""

    def __init__(self, coarsening, bound: str, offers: Iterable[Action] = OFFERS):
        self.coarsening, self.bound, self.offers = coarsening, bound, tuple(offers)
        for offer in self.offers:
            coarsening.require_invariant(offer)  # a refused action is not one that is refused in some states: it is no model

    def is_goal(self, block: CompressedState) -> bool:
        return self.coarsening.is_goal(block)

    def actions(self, block: CompressedState) -> list[SolverAction]:
        found = []
        for offer in self.offers:
            try:
                weights = integer_weights(self.coarsening.kernel(block, offer, self.bound))
            except ActionError:
                continue
            found.append(SolverAction(offer.label(DATA), PRICES[offer.label(DATA)], tuple(Outcome(s, w) for s, w in weights.items())))
        return found


# --- the brute force: concrete items, their exact states, grouped by block ---------------------------------


def concrete_items(
    data,
    mod_ids: Iterable[str],
    *,
    crafted: Iterable[str] = (),
    largest: int = 4,
    rarities: Iterable[Rarity] = (Rarity.RARE,),
) -> Iterator[Item]:
    """Every amulet of up to `largest` ordinary mods from `mod_ids` (distinct families, at most three a side).

    Each mod may be the fractured one (at most one is), and one of `crafted` may be on the item as a crafted mod.
    A magic item holds at most two mods and no crafted mod.
    """
    tiers = tier_table(data, AMULET)

    def rolled(mod_id: str, **flags) -> ExplicitMod:
        values = tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats)
        return ExplicitMod(mod_id, tiers.get(mod_id, 1), values, **flags)

    ordinary = [rolled(mod_id) for mod_id in mod_ids]
    crafted_mods = [None, *(rolled(mod_id, crafted=True) for mod_id in crafted)]
    for rarity in rarities:
        for size in range(1, (2 if rarity is Rarity.MAGIC else largest) + 1):
            for chosen in combinations(ordinary, size):
                for fractured in (None, *range(size)):
                    mods = [dataclasses.replace(e, fractured=True) if i == fractured else e for i, e in enumerate(chosen)]
                    for extra in crafted_mods if rarity is Rarity.RARE else [None]:
                        try:
                            yield Item.build(data, base_id=AMULET, item_level=LEVEL, rarity=rarity, mods=(*mods, *([extra] if extra else [])))
                        except ValueError:  # two mods of one family, or a full side: not an item
                            continue


def blocks_of(ab: Abstraction, coarsening, items: Iterable[Item]) -> dict[CompressedState, set[CompressedState]]:
    """The exact states of `items`, grouped by the block `coarsening` puts them in."""
    grouped: dict[CompressedState, set[CompressedState]] = defaultdict(set)
    for entry in items:
        state = ab.compress(entry)
        grouped[coarsening.coarsen(state)].add(state)
    return grouped


_MEMOS: dict[int, tuple[Abstraction, dict]] = {}


def exact_kernel(ab: Abstraction, state: CompressedState, action: Action):
    """`ab.kernel(state, action)`, remembered per abstraction and (state, action) with its refusal: the levels of a test share it."""
    memo = _MEMOS.setdefault(id(ab), (ab, {}))[1]
    key = (state, action)
    if key not in memo:
        try:
            memo[key] = ab.kernel(state, action)
        except ActionError as refusal:
            memo[key] = refusal
    if isinstance(memo[key], ActionError):
        raise memo[key]
    return memo[key]


def pushed(coarsening, exact) -> dict[CompressedState, Fraction]:
    """An exact kernel pushed through `coarsen`."""
    total: dict[CompressedState, Fraction] = defaultdict(Fraction)
    for state, chance in exact.items():
        total[coarsening.coarsen(state)] += chance
    return dict(total)


def compare_members(action: Action, ab: Abstraction, coarsening, blocks: dict[CompressedState, set[CompressedState]]) -> int:
    """Check `coarsening.kernel` of `action` against its members on `blocks`; how many members were compared with another member of their block.

    The members are the exact states found by brute force; the result counts those beyond the first of each block. Each one's own kernel, pushed through `coarsen`,
    must be the same where the action can be taken (exact fractions, so within any tolerance); the lower model
    must offer the action when some member can take it and charge that kernel, the upper only when every member
    can; where it is not offered, the action's own refusal comes back. `coarsening.members` must list every state.
    """
    compared = 0
    for block, members in blocks.items():
        assert members <= set(coarsening.members(block)), "the members of a block include every exact state of it"
        legal: dict = {}
        for member in members:
            try:
                legal[member] = pushed(coarsening, exact_kernel(ab, member, action))
            except ActionError:
                continue
        first = next(iter(legal.values()), None)
        assert all(kernel == first for kernel in legal.values()), "the members of a block give the same kernel pushed through the blocks"
        compared += len(members) - 1
        if first is None:
            for bound in ("lower", "upper"):
                with pytest.raises(ActionError):
                    coarsening.kernel(block, action, bound)
            continue
        assert coarsening.kernel(block, action, "lower") == first, "the lower model charges the pushed kernel"
        if len(legal) == len(members):
            assert coarsening.kernel(block, action, "upper") == first, "the upper model offers the action when every member can take it"
        else:
            with pytest.raises(ActionError):
                coarsening.kernel(block, action, "upper")
    return compared
