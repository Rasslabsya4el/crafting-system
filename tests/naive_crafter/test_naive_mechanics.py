"""The mechanics of tickets #608 to #610 on a tiny hand-made export: fossils, the Harvest reforge, the Exalted, Annulment and Fracturing Orbs, the metamods, Remove Crafted Mods.

Like `test_naive_units.py`, no real dump is read: the ring below has the mods listed, so every rule has a case whose answer is worked out by hand, and every new law of
`craft.Laws` is turned off in turn to show that a test sees it (the "mutation tests" of the tickets; the covered routes R08, R09 and R12 have route-level ones in
`tests/test_naive_crafter_routes.py`, R04 and R14 are judged by the heavy run).

  prefixes (ring, item level 80)                       suffixes
    PFIRE  GFire  [fire]            1000                 SSPEED GSpeed [speed]   1000
    PCOLD  GCold  [cold]            1000                 SMANA  GMana  [mana]    1000
    PLIFE  GLife  [life]            1000                 SATT   GAtt   [attack]  1000
    PATT   GAtt2  [attack]          1000                 SCAST  GCast  [caster]  1000
    PPLAIN GPlain []                1000                 SPLAIN GSPlain []       1000
    PBOTH  GBoth  [fire, speed]     1000
  crafted (not in any pool): MATT (Cannot roll Attack Modifiers), MCAST (Cannot roll Caster Modifiers), MMULTI (Can have up to 3 Crafted Modifiers), MLOCK (Suffixes Cannot
  Be Changed), BENCHS and BENCHS2 (suffixes), BENCHP (a prefix); EssForced is the essence's forced suffix.
  fossils: Fire Test Fossil (fire x10, cold blocked), Speed Test Fossil (speed x10, mana blocked), Cut Test Fossil (attack x0.15).
"""

import math
from random import Random

import pytest
from independent.export import RawExport
from naive_crafter.craft import (
    Crafter,
    Held,
    Item,
    Laws,
    Refused,
    Unsupported,
)
from naive_crafter.fossils import FossilSet
from naive_crafter.world import World

from .test_naive_units import CHAOS, RING, currency, mod

Z = 4.5
SEED = 20261107


def tagged(m: dict, *tags: str) -> dict:
    m["implicit_tags"] = list(tags)
    return m


def meta_mod(group: str, side: str, text: str) -> dict:
    return tagged(mod(group, side, 1, 0, domain="crafted", spawn=(), low=1, high=1, text=text))


def ring_mods() -> dict:
    return {
        "PFIRE": tagged(mod("GFire", "prefix", 1, 1000), "fire"),
        "PCOLD": tagged(mod("GCold", "prefix", 1, 1000), "cold"),
        "PLIFE": tagged(mod("GLife", "prefix", 1, 1000), "life"),
        "PATT": tagged(mod("GAtt2", "prefix", 1, 1000), "attack"),
        "PPLAIN": tagged(mod("GPlain", "prefix", 1, 1000)),
        "PBOTH": tagged(mod("GBoth", "prefix", 1, 1000), "fire", "speed"),
        "SSPEED": tagged(mod("GSpeed", "suffix", 1, 1000), "speed"),
        "SMANA": tagged(mod("GMana", "suffix", 1, 1000), "mana"),
        "SATT": tagged(mod("GAtt", "suffix", 1, 1000), "attack"),
        "SCAST": tagged(mod("GCast", "suffix", 1, 1000), "caster"),
        "SPLAIN": tagged(mod("GSPlain", "suffix", 1, 1000)),
        "EssForced": tagged(mod("GE", "suffix", 90, 0, essence=True, spawn=(("default", 0),), low=7, high=8)),
        "MATT": meta_mod("ItemGenerationCannotRollAttackAffixes", "suffix", "Cannot roll Attack Modifiers"),
        "MCAST": meta_mod("ItemGenerationCannotRollCasterAffixes", "suffix", "Cannot roll Caster Modifiers"),
        "MMULTI": meta_mod("ItemGenerationCanHaveMultipleCraftedMods", "suffix", "Can have up to 3 Crafted Modifiers"),
        "MLOCK": meta_mod("ItemGenerationCannotChangeSuffixes", "prefix", "Suffixes Cannot Be Changed"),
        "BENCHS": meta_mod("GBenchS", "suffix", "bench suffix one"),
        "BENCHS2": meta_mod("GBenchS2", "suffix", "bench suffix two"),
        "BENCHP": meta_mod("GBenchP", "prefix", "bench prefix"),
    }


def fossil(name: str, positive=(), negative=(), **extra) -> dict:
    record = {
        "name": name,
        "positive_mod_weights": [{"tag": tag, "weight": weight} for tag, weight in positive],
        "negative_mod_weights": [{"tag": tag, "weight": weight} for tag, weight in negative],
        "added_mods": [], "forced_mods": [], "sell_price_mods": [], "allowed_tags": [], "forbidden_tags": [],
        "rolls_lucky": False, "mirrors": False, "changes_quality": False,
    }  # fmt: skip
    record.update(extra)
    return record


FIRE, SPEED, CUT = "Fire Test Fossil", "Speed Test Fossil", "Cut Test Fossil"
FOSSILS = {
    FIRE: fossil(FIRE, [("fire", 1000)], [("cold", 0)]),
    SPEED: fossil(SPEED, [("speed", 1000)], [("mana", 0)]),
    CUT: fossil(CUT, [], [("attack", 15)]),
    "Opulent Fossil": fossil("Opulent Fossil", [("drop", 1000)]),
    "Hollow Test Fossil": fossil("Hollow Test Fossil", forced_mods=["EssForced"]),
    "Ringless Fossil": fossil("Ringless Fossil", [("fire", 1000)], allowed_tags=["amulet"]),
    "Forbidding Fossil": fossil("Forbidding Fossil", [("fire", 1000)], forbidden_tags=["ring"]),
}


def raw() -> RawExport:
    base = {"name": "Test Ring", "tags": ["ring", "default"], "item_class": "Ring", "domain": "item", "release_state": "released", "implicits": []}
    bases = {RING: base, CHAOS: currency("Chaos Orb"), "Metadata/Items/Currency/CurrencyConvertToNormal": currency("Orb of Scouring")}
    bench = lambda mod_id, text=None: {"actions": {"add_explicit_mod": mod_id}, "cost": {CHAOS: 1}, "item_classes": ["Ring"], "bench_tier": 1}  # noqa: E731
    options = [bench(mod_id) for mod_id in ("MATT", "MCAST", "MMULTI", "MLOCK", "BENCHS", "BENCHS2", "BENCHP")]
    options.append({"actions": {"remove_crafted_mods": True}, "cost": {"Metadata/Items/Currency/CurrencyConvertToNormal": 1}, "item_classes": ["Ring"], "bench_tier": 0})
    essences = {"Metadata/Items/Currency/CurrencyEssenceHigh": {"name": "Shrieking Essence of Test", "level": 6, "item_level_restriction": None, "mods": {"Ring": "EssForced"}}}
    return RawExport(ring_mods(), bases, options, essences, "tiny")


def crafter(laws: Laws | None = None, influences=()) -> Crafter:
    return Crafter(raw(), RING, 80, influences=influences, laws=laws)


def fossils(*names: str) -> FossilSet:
    return FossilSet(tuple(names), FOSSILS)


def held(*ids, fractured=(), crafted=()):
    return tuple(Held(mod_id, (1,), fractured=mod_id in fractured, crafted=mod_id in crafted) for mod_id in ids)


def rare(*ids, fractured=(), crafted=()) -> Item:
    return Item("rare", held(*ids, fractured=fractured, crafted=crafted))


def weights(pool) -> dict[str, float]:
    return dict(zip(pool.ids, pool.weights, strict=True))


def z_of(hits: int, n: int, p: float) -> float:
    return (hits - n * p) / math.sqrt(n * p * (1 - p))


# --- fossils (#608) ---------------------------------------------------------------------------------------------------------------------------


def test_a_fossil_boosts_the_tags_it_names_blocks_the_ones_it_forbids_and_a_mod_with_two_boosted_tags_gets_the_factors_added():
    pool = crafter().pool(fossils=fossils(FIRE, SPEED))

    assert weights(pool) == {
        "PFIRE": 10000.0, "PLIFE": 1000.0, "PATT": 1000.0, "PPLAIN": 1000.0, "PBOTH": 20000.0,
        "SSPEED": 10000.0, "SATT": 1000.0, "SCAST": 1000.0, "SPLAIN": 1000.0,
    }  # fmt: skip  # PCOLD and SMANA are blocked; PBOTH is fire and speed: 10 + 10, not 10 x 10


def test_a_cut_factor_below_one_multiplies_and_is_not_a_block():
    pool = crafter().pool(fossils=fossils(CUT))

    assert weights(pool)["PATT"] == pytest.approx(150.0) and weights(pool)["SATT"] == pytest.approx(150.0) and weights(pool)["PFIRE"] == 1000.0


def test_without_the_boost_law_the_boosted_tags_keep_their_weight():
    pool = crafter(Laws(fossil_boost=False)).pool(fossils=fossils(FIRE, SPEED))

    assert weights(pool)["PFIRE"] == 1000.0 and weights(pool)["PBOTH"] == 1000.0 and "PCOLD" not in weights(pool)


def test_without_the_block_law_a_blocked_tag_stays_in_the_pool():
    pool = crafter(Laws(fossil_block=False)).pool(fossils=fossils(FIRE, SPEED))

    assert weights(pool)["PCOLD"] == 1000.0 and weights(pool)["SMANA"] == 1000.0 and weights(pool)["PFIRE"] == 10000.0


def test_a_resonator_rerolls_a_rare_item_to_four_five_or_six_mods_without_the_blocked_mods_and_keeps_a_fractured_one():
    c = crafter()
    rng = Random(SEED)
    counts = {4: 0, 5: 0, 6: 0}
    for _ in range(4000):
        item = c.fossil(rare("PPLAIN", "SPLAIN", "SATT", fractured=("PPLAIN",)), rng, fossils(FIRE, SPEED))
        ids = {held_mod.mod_id for held_mod in item.mods}
        counts[len(item.mods)] += 1
        assert "PPLAIN" in ids and not ids & {"PCOLD", "SMANA"} and item.rarity == "rare"
    assert abs(z_of(counts[4], 4000, 8 / 12)) < Z and abs(z_of(counts[5], 4000, 3 / 12)) < Z and abs(z_of(counts[6], 4000, 1 / 12)) < Z


def test_a_resonator_takes_a_rare_item_only_and_not_one_with_a_metamod_unless_that_law_is_off_and_asks_what_the_fossils_ask_of_the_base():
    c = crafter()
    rng = Random(SEED)
    for item in (Item("normal"), Item("magic", held("PFIRE"))):
        with pytest.raises(Refused):
            c.fossil(item, rng, fossils(FIRE))
    with pytest.raises(Refused, match="metamod"):
        c.fossil(rare("PFIRE", "MATT", crafted=("MATT",)), rng, fossils(FIRE))
    assert crafter(Laws(metamod_refuses_rerolls=False)).fossil(rare("PFIRE", "MATT", crafted=("MATT",)), rng, fossils(FIRE)).rarity == "rare"
    assert crafter().fossil(rare("PFIRE", "MMULTI", crafted=("MMULTI",)), rng, fossils(FIRE)).rarity == "rare"  # the multimod does not block it
    with pytest.raises(Refused, match="base tags"):
        c.fossil(rare(), rng, fossils("Ringless Fossil"))
    with pytest.raises(Refused, match="forbids"):
        c.fossil(rare(), rng, fossils("Forbidding Fossil"))


def test_a_fossil_that_does_more_than_change_the_weights_is_refused_by_name_and_so_is_the_same_fossil_twice():
    for name in ("Opulent Fossil", "Hollow Test Fossil"):
        with pytest.raises(Unsupported, match="lacks"):
            fossils(name)
    with pytest.raises(Unsupported, match="one fossil of each type"):
        fossils(FIRE, FIRE)
    with pytest.raises(Unsupported, match="no fossil of this name"):
        fossils("Nonesuch Fossil")


# --- the Harvest reforge (#609) -------------------------------------------------------------------------------------------------------------


def test_a_harvest_reforge_always_holds_a_mod_of_its_tag_which_counts_in_the_total_and_keeps_the_fractured_mod():
    c = crafter()
    rng = Random(SEED)
    counts = {4: 0, 5: 0, 6: 0}
    for _ in range(3000):
        item = c.harvest(rare("PFIRE", "SPLAIN", fractured=("PFIRE",)), rng, "life")
        ids = [held_mod.mod_id for held_mod in item.mods]
        counts[len(ids)] += 1
        assert "PLIFE" in ids and "PFIRE" in ids and len(ids) == len(set(ids))
    assert abs(z_of(counts[4], 3000, 8 / 12)) < Z and abs(z_of(counts[6], 3000, 1 / 12)) < Z


def test_the_guaranteed_mod_is_added_even_when_the_kept_mods_already_reach_the_total():
    item = crafter().harvest(rare("PFIRE", "PCOLD", "SSPEED", "SMANA", fractured=("PFIRE", "PCOLD", "SSPEED", "SMANA")), Random(SEED), "life")

    assert len(item.mods) in (5, 6) and "PLIFE" in {held_mod.mod_id for held_mod in item.mods}  # four kept, the guaranteed one, and a sixth when the total drawn is 6


def test_without_the_guarantee_a_harvest_reforge_is_a_chaos_orb():
    c = crafter(Laws(harvest_guarantee=False))
    rng = Random(SEED)
    without = sum("PLIFE" not in {held_mod.mod_id for held_mod in c.harvest(rare("PFIRE", fractured=("PFIRE",)), rng, "life").mods} for _ in range(400))

    assert without > 100  # a chaos reforge holds the life mod only about a third of the time


def test_a_harvest_reforge_is_refused_when_the_pool_has_no_mod_of_the_tag_or_none_fits_and_on_a_normal_or_magic_item():
    c = crafter()
    rng = Random(SEED)
    with pytest.raises(Refused, match="no mod with the tag"):
        c.harvest(rare("PFIRE"), rng, "chaos")
    with pytest.raises(Refused, match="fits"):
        c.harvest(rare("PLIFE", fractured=("PLIFE",)), rng, "life")  # the only life mod's group is on the item
    with pytest.raises(Refused):
        c.harvest(Item("magic", held("PFIRE")), rng, "life")
    with pytest.raises(Unsupported, match="metamod"):
        c.harvest(rare("PFIRE", "MATT", crafted=("MATT",)), rng, "life")


# --- the Exalted Orb (#610) ---------------------------------------------------------------------------------------------------------------


def test_an_exalted_orb_adds_one_mod_to_a_rare_item_keeping_all_and_is_refused_on_a_full_or_a_magic_item():
    c = crafter()
    rng = Random(SEED)
    item = c.exalt(rare("PFIRE", "SSPEED", fractured=("PFIRE",)), rng)
    assert len(item.mods) == 3 and item.mods[0].fractured and item.rarity == "rare"
    with pytest.raises(Refused):
        c.exalt(Item("magic", held("PFIRE")), rng)
    full = rare("PFIRE", "PCOLD", "PLIFE", "SSPEED", "SMANA", "SATT")
    with pytest.raises(Refused, match="no mod"):
        c.exalt(full, rng)
    only_prefixes_left = rare("SSPEED", "SMANA", "SATT", "PFIRE")
    for _ in range(50):
        assert c.exalt(only_prefixes_left, rng).mods[-1].mod_id in {"PCOLD", "PLIFE", "PATT", "PPLAIN", "PBOTH"}  # the suffixes are full


def test_under_cannot_roll_attack_modifiers_an_exalted_orb_never_adds_an_attack_mod_and_without_the_law_it_does_with_its_weight():
    item = rare("PPLAIN", "MATT", crafted=("MATT",))
    rng = Random(SEED)
    barred = crafter()
    free = crafter(Laws(metamod_filter=False))
    with_filter = sum(barred.exalt(item, rng).mods[-1].mod_id in {"PATT", "SATT"} for _ in range(3000))
    without = sum(free.exalt(item, rng).mods[-1].mod_id in {"PATT", "SATT"} for _ in range(3000))

    assert with_filter == 0
    assert abs(z_of(without, 3000, 2 / 10)) < Z  # PATT and SATT of the ten mods that can still be added (PPLAIN's group and MATT's are on the item)


def test_cannot_roll_caster_modifiers_filters_the_caster_tag_the_same_way():
    item = rare("PPLAIN", "MCAST", crafted=("MCAST",))
    rng = Random(SEED)

    assert sum(crafter().exalt(item, rng).mods[-1].mod_id == "SCAST" for _ in range(1500)) == 0


def test_a_reroll_is_filtered_only_by_a_metamod_it_leaves_on_the_item():
    c = crafter()
    rng = Random(SEED)
    kept = [c.chaos(rare("MATT", "PPLAIN", fractured=("MATT",), crafted=("MATT",)), rng) for _ in range(300)]
    gone = [c.chaos(rare("MATT", "PPLAIN", crafted=("MATT",)), rng) for _ in range(300)]

    assert not any({held_mod.mod_id for held_mod in item.mods} & {"PATT", "SATT"} for item in kept)
    assert any({held_mod.mod_id for held_mod in item.mods} & {"PATT", "SATT"} for item in gone) and not any(held_mod.crafted for item in gone for held_mod in item.mods)


# --- the Orb of Annulment ---------------------------------------------------------------------------------------------------------------------


def removed(c: Crafter, item: Item, trials: int, seed=SEED) -> dict[str, int]:
    rng = Random(seed)
    found: dict[str, int] = {}
    for _ in range(trials):
        after = c.annul(item, rng)
        assert len(after.mods) == len(item.mods) - 1 and after.rarity == item.rarity
        for gone in {held_mod.mod_id for held_mod in item.mods} - {held_mod.mod_id for held_mod in after.mods}:
            found[gone] = found.get(gone, 0) + 1
    return found


def test_an_annulment_removes_one_mod_with_equal_chance_and_never_a_fractured_one_and_keeps_the_rarity():
    gone = removed(crafter(), rare("PFIRE", "PCOLD", "SSPEED", fractured=("PFIRE",)), 3000)

    assert "PFIRE" not in gone and abs(z_of(gone["PCOLD"], 3000, 1 / 2)) < Z
    assert crafter().annul(Item("magic", held("PFIRE")), Random(1)) == Item("magic", ())  # a magic item left with no mod stays magic


def test_without_the_law_an_annulment_removes_a_fractured_mod_too():
    gone = removed(crafter(Laws(annul_spares_fractured=False)), rare("PFIRE", "PCOLD", "SSPEED", fractured=("PFIRE",)), 3000)

    assert abs(z_of(gone["PFIRE"], 3000, 1 / 3)) < Z


def test_an_annulment_is_refused_on_a_normal_item_and_on_one_with_nothing_it_can_remove():
    c = crafter()
    with pytest.raises(Refused):
        c.annul(Item("normal"), Random(1))
    with pytest.raises(Refused, match="no mod"):
        c.annul(rare("PFIRE", fractured=("PFIRE",)), Random(1))


def test_under_cannot_roll_attack_modifiers_an_annulment_does_not_remove_an_attack_mod_and_the_metamod_itself_can_go():
    item = rare("PATT", "SSPEED", "MATT", crafted=("MATT",))
    gone = removed(crafter(), item, 3000)
    gone_free = removed(crafter(Laws(metamod_filter=False)), item, 3000)

    assert "PATT" not in gone and abs(z_of(gone["SSPEED"], 3000, 1 / 2)) < Z and abs(z_of(gone["MATT"], 3000, 1 / 2)) < Z
    assert abs(z_of(gone_free["PATT"], 3000, 1 / 3)) < Z


# --- the Fracturing Orb ------------------------------------------------------------------------------------------------------------------------


def test_a_fracturing_orb_fractures_one_mod_with_equal_chance_and_changes_nothing_else():
    c = crafter()
    rng = Random(SEED)
    item = rare("PFIRE", "PCOLD", "SSPEED", "SMANA")
    hits: dict[str, int] = {}
    for _ in range(4000):
        after = c.fracture(item, rng)
        fractured = [held_mod.mod_id for held_mod in after.mods if held_mod.fractured]
        assert len(fractured) == 1 and [held_mod.mod_id for held_mod in after.mods] == [held_mod.mod_id for held_mod in item.mods]
        hits[fractured[0]] = hits.get(fractured[0], 0) + 1
    assert all(abs(z_of(count, 4000, 1 / 4)) < Z for count in hits.values()) and len(hits) == 4


def test_a_fracturing_orb_needs_four_mods_a_rare_item_with_no_fractured_mod_and_no_influence():
    rng = Random(SEED)
    with pytest.raises(Refused, match="four"):
        crafter().fracture(rare("PFIRE", "PCOLD", "SSPEED"), rng)
    assert len(crafter(Laws(fracture_needs_four=False)).fracture(rare("PFIRE", "PCOLD", "SSPEED"), rng).mods) == 3
    with pytest.raises(Refused):
        crafter().fracture(Item("magic", held("PFIRE", "PCOLD", "SSPEED", "SMANA")), rng)
    with pytest.raises(Refused, match="fractured"):
        crafter().fracture(rare("PFIRE", "PCOLD", "SSPEED", "SMANA", fractured=("PFIRE",)), rng)
    with pytest.raises(Refused, match="influenced"):
        crafter(influences=("hunter",)).fracture(rare("PFIRE", "PCOLD", "SSPEED", "SMANA"), rng)


def test_a_crafted_mod_and_a_metamod_can_be_fractured_and_then_survive_a_reroll():
    rng = Random(SEED)
    item = rare("PFIRE", "PCOLD", "SSPEED", "MATT", crafted=("MATT",))
    seen = set()
    for _ in range(400):
        after = crafter().fracture(item, rng)
        seen |= {held_mod.mod_id for held_mod in after.mods if held_mod.fractured}

    assert seen == {"PFIRE", "PCOLD", "SSPEED", "MATT"}


# --- the bench: metamods and Remove Crafted Mods -----------------------------------------------------------------------------------------------


def test_an_item_holds_one_crafted_mod_but_three_with_the_multimod_which_counts_as_one():
    c = crafter()
    rng = Random(SEED)
    one = c.bench(rare("PFIRE"), rng, "BENCHS")
    with pytest.raises(Refused, match="as many crafted"):
        c.bench(one, rng, "BENCHP")
    many = c.bench(c.bench(c.bench(rare("PFIRE"), rng, "MMULTI"), rng, "BENCHS"), rng, "BENCHP")
    assert sum(held_mod.crafted for held_mod in many.mods) == 3
    with pytest.raises(Refused, match="as many crafted"):
        c.bench(many, rng, "BENCHS2")


def test_without_the_multimod_law_the_limit_stays_one():
    c = crafter(Laws(multimod=False))
    rng = Random(SEED)
    with pytest.raises(Refused, match="as many crafted"):
        c.bench(c.bench(rare("PFIRE"), rng, "MMULTI"), rng, "BENCHS")


def test_a_bench_craft_still_follows_the_slot_and_the_group_rules_under_the_multimod():
    c = crafter()
    rng = Random(SEED)
    item = rare("PFIRE", "SSPEED", "SMANA", "MMULTI", crafted=("MMULTI",))  # three suffixes, the multimod one of them
    with pytest.raises(Refused, match="no open slot"):
        c.bench(item, rng, "BENCHS")
    with pytest.raises(Refused, match="group"):
        c.bench(c.bench(rare("MMULTI", crafted=("MMULTI",)), rng, "MATT"), rng, "MATT")


def test_remove_crafted_mods_takes_every_crafted_mod_and_metamod_off_and_leaves_the_rest():
    c = crafter()
    item = rare("PFIRE", "PCOLD", "SSPEED", "MATT", "BENCHP", "BENCHS", fractured=("PCOLD",), crafted=("MATT", "BENCHP", "BENCHS"))
    after = c.remove_crafted(item)

    assert [held_mod.mod_id for held_mod in after.mods] == ["PFIRE", "PCOLD", "SSPEED"] and after.rarity == "rare"
    assert c.barred_tags(after.mods) == frozenset()  # the metamod's effect ends with it
    with pytest.raises(Refused, match="no crafted"):
        c.remove_crafted(after)
    with pytest.raises(Refused):
        c.remove_crafted(Item("normal"))


def test_an_essence_is_refused_by_a_metamod_but_not_by_the_multimod_and_without_the_law_it_is_taken():
    record = raw().essences["Metadata/Items/Currency/CurrencyEssenceHigh"]
    rng = Random(SEED)
    with pytest.raises(Refused, match="metamod"):
        crafter().essence(rare("PFIRE", "MATT", crafted=("MATT",)), rng, record)
    with pytest.raises(Refused, match="metamod"):
        crafter().essence(rare("PFIRE", "MLOCK", crafted=("MLOCK",)), rng, record)
    assert crafter().essence(rare("PFIRE", "MMULTI", crafted=("MMULTI",)), rng, record).rarity == "rare"
    assert crafter(Laws(metamod_refuses_rerolls=False)).essence(rare("PFIRE", "MATT", crafted=("MATT",)), rng, record).rarity == "rare"


# --- the actions of a route (the world) ---------------------------------------------------------------------------------------------------------

TARGET = """
base: Test Ring
item_level: 80
requirements:
  - family: GLife
    mod: PLIFE
start_item:
  rarity: rare
  mods: []
start: bought
"""
PRICES = {
    "prices": {
        "Exalted Orb": {"chaos": 2.0},
        "Orb of Annulment": {"chaos": 11.0},
        "Fracturing Orb": {"chaos": 260.0},
        "Chaos Orb": {"chaos": 1.0},
        "Orb of Scouring": {"chaos": 0.5},
        "Potent Chaotic Resonator": {"chaos": 1.5},
        "Powerful Chaotic Resonator": {"chaos": 3.0},
        FIRE: {"chaos": 20.0},
        SPEED: {"chaos": 30.0},
        CUT: {"chaos": 40.0},
        "Wild Crystallised Lifeforce": {"chaos": 0.02},
        "Primal Crystallised Lifeforce": {"chaos": 0.04},
        "Test Ring, rare": {"chaos": 5.0},
    }
}


def world() -> World:
    w = World(raw(), TARGET, PRICES, "Test Ring, rare")
    w.fossil_records = FOSSILS
    return w


def test_a_fossil_set_costs_the_resonator_of_its_size_and_each_fossil():
    w = world()

    assert w.action(f"Fossils {FIRE} + {SPEED}").cost == pytest.approx(1.5 + 20.0 + 30.0)
    assert w.action(f"Fossils {FIRE} + {SPEED} + {CUT}").cost == pytest.approx(3.0 + 20.0 + 30.0 + 40.0)
    assert w.action(f"Fossils {FIRE} + {SPEED}").kind == "fossil"
    with pytest.raises(Unsupported, match="no Chaotic resonator has 5 sockets"):
        w.action("Fossils A + B + C + D + E")
    with pytest.raises(Unsupported, match="lacks the fossil"):
        w.action("Fossils Opulent Fossil + Fire Test Fossil")


def test_a_harvest_reforge_costs_its_lifeforce_and_the_ones_not_modelled_are_named():
    w = world()

    assert w.action("Harvest Reforge Life").cost == pytest.approx(75 * 0.02) and w.action("Harvest Reforge Life").tag == "life"
    assert w.action("Harvest Reforge Defence").tag == "defences" and w.action("Harvest Reforge Defence").cost == pytest.approx(75 * 0.04)
    with pytest.raises(Unsupported, match="more or less likely"):
        w.action("Harvest Reforge more likely")


def test_the_orbs_the_bench_metamods_and_remove_crafted_mods_are_found_and_priced():
    w = world()

    assert [w.action(label).kind for label in ("Exalted Orb", "Orb of Annulment", "Fracturing Orb")] == ["exalted", "annulment", "fracturing"]
    assert w.action("Remove Crafted Mods").kind == "remove_crafted" and w.action("Remove Crafted Mods").cost == 0.5
    assert w.action("Bench craft Cannot roll Attack Modifiers").mod_id == "MATT"
    assert w.action("Bench craft Can have up to 3 Crafted Modifiers").mod_id == "MMULTI"
    with pytest.raises(Unsupported, match="lock a side"):
        w.action("Bench craft Suffixes Cannot Be Changed")
