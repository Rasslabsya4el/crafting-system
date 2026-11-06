"""Unit tests of the reconcile code on tiny hand-made files (ticket #412). No real game data, no real example file."""

import json
from copy import deepcopy

import pytest
import yaml

from .checks import Disagreement, _pool_differences, check_ids, reconcile, reconcile_files, slots
from .export import Export, ExportMissing, load_export, version_folder
from .files import (
    FileFormatError,
    buy_spec_of,
    price_files_of,
    priced_base_name,
    priced_category,
    priced_item_level,
    priced_rarity,
    read_buy_spec,
    read_buy_specs,
    read_price_entry,
    read_target,
)
from .ladder import (
    base_ids_of,
    bases_named,
    bases_of_category,
    is_royale,
    ladder,
    normalise_stat_text,
    pool_of,
    spawn_weight,
    stat_ranges,
)

RING = "Metadata/Items/Rings/Ring1"
RING2 = "Metadata/Items/Rings/Ring2"
TWIN_A = "Metadata/Items/Boots/TwinA"
TWIN_B = "Metadata/Items/Boots/TwinB"


def _mod(type_, level, low, high, spawn, *, generation="suffix", domain="item", text=None):
    return {
        "type": type_,
        "generation_type": generation,
        "domain": domain,
        "required_level": level,
        "spawn_weights": [{"tag": tag, "weight": weight} for tag, weight in spawn] + [{"tag": "default", "weight": 0}],
        "stats": [{"id": "stat", "min": low, "max": high}],
        "text": text or f"+({low}-{high})% to Resist",
    }


def _base(name, item_class, tags, release="released"):
    return {"name": name, "item_class": item_class, "tags": tags, "release_state": release, "domain": "item"}


EXPORT = Export(
    mods={
        "ResA1": _mod("ResA", 1, 6, 11, [("ring", 1000)]),
        "ResA2": _mod("ResA", 13, 12, 17, [("ring", 1000)]),
        "ResA3": _mod("ResA", 25, 18, 23, [("ring", 1000)]),
        "ResAOff": _mod("ResA", 40, 24, 29, [("ring", 0)]),  # weight 0 on rings: not on the ladder
        "ResAAmuletOnly": _mod("ResA", 50, 30, 35, [("amulet", 1000)]),
        "ResAFirstZero": _mod("ResA", 60, 36, 41, [("ring", 0), ("default", 1000)]),  # the first matching entry decides
        "ResBType": _mod("ResB", 70, 40, 45, [("ring", 1000)]),  # another type
        "ResCrafted": _mod("ResA", 80, 46, 48, [("ring", 1000)], domain="crafted"),
        "ResPrefix": _mod("ResA", 90, 50, 52, [("ring", 1000)], generation="prefix"),
        "TieA": _mod("Tie", 10, 1, 2, [("ring", 1)], text="tie a"),
        "TieB": _mod("Tie", 10, 3, 4, [("ring", 1)], text="tie b"),
        "TieLow": _mod("Tie", 5, 0, 1, [("ring", 1)], text="tie low"),
        "Speed1": _mod("Speed", 55, 30, 30, [("ring", 1)], text="30% increased Movement Speed"),
        "ResA2Royale": _mod("ResA", 5, 20, 30, [("ring", 1000)]),  # a Battle Royale copy that can spawn (#248): never on the ladder
    },
    bases={
        RING: _base("Ruby Ring", "Ring", ["ring", "default"]),
        RING2: _base("Sapphire Ring", "Ring", ["ring", "default"]),
        "Metadata/Items/Rings/Old": _base("Ruby Ring", "Ring", ["ring", "default"], release="removed"),
        TWIN_A: _base("Twin Boots", "Boots", ["boots", "default"]),
        TWIN_B: _base("Twin Boots", "Boots", ["boots", "default"]),
        "Metadata/Items/Amulets/A": _base("Gold Amulet", "Amulet", ["amulet", "default"]),
        "Metadata/Items/Rings/RingRoyale9": _base("Ruby Ring", "Ring", ["not_for_sale", "ring", "default"]),
        "Metadata/Items/Belts/Belt3": _base("Cloth Belt", "Belt", ["belt", "default"]),
        "Metadata/Items/Belts/BeltRoyale1": _base("Cloth Belt", "Belt", ["not_for_sale", "belt", "default"]),
        "Metadata/Items/Boots/Atlas1": _base("Pied Boots", "Boots", ["not_for_sale", "boots", "default"]),
        "Metadata/Items/Boots/Atlas2": _base("Pied Boots", "Boots", ["not_for_sale", "boots", "default"]),
    },
)

TARGET = {
    "base": "Ruby Ring",
    "item_level": 80,
    "influence": [],
    "requirements": [{"family": "ResA"}],
    "start_item": {"rarity": "rare", "mods": [{"mod": "ResA2", "tier": 2, "values": [14], "fractured": True}]},
    "start": "bought",
    "start_price": "T start ring",
}
SPEC = {
    "name": "T start ring",
    "base_type": "Ruby Ring",
    "category": "accessory.ring",
    "rarity": "rare",
    "item_level_min": 80,
    "corrupted": False,
    "mods": [{"stat": "+#% to Resist", "minimum": 12, "fractured": True}],
}
ENTRY = {
    "chaos": 5.0,
    "source": "trade-api",
    "detail": {
        "query": {
            "query": {
                "filters": {
                    "misc_filters": {"filters": {"ilvl": {"min": 80}}},
                    "type_filters": {"filters": {"category": {"option": "accessory.ring"}, "rarity": {"option": "rare"}}},
                },
                "type": "Ruby Ring",
            }
        }
    },
}


def _write(tmp_path, name, document):
    path = tmp_path / name
    if name.endswith(".json"):
        path.write_text(json.dumps(document), encoding="utf-8")
    else:
        path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def _run(tmp_path, *, target=None, spec=None, entry=None, export=EXPORT):
    """Write the three files (each with the given changes applied) and reconcile them."""
    target_doc, spec_doc, entry_doc = deepcopy(TARGET), deepcopy(SPEC), deepcopy(ENTRY)
    for document, change in ((target_doc, target), (spec_doc, spec), (entry_doc, entry)):
        if change:
            change(document)
    target_file = read_target(_write(tmp_path, "t.yaml", target_doc))
    spec_file = read_buy_spec(_write(tmp_path, "b.yaml", spec_doc))
    price_path = _write(tmp_path, "prices.json", {"prices": {"T start ring": entry_doc}})
    found = read_price_entry(price_path, "T start ring")
    return reconcile(target_file, spec_file, export, [found])


def _bad(result):
    return {slot: [str(item) for item in items] for slot, items in result.items() if items}


# --- the ladder ----------------------------------------------------------------------------------------


def test_the_ladder_orders_by_required_level_with_tier_1_the_highest():
    tiers = ladder(EXPORT.mods, ["ring", "default"], "item", "ResA2")

    assert tiers == {"ResA3": 1, "ResA2": 2, "ResA1": 3}


def test_the_ladder_leaves_out_zero_weight_other_type_other_domain_other_generation_and_other_base_mods():
    tiers = ladder(EXPORT.mods, ["ring", "default"], "item", "ResA1")

    assert set(tiers) == {"ResA1", "ResA2", "ResA3"}


def test_a_battle_royale_mod_that_can_spawn_is_not_on_the_ladder_and_does_not_shift_the_tiers():
    tiers = ladder(EXPORT.mods, ["ring", "default"], "item", "ResA1")

    assert "ResA2Royale" not in tiers
    assert tiers["ResA1"] == 3  # tier 4 if the Royale copy (level 5) counted
    assert spawn_weight(EXPORT.mods["ResA2Royale"], ["ring"]) > 0
    assert is_royale("ResA2Royale") and is_royale("Metadata/Items/Belts/BeltRoyale1") and not is_royale("ResA2")


def test_the_first_matching_spawn_entry_decides_the_weight():
    mod = EXPORT.mods["ResAFirstZero"]

    assert spawn_weight(mod, ["ring", "default"]) == 0
    assert spawn_weight(mod, ["default"]) == 1000
    assert spawn_weight(mod, ["amulet"]) == 0  # no entry matches


def test_a_ladder_on_another_base_has_other_members():
    assert ladder(EXPORT.mods, ["amulet"], "item", "ResAAmuletOnly") == {"ResAAmuletOnly": 1}


def test_mods_that_tie_on_the_required_level_share_a_tier_and_the_next_one_skips():
    tiers = ladder(EXPORT.mods, ["ring", "default"], "item", "TieLow")

    assert tiers == {"TieA": 1, "TieB": 1, "TieLow": 3}


def test_a_mod_that_cannot_spawn_on_the_base_is_absent_from_its_own_ladder():
    assert "ResAAmuletOnly" not in ladder(EXPORT.mods, ["ring", "default"], "item", "ResAAmuletOnly")


def test_the_ladder_does_not_depend_on_the_order_of_the_mods():
    reversed_mods = dict(reversed(list(EXPORT.mods.items())))

    assert ladder(reversed_mods, ["ring", "default"], "item", "ResA2") == ladder(EXPORT.mods, ["ring", "default"], "item", "ResA2")


def test_stat_ranges_follow_the_order_of_the_stats():
    assert stat_ranges(EXPORT.mods["ResA2"]) == [(12, 17)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("+(13-16) to all Attributes", "+# to all Attributes"),
        ("+#% to Lightning Resistance", "+#% to Lightning Resistance"),
        ("30% increased Movement Speed", "#% increased Movement Speed"),
        ("(5-10)% increased Rarity\n+1 to Level", "#% increased Rarity\n+# to Level"),
        ("  +(1.5-2.5)   per second ", "+# per second"),
    ],
)
def test_normalise_stat_text(text, expected):
    assert normalise_stat_text(text) == expected


def test_base_ids_of_reads_an_id_a_name_a_shared_name_and_ignores_unreleased_bases():
    assert base_ids_of(EXPORT.bases, RING) == [RING]
    assert base_ids_of(EXPORT.bases, "Ruby Ring") == [RING]  # the removed base of the same name is not one
    assert base_ids_of(EXPORT.bases, "Twin Boots") == [TWIN_A, TWIN_B]
    assert base_ids_of(EXPORT.bases, "No Such Base") == []
    assert bases_named(EXPORT.bases, "Twin Boots") == [TWIN_A, TWIN_B]


def test_a_royale_base_is_not_a_namesake_and_a_not_for_sale_one_is_dropped_only_if_others_are_on_sale():
    assert bases_named(EXPORT.bases, "Cloth Belt") == ["Metadata/Items/Belts/Belt3"]  # the Royale belt is no second base
    assert bases_named(EXPORT.bases, "Pied Boots") == ["Metadata/Items/Boots/Atlas1", "Metadata/Items/Boots/Atlas2"]  # all not for sale: all stay
    assert bases_named(EXPORT.bases, "Ruby Ring") == [RING]  # the Royale ring and the removed ring are not namesakes


def test_the_bases_of_a_category_are_the_released_royale_free_ones_on_sale():
    assert bases_of_category(EXPORT.bases, "accessory.ring") == [RING, RING2]
    assert bases_of_category(EXPORT.bases, "armour.boots") == [TWIN_A, TWIN_B]
    assert bases_of_category(EXPORT.bases, "no.such") == []


def test_the_pool_of_a_base_is_its_ordinary_spawnable_mods_without_royale_copies():
    pool = pool_of(EXPORT.mods, ["ring", "default"], "item")

    assert "ResA1" in pool and "ResA3" in pool
    assert "ResA2Royale" not in pool and "ResCrafted" not in pool and "ResAOff" not in pool
    cache = {}
    assert pool_of(EXPORT.mods, ["ring", "default"], "item", cache) == pool
    assert pool_of(EXPORT.mods, ["default", "ring"], "item", cache) is cache[(id(EXPORT.mods), "item", ("default", "ring"))]


JEWEL_MODS = {
    "IncreasedLife": _mod("Life", 1, 5, 9, [("default", 1000)], generation="prefix"),  # item domain, a default weight: no jewel mod
    "LifeRegeneration": _mod("Regen", 1, 1, 2, [("default", 1000)]),
    "JewelLife": _mod("JewelLife", 1, 5, 9, [("jewel", 1000)], generation="prefix", domain="misc"),
    "JewelResist": _mod("JewelResist", 1, 3, 5, [("jewel", 1000)], domain="misc"),
    "RingResist": _mod("RingResist", 1, 3, 5, [("ring", 1000)]),
}


def test_the_pool_of_a_jewel_is_its_own_domain_not_the_item_domain_mods_with_a_default_weight():
    jewel_tags = ["jewel", "default"]

    assert pool_of(JEWEL_MODS, jewel_tags, "misc") == {"JewelLife", "JewelResist"}
    assert pool_of(JEWEL_MODS, jewel_tags, "item") == {"IncreasedLife", "LifeRegeneration"}  # what every base used to get
    assert pool_of(JEWEL_MODS, ["ring", "default"], "item") == {"IncreasedLife", "LifeRegeneration", "RingResist"}


def test_the_pool_cache_keeps_the_domains_of_one_tag_list_apart():
    cache = {}

    assert pool_of(JEWEL_MODS, ["jewel", "default"], "misc", cache) == {"JewelLife", "JewelResist"}
    assert pool_of(JEWEL_MODS, ["jewel", "default"], "item", cache) == {"IncreasedLife", "LifeRegeneration"}
    assert pool_of(JEWEL_MODS, ["jewel", "default"], "misc", cache) == {"JewelLife", "JewelResist"}
    assert len(cache) == 2


def test_the_pools_the_checks_compare_are_those_of_each_base_own_domain():
    jewel = {"name": "Cobalt Jewel", "item_class": "Jewel", "tags": ["jewel", "default"], "release_state": "released", "domain": "misc"}
    other_jewel = {**jewel, "name": "Crimson Jewel", "tags": ["jewel", "default"]}
    ring = _base("Ruby Ring", "Ring", ["ring", "default"])
    export = Export(mods=JEWEL_MODS, bases={"Metadata/Jewel1": jewel, "Metadata/Jewel2": other_jewel, RING: ring})

    assert _pool_differences(export, ["Metadata/Jewel1"], ["Metadata/Jewel2"]) == []
    assert _pool_differences(export, ["Metadata/Jewel1"], [RING]) == [f"{RING} (+3 -2)"]  # 3 ring-side mods in, the 2 jewel mods out


# --- the files -----------------------------------------------------------------------------------------


def test_a_target_without_start_item_starts_normal_and_one_with_mods_and_no_rarity_starts_rare(tmp_path):
    bare = read_target(_write(tmp_path, "a.yaml", {"base": "X", "item_level": 1}))
    unnamed = read_target(
        _write(tmp_path, "b.yaml", {"base": "X", "item_level": 1, "start_item": {"mods": [{"mod": "M"}]}})
    )
    empty = read_target(_write(tmp_path, "c.yaml", {"base": "X", "item_level": 1, "start_item": {}}))
    written = read_target(
        _write(tmp_path, "d.yaml", {"base": "X", "item_level": 1, "start_item": {"rarity": "magic"}})
    )

    assert (bare.rarity, unnamed.rarity, empty.rarity, written.rarity) == ("normal", "rare", "normal", "magic")
    assert unnamed.start_mods[0].tier is None and unnamed.start_mods[0].values == ()


def test_a_target_without_a_base_or_item_level_is_a_format_error(tmp_path):
    with pytest.raises(FileFormatError, match="no `base`"):
        read_target(_write(tmp_path, "a.yaml", {"item_level": 1}))
    with pytest.raises(FileFormatError, match="top level"):
        read_target(_write(tmp_path, "b.yaml", ["not", "a", "mapping"]))


def test_the_price_file_of_a_target_is_relative_to_its_folder(tmp_path):
    (tmp_path / "sub").mkdir()
    target = read_target(
        _write(tmp_path / "sub", "t.yaml", {"base": "X", "item_level": 1, "price_file": "../prices.json"})
    )

    assert target.price_file == (tmp_path / "prices.json").resolve()


def test_the_buy_spec_of_a_target_is_the_one_named_by_its_start_price(tmp_path):
    target = read_target(_write(tmp_path, "t.yaml", TARGET))
    one = read_buy_spec(_write(tmp_path, "one.yaml", SPEC))
    other = read_buy_spec(_write(tmp_path, "two.yaml", {**SPEC, "name": "Other"}))
    twin = read_buy_spec(_write(tmp_path, "three.yaml", SPEC))
    unpriced = read_target(_write(tmp_path, "u.yaml", {"base": "X", "item_level": 1}))

    assert buy_spec_of(target, [other, one]) is one
    assert buy_spec_of(target, [other]) is None
    assert buy_spec_of(unpriced, [one]) is None
    with pytest.raises(FileFormatError, match="2 buy specs"):
        buy_spec_of(target, [one, twin])


def test_read_buy_specs_reads_a_folder_in_name_order(tmp_path):
    _write(tmp_path, "b.yaml", {**SPEC, "name": "B"})
    _write(tmp_path, "a.yaml", {**SPEC, "name": "A"})

    assert [spec.name for spec in read_buy_specs(tmp_path)] == ["A", "B"]


def test_price_files_are_found_by_the_start_price_key_or_the_targets_own_price_file(tmp_path):
    prices = tmp_path / "prices"
    prices.mkdir()
    _write(prices, "one.json", {"prices": {"T start ring": ENTRY}})
    _write(prices, "two.json", {"prices": {"Other": ENTRY}})
    _write(prices, "three.json", {"prices": {"T start ring": ENTRY}})
    target = read_target(_write(tmp_path, "t.yaml", TARGET))
    explicit = read_target(_write(tmp_path, "e.yaml", {**TARGET, "price_file": "prices/two.json"}))
    missing = read_target(_write(tmp_path, "m.yaml", {**TARGET, "price_file": "prices/none.json"}))
    unpriced = read_target(_write(tmp_path, "u.yaml", {"base": "X", "item_level": 1}))

    assert [path.name for path in price_files_of(target, prices)] == ["one.json", "three.json"]
    assert [path.name for path in price_files_of(explicit, prices)] == ["two.json"]
    assert price_files_of(missing, prices) == []
    assert price_files_of(unpriced, prices) == []
    assert read_price_entry(prices / "two.json", "T start ring") is None


def test_the_priced_base_and_item_level_come_from_the_query_else_from_the_key(tmp_path):
    path = _write(
        tmp_path,
        "p.json",
        {
            "prices": {
                "T start ring": ENTRY,
                "Lion Pelt, normal, item level 84": {"chaos": 2, "source": "hand"},
                "Thicket Bow, normal, item level 78-79, Hunter influence": {"chaos": 2, "source": "ninja"},
                "R12 start amulet": {"chaos": 1, "source": "trade-api"},
            }
        },
    )
    by_query = read_price_entry(path, "T start ring")
    by_key = read_price_entry(path, "Lion Pelt, normal, item level 84")
    hunter = read_price_entry(path, "Thicket Bow, normal, item level 78-79, Hunter influence")
    none = read_price_entry(path, "R12 start amulet")

    assert (priced_base_name(by_query), priced_item_level(by_query), priced_category(by_query)) == ("Ruby Ring", (80, "query"), "accessory.ring")
    assert (priced_base_name(by_key), priced_item_level(by_key), priced_category(by_key)) == ("Lion Pelt", (84, "label"), None)
    assert (priced_base_name(hunter), priced_item_level(hunter)) == ("Thicket Bow", (78, "label"))
    assert (priced_base_name(none), priced_item_level(none)) == (None, (None, ""))


def test_a_base_id_in_brackets_in_a_key_is_a_label_and_a_query_with_no_type_prices_every_base_whatever_the_key_says(tmp_path):
    path = _write(
        tmp_path,
        "p.json",
        {
            "prices": {
                "Two-Toned Boots [BootsAtlas1], normal, item level 86-100": {"chaos": 5, "source": "poe.ninja"},
                "Amethyst Ring, item level 75, fractured +(13-16) to all Attributes": {
                    "chaos": 2,
                    "source": "trade-api",
                    "detail": {"query": {"query": {"filters": {"type_filters": {"filters": {"category": {"option": "accessory.ring"}}}}}}},
                },
            }
        },
    )

    labelled = read_price_entry(path, "Two-Toned Boots [BootsAtlas1], normal, item level 86-100")
    category_only = read_price_entry(path, "Amethyst Ring, item level 75, fractured +(13-16) to all Attributes")

    assert (priced_base_name(labelled), priced_item_level(labelled)) == ("Two-Toned Boots", (86, "label"))
    assert (priced_base_name(category_only), priced_category(category_only)) == (None, "accessory.ring")


def test_a_poe_ninja_line_has_its_own_item_level_in_the_note_which_wins_over_the_label(tmp_path):
    path = _write(
        tmp_path,
        "p.json",
        {
            "prices": {
                "Quiver [Q5], normal, item level 81": {"chaos": 9, "source": "poe.ninja", "note": "the cheapest normal Quiver line of item level 81 or more with at least 5 observations (item level 85, 43 observations); no line below item level 82"},
                "Belt, normal, item level 86-100": {"chaos": 9, "source": "poe.ninja", "note": "poe.ninja BaseType overview: a normal Belt of item level 86, 41 observations"},
                "Only, item level 70": {"chaos": 9, "source": "poe.ninja", "note": "item level 81 or more, no line below item level 82"},
            }
        },
    )

    assert priced_item_level(read_price_entry(path, "Quiver [Q5], normal, item level 81")) == (85, "note")
    assert priced_item_level(read_price_entry(path, "Belt, normal, item level 86-100")) == (86, "note")
    assert priced_item_level(read_price_entry(path, "Only, item level 70")) == (70, "label")  # "81 or more" is a floor, not a record


# --- the export ----------------------------------------------------------------------------------------


def test_the_export_is_read_from_the_pinned_version_folder(tmp_path):
    pin = tmp_path / "PIN.json"
    pin.write_text(json.dumps({"version": "9.9"}), encoding="utf-8")
    folder = tmp_path / "cache" / "repoe-fork" / "9.9"
    folder.mkdir(parents=True)
    (folder / "mods.json").write_text(json.dumps({"M": {}}), encoding="utf-8")
    (folder / "base_items.json").write_text(json.dumps({"B": {}}), encoding="utf-8")

    export = load_export(tmp_path / "cache", pin)

    assert version_folder(tmp_path / "cache", pin) == folder
    assert export.mods == {"M": {}} and export.bases == {"B": {}}


def test_a_missing_export_file_is_reported_with_its_folder(tmp_path):
    pin = tmp_path / "PIN.json"
    pin.write_text(json.dumps({"version": "9.9"}), encoding="utf-8")
    (tmp_path / "cache" / "repoe-fork" / "9.9").mkdir(parents=True)

    with pytest.raises(ExportMissing, match="mods.json is not in"):
        load_export(tmp_path / "cache", pin)


def test_with_no_pin_the_only_version_folder_is_used_and_two_are_refused(tmp_path):
    holder = tmp_path / "repoe-fork"
    (holder / "1.0").mkdir(parents=True)

    assert version_folder(tmp_path, None) == holder / "1.0"
    (holder / "2.0").mkdir()
    with pytest.raises(ExportMissing, match="2 version folders"):
        version_folder(tmp_path, None)


def test_a_pin_file_that_is_given_but_absent_or_without_a_version_is_an_error_not_a_fallback(tmp_path):
    (tmp_path / "repoe-fork" / "1.0").mkdir(parents=True)  # the only version folder: the old fallback would take it

    with pytest.raises(ExportMissing, match="the pin file .*no-pin.json is not there"):
        version_folder(tmp_path, tmp_path / "no-pin.json")
    empty = tmp_path / "empty-pin.json"
    empty.write_text("{}", encoding="utf-8")
    with pytest.raises(ExportMissing, match="names no version"):
        version_folder(tmp_path, empty)


# --- the reconciliation --------------------------------------------------------------------------------


def test_files_that_agree_have_every_slot_empty(tmp_path):
    result = _run(tmp_path)

    assert _bad(result) == {}
    assert sorted(result) == sorted(
        [
            "target.base", "start_price.written", "buy_spec.exists",
            "buy.base", "buy.category", "buy.item_level", "buy.rarity", "buy.influence", "buy.pool",
            "start_mod.ResA2.tier", "start_mod.ResA2.values", "start_mod.ResA2.buy_mod", "start_mod.ResA2.buy_minimum",
            "buy_mod.+#% to Resist.in_target",
            "price.entry", "price.base", "price.item_level", "price.rarity", "price.source", "price.pool",
        ]
    )  # fmt: skip


def test_the_slots_come_from_the_two_yaml_files_alone(tmp_path):
    target = read_target(_write(tmp_path, "t.yaml", TARGET))
    spec = read_buy_spec(_write(tmp_path, "b.yaml", SPEC))

    assert slots(target, spec) == [
        "target.base", "start_price.written", "buy_spec.exists",
        "buy.base", "buy.category", "buy.item_level", "buy.rarity", "buy.influence", "buy.pool",
        "start_mod.ResA2.tier", "start_mod.ResA2.values", "start_mod.ResA2.buy_mod", "start_mod.ResA2.buy_minimum",
        "buy_mod.+#% to Resist.in_target",
        "price.entry", "price.base", "price.item_level", "price.rarity", "price.source", "price.pool",
    ]  # fmt: skip
    assert slots(target, None) == [
        "target.base", "start_price.written", "buy_spec.exists", "start_mod.ResA2.tier", "start_mod.ResA2.values",
        "price.entry", "price.base", "price.item_level", "price.rarity", "price.source", "price.pool",
    ]  # fmt: skip


def test_a_bought_target_with_no_start_price_and_no_buy_spec_fails_both_slots_and_has_no_price_slots(tmp_path):
    target = read_target(_write(tmp_path, "t.yaml", {"base": "Ruby Ring", "item_level": 80, "start": "bought"}))

    result = reconcile(target, None, EXPORT, [])

    assert slots(target, None) == ["target.base", "start_price.written", "buy_spec.exists"]
    assert [slot for slot, items in result.items() if items] == ["start_price.written", "buy_spec.exists"]
    assert result["start_price.written"][0].values == ("bought", "no price key")
    assert result["buy_spec.exists"][0].values == ("none", "no buy spec")


def test_a_given_target_needs_no_start_price_and_no_buy_spec_and_has_no_price_slots(tmp_path):
    target = read_target(_write(tmp_path, "t.yaml", {"base": "Ruby Ring", "item_level": 80, "start": "given"}))

    result = reconcile(target, None, EXPORT, [])

    assert slots(target, None) == ["target.base", "start_price.written", "buy_spec.exists"]
    assert [slot for slot, items in result.items() if items] == []


def test_a_target_that_does_not_say_how_its_start_item_is_had_fails_the_start_slot(tmp_path):
    target = read_target(_write(tmp_path, "t.yaml", {"base": "Ruby Ring", "item_level": 80}))

    result = reconcile(target, None, EXPORT, [])

    assert [slot for slot, items in result.items() if items] == ["start_price.written"]
    assert result["start_price.written"][0].values == ("none", "not said")


def test_a_start_price_with_no_buy_spec_fails_only_the_spec_slot(tmp_path):
    target = read_target(_write(tmp_path, "t.yaml", TARGET))

    result = reconcile(target, None, EXPORT, [])

    assert [slot for slot, items in result.items() if items and not slot.startswith("price.")] == ["buy_spec.exists"]
    assert result["buy_spec.exists"][0].values == ("T start ring", "no buy spec")


def test_a_bought_target_with_a_key_and_a_spec_but_no_price_entry_fails_the_entry_slot(tmp_path):
    target = read_target(_write(tmp_path, "t.yaml", TARGET))
    spec = read_buy_spec(_write(tmp_path, "b.yaml", SPEC))

    result = reconcile(target, spec, EXPORT, [])

    assert result["price.entry"][0].values == ("T start ring", "no entry")


def test_removing_the_start_price_or_renaming_the_spec_is_a_failure_and_changes_the_check_set(tmp_path):
    whole = [read_target(_write(tmp_path, "t.yaml", TARGET))]
    specs = [read_buy_spec(_write(tmp_path, "b.yaml", SPEC))]
    unpriced = [read_target(_write(tmp_path, "t.yaml", {k: v for k, v in TARGET.items() if k != "start_price"}))]
    renamed = [read_buy_spec(_write(tmp_path, "r.yaml", {**SPEC, "name": "another name"}))]

    full = check_ids(whole, specs)

    assert full[0] == "t::target.base"
    assert set(check_ids(unpriced, specs)) < set(full)  # the price checks and the spec checks are gone
    assert set(check_ids(whole, renamed)) < set(full)  # the spec checks are gone
    assert reconcile(unpriced[0], None, EXPORT, [])["start_price.written"] != []
    assert reconcile(whole[0], None, EXPORT, [])["buy_spec.exists"] != []


def test_a_base_that_is_not_in_the_game_data_is_reported_once(tmp_path):
    result = _run(tmp_path, target=lambda d: d.update(base="No Such Base"))

    assert list(_bad(result)) == ["target.base", "price.base"]


def test_the_target_base_by_id_agrees_with_the_spec_by_name(tmp_path):
    assert _bad(_run(tmp_path, target=lambda d: d.update(base=RING))) == {}


@pytest.mark.parametrize(
    ("spec_change", "slot"),
    [
        (lambda d: d.pop("base_type"), "buy.base"),
        (lambda d: d.update(base_type="Sapphire Ring"), "buy.base"),
        (lambda d: d.update(category="accessory.amulet"), "buy.category"),
        (lambda d: d.pop("category"), "buy.category"),
        (lambda d: d.update(item_level_min=75), "buy.item_level"),
        (lambda d: d.pop("item_level_min"), "buy.item_level"),
        (lambda d: d.update(rarity="normal"), "buy.rarity"),
        (lambda d: d.update(rarity="nonunique"), "buy.rarity"),
        (lambda d: d.update(influence=["hunter"]), "buy.influence"),
    ],
)
def test_a_buy_spec_fact_that_differs_from_the_target_is_a_disagreement_in_its_own_slot(tmp_path, spec_change, slot):
    assert list(_bad(_run(tmp_path, spec=spec_change))) == [slot]


def test_the_trade_category_comes_from_the_item_class_of_the_base(tmp_path):
    result = _run(tmp_path, target=lambda d: d.update(base="Gold Amulet", start_item={"rarity": "rare"}))

    assert "buy.category" in _bad(result)  # the spec still says accessory.ring for an amulet


def test_an_item_class_with_no_known_trade_category_is_a_disagreement_not_a_pass(tmp_path):
    export = Export(mods=EXPORT.mods, bases={**EXPORT.bases, "Metadata/X": _base("Odd Thing", "Odd Class", ["default"])})
    result = _run(tmp_path, target=lambda d: d.update(base="Odd Thing", start_item={"rarity": "rare"}), export=export)

    assert "?Odd Class" in "".join(_bad(result)["buy.category"])


def test_a_hand_written_tier_that_the_ladder_does_not_give_is_a_disagreement(tmp_path):
    result = _bad(_run(tmp_path, target=lambda d: d["start_item"]["mods"][0].update(tier=3)))

    assert list(result) == ["start_mod.ResA2.tier"]
    assert "tier = 3" in result["start_mod.ResA2.tier"][0] and "tier 2 of 3" in result["start_mod.ResA2.tier"][0]


def test_a_start_mod_with_no_written_tier_or_values_has_nothing_to_reconcile(tmp_path):
    def change(document):
        del document["start_item"]["mods"][0]["tier"]
        del document["start_item"]["mods"][0]["values"]

    assert _bad(_run(tmp_path, target=change)) == {}


@pytest.mark.parametrize("values", [[11], [18], [14, 1]])
def test_a_value_outside_the_range_or_of_the_wrong_length_is_a_disagreement(tmp_path, values):
    result = _bad(_run(tmp_path, target=lambda d: d["start_item"]["mods"][0].update(values=values)))

    assert "start_mod.ResA2.values" in result


def test_the_range_ends_are_inside_the_values(tmp_path):
    for value in (12, 17):
        assert _bad(_run(tmp_path, target=lambda d, v=value: d["start_item"]["mods"][0].update(values=[v]),
                         spec=lambda d, v=value: d["mods"][0].update(minimum=min(v, 12)))) == {}  # fmt: skip


def test_a_start_mod_that_is_not_in_the_game_data_fails_both_data_slots_and_the_spec_slot(tmp_path):
    result = _bad(_run(tmp_path, target=lambda d: d["start_item"]["mods"][0].update(mod="Ghost")))

    assert set(result) == {
        "start_mod.Ghost.tier", "start_mod.Ghost.values", "start_mod.Ghost.buy_mod", "buy_mod.+#% to Resist.in_target",
    }  # fmt: skip


def test_a_start_mod_that_cannot_spawn_on_the_base_is_a_tier_disagreement(tmp_path):
    result = _bad(_run(tmp_path, target=lambda d: d["start_item"]["mods"][0].update(mod="ResAAmuletOnly", values=[31])))

    assert "cannot spawn on" in result["start_mod.ResAAmuletOnly.tier"][0]


def test_a_tier_that_differs_between_bases_of_one_name_is_a_disagreement(tmp_path):
    mods = {**EXPORT.mods, "Boot1": _mod("Boot", 1, 1, 2, [("boots", 1)]), "Boot2": _mod("Boot", 9, 3, 4, [("extra", 1)])}
    bases = {**EXPORT.bases, TWIN_B: _base("Twin Boots", "Boots", ["boots", "extra", "default"])}  # Boot2 spawns on this one only
    export = Export(mods=mods, bases=bases)

    def target(document):
        document["base"] = "Twin Boots"
        document["start_item"]["mods"] = [{"mod": "Boot1", "tier": 2, "values": [1], "fractured": True}]

    result = _bad(_run(tmp_path, target=target, export=export))

    assert any("differs between the bases" in line for line in result["start_mod.Boot1.tier"])


@pytest.mark.parametrize(
    ("spec_change", "slot"),
    [
        (lambda d: d["mods"][0].pop("minimum"), "start_mod.ResA2.buy_minimum"),  # none: every tier matches
        (lambda d: d["mods"][0].update(minimum=11), "start_mod.ResA2.buy_minimum"),  # the tier below still matches
        (lambda d: d["mods"][0].update(minimum=15), "start_mod.ResA2.buy_minimum"),  # above the start mod's own roll
        (lambda d: d["mods"][0].update(stat="+#% to Fire Resist"), "start_mod.ResA2.buy_mod"),
        (lambda d: d["mods"][0].update(fractured=False), "start_mod.ResA2.buy_mod"),
    ],
)
def test_the_spec_mod_must_select_the_start_mods_tier(tmp_path, spec_change, slot):
    result = _bad(_run(tmp_path, spec=spec_change))

    assert slot in result


def test_the_minimum_may_be_anywhere_from_just_above_the_lower_tier_to_the_start_roll(tmp_path):
    for minimum in (12, 13, 14):
        assert _bad(_run(tmp_path, spec=lambda d, m=minimum: d["mods"][0].update(minimum=m))) == {}


def test_the_top_tier_has_no_floor_and_the_lowest_tier_needs_no_lower_bound(tmp_path):
    def top(document):
        document["start_item"]["mods"][0].update(mod="ResA3", tier=1, values=[20])

    def bottom(document):
        document["start_item"]["mods"][0].update(mod="ResA1", tier=3, values=[7])

    spec_top = lambda d: d["mods"][0].update(minimum=18)
    spec_bottom = lambda d: d["mods"][0].update(minimum=1)

    assert _bad(_run(tmp_path, target=top, spec=spec_top)) == {}
    assert _bad(_run(tmp_path, target=bottom, spec=spec_bottom)) == {}


def test_a_buy_spec_mod_the_target_does_not_have_is_a_disagreement(tmp_path):
    result = _bad(_run(tmp_path, spec=lambda d: d["mods"].append({"stat": "+# to Dexterity", "minimum": 5})))

    assert list(result) == ["buy_mod.+# to Dexterity.in_target"]


def test_a_mod_listed_twice_in_a_buy_spec_is_a_format_error(tmp_path):
    with pytest.raises(FileFormatError, match="listed 2 times"):
        _run(tmp_path, spec=lambda d: d["mods"].append(dict(d["mods"][0])))


def test_a_spec_mod_with_several_stats_is_refused_not_passed(tmp_path):
    mods = {**EXPORT.mods, "Hybrid": _mod("Hy", 1, 1, 2, [("ring", 1)], text="+(1-2) to A")}
    mods["Hybrid"]["stats"].append({"id": "other", "min": 3, "max": 4})
    export = Export(mods=mods, bases=EXPORT.bases)

    def target(document):
        document["start_item"]["mods"] = [{"mod": "Hybrid", "tier": 1, "values": [1, 3], "fractured": True}]

    with pytest.raises(FileFormatError, match="2 stats"):
        _run(tmp_path, target=target, spec=lambda d: d["mods"][0].update(stat="+# to A"), export=export)


def test_a_one_line_stat_matches_data_text_with_a_fixed_number(tmp_path):
    def target(document):
        document["start_item"]["mods"] = [{"mod": "Speed1", "tier": 1, "values": [30], "fractured": True}]

    result = _run(tmp_path, target=target, spec=lambda d: d["mods"][0].update(stat="#% increased Movement Speed", minimum=30))

    assert _bad(result) == {}


def test_an_entry_priced_for_a_shared_base_name_is_a_disagreement_by_base_id(tmp_path):
    def target(document):
        document["base"] = TWIN_A
        document["start_item"] = {"rarity": "rare"}

    def entry(document):
        document["detail"]["query"]["query"]["type"] = "Twin Boots"

    result = _bad(_run(tmp_path, target=target, spec=lambda d: d.update(base_type="Twin Boots", category="armour.boots", mods=[]), entry=entry))

    assert list(result) == ["price.base"]
    assert "shared by 2 bases" in result["price.base"][0]


def test_a_target_that_names_a_shared_base_by_name_is_a_disagreement_even_if_the_entry_matches(tmp_path):
    def target(document):
        document["base"] = "Twin Boots"
        document["start_item"] = {"rarity": "rare"}

    def entry(document):
        document["detail"]["query"]["query"]["type"] = "Twin Boots"

    result = _bad(_run(tmp_path, target=target, spec=lambda d: d.update(base_type="Twin Boots", category="armour.boots", mods=[]), entry=entry))

    assert "price.base" in result


def test_an_entry_for_another_single_base_is_a_disagreement(tmp_path):
    result = _bad(_run(tmp_path, entry=lambda d: d["detail"]["query"]["query"].update(type="Sapphire Ring")))

    assert list(result) == ["price.base"]


def test_an_entry_with_no_base_prices_any_item_of_the_category(tmp_path):
    result = _bad(_run(tmp_path, entry=lambda d: d["detail"]["query"]["query"].pop("type")))

    assert list(result) == ["price.base"]
    assert "category accessory.ring" in result["price.base"][0]


def test_an_entry_whose_base_name_is_not_in_the_game_data_is_a_disagreement(tmp_path):
    result = _bad(_run(tmp_path, entry=lambda d: d["detail"]["query"]["query"].update(type="Ghost Ring")))

    assert "price.base" in result


def test_an_entry_priced_for_another_item_level_or_none_is_a_disagreement(tmp_path):
    lower = _bad(_run(tmp_path, entry=lambda d: d["detail"]["query"]["query"]["filters"]["misc_filters"]["filters"]["ilvl"].update(min=75)))
    none = _bad(_run(tmp_path, entry=lambda d: d["detail"]["query"]["query"]["filters"]["misc_filters"]["filters"].pop("ilvl")))

    assert list(lower) == ["price.item_level"] and list(none) == ["price.item_level"]


def _hand_target(tmp_path):
    return read_target(_write(tmp_path, "t.yaml", {**TARGET, "start_price": "Ruby Ring, normal, item level 80", "start_item": {"rarity": "normal"}}))


def test_a_stand_in_entry_is_read_by_the_words_of_its_key_and_the_level_of_its_note(tmp_path):
    note = "poe.ninja BaseType overview: a normal Ruby Ring of item level 80, 3 observations"
    price_path = _write(tmp_path, "p.json", {"prices": {"Ruby Ring, normal, item level 80": {"chaos": 2, "source": "poe.ninja", "note": note}}})
    entry = read_price_entry(price_path, "Ruby Ring, normal, item level 80")

    result = reconcile(_hand_target(tmp_path), None, EXPORT, [entry])

    assert [slot for slot, items in result.items() if items and slot.startswith("price.")] == ["price.source"]
    assert result["price.source"][0].values == ("trade-api", "poe.ninja")


def test_a_stand_in_whose_note_gives_another_level_than_its_label_is_a_level_disagreement(tmp_path):
    note = "the cheapest normal Ruby Ring line of item level 80 or more (item level 85, 43 observations)"
    price_path = _write(tmp_path, "p.json", {"prices": {"Ruby Ring, normal, item level 80": {"chaos": 2, "source": "poe.ninja", "note": note}}})

    result = reconcile(_hand_target(tmp_path), None, EXPORT, [read_price_entry(price_path, "Ruby Ring, normal, item level 80")])

    assert result["price.item_level"][0].values == ("80", "85")


def test_a_hand_entry_with_the_level_only_in_its_key_is_a_cannot_tell_not_a_pass(tmp_path):
    price_path = _write(tmp_path, "p.json", {"prices": {"Ruby Ring, normal, item level 80": {"chaos": 2, "source": "hand", "note": "a hand price"}}})

    result = reconcile(_hand_target(tmp_path), None, EXPORT, [read_price_entry(price_path, "Ruby Ring, normal, item level 80")])

    assert result["price.item_level"][0].values == ("80", "cannot tell (label 80)")
    assert result["price.source"][0].values == ("trade-api", "hand")


def test_an_entry_with_no_level_and_no_base_anywhere_is_reported_on_both_slots(tmp_path):
    price_path = _write(tmp_path, "p.json", {"prices": {"Ruby": {"chaos": 2, "source": "trade-api"}}})
    target = read_target(_write(tmp_path, "t.yaml", {**TARGET, "start_price": "Ruby", "start_item": {"rarity": "normal"}}))

    result = reconcile(target, None, EXPORT, [read_price_entry(price_path, "Ruby")])

    assert result["price.item_level"][0].values == ("80", "none")
    assert result["price.base"][0].values == ("Ruby Ring", "no base")


def _bone_export():
    mods = {**EXPORT.mods, "BoneMod": _mod("Bone", 1, 1, 2, [("bone", 1000)])}
    bases = {**EXPORT.bases, "Metadata/Items/Rings/Bone": _base("Bone Ring", "Ring", ["bone", "ring", "default"])}
    return Export(mods=mods, bases=bases)


def test_a_spec_with_no_base_type_accepts_every_ring_and_one_with_another_pool_is_a_disagreement(tmp_path):
    result = _run(tmp_path, spec=lambda d: d.pop("base_type"), export=_bone_export())

    assert result["buy.pool"][0].values == ("Ruby Ring", "Metadata/Items/Rings/Bone (+1 -0)")


def test_a_spec_by_a_base_type_accepts_that_name_only_so_the_pool_agrees(tmp_path):
    assert _run(tmp_path, export=_bone_export())["buy.pool"] == []


def test_a_category_only_price_entry_accepts_every_ring_and_its_pool_difference_is_reported(tmp_path):
    result = _run(tmp_path, entry=lambda d: d["detail"]["query"]["query"].pop("type"), export=_bone_export())

    assert result["price.pool"][0].values == ("Ruby Ring", "Metadata/Items/Rings/Bone (+1 -0)")
    assert result["price.base"][0].values == ("Ruby Ring", "any accessory.ring")


def test_a_shared_name_whose_bases_have_another_pool_is_a_pool_disagreement(tmp_path):
    mods = {**EXPORT.mods, "BootMod": _mod("Boot", 1, 1, 2, [("extra", 1000)])}
    bases = {**EXPORT.bases, TWIN_B: _base("Twin Boots", "Boots", ["extra", "boots", "default"])}
    export = Export(mods=mods, bases=bases)

    def target(document):
        document["base"] = TWIN_A
        document["start_item"] = {"rarity": "rare"}

    def entry(document):
        document["detail"]["query"]["query"]["type"] = "Twin Boots"

    result = _run(tmp_path, target=target, spec=lambda d: d.update(base_type="Twin Boots", category="armour.boots", mods=[]), entry=entry, export=export)

    assert result["buy.pool"][0].values == ("Twin Boots", f"{TWIN_B} (+1 -0)")
    assert result["price.pool"][0].values == ("Twin Boots", f"{TWIN_B} (+1 -0)")


def test_a_start_price_in_no_price_file_is_a_disagreement(tmp_path):
    target = read_target(_write(tmp_path, "t.yaml", TARGET))

    result = reconcile(target, None, EXPORT, [])

    assert [str(item) for item in result["price.entry"]] != [] and result["price.base"] == []


def test_reconcile_files_finds_the_spec_and_the_price_entries_itself(tmp_path):
    prices = tmp_path / "prices"
    prices.mkdir()
    _write(prices, "p.json", {"prices": {"T start ring": ENTRY}})
    target = read_target(_write(tmp_path, "t.yaml", TARGET))
    spec = read_buy_spec(_write(tmp_path, "b.yaml", SPEC))

    result = reconcile_files(target, [spec], EXPORT, prices)

    assert _bad(result) == {}
    assert result["price.base"] == []


def test_a_disagreement_prints_both_places_and_both_values():
    item = Disagreement("buy.base", "target: Ruby Ring", "spec: any ring", "Ruby Ring", "any ring")

    assert str(item) == "buy.base: target: Ruby Ring  <>  spec: any ring  [Ruby Ring <> any ring]"
    assert item.values == ("Ruby Ring", "any ring")


# --- the rarity of the search the price was taken with ------------------------------------------------------------


def test_an_entry_priced_for_another_rarity_than_the_start_item_is_a_disagreement(tmp_path):
    result = _bad(_run(tmp_path, entry=lambda d: d["detail"]["query"]["query"]["filters"]["type_filters"]["filters"]["rarity"].update(option="normal")))

    assert list(result) == ["price.rarity"]


def test_an_entry_with_no_search_has_no_rarity_to_compare(tmp_path):
    price_path = _write(tmp_path, "p.json", {"prices": {"Ruby Ring, normal, item level 80": {"chaos": 2, "source": "poe.ninja"}}})
    entry = read_price_entry(price_path, "Ruby Ring, normal, item level 80")

    assert priced_rarity(entry) is None


def test_the_base_s_own_implicit_of_a_spec_narrows_the_bases_it_accepts_and_is_no_bought_mod(tmp_path):
    mods = {**EXPORT.mods, "BootMod": _mod("Boot", 1, 1, 2, [("extra", 1000)]), "ImpA": _mod("Imp", 1, 5, 9, [], domain="item", generation="unique", text="+(5-9)% to A Resistance"),
            "ImpB": _mod("Imp", 1, 5, 9, [], domain="item", generation="unique", text="+(5-9)% to B Resistance")}
    bases = {**EXPORT.bases, TWIN_A: {**_base("Twin Boots", "Boots", ["boots", "default"]), "implicits": ["ImpA"]},
             TWIN_B: {**_base("Twin Boots", "Boots", ["extra", "boots", "default"]), "implicits": ["ImpB"]}}  # B has another pool
    export = Export(mods=mods, bases=bases)

    def target(document):
        document["base"] = TWIN_A
        document["start_item"] = {"rarity": "rare"}

    def spec(document):
        document.update(base_type="Twin Boots", category="armour.boots")
        document["mods"] = [{"stat": "+(5-9)% to A Resistance", "implicit": True, "own": True}]

    result = _run(tmp_path, target=target, spec=spec, entry=lambda d: d["detail"]["query"]["query"].update(type="Twin Boots"), export=export)

    assert result["buy.pool"] == []  # without the implicit the spec would accept Twin B, whose pool has one more mod
    assert _run(tmp_path, target=target, spec=lambda d: (spec(d), d.update(mods=[])), entry=lambda d: d["detail"]["query"]["query"].update(type="Twin Boots"), export=export)["buy.pool"] != []
    assert "buy_mod.+#% to A Resistance.in_target" not in result
