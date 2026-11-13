"""What the methods in scope spend, and which of it a price file does not price (#885).

The walk runs on the real 3.29.3.3 data (skipped where the cache is absent; CI fetches it). What it must find is written here by
hand from the claims: the beasts of `beastcraft.recipe_beasts`, `imprint.beast_recipes` and `influence_beast.recipes`, the six
influenced Exalted Orbs, the Eldritch currency, the Awakener's Orb. The default price file is not read here: the test that holds it
complete comes with the data (the second PR of #885).
"""

from datetime import UTC, datetime

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import kinds
from crafting_system.planner._offers import Offer, price_offers
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.prices.essence_recipe import tier_of
from crafting_system.prices.price_file import MarketRecord
from crafting_system.prices.spends import ASKED_ONCE, DEFERRED_KINDS, kinds_in_scope, probe_items, spends, spent_names, unpriced

SPEND_NOTHING = {"unveil", "pick", "restore"}  # free steps (`resources` is empty), and listed only on an item that holds a veiled mod or an imprint

BEASTS = {
    "beast-side-swap": {"Farric Wolf Alpha", "Farric Lynx Alpha"},
    "wild-bristle-matron": {"Wild Bristle Matron"},
    "aspect-beast": {"Saqawal, First of the Sky", "Farrul, First of the Plains", "Craiceann, First of the Deep", "Fenumus, First of the Night", "The Black Mórrígan"},
    "talisman-fracture": {"Farric Frost Hellion Alpha", "Fenumal Plagued Arachnid", "The Black Mórrígan"},
    "imprint": {"Craicic Croaker", "Fenumal Plagued Arachnid"},
    "beast-influence-recipe": {"Craicic Maw", "Fenumal Devourer", "Saqawine Blood Viper", "Farric Goliath", "Craicic Watcher", "Fenumal Queen", "Fenumal Scrabbler"},
}
CHAOS = "Chaos Orb"  # the rare beasts of any kind, at the setting `beastcraft.any_rare_creature_price`


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def walked(data):
    return spends(data)


def test_every_registered_kind_is_in_scope_unless_it_is_deferred_by_name():
    registered = {entry.name for entry in kinds()}

    assert set(DEFERRED_KINDS) <= registered  # no stale name: a renamed kind would come back into scope unseen otherwise
    assert set(kinds_in_scope()) == registered - set(DEFERRED_KINDS)
    assert {"essence", "fossil-set", "bench-craft", "aspect-beast", "imprint", "awakeners-orb", "eldritch-chaos-orb", "influenced-exalted-orb", "catalyst"} <= set(kinds_in_scope())
    assert not {"recombinator", "vaal", "locus", "chromatic-orb", "orb-of-remembrance", "tempering", "re-anoint"} & set(kinds_in_scope())
    assert set(ASKED_ONCE) <= registered


def test_the_walk_reaches_every_kind_in_scope(walked):
    assert set(walked) == set(kinds_in_scope())
    assert {kind for kind, spent in walked.items() if not spent} == SPEND_NOTHING


def test_the_walk_finds_the_beasts_of_every_beast_recipe(walked):
    for kind, beasts in BEASTS.items():
        assert set(walked[kind]) - {CHAOS} == beasts, kind


def test_the_walk_finds_the_currency_of_the_other_methods(walked):
    assert set(walked["influenced-exalted-orb"]) == {f"{name}'s Exalted Orb" for name in ("Shaper", "Elder", "Crusader", "Hunter", "Redeemer", "Warlord")}
    assert set(walked["awakeners-orb"]) == {"Awakener's Orb"}
    assert set(walked["eldritch-implicit-currency"]) == {f"{size} Eldritch {kind}" for size in ("Lesser", "Greater", "Grand", "Exceptional") for kind in ("Ember", "Ichor")}
    assert {name for kind in ("eldritch-chaos-orb", "eldritch-exalted-orb", "eldritch-annulment-orb", "orb-of-conflict") for name in walked[kind]} == {
        "Eldritch Chaos Orb", "Eldritch Exalted Orb", "Eldritch Orb of Annulment", "Orb of Conflict",
    }  # fmt: skip
    assert set(walked["veiled-chaos-orb"]) | set(walked["veiled-exalted-orb"]) == {"Veiled Chaos Orb", "Veiled Exalted Orb"}
    assert len(walked["catalyst"]) == 12 and all(name.endswith(" Catalyst") for name in walked["catalyst"])
    assert set(walked["harvest-add-remove"]) == {f"{colour} Crystallised Lifeforce" for colour in ("Primal", "Vivid", "Wild", "Sacred")}
    assert set(walked["fracturing-orb"]) == {"Fracturing Orb"}
    assert walked["wild-bristle-matron"]["Wild Bristle Matron"] == "Beastcraft Wild Bristle Matron (add a metamod)"  # the action that spends it, by its label


def test_the_walk_finds_every_essence_and_fossil_of_the_game_data(walked, data):
    essences = {record.name for record in data.essences.values() if any(entry.mod_id is not None for entry in record.mods)}
    spent = set(walked["essence"]) | set(walked["corrupted-essence"])

    assert spent == essences - {"Essence of Desolation"}  # not an action: it has no ordinary source in 3.29
    assert all(tier_of(name) is not None for name in walked["essence"])  # the upgrade recipe knows the tier of each
    assert all(tier_of(name) is None for name in walked["corrupted-essence"])
    fossils = {name for name in walked["fossil-set"] if name.endswith(" Fossil")}
    assert len(fossils) == 25 and {name for name in walked["fossil-set"] if name.endswith(" Resonator")} == {
        f"{size} Chaotic Resonator" for size in ("Primitive", "Potent", "Powerful", "Prime")
    }


def test_no_deferred_method_is_walked_and_the_names_are_those_of_the_kinds_asked(data, walked):
    names = spent_names(data, kind_names=["blessed-orb", "vaal"])  # a kind is asked when named, deferred or not

    assert names == ["Blessed Orb", "Vaal Orb"]
    everything = {name for spent in walked.values() for name in spent}
    assert not {"Gold", "Thaumaturgic Dust", "Orb of Fusing", "Jeweller's Orb", "Tempering Orb", "Orb of Remembrance", "Locus of Corruption (use)"} & everything


def test_the_probe_holds_each_class_at_each_rarity_and_influence_and_a_talisman(data):
    items = probe_items(data)
    bases = {item.base_id for item in items}
    classes = {data.base_items[base_id].item_class for base_id in bases}

    assert {"Amulet", "Ring", "Belt", "Body Armour", "Boots", "Gloves", "Helmet", "Shield", "Quiver", "Bow", "Wand", "Jewel", "AbyssJewel"} <= classes
    assert "HiddenItem" not in classes and "StackableCurrency" not in classes
    assert sum("talisman" in data.base_items[base_id].tags for base_id in bases) == 1
    ring = [item for item in items if data.base_items[item.base_id].item_class == "Ring"]
    assert len(ring) == 9 and len({(item.rarity, item.influences) for item in ring}) == 9  # three rarities, and a rare of each of the six influences
    assert items == probe_items(data)


# --- which names a file does not price: no game data needed ---------------------------------------------------------------------


def price_file(prices, markets=None):
    return PriceFile("Allflame", datetime(2026, 7, 31, tzinfo=UTC), 176.6, prices, markets or {})


def test_a_name_is_unpriced_when_the_file_has_no_row_for_it():
    prices = price_file({"Wild Bristle Matron": PriceEntry(60.0, "poe.ninja"), "Exalted Orb": PriceEntry(1.4, "poe.ninja")})

    assert unpriced(["Wild Bristle Matron", "Farric Wolf Alpha", "Exalted Orb", "Awakener's Orb", "Farric Wolf Alpha"], prices) == ["Awakener's Orb", "Farric Wolf Alpha"]
    assert unpriced([], prices) == []


def test_a_name_the_planner_prices_without_a_row_is_not_unpriced():
    """A Chaos Orb is 1, a Divine Orb the file's rate, and the standing defaults (Dust, Gold, a use of the Locus) hold with no row."""
    assert unpriced(["Chaos Orb", "Divine Orb", "Thaumaturgic Dust", "Gold", "Locus of Corruption (use)"], price_file({})) == []


def test_unpriced_reads_a_name_as_the_planner_prices_an_offer():
    """Held equal to `price_offers`, name by name: an offer is dropped exactly for the names `unpriced` gives."""
    thin = MarketRecord("thin", "Allflame", datetime(2026, 7, 31, tzinfo=UTC).date(), 4, 4, "hash", {"query": {}}, chaos=7.0, used=4)
    prices = price_file({"Exalted Orb": PriceEntry(1.4, "poe.ninja")}, {"Thin Beast": thin})
    names = ["Chaos Orb", "Divine Orb", "Exalted Orb", "Thin Beast", "Locus of Corruption (use)", "Gold", "Awakener's Orb", "Farric Wolf Alpha"]

    priced, dropped = price_offers([Offer(name, object(), {name: 1}) for name in names], prices)

    assert sorted(name for offer in dropped for name in offer.missing) == unpriced(names, prices) == ["Awakener's Orb", "Farric Wolf Alpha"]
    assert len(priced) == 6
    _, dropped_ninja = price_offers([Offer(name, object(), {name: 1}) for name in names], prices, "ninja")  # no trade record is read under `ninja`
    assert sorted(name for offer in dropped_ninja for name in offer.missing) == unpriced(names, prices, "ninja") == ["Awakener's Orb", "Farric Wolf Alpha", "Thin Beast"]
