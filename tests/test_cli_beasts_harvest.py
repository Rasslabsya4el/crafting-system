"""The beast and Harvest crafts as planner kinds: offered only when a target names them, priced, and planned end to end (ticket #149).

The kinds are `opt_in` (a target that is not about them must not pay for their states), so `offers_for` lists them only for a target that names them
in `actions:`; an aspect is offered as well only for a target that wants it (`Adds.wanted_only`). Two small targets are solved with a hand figure:

* a resistance swap: the item holds a Fire Resistance and a maximum Fire Resistance, the goal is the Cold Resistance, the craft is Fire to Cold. It
  swaps one of the two with chance 1/2 each: the Fire Resistance becomes the goal, the maximum becomes a maximum Cold Resistance, after which the only
  Fire mod left is the Fire Resistance and the next use ends it. The mean number of uses is 1 + 1/2 = 3/2, each 500 Vivid lifeforce;
* an aspect: one craft, whatever it costs, exactly once.
"""

import dataclasses
import datetime

import pytest
from beasts_support import ASPECT_IDS, beast_data
from test_actions_harvest_swap import COLD_RESIST, FIRE_RESIST, MAX_FIRE, WORLD as SWAP_WORLD, mod as world_mod

from crafting_system.abstraction import Goal, Wanted
from crafting_system.actions import AspectBeast
from crafting_system.cli import build_report, make_plan, render_text
from crafting_system.cli._offers import offers_for
from crafting_system.items import Item, Rarity
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.targets import load_target

AMULET = "Metadata/Items/Amulets/Amulet1"
VIVID = "Vivid Crystallised Lifeforce"
WORLD = dataclasses.replace(  # the bench crafts of mods the small pool lacks are left out
    SWAP_WORLD, bench_options=tuple(option for option in SWAP_WORLD.bench_options if option.actions.add_explicit_mod in (None, *SWAP_WORLD.mods))
)
BEAST_DATA = beast_data(data=WORLD)
CAT_30 = ASPECT_IDS["cat", 30]


def price_file(**prices: float) -> PriceFile:
    entries = {name.replace("_", " "): PriceEntry(chaos, "test") for name, chaos in prices.items()}
    return PriceFile("Test", datetime.datetime(2026, 11, 1, tzinfo=datetime.UTC), 300.0, entries)


def start_item() -> Item:
    return Item.build(WORLD, base_id=AMULET, item_level=84, rarity=Rarity.RARE, mods=(world_mod(FIRE_RESIST), world_mod(MAX_FIRE)))


def test_the_beast_and_harvest_kinds_are_offered_only_when_a_target_names_them():
    goal = Goal((Wanted(frozenset({COLD_RESIST})),))
    start = start_item()
    default = {offer.label for offer in offers_for(WORLD, goal, AMULET, start, None).offers}
    assert not any(label.startswith(("Harvest Swap", "Harvest Add", "Beastcraft")) for label in default)
    named = offers_for(WORLD, goal, AMULET, start, ["harvest-resistance-swap", "harvest-add-remove"])
    labels = {offer.label for offer in named.offers}
    assert "Harvest Swap Resistance Fire to Cold" in labels and "Harvest Add Remove Fire" in labels
    assert not any(label.startswith("Harvest Swap Damage") for label in labels)  # a kind not named


def test_an_aspect_is_offered_for_a_target_that_names_the_kind_and_wants_the_aspect():
    start = Item.build(BEAST_DATA, base_id=AMULET, item_level=84, rarity=Rarity.RARE, mods=(world_mod(FIRE_RESIST),))
    wanted = Goal((Wanted(frozenset({CAT_30})),))
    other = Goal((Wanted(frozenset({COLD_RESIST})),))
    assert [offer.action for offer in offers_for(BEAST_DATA, wanted, AMULET, start, ["aspect-beast"]).offers] == [AspectBeast("cat", 30)]
    unwanted = offers_for(BEAST_DATA, other, AMULET, start, ["aspect-beast"])
    assert unwanted.offers == () and any("fixed mod" in left.reason for left in unwanted.left_out)
    assert not [offer for offer in offers_for(BEAST_DATA, wanted, AMULET, start, None).offers if isinstance(offer.action, AspectBeast)]  # the kind is not named


def test_a_swap_target_is_planned_end_to_end_with_the_hand_figure(tmp_path):
    path = tmp_path / "swap.yaml"
    lines = []
    for mod_id in (FIRE_RESIST, MAX_FIRE):
        entry = world_mod(mod_id)
        lines.append(f"    - mod: {mod_id}\n      tier: {entry.tier}\n      values: {list(entry.values)}")
    path.write_text(
        "base: Paua Amulet\nitem_level: 84\ninfluence: []\nrequirements:\n  - family: " + WORLD.mods[COLD_RESIST].families[0] + "\n    mod: " + COLD_RESIST + "\n"
        "start_item:\n  rarity: rare\n  mods:\n" + "\n".join(lines) + "\nactions: [harvest-resistance-swap]\n",
        encoding="utf-8",
    )
    target = load_target(path, WORLD)
    plan = make_plan(WORLD, target, price_file(Vivid_Crystallised_Lifeforce=0.02))
    uses = 1.5
    assert plan.mean_remaining == pytest.approx(uses * 500 * 0.02, rel=1e-12)
    assert {priced.label for priced in plan.offers} == {"Harvest Swap Resistance Fire to Cold", "Harvest Swap Resistance Fire to Lightning",
        "Harvest Swap Resistance Cold to Fire", "Harvest Swap Resistance Cold to Lightning", "Harvest Swap Resistance Lightning to Fire",
        "Harvest Swap Resistance Lightning to Cold"} - {d.label for d in plan.dropped}
    text = render_text(build_report(plan, WORLD))
    assert "Harvest Swap Resistance Fire to Cold" in text


def test_an_aspect_target_is_planned_end_to_end_and_costs_the_beasts_once(tmp_path):
    path = tmp_path / "aspect.yaml"
    mod = BEAST_DATA.mods[CAT_30]
    path.write_text(
        "base: Paua Amulet\nitem_level: 84\ninfluence: []\nrequirements:\n  - family: " + mod.families[0] + "\n    mod: " + CAT_30 + "\n"
        "start_item:\n  rarity: rare\n  mods:\n    - mod: " + FIRE_RESIST + "\n      tier: 1\n      values: [6]\nactions: [aspect-beast]\n",
        encoding="utf-8",
    )
    target = load_target(path, BEAST_DATA)
    resources = dict(AspectBeast("cat", 30).resources(BEAST_DATA))
    prices = {name: PriceEntry(7.0 + number, "test") for number, name in enumerate(sorted(n for n in resources if n != "Chaos Orb"))}
    plan = make_plan(BEAST_DATA, target, PriceFile("Test", datetime.datetime(2026, 11, 1, tzinfo=datetime.UTC), 300.0, prices))
    expected = sum(float(count) if name == "Chaos Orb" else prices[name].chaos * count for name, count in resources.items())
    assert plan.mean_remaining == pytest.approx(expected, rel=1e-12)
    assert [priced.label for priced in plan.offers] == ["Beastcraft Aspect of the Cat (level 30)"]
