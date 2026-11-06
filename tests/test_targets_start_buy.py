"""The bought start item is described once: the buy spec, the trade query and the price key are computed from the target (#474, OR-3).

The data is the small fixture export (`items_support.DATA`): a Paua Amulet pool whose Lightning Resistance tiers need item levels 1, 13,
25, 37, 49, 60, 72 and 84, plus hand-made bases added below (a twin of the amulet, a Battle Royale copy, a base with no trade category).
The real benchmark targets, with the stored price entries, are in `test_start_buy_real.py`.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from targets_support import DATA, parse

from crafting_system.cli._plan import PlanError, resolve_start_price
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.prices.trade_query import build_query
from crafting_system.prices.trade_stats import parse_trade_stats, resolve_buy_mod
from crafting_system.targets import StartBuyError, buy_spec_of, parse_target, start_price_key
from crafting_system.targets.start_buy import TRADE_CATEGORY, item_level_window, same_name_bases

AMULET = "Metadata/Items/Amulets/Amulet1"
STATS = parse_trade_stats(json.loads((Path(__file__).parent / "fixtures" / "trade" / "stats_excerpt.json").read_text(encoding="utf-8")))

FRACTURED_RESIST = """\
buys_start_item: true
requirements:
  - family: IncreasedLife
start_item:
  mods:
    - mod: LightningResist7
      tier: 2
      values: [43]
      fractured: true
"""


def target_at(level: int, tail: str, *, base: str = "Paua Amulet", data=DATA):
    return parse_target(f"base: {base}\nitem_level: {level}\n{tail}", data, source="t.yaml")


# -- the category -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("base", "requirement", "category"),
    [
        ("Paua Amulet", "family: IncreasedLife", "accessory.amulet"),
        ("Leather Belt", "family: FireResistance", "accessory.belt"),
        ("Thicket Bow", "family: IncreasedAttackSpeed", "weapon.bow"),
        ("Simple Robe", "family: IncreasedLife", "armour.chest"),
    ],
)
def test_the_trade_category_comes_from_the_item_class_of_the_base(base, requirement, category):
    name = {"Simple Robe": "Simple Robe"}.get(base, base)
    found = buy_spec_of(DATA, target_at(80, f"buys_start_item: true\nrequirements:\n  - {requirement}\n", base=name))

    assert found.category == category
    assert found.base_type == name


def test_a_base_class_with_no_trade_category_is_refused_by_name():
    target = target_at(80, "buys_start_item: true\nrequirements:\n  - family: IncreasedAttackSpeed\n", base="Rusted Sword")

    with pytest.raises(StartBuyError, match="One Hand Sword"):
        buy_spec_of(DATA, target)


def test_the_category_map_has_the_ten_classes_of_the_benchmark_routes():
    assert set(TRADE_CATEGORY.values()) == {
        "accessory.amulet",
        "accessory.ring",
        "accessory.belt",
        "armour.boots",
        "armour.gloves",
        "armour.helmet",
        "armour.chest",
        "armour.shield",
        "armour.quiver",
        "weapon.bow",
    }


# -- the item level window --------------------------------------------------------------------------------------


@pytest.mark.parametrize(("level", "window"), [(84, (84, 100)), (81, (81, 83)), (76, (76, 80)), (72, (72, 74))])
def test_the_window_runs_from_the_target_level_to_the_highest_level_with_the_same_pool(level, window):
    target = target_at(level, FRACTURED_RESIST.replace("LightningResist7", "LightningResist1").replace("values: [43]", "values: [6]"))

    assert item_level_window(DATA, target) == window


def test_a_window_that_ends_below_the_top_has_a_maximum_in_the_query_and_one_that_runs_to_the_top_has_none():
    closed = buy_spec_of(DATA, target_at(81, "buys_start_item: true\nrequirements:\n  - family: IncreasedLife\n"))
    open_ = buy_spec_of(DATA, target_at(84, "buys_start_item: true\nrequirements:\n  - family: IncreasedLife\n"))

    assert (closed.item_level_min, closed.item_level_max) == (81, 83)
    assert (open_.item_level_min, open_.item_level_max) == (84, None)
    assert build_query(closed, []).body()["query"]["filters"]["misc_filters"]["filters"]["ilvl"] == {"min": 81, "max": 83}
    assert build_query(open_, []).body()["query"]["filters"]["misc_filters"]["filters"]["ilvl"] == {"min": 84}


# -- the start mods ---------------------------------------------------------------------------------------------


def test_the_minimum_is_the_lowest_roll_of_the_tier_the_target_names_not_the_roll_it_holds():
    spec = buy_spec_of(DATA, target_at(84, FRACTURED_RESIST))

    (mod,) = spec.mods
    assert (mod.minimum, mod.fractured) == (42, True)  # LightningResist7 is +(42-45)%, the item holds 43


def test_another_tier_of_the_family_gives_another_minimum():
    spec = buy_spec_of(DATA, target_at(84, FRACTURED_RESIST.replace("LightningResist7", "LightningResist2").replace("[43]", "[14]")))

    assert [mod.minimum for mod in spec.mods] == [12]  # +(12-17)%


def test_a_mod_that_is_not_fractured_is_searched_among_the_explicit_mods():
    spec = buy_spec_of(DATA, target_at(84, FRACTURED_RESIST.replace("      fractured: true\n", "")))
    query = build_query(spec, [resolve_buy_mod(mod, list(DATA.mods.values()), STATS) for mod in spec.mods]).body()["query"]

    assert query["stats"][0]["filters"][0]["id"] == "explicit.stat_1671376347"
    assert "fractured_item" not in query["filters"]["misc_filters"]["filters"]


def test_the_query_of_a_fractured_start_mod_asks_for_a_fractured_item_and_the_minimum():
    spec = buy_spec_of(DATA, target_at(84, FRACTURED_RESIST))
    query = build_query(spec, [resolve_buy_mod(mod, list(DATA.mods.values()), STATS) for mod in spec.mods]).body()

    assert query["query"]["stats"] == [{"type": "and", "filters": [{"id": "fractured.stat_1671376347", "disabled": False, "value": {"min": 42}}]}]
    assert query["query"]["filters"]["misc_filters"]["filters"]["fractured_item"] == {"option": "true"}
    assert query["query"]["type"] == "Paua Amulet"
    assert query["query"]["filters"]["type_filters"]["filters"] == {"category": {"option": "accessory.amulet"}, "rarity": {"option": "rare"}}


def test_a_crafted_start_mod_is_refused_because_nobody_sells_it():
    target = target_at(84, FRACTURED_RESIST.replace("LightningResist7", "JunMaster2AllDamage2_").replace("[43]", "[12]").replace("      fractured: true\n", "      crafted: true\n"))

    with pytest.raises(StartBuyError, match="crafted"):
        buy_spec_of(DATA, target)


def test_a_mod_of_two_stats_is_refused():
    text = FRACTURED_RESIST.replace("LightningResist7", "AddedLightningDamage3").replace("[43]", "[1, 22]")

    with pytest.raises(StartBuyError, match="one-stat"):
        buy_spec_of(DATA, target_at(84, text))


# -- the rarity -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "rarity"),
    [
        ("", "normal"),  # no start_item block: a fresh normal item
        ("start_item:\n  rarity: rare\n  mods: []\n", "normal"),  # R08 and R09: bought Normal, made rare by the Alchemy folded into the price
        ("start_item:\n  rarity: magic\n  mods: []\n", "magic"),
    ],
)
def test_the_rarity_is_the_start_items_and_a_rare_with_no_mods_is_searched_as_normal(start, rarity):
    spec = buy_spec_of(DATA, target_at(84, f"buys_start_item: true\nrequirements:\n  - family: IncreasedLife\n{start}"))

    assert spec.rarity == rarity


def test_a_rare_start_item_with_a_mod_stays_rare():
    assert buy_spec_of(DATA, target_at(84, FRACTURED_RESIST)).rarity == "rare"


# -- the influences ---------------------------------------------------------------------------------------------


def test_the_influences_of_the_start_item_are_in_the_spec_the_query_and_the_key():
    target = target_at(84, "influence: [hunter]\nbuys_start_item: true\nrequirements:\n  - family: FireResistance\n", base="Leather Belt")
    spec = buy_spec_of(DATA, target)
    body = build_query(spec, []).body()["query"]

    assert spec.influences == ("hunter",)
    assert body["stats"][0]["filters"] == [{"id": "pseudo.pseudo_has_hunter_influence", "disabled": False, "value": {"min": 1}}]
    assert spec.name == "Leather Belt, normal, item level 84-100, Hunter influence"


# -- the price key ----------------------------------------------------------------------------------------------


def test_the_key_reads_as_the_item():
    assert start_price_key(DATA, target_at(76, FRACTURED_RESIST)) == "Paua Amulet, item level 76-80, fractured +(42-45)% to Lightning Resistance"


def test_the_key_is_the_name_of_the_spec_and_depends_on_nothing_but_the_target():
    target = target_at(84, FRACTURED_RESIST)

    assert start_price_key(DATA, target) == buy_spec_of(DATA, target).name
    assert start_price_key(DATA, target) == start_price_key(DATA, target_at(84, FRACTURED_RESIST.replace("IncreasedLife", "FireResistance")))


def test_a_one_level_window_says_the_level_once():
    assert start_price_key(DATA, target_at(75, FRACTURED_RESIST)) == "Paua Amulet, item level 75, fractured +(42-45)% to Lightning Resistance"


def test_two_items_that_differ_have_two_keys():
    plain = "buys_start_item: true\nrequirements:\n  - family: IncreasedLife\n"
    keys = {
        start_price_key(DATA, target_at(84, plain)),
        start_price_key(DATA, target_at(81, plain)),
        start_price_key(DATA, target_at(84, plain + "start_item:\n  rarity: magic\n  mods: []\n")),
        start_price_key(DATA, target_at(84, FRACTURED_RESIST)),
        start_price_key(DATA, target_at(84, FRACTURED_RESIST.replace("LightningResist7", "LightningResist2").replace("[43]", "[14]"))),
    }

    assert len(keys) == 5


# -- a name that two bases share --------------------------------------------------------------------------------


def with_bases(**bases: dict) -> object:
    """The fixture data plus the amulet's twins: `bases` maps a new id to the fields that differ from the Paua Amulet."""
    amulet = DATA.base_items[AMULET]
    added = {base_id: replace(amulet, id=base_id, **fields) for base_id, fields in bases.items()}
    return replace(DATA, base_items={**DATA.base_items, **added})


def test_a_name_with_one_base_is_not_told_apart():
    assert same_name_bases(DATA, AMULET) == (AMULET,)
    assert start_price_key(DATA, target_at(84, FRACTURED_RESIST)).startswith("Paua Amulet, ")


def test_a_name_that_two_released_bases_share_puts_the_base_id_in_the_key():
    data = with_bases(**{"Metadata/Items/Amulets/Amulet1Twin": {}})
    first = parse_target(f"base: {AMULET}\nitem_level: 84\n{FRACTURED_RESIST}", data, source="t.yaml")
    second = parse_target(f"base: Metadata/Items/Amulets/Amulet1Twin\nitem_level: 84\n{FRACTURED_RESIST}", data, source="t.yaml")

    assert same_name_bases(data, AMULET) == (AMULET, "Metadata/Items/Amulets/Amulet1Twin")
    assert start_price_key(data, first) == "Paua Amulet [Amulet1], item level 84-100, fractured +(42-45)% to Lightning Resistance"
    assert start_price_key(data, second) == "Paua Amulet [Amulet1Twin], item level 84-100, fractured +(42-45)% to Lightning Resistance"


def test_the_trade_site_cannot_tell_such_bases_apart_so_the_query_is_the_same_for_both():
    data = with_bases(**{"Metadata/Items/Amulets/Amulet1Twin": {}})
    first = buy_spec_of(data, parse_target(f"base: {AMULET}\nitem_level: 84\n{FRACTURED_RESIST}", data, source="t.yaml"))
    second = buy_spec_of(data, parse_target(f"base: Metadata/Items/Amulets/Amulet1Twin\nitem_level: 84\n{FRACTURED_RESIST}", data, source="t.yaml"))

    assert first.name != second.name
    assert replace(first, name="x") == replace(second, name="x")


def test_a_battle_royale_copy_and_an_unreleased_base_are_not_a_second_base():
    data = with_bases(**{"Metadata/Items/Amulets/Amulet1Royale": {}, "Metadata/Items/Amulets/Amulet1Beta": {"release_state": "unreleased"}})

    assert same_name_bases(data, AMULET) == (AMULET,)


def test_where_a_name_has_bases_on_sale_the_ones_not_for_sale_are_left_out():
    data = with_bases(**{"Metadata/Items/Amulets/Amulet1Gift": {"tags": ("amulet", "default", "not_for_sale")}})

    assert same_name_bases(data, AMULET) == (AMULET,)


def test_where_every_base_of_the_name_is_not_for_sale_all_stay():
    plain = DATA.base_items[AMULET]
    data = replace(DATA, base_items={**DATA.base_items, AMULET: replace(plain, tags=(*plain.tags, "not_for_sale"))})
    data = replace(data, base_items={**data.base_items, "Metadata/Items/Amulets/Amulet1Twin": replace(data.base_items[AMULET], id="Metadata/Items/Amulets/Amulet1Twin")})

    assert same_name_bases(data, AMULET) == (AMULET, "Metadata/Items/Amulets/Amulet1Twin")


# -- the price the planner looks up ------------------------------------------------------------------------------


def prices(**entries: float) -> PriceFile:
    from datetime import UTC, datetime

    return PriceFile("Allflame", datetime(2026, 11, 1, tzinfo=UTC), 400.0, {name: PriceEntry(chaos, "trade-api") for name, chaos in entries.items()})


def test_a_target_that_buys_its_start_item_is_priced_under_its_computed_key():
    target = target_at(84, FRACTURED_RESIST)
    key = start_price_key(DATA, target)

    found = resolve_start_price(DATA, target, prices(**{key: 7.5}), None)

    assert (found.name, found.chaos, found.source) == (key, 7.5, "trade-api")


def test_a_key_that_is_not_in_the_price_file_is_an_error_that_names_the_key_and_the_trade_command():
    target = target_at(84, FRACTURED_RESIST)

    with pytest.raises(PlanError) as error:
        resolve_start_price(DATA, target, prices(**{"R12 start amulet": 1.0}), None)

    assert start_price_key(DATA, target) in str(error.value)
    assert "python -m crafting_system.cli trade" in str(error.value)


def test_a_price_typed_under_the_old_name_of_the_item_is_not_found():
    target = target_at(84, FRACTURED_RESIST)

    with pytest.raises(PlanError):
        resolve_start_price(DATA, target, prices(**{"Paua Amulet (ilvl 84)": 1.0}), None)


def test_a_target_that_does_not_buy_counts_its_start_item_as_free():
    target = target_at(84, FRACTURED_RESIST.replace("buys_start_item: true\n", ""))

    found = resolve_start_price(DATA, target, prices(), None)

    assert (found.name, found.chaos) == (None, 0.0)


def test_the_price_given_on_the_command_line_wins_and_carries_the_computed_key():
    target = target_at(84, FRACTURED_RESIST)

    found = resolve_start_price(DATA, target, prices(), 3.0)

    assert (found.name, found.chaos, found.source) == (start_price_key(DATA, target), 3.0, "given on the command line")


def test_the_old_start_price_key_is_no_longer_read():
    with pytest.raises(Exception, match="start_price"):
        parse(FRACTURED_RESIST + "start_price: R12 start amulet\n")
