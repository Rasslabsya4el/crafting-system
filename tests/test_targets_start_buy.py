"""The bought start item is described once: the buy spec, the trade query and the price key are computed from the target (#474, OR-3).

The data is the small fixture export (`items_support.DATA`): a Paua Amulet pool whose Lightning Resistance tiers need item levels 1, 13,
25, 37, 49, 60, 72 and 84, plus hand-made bases added below (a twin of the amulet, a Battle Royale copy, a base with no trade category).
The real benchmark targets, with the stored price entries, are in `test_start_buy_real.py`.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from start_support import with_start
from targets_support import DATA, parse

from crafting_system.cli._plan import PlanError, resolve_start_price
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.prices.trade_query import BuyMod, BuySpec, TradeSpecError, build_query
from crafting_system.prices.trade_stats import parse_trade_stats, resolve_buy_mod
from crafting_system.targets import StartBuyError, base_in_words, buy_spec_of, parse_target, plain_base_names, start_price_key
from crafting_system.targets.start_buy import (
    TRADE_CATEGORY,
    differences_between_same_name_bases,
    item_level_window,
    same_name_bases,
    shared_name_refusal,
)

AMULET = "Metadata/Items/Amulets/Amulet1"
STATS = parse_trade_stats(json.loads((Path(__file__).parent / "fixtures" / "trade" / "stats_excerpt.json").read_text(encoding="utf-8")))

FRACTURED_RESIST = """\
start: bought
requirements:
  - family: IncreasedLife
start_item:
  rarity: rare
  mods:
    - mod: LightningResist7
      values: [43]
      fractured: true
"""


def target_at(level: int, tail: str, *, base: str = "Paua Amulet", data=DATA):
    return parse_target(with_start(f"base: {base}\nitem_level: {level}\n{tail}"), data, source="t.yaml")


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
    found = buy_spec_of(DATA, target_at(80, f"start: bought\nrequirements:\n  - {requirement}\n", base=name))

    assert found.category == category
    assert found.base_type == name


def test_a_base_class_with_no_trade_category_is_refused_by_name():
    target = target_at(80, "start: bought\nrequirements:\n  - family: IncreasedAttackSpeed\n", base="Rusted Sword")

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
    closed = buy_spec_of(DATA, target_at(81, "start: bought\nrequirements:\n  - family: IncreasedLife\n"))
    open_ = buy_spec_of(DATA, target_at(84, "start: bought\nrequirements:\n  - family: IncreasedLife\n"))

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
        ("", "normal"),  # the test helper states `rarity: normal` for a text with no start_item block (#545)
        ("start_item:\n  rarity: rare\n  mods: []\n", "rare"),  # R08 and R09: the target's rarity is kept, whatever a price file folds in
        ("start_item:\n  rarity: magic\n  mods: []\n", "magic"),
    ],
)
def test_the_rarity_is_the_start_items_even_for_a_rare_with_no_mods(start, rarity):
    spec = buy_spec_of(DATA, target_at(84, f"start: bought\nrequirements:\n  - family: IncreasedLife\n{start}"))

    assert spec.rarity == rarity


def test_a_rare_start_item_with_a_mod_stays_rare():
    assert buy_spec_of(DATA, target_at(84, FRACTURED_RESIST)).rarity == "rare"


# -- the influences ---------------------------------------------------------------------------------------------


def test_the_influences_of_the_start_item_are_in_the_spec_the_query_and_the_key():
    target = target_at(84, "influence: [hunter]\nstart: bought\nrequirements:\n  - family: FireResistance\n", base="Leather Belt")
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
    plain = "start: bought\nrequirements:\n  - family: IncreasedLife\n"
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


TWIN = "Metadata/Items/Amulets/Amulet1Twin"
IMPLICIT_STATS = parse_trade_stats(
    {"result": [{"id": "implicit", "entries": [{"id": "implicit.stat_77", "text": "+# to maximum Life"}, {"id": "implicit.stat_88", "text": "#% increased Mana Regeneration Rate"}]}]}
)


def twin_pair(**fields):
    """(data, spec of the amulet, spec of its twin): the same name, the twin with the fields given."""
    data = with_bases(**{TWIN: fields})
    first = buy_spec_of(data, parse_target(f"base: {AMULET}\nitem_level: 84\n{FRACTURED_RESIST}", data, source="t.yaml"))
    second = buy_spec_of(data, parse_target(f"base: {TWIN}\nitem_level: 84\n{FRACTURED_RESIST}", data, source="t.yaml"))
    return data, first, second


def own_filters(data, spec):
    return [resolve_buy_mod(mod, list(data.mods.values()), IMPLICIT_STATS) for mod in spec.mods if mod.own]


def test_bases_of_one_name_whose_implicits_differ_are_told_apart_by_their_own_implicit_in_the_query():
    data, first, second = twin_pair(implicits=("IncreasedLifeImplicitBelt1",))

    assert first.name != second.name
    assert [(mod.stat, mod.implicit, mod.own, mod.minimum) for mod in first.mods if mod.own] == [("(20-30)% increased Mana Regeneration Rate", True, True, None)]
    assert [found.id for found in own_filters(data, first)] == ["implicit.stat_88"]
    assert [found.id for found in own_filters(data, second)] == ["implicit.stat_77"]
    query = build_query(second, own_filters(data, second)).body()["query"]
    assert query["stats"][0]["filters"] == [{"id": "implicit.stat_77", "disabled": False}]


def test_the_own_implicit_is_part_of_the_base_so_the_spec_needs_no_corrupted_item_but_a_bought_implicit_still_does():
    _, first, _ = twin_pair(implicits=("IncreasedLifeImplicitBelt1",))

    assert first.corrupted is False
    with pytest.raises(TradeSpecError, match="corrupted"):
        BuySpec("x", category="accessory.amulet", mods=(BuyMod("(20-30)% increased Mana Regeneration Rate", implicit=True),))
    with pytest.raises(TradeSpecError, match="own"):
        BuyMod("x", own=True)


def test_bases_of_one_name_whose_implicits_read_alike_are_not_told_apart_and_ask_for_no_implicit():
    """The two Penetrating Arrow Quivers have two implicit mods with the same text, and the same pool."""
    _, first, second = twin_pair(implicits=("ManaRegenerationImplicitAmulet1",))

    assert first.name != second.name
    assert replace(first, name="x") == replace(second, name="x")
    assert not any(mod.own for mod in first.mods)


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


def test_a_target_that_gives_its_start_item_has_a_given_start_item_that_costs_nothing():
    target = target_at(84, FRACTURED_RESIST.replace("start: bought\n", "start: given\n"))

    found = resolve_start_price(DATA, target, prices(), None)

    assert (found.name, found.chaos, found.given) == (None, 0.0, True)


def test_the_price_given_on_the_command_line_wins_and_carries_the_computed_key():
    target = target_at(84, FRACTURED_RESIST)

    found = resolve_start_price(DATA, target, prices(), 3.0)

    assert (found.name, found.chaos, found.source) == (start_price_key(DATA, target), 3.0, "given on the command line")


def test_the_old_start_price_key_is_no_longer_read():
    with pytest.raises(Exception, match="start_price"):
        parse(FRACTURED_RESIST + "start_price: R12 start amulet\n")


# -- the minimum is the number of the mod's stat, not a number read from its text ----------------------------------


def test_the_minimum_is_the_low_end_of_the_stat_range_even_where_the_text_shows_another_number():
    """LifeLeechPermyriadSuffix1's text says (0.2-0.4)% and its stat range is 20 to 40: the minimum is read from the stat."""
    text = FRACTURED_RESIST.replace("LightningResist7", "LifeLeechPermyriadSuffix1").replace("[43]", "[30]")

    (mod,) = buy_spec_of(DATA, target_at(84, text)).mods

    assert mod.minimum == 20


# -- a price taken for another item says so -------------------------------------------------------------------------


def wider_prices(change):
    """A price file whose entry for the target of FRACTURED_RESIST at item level 76 keeps a search that `change` altered."""
    target = target_at(76, FRACTURED_RESIST)
    spec = buy_spec_of(DATA, target)
    body = build_query(spec, [resolve_buy_mod(mod, list(DATA.mods.values()), STATS) for mod in spec.mods]).body()
    change(body["query"])
    entry = PriceEntry(7.5, "trade-api", "a note", {"query": body})
    return target, PriceFile("Allflame", prices_date(), 400.0, {spec.name: entry})


def prices_date():
    from datetime import UTC, datetime

    return datetime(2026, 11, 1, tzinfo=UTC)


def test_a_price_whose_stored_search_is_the_computed_one_says_nothing():
    target, prices = wider_prices(lambda query: None)

    assert resolve_start_price(DATA, target, prices, None).taken_for is None


def test_a_price_whose_stored_search_was_wider_in_item_level_says_what_it_was_taken_for():
    target, prices = wider_prices(lambda query: query["filters"]["misc_filters"]["filters"].__setitem__("ilvl", {"min": 76}))

    found = resolve_start_price(DATA, target, prices, None)

    assert found.taken_for == "price taken for a wider item (item level 76 or more)"
    assert found.chaos == 7.5  # the number is the stored one: only the line is new


def test_a_price_taken_for_another_rarity_and_with_no_base_type_says_both():
    def change(query):
        query["filters"]["type_filters"]["filters"]["rarity"] = {"option": "nonunique"}
        del query["type"]

    target, prices = wider_prices(change)

    found = resolve_start_price(DATA, target, prices, None)

    assert found.taken_for == "price taken for another item (rarity nonunique, any amulet base)"


def test_a_lower_minimum_is_a_wider_item_and_a_price_with_no_stored_search_has_no_line():
    def change(query):
        del query["stats"][0]["filters"][0]["value"]

    target, prices = wider_prices(change)

    assert resolve_start_price(DATA, target, prices, None).taken_for == "price taken for a wider item (a lower minimum)"
    plain = PriceFile("Allflame", prices_date(), 400.0, {start_price_key(DATA, target): PriceEntry(2.0, "poe.ninja")})
    assert resolve_start_price(DATA, target, plain, None).taken_for is None


CORRUPTED_RESIST = FRACTURED_RESIST.replace("start: bought\n", "start: bought\nallow_corrupted: true\n").replace(
    "      fractured: true\n", "      fractured: true\n  corrupted: true\n"
)


def test_a_price_whose_stored_search_has_no_corruption_filter_was_taken_for_a_wider_item():
    def change(query):
        del query["filters"]["misc_filters"]["filters"]["corrupted"]

    target, prices = wider_prices(change)

    found = resolve_start_price(DATA, target, prices, None)

    assert found.taken_for == "price taken for a wider item (corrupted or not)"
    assert found.chaos == 7.5


def test_a_price_taken_for_corrupted_items_says_it_was_taken_for_another_item_that_is_corrupted():
    def change(query):
        query["filters"]["misc_filters"]["filters"]["corrupted"] = {"option": "true"}

    target, prices = wider_prices(change)

    assert resolve_start_price(DATA, target, prices, None).taken_for == "price taken for another item (corrupted)"


def test_a_corrupted_start_item_priced_by_a_search_for_uncorrupted_items_says_it_was_taken_for_another_item_not_corrupted():
    target = target_at(76, CORRUPTED_RESIST)
    _, uncorrupted = wider_prices(lambda query: None)
    (entry,) = uncorrupted.prices.values()
    prices = PriceFile("Allflame", prices_date(), 400.0, {start_price_key(DATA, target): entry})  # a search for uncorrupted items stored under the corrupted key

    assert buy_spec_of(DATA, target).corrupted is True
    assert resolve_start_price(DATA, target, prices, None).taken_for == "price taken for another item (not corrupted)"


# -- two items that differ in one thing read two price entries (#471, OR-3) ------------------------------------------


def only_priced(data, target) -> PriceFile:
    """A price file that prices the start item of `target` and nothing else."""
    return PriceFile("Allflame", prices_date(), 400.0, {start_price_key(data, target): PriceEntry(7.5, "trade-api")})


def reads_other_entries(data, first, second) -> bool:
    """True when the price file of `first` does not serve `second` (it has no entry for it) and the other way round."""
    for priced, other in ((first, second), (second, first)):
        assert resolve_start_price(data, priced, only_priced(data, priced), None).chaos == 7.5
        with pytest.raises(PlanError, match="no price for the start item"):
            resolve_start_price(data, other, only_priced(data, priced), None)
    return True


def test_two_targets_that_differ_only_in_corruption_read_two_price_entries():
    plain = target_at(84, FRACTURED_RESIST)
    corrupted = target_at(84, CORRUPTED_RESIST)

    assert start_price_key(DATA, corrupted) == "Paua Amulet, item level 84-100, corrupted, fractured +(42-45)% to Lightning Resistance"
    assert reads_other_entries(DATA, plain, corrupted)


def test_two_targets_that_differ_only_in_base_id_read_two_price_entries():
    data = with_bases(**{TWIN: {}})
    first = parse_target(f"base: {AMULET}\nitem_level: 84\n{FRACTURED_RESIST}", data, source="t.yaml")
    second = parse_target(f"base: {TWIN}\nitem_level: 84\n{FRACTURED_RESIST}", data, source="t.yaml")

    assert reads_other_entries(data, first, second)


def test_two_targets_that_differ_only_in_rarity_read_two_price_entries():
    plain = "start: bought\nrequirements:\n  - family: IncreasedLife\n"
    rare = target_at(84, plain + "start_item:\n  rarity: rare\n  mods: []\n")
    magic = target_at(84, plain + "start_item:\n  rarity: magic\n  mods: []\n")

    assert reads_other_entries(DATA, rare, magic)


def test_two_targets_that_differ_only_in_influences_read_two_price_entries():
    tail = "start: bought\nrequirements:\n  - family: FireResistance\n"

    assert reads_other_entries(
        DATA, target_at(84, tail, base="Leather Belt"), target_at(84, "influence: [hunter]\n" + tail, base="Leather Belt")
    )


# -- a poe.ninja line prices the bases of a shared name only when they are one item to a crafter (#471) ------------


def ninja_prices(data, target, source="poe.ninja") -> PriceFile:
    return PriceFile("Allflame", prices_date(), 400.0, {start_price_key(data, target): PriceEntry(9.0, source)})


def shared_amulet(**fields):
    """The amulet and a twin of its name, the twin with the fields given; the target is the amulet."""
    data = with_bases(**{TWIN: fields})
    return data, parse_target(f"base: {AMULET}\nitem_level: 84\n{FRACTURED_RESIST}", data, source="t.yaml")


LEGACY_TAG = {"tags": ("amulet", "default", "trade_market_legacy_item")}  # a tag no mod reads, like the real Quiver12's
DIFFERENT_CLASS = {"item_class": "Ring"}
DIFFERENT_IMPLICIT = {"implicits": ("IncreasedLifeImplicitBelt1",)}
DIFFERENT_MOD_TAGS = {"tags": ("ring", "default")}  # both tags are read by mod weights: the pool differs


@pytest.mark.parametrize("fields", [{}, LEGACY_TAG], ids=["identical twin", "twin with a tag no mod reads"])
def test_a_poe_ninja_price_of_a_shared_name_prices_a_base_whose_twins_agree_in_class_implicits_and_tags(fields):
    data, target = shared_amulet(**fields)

    assert shared_name_refusal(data, AMULET, "poe.ninja", "x") is None
    assert resolve_start_price(data, target, ninja_prices(data, target), None).chaos == 9.0


@pytest.mark.parametrize(
    ("fields", "differ"),
    [(DIFFERENT_CLASS, "item class"), (DIFFERENT_IMPLICIT, "implicit mods"), (DIFFERENT_MOD_TAGS, "mod tags")],
    ids=["item class", "implicit mods", "mod tags"],
)
def test_a_poe_ninja_price_is_refused_for_a_shared_name_when_the_bases_differ_in_one_thing(fields, differ):
    data, target = shared_amulet(**fields)

    with pytest.raises(PlanError) as error:
        resolve_start_price(data, target, ninja_prices(data, target), None)

    assert str(error.value) == (
        "the price of the start item 'Paua Amulet [Amulet1], item level 84-100, fractured +(42-45)% to Lightning Resistance' is refused: "
        f"it comes from poe.ninja, whose line has a name and no base id, and the name 'Paua Amulet' belongs to 2 bases that differ in {differ}, "
        "so the line is the price of none of them. Price this base on the trade site, or write its price by hand"
    )


def test_the_refusal_names_every_thing_that_differs():
    data, _ = shared_amulet(**DIFFERENT_CLASS, **DIFFERENT_IMPLICIT)

    assert differences_between_same_name_bases(data, AMULET) == ("item class", "implicit mods")


@pytest.mark.parametrize("source", ["poe.ninja-history", "poe.ninja-previous-league", "poe.watch"])
def test_every_name_only_source_is_refused_for_a_shared_name_that_differs_and_says_which(source):
    data, target = shared_amulet(**DIFFERENT_IMPLICIT)

    with pytest.raises(PlanError, match=f"it comes from {source}, whose line has a name and no base id"):
        resolve_start_price(data, target, ninja_prices(data, target, source), None)


@pytest.mark.parametrize("source", ["trade-api", "hand", "override"])
def test_a_price_from_another_source_is_kept_for_a_shared_name_that_differs(source):
    data, target = shared_amulet(**DIFFERENT_IMPLICIT)

    assert resolve_start_price(data, target, ninja_prices(data, target, source), None).chaos == 9.0


def test_a_poe_ninja_price_is_kept_for_a_name_one_base_has():
    target = target_at(84, FRACTURED_RESIST)

    assert resolve_start_price(DATA, target, ninja_prices(DATA, target), None).chaos == 9.0


def test_the_price_given_on_the_command_line_is_kept_for_a_shared_name_that_differs():
    data, target = shared_amulet(**DIFFERENT_IMPLICIT)

    assert resolve_start_price(data, target, ninja_prices(data, target), 3.0).chaos == 3.0


# -- the page names a base by its game name, never its id (#553, #481) -------------------------------------------------------


def test_two_bases_of_one_name_are_told_apart_in_words_by_class_then_implicit_then_pool():
    assert base_in_words(DATA, AMULET) == ""
    data, _ = shared_amulet(**DIFFERENT_CLASS)
    assert base_in_words(data, TWIN) == "item class Ring" and base_in_words(data, AMULET) == "item class Amulet"
    data, _ = shared_amulet(**DIFFERENT_IMPLICIT)
    assert base_in_words(data, TWIN) == "the implicit +(25-40) to maximum Life"
    assert base_in_words(data, AMULET) == "the implicit (20-30)% increased Mana Regeneration Rate"
    data, _ = shared_amulet(**DIFFERENT_MOD_TAGS)
    assert base_in_words(data, TWIN) == "a different pool of mods"
    data, _ = shared_amulet(**DIFFERENT_CLASS, **DIFFERENT_IMPLICIT)
    assert base_in_words(data, TWIN) == "item class Ring, the implicit +(25-40) to maximum Life"


@pytest.mark.parametrize("fields", [{}, LEGACY_TAG], ids=["identical twin", "twin with a tag no mod reads"])
def test_two_bases_that_play_alike_are_said_to_play_alike_and_not_told_by_an_id(fields):
    data, _ = shared_amulet(**fields)

    assert base_in_words(data, AMULET) == base_in_words(data, TWIN) == "one of 2 bases of this name that play alike"


def test_the_price_name_of_a_shared_base_is_said_in_words_for_the_page_and_keeps_its_id_in_the_key():
    data, target = shared_amulet(**DIFFERENT_IMPLICIT)
    key = start_price_key(data, target)

    assert key.startswith("Paua Amulet [Amulet1], ")  # the key of the price file and the JSON is not changed
    shown = plain_base_names(data, key)
    assert shown.startswith("Paua Amulet (the implicit (20-30)% increased Mana Regeneration Rate), item level 84-100")
    assert "[" not in shown and "Amulet1" not in shown


def test_the_vendor_line_of_a_shared_base_is_said_in_words_and_a_bracket_that_is_no_base_is_left():
    data, _ = shared_amulet(**LEGACY_TAG)

    assert plain_base_names(data, "Paua Amulet [Amulet1] (ilvl 86)") == "Paua Amulet (one of 2 bases of this name that play alike) (ilvl 86)"
    assert plain_base_names(data, "Lion Pelt (ilvl 84)") == "Lion Pelt (ilvl 84)"
    assert plain_base_names(data, "an item [not a base]") == "an item [not a base]"
    assert plain_base_names(DATA, "Paua Amulet [Amulet1], item level 84") == "Paua Amulet [Amulet1], item level 84"  # a name one base has has no id to say
    assert plain_base_names(DATA, "price [default]") == "price [default]"


def test_an_item_class_is_named_without_an_article_so_no_a_or_an_is_guessed():
    data, _ = shared_amulet(item_class="One Hand Sword")

    assert base_in_words(data, TWIN) == "item class One Hand Sword"  # not "an one hand sword" (the Energy Blade bases)
