"""Strict validation: malformed raw data raises RawFormatError naming the record and the field."""

import pytest
from repoe_support import no_network, raw_fixtures  # noqa: F401

from crafting_system.data.errors import DataError, RawFormatError
from crafting_system.data.normalize import normalize_game_data

MOD = "LocalAddedFireDamageTwoHand1"
BASE = "Metadata/Items/Armours/BodyArmours/BodyInt1"
FOSSIL = "Metadata/Items/Currency/CurrencyDelveCraftingFire"
ESSENCE = "Metadata/Items/Currency/CurrencyEssenceHatred1"


def normalize(raw):
    return normalize_game_data(
        raw["mods.json"],
        raw["base_items.json"],
        raw["fossils.json"],
        raw["essences.json"],
        raw["crafting_bench_options.json"],
        version="0.0-test",
    )


def delete(key):
    return lambda record: record.pop(key)


def put(key, value):
    return lambda record: record.__setitem__(key, value)


def put_in(key, index, inner_key, value):
    return lambda record: record[key][index].__setitem__(inner_key, value)


CASES = [
    # (raw file, record id or index, mutation of that record, field named in the message)
    ("mods.json", MOD, delete("groups"), "groups"),
    ("mods.json", MOD, delete("text"), "text"),
    ("mods.json", MOD, put("groups", "FireDamage"), "groups"),
    ("mods.json", MOD, put("groups", ["FireDamage", 3]), "groups"),
    ("mods.json", MOD, put("required_level", "1"), "required_level"),
    ("mods.json", MOD, put("required_level", True), "required_level"),
    ("mods.json", MOD, put("required_level", 1.5), "required_level"),
    ("mods.json", MOD, put("domain", None), "domain"),
    ("mods.json", MOD, put("is_essence_only", 0), "is_essence_only"),
    ("mods.json", MOD, put("text", 5), "text"),
    ("mods.json", MOD, put("spawn_weights", {"bow": 1}), "spawn_weights"),
    ("mods.json", MOD, put_in("spawn_weights", 1, "weight", "1400"), "spawn_weights"),
    ("mods.json", MOD, put_in("spawn_weights", 1, "weight", True), "spawn_weights"),
    ("mods.json", MOD, put_in("generation_weights", 0, "tag", 7), "generation_weights"),
    ("mods.json", MOD, lambda r: r["generation_weights"][0].pop("weight"), "generation_weights"),
    ("mods.json", MOD, put("adds_tags", [None]), "adds_tags"),
    ("mods.json", MOD, delete("implicit_tags"), "implicit_tags"),
    ("mods.json", MOD, put_in("stats", 0, "min", 1.5), "stats"),
    ("mods.json", MOD, put_in("stats", 1, "max", False), "stats"),
    ("mods.json", MOD, lambda r: r["stats"][0].pop("id"), "stats"),
    ("base_items.json", BASE, put("tags", "armour"), "tags"),
    ("base_items.json", BASE, put("drop_level", True), "drop_level"),
    ("base_items.json", BASE, delete("item_class"), "item_class"),
    ("base_items.json", BASE, put("implicits", [1]), "implicits"),
    ("base_items.json", BASE, put("release_state", None), "release_state"),
    ("fossils.json", FOSSIL, put("changes_quality", 1), "changes_quality"),
    ("fossils.json", FOSSIL, put("corrupted_essence_chance", True), "corrupted_essence_chance"),
    ("fossils.json", FOSSIL, delete("mirrors"), "mirrors"),
    ("fossils.json", FOSSIL, put("allowed_tags", None), "allowed_tags"),
    ("fossils.json", FOSSIL, put_in("positive_mod_weights", 0, "weight", "1000"), "positive_mod_weights"),
    ("fossils.json", FOSSIL, put("name", 3), "name"),
    ("essences.json", ESSENCE, delete("type"), "type"),
    ("essences.json", ESSENCE, lambda r: r["type"].__setitem__("tier", "1"), "tier"),
    ("essences.json", ESSENCE, lambda r: r["type"].__setitem__("is_corruption_only", 0), "is_corruption_only"),
    ("essences.json", ESSENCE, put("mods", ["ColdResist1"]), "mods"),
    ("essences.json", ESSENCE, lambda r: r["mods"].__setitem__("Bow", 4), "mods"),
    ("essences.json", ESSENCE, put("item_level_restriction", "35"), "item_level_restriction"),
    ("essences.json", ESSENCE, put("level", True), "level"),
    ("essences.json", ESSENCE, delete("spawn_level_min"), "spawn_level_min"),
    ("crafting_bench_options.json", 0, delete("actions"), "actions"),
    ("crafting_bench_options.json", 0, lambda r: r["actions"].pop("reroll_rarity"), "reroll_rarity"),
    ("crafting_bench_options.json", 0, lambda r: r["actions"].__setitem__("change_socket_count", True), "change_socket_count"),
    ("crafting_bench_options.json", 0, lambda r: r["actions"].__setitem__("color_sockets", 2), "color_sockets"),
    ("crafting_bench_options.json", 0, lambda r: r["actions"].__setitem__("remove_crafted_mods", 1), "remove_crafted_mods"),
    ("crafting_bench_options.json", 0, put("cost", [["x", 1]]), "cost"),
    ("crafting_bench_options.json", 0, lambda r: r["cost"].__setitem__("Item", True), "cost"),
    ("crafting_bench_options.json", 0, put("bench_tier", "0"), "bench_tier"),
    ("crafting_bench_options.json", 0, put("master", None), "master"),
    ("crafting_bench_options.json", 0, put("item_classes", "Belt"), "item_classes"),
]


@pytest.mark.parametrize(("file", "record_id", "mutate", "field"), CASES)
def test_a_malformed_field_names_the_record_and_the_field(file, record_id, mutate, field):
    raw = raw_fixtures()
    records = raw[file]
    mutate(records[record_id])

    with pytest.raises(RawFormatError) as caught:
        normalize(raw)

    message = str(caught.value)
    assert str(record_id) in message
    assert field in message


@pytest.mark.parametrize(
    ("file", "record_id"),
    [
        ("mods.json", MOD),
        ("base_items.json", BASE),
        ("fossils.json", FOSSIL),
        ("essences.json", ESSENCE),
        ("crafting_bench_options.json", 2),
    ],
)
@pytest.mark.parametrize("bad", [[], "text", 5, None])
def test_a_record_that_is_not_an_object_names_its_id(file, record_id, bad):
    raw = raw_fixtures()
    raw[file][record_id] = bad

    with pytest.raises(RawFormatError) as caught:
        normalize(raw)

    assert str(record_id) in str(caught.value)
    assert "object" in str(caught.value)


@pytest.mark.parametrize(
    "file", ["mods.json", "base_items.json", "fossils.json", "essences.json"]
)
def test_a_file_that_is_not_an_object_of_records_is_rejected(file):
    raw = raw_fixtures()
    raw[file] = [raw[file]]

    with pytest.raises(RawFormatError, match=file):
        normalize(raw)


def test_a_bench_file_that_is_not_a_list_is_rejected():
    raw = raw_fixtures()
    raw["crafting_bench_options.json"] = {"a": raw["crafting_bench_options.json"]}

    with pytest.raises(RawFormatError, match="crafting_bench_options.json"):
        normalize(raw)


def test_raw_format_error_is_a_data_error():
    assert issubclass(RawFormatError, DataError)


def test_an_extra_unknown_key_is_not_an_error():
    raw = raw_fixtures()
    raw["mods.json"][MOD]["brand_new_key"] = {"anything": [1, 2]}
    raw["crafting_bench_options.json"][0]["actions"]["brand_new_action"] = 1

    assert MOD in normalize(raw).mods
