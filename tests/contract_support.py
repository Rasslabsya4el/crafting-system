"""The contract suite of the actions (ticket #108): every check that any action must pass, with no edit per action.

`check_action(action, item)` runs the checks on one action and one item; `contract_pairs()` lists the
`(kind, action, item)` triples of the catalog on the fixture items, a few members of each kind. A new
method needs no line here: it registers its kind in the catalog and the suite finds it. The toy action
of `test_actions_toy.py` runs the same `check_action`.

The checks, each against something written without the code under test:

* the outcomes sum to one, seen through a label that tells every mod apart and through a coarse one;
* the finished items listed by brute force from `components` give each mod the chance `chance_all` says;
* the sampler holds each mod as often as that chance, within five standard errors (fixed seed);
* the kernel of `abstraction` equals the brute force on the compressed finished items (layer 1,
  ADR-0019), unless the action fractures a mod (the fossil tests cover that one);
* what the action declares agrees with what it does: an action that reads no junk keeps none, and an
  action that adds nothing unnamed only adds the mods it names;
* the resources are whole counts of named things and price the offer from a fixture price file.

The data is the fixture pool of `abstraction_pool.SMALL` plus the mods the fixture essences, fossils
and bench options name, so that every kind has something to do and the brute force stays small.
"""

import dataclasses
import datetime
import math
import random
from collections import defaultdict
from fractions import Fraction

from abstraction_pool import GEM, LEVEL, LIFE_1, LIFE_2, MANA_1, POOL_IDS, RESIST_1, RESIST_2, RESISTS
from items_support import AMULET, DATA

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    Action,
    ActionError,
    Adds,
    Fixed,
    Reads,
    kinds,
)
from crafting_system.data import BaseItem
from crafting_system.cli._offers import offer_of, price_offers
from crafting_system.items import ExplicitMod, Item, Metamod, Rarity, tier_table
from crafting_system.prices import CHAOS_ORB, PriceEntry, PriceFile


def _fixture_data():
    keep = set(POOL_IDS)
    for essence in DATA.essences.values():
        keep.update(entry.mod_id for entry in essence.mods if entry.mod_id)
    for fossil in DATA.fossils.values():
        keep.update(fossil.forced_mods)
        keep.update(fossil.added_mods)
    for option in DATA.bench_options:
        if option.actions.add_explicit_mod:
            keep.add(option.actions.add_explicit_mod)
    keep &= set(DATA.mods)
    # the fixture names currencies in bench costs that it holds no base item for: add one, named by its id
    bases = dict(DATA.base_items)
    for option in DATA.bench_options:
        for entry in option.cost:
            bases.setdefault(
                entry.item_id,
                BaseItem(entry.item_id, entry.item_id.rsplit("/", 1)[-1], "StackableCurrency", "currency", 1, (), (), "released"),
            )
    return dataclasses.replace(
        DATA, mods={mod_id: mod for mod_id, mod in DATA.mods.items() if mod_id in keep}, base_items=bases
    )


CONTRACT_DATA = _fixture_data()
TIERS = tier_table(CONTRACT_DATA, AMULET)
GOAL = Goal((Wanted(frozenset({GEM})), Wanted(RESISTS), Wanted(frozenset({LIFE_1, LIFE_2}))))
SAMPLES = 1_000
SIGMAS = 5.0


def _roll(mod_id: str, *, fractured: bool = False, crafted: bool = False) -> ExplicitMod:
    mod = CONTRACT_DATA.mods[mod_id]
    values = tuple(min(stat.min, stat.max) for stat in mod.stats)
    return ExplicitMod(mod_id, TIERS.get(mod_id, 1), values, fractured=fractured, crafted=crafted)


def _item(rarity: Rarity, *mods: ExplicitMod) -> Item:
    return Item.build(CONTRACT_DATA, base_id=AMULET, item_level=LEVEL, rarity=rarity, mods=mods)


def _ordinary_crafted_mod() -> str | None:
    """A bench-crafted mod that is no metamod, for the item that holds a crafted mod."""
    metamods = {metamod.value for metamod in Metamod}
    for option in CONTRACT_DATA.bench_options:
        mod_id = option.actions.add_explicit_mod
        mod = CONTRACT_DATA.mods.get(mod_id) if mod_id else None
        if mod is not None and mod.generation_type in ("prefix", "suffix") and mod.stats and not metamods & set(mod.families):
            return mod_id
    return None


def fixture_items() -> dict[str, Item]:
    """The items the catalog is asked about: one of each rarity, and a rare item with fractured, junk and crafted mods."""
    items = {
        "normal": _item(Rarity.NORMAL),
        "magic": _item(Rarity.MAGIC, _roll(LIFE_1)),
        "rare_junk": _item(Rarity.RARE, _roll(RESIST_2), _roll(LIFE_1)),
        "rare_fractured": _item(Rarity.RARE, _roll(RESIST_1, fractured=True), _roll(MANA_1)),
    }
    crafted = _ordinary_crafted_mod()
    if crafted is not None:
        items["rare_crafted"] = _item(Rarity.RARE, _roll(RESIST_2), _roll(crafted, crafted=True))
    return items


def contract_pairs(per_kind: int = 3) -> list[tuple[str, Action, str]]:
    """`(kind name, action, item name)` for up to `per_kind` members of each registered kind on each fixture item."""
    found = []
    for name, item in fixture_items().items():
        for entry in kinds():
            members = list(entry.members(CONTRACT_DATA, item))
            picked = members if len(members) <= per_kind else [members[0], members[len(members) // 2], members[-1]]
            found.extend((entry.name, action, name) for action in picked)
    return found


# --- the brute force ----------------------------------------------------------------------------


def finished(outcomes, data=CONTRACT_DATA) -> list[tuple[Fraction, Item]]:
    """Every finished item with its probability, listed from the mixture: a fixed result, or one item per outcome of a pool draw."""
    items = []
    for share, part in outcomes.components:
        if isinstance(part, Fixed):
            items.append((share, part.result))
            continue
        for outcome, chance in part.distribution(lambda mod: mod.id).items():
            added = tuple(
                _roll_in(data, mod_id) for mod_id, count in sorted(outcome) for _ in range(count)
            )
            items.append((share * chance, part.retained.changed(data, mods=(*part.retained.mods, *added))))
    return items


def _roll_in(data, mod_id: str) -> ExplicitMod:
    mod = data.mods[mod_id]
    values = tuple(min(stat.min, stat.max) for stat in mod.stats)
    return ExplicitMod(mod_id, tier_table(data, AMULET).get(mod_id, 1), values)


# --- the checks ----------------------------------------------------------------------------------


def check_action(action: Action, item: Item, data=CONTRACT_DATA, goal: Goal = GOAL) -> bool:
    """Run every check of the contract on `action` used on `item`; False when the game or the rules refuse it here (nothing to check).

    Raises `AssertionError` naming the check that failed.
    """
    try:
        outcomes = action.outcomes(data, item)
    except ActionError:
        return False
    name = action.label(data)
    assert isinstance(name, str) and name, "the label is a name"
    reads, adds = action.reads(data), action.adds(data, item)
    assert isinstance(reads, Reads) and isinstance(adds, Adds)

    check_sums_to_one(outcomes, data)
    items = finished(outcomes, data)
    check_chances_agree(outcomes, items, data)
    check_sampler_follows_the_chances(outcomes, items, data)
    check_declarations_agree(action, reads, adds, outcomes, items, item)
    if not outcomes.fractures:
        check_kernel_equals_brute_force(action, reads, item, items, data, goal)
    check_resources_are_priced(action, item, data)
    return True


def check_sums_to_one(outcomes, data) -> None:
    for label in (lambda mod: mod.id, lambda mod: mod.generation_type):
        assert sum(outcomes.distribution(label).values()) == 1, "the outcomes sum to exactly one"
    assert sum(share for share, _ in outcomes.components) == 1, "the components sum to exactly one"


def _held(items, mod_id: str) -> Fraction:
    return sum((chance for chance, item in items if any(e.mod_id == mod_id for e in item.mods)), Fraction(0))


def check_chances_agree(outcomes, items, data) -> None:
    assert sum(chance for chance, _ in items) == 1, "the listed finished items sum to one"
    for mod_id in data.mods:
        assert _held(items, mod_id) == outcomes.chance_all([mod_id]), f"chance_all of {mod_id} is the listed items'"


def check_sampler_follows_the_chances(outcomes, items, data) -> None:
    rng = random.Random(20261031)
    seen: dict[str, int] = defaultdict(int)
    for _ in range(SAMPLES):
        drawn = outcomes.sample(rng)
        drawn.validate(data)
        for mod_id in {entry.mod_id for entry in drawn.mods}:
            seen[mod_id] += 1
    for mod_id in data.mods:
        chance = float(outcomes.chance_all([mod_id]))
        error = SIGMAS * math.sqrt(chance * (1 - chance) / SAMPLES) + 1e-9
        assert abs(seen[mod_id] / SAMPLES - chance) <= error, f"the sampler holds {mod_id} as often as chance_all says"


def check_declarations_agree(action, reads: Reads, adds: Adds, outcomes, items, given: Item) -> None:
    junk = {entry.mod_id for entry in given.mods if not entry.fractured and not entry.crafted}
    if not reads.junk:
        for _, part in outcomes.components:
            kept = {entry.mod_id for entry in part.retained.mods if not entry.fractured and not entry.crafted}
            assert not kept & junk, "an action that reads no junk erases it"
    if adds.named is not None and not adds.draws:
        held = {(entry.mod_id, entry.fractured, entry.crafted) for entry in given.mods}
        for _, result in items:
            new = {entry.mod_id for entry in result.mods if (entry.mod_id, entry.fractured, entry.crafted) not in held}
            assert new <= adds.named, "an action that draws nothing adds only the mods it names"
    if adds.named is not None and adds.crafted:
        for _, result in items:
            crafted = {entry.mod_id for entry in result.mods if entry.crafted}
            assert adds.named & crafted or not adds.named, "the named mods are added as crafted mods"


def check_kernel_equals_brute_force(action, reads: Reads, item: Item, items, data, goal: Goal) -> None:
    enabled = [action] if reads.junk else []
    ab = Abstraction(data, goal, AMULET, LEVEL, enabled)
    expected: dict = defaultdict(Fraction)
    for chance, result in items:
        expected[ab.compress(result)] += chance
    kernel = ab.kernel(ab.compress(item), action)
    assert dict(kernel) == dict(expected), "the kernel equals the brute force on the compressed finished items"
    assert sum(kernel.values()) == 1


def check_resources_are_priced(action, item: Item, data) -> None:
    resources = action.resources(data)
    assert resources, "one use consumes something"
    assert all(isinstance(name, str) and name and isinstance(count, int) and count > 0 for name, count in resources.items())
    prices = {name: PriceEntry(2.0, "test") for name in resources if name != CHAOS_ORB}
    file = PriceFile("Test", datetime.datetime(2026, 10, 31, tzinfo=datetime.UTC), 300.0, prices)
    offer = offer_of(action, action.label(data), data, item)
    priced, dropped = price_offers([offer], file)
    assert not dropped and len(priced) == 1, "every resource is found in a price file that names it"
    expected = sum(float(count) if name == CHAOS_ORB else 2.0 * count for name, count in resources.items())
    assert priced[0].cost == expected
