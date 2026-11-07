"""The numbers PoEDB publishes, against our data, our model and the recorded Craft of Exile counts (ticket #544).

`tests/fixtures/coe_recorded/poedb_published.json` holds what two PoEDB pages said on 2026-11-07 (facts only):

* `https://poedb.tw/us/Belts`, tab "Modifiers Calc", item class Belt: every mod with its level, side, family and weight
  (claim `magic_orbs.poedb_belt_weights`);
* `https://poedb.tw/us/Essence`: what each essence does, its tier and its level cap (claims `essence.poedb_*`).

The PoE wiki loads only in the desktop app's browser pane (an anonymous GET gets a bot check), so its numbers stay those
of the existing claims (`affix_count.rare_reroll_ratio`, `magic_orbs.magic_mod_count`), which this module also checks
against the recorded counts.

The tier odds of the three magic-item orbs are worked out here from the published weights ALONE, by the draw rule
(a mod's chance is its weight over the weights eligible for the draw), and then compared three ways: with our exact
model (equality), and with the recorded emulator counts (the binomial test of `coe_recorded_support`).

Needs the cached dump (`CRAFTING_CACHE_DIR`); CI fetches it.
"""

import json
import re
from fractions import Fraction
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from coe_recorded_support import ALPHA, Cell, OurCase, failures, load_recorded

from crafting_system.actions import ApplyEssence
from crafting_system.items import Item, Rarity
from crafting_system.items.spawn import spawn_weight
from crafting_system.rules import load_registry

PUBLISHED = json.loads((Path(__file__).resolve().parent / "fixtures" / "coe_recorded" / "poedb_published.json").read_text(encoding="utf-8"))
ROWS = PUBLISHED["belt_modifiers"]["rows"]
ESSENCES = PUBLISHED["essences"]["entries"]
RECORDED = load_recorded()["cases"]
BELT = "Metadata/Items/Belts/Belt3"
ITEM_LEVEL = 86


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def claims():
    return load_registry()


@pytest.fixture(scope="module")
def ours(data):
    return {case: OurCase(data, RECORDED[case]) for case in ("alteration-r13-belt", "augmentation-r13-belt", "regal-r13-belt")}


def mod_id_of(data, row) -> str:
    found = [
        m.id for m in data.mods.values()
        if (m.name, m.required_level, m.generation_type) == (row["name"], row["level"], row["side"]) and m.domain == "item"
        and spawn_weight(m, data.base_items[BELT].tags) > 0
    ]  # fmt: skip
    assert len(found) == 1, (row, found)
    return found[0]


# --- the published table is the claim, and is our Leather Belt pool ---------------------------------------


def test_the_claim_states_the_table_it_quotes(claims):
    value = claims["magic_orbs.poedb_belt_weights"].value
    assert len(ROWS) == value["rows"]
    assert sum(r["weight"] for r in ROWS if r["side"] == "prefix") == value["prefix_total"]
    assert sum(r["weight"] for r in ROWS if r["side"] == "suffix") == value["suffix_total"]
    fecund = next(r for r in ROWS if r["name"] == "Fecund")
    assert (fecund["level"], fecund["families"], fecund["weight"]) == (64, ["IncreasedLife"], 1000)


def test_poedb_s_belt_table_is_our_leather_belt_pool(data):
    """Same mods (name, level, side), same weights: our pool is not a different table than the published one."""
    base = data.base_items[BELT]
    ours = sorted(
        (m.name, m.required_level, m.generation_type, int(spawn_weight(m, base.tags)))
        for m in data.mods.values()
        if m.domain == "item" and m.generation_type in ("prefix", "suffix") and spawn_weight(m, base.tags) > 0
    )  # fmt: skip
    theirs = sorted((r["name"], r["level"], r["side"], r["weight"]) for r in ROWS)
    assert ours == theirs


# --- the tier odds from the published weights alone ---------------------------------------------------------


def eligible(side=None, without=()):
    """The published rows an item of level 86 can draw: level at most 86, in the given side, outside the given families."""
    return [
        r for r in ROWS
        if r["level"] <= ITEM_LEVEL and (side is None or r["side"] == side) and not set(r["families"]) & set(without)
    ]  # fmt: skip


def odds_augmentation() -> dict[tuple, Fraction]:
    """A magic belt with a suffix gets one prefix: weight over the prefix weights."""
    rows = eligible("prefix")
    total = sum(r["weight"] for r in rows)
    return {(r["name"], r["level"], r["side"]): Fraction(r["weight"], total) for r in rows}


def odds_regal() -> dict[tuple, Fraction]:
    """A magic belt with Mana (prefix) and Cold Resistance (suffix) becomes rare and gets one mod from both sides, minus the two families."""
    rows = eligible(without=("IncreasedMana", "ColdResistance"))
    total = sum(r["weight"] for r in rows)
    return {(r["name"], r["level"], r["side"]): Fraction(r["weight"], total) for r in rows}


def odds_alteration() -> dict[tuple, Fraction]:
    """One or two mods, 1/2 each (the claim `magic_orbs.magic_mod_count`); the second is on the side the first left.

    P(x) = w_x / W + 1/2 * (W_other / W) * (w_x / W_side), with W the weight of all eligible mods, W_side that of x's side and
    W_other that of the other side: x is the first draw, or (with two mods) the second one after a first draw on the other side.
    """
    everything = eligible()
    total = sum(r["weight"] for r in everything)
    side_total = {side: sum(r["weight"] for r in everything if r["side"] == side) for side in ("prefix", "suffix")}
    other = {"prefix": "suffix", "suffix": "prefix"}
    return {
        (r["name"], r["level"], r["side"]): Fraction(r["weight"], total)
        + Fraction(1, 2) * Fraction(side_total[other[r["side"]]], total) * Fraction(r["weight"], side_total[r["side"]])
        for r in everything
    }


ODDS = {"augmentation-r13-belt": odds_augmentation, "regal-r13-belt": odds_regal, "alteration-r13-belt": odds_alteration}


@pytest.mark.parametrize("case", sorted(ODDS))
def test_the_published_weights_give_our_exact_chance_of_every_mod(data, ours, case):
    published = {mod_id_of(data, dict(name=k[0], level=k[1], side=k[2])): chance for k, chance in ODDS[case]().items()}
    model = {mod_id: chance for mod_id, chance in ours[case].marginals().items() if chance}  # the closed side's mods have chance 0
    assert set(model) == set(published)
    assert model == published


@pytest.mark.parametrize("case", sorted(ODDS))
def test_the_published_weights_give_the_emulator_s_frequencies(data, case):
    record = RECORDED[case]
    cells = [
        Cell(case, "mod", mod_id_of(data, dict(name=k[0], level=k[1], side=k[2])), record["applied"],
             record["mods"].get(mod_id_of(data, dict(name=k[0], level=k[1], side=k[2])), 0), float(chance))
        for k, chance in ODDS[case]().items()
    ]  # fmt: skip
    assert sum(cell.testable for cell in cells) >= 30
    bad = failures(cells, ALPHA)
    assert not bad, "\n".join(cell.describe() for cell in bad)


@pytest.mark.parametrize("case", sorted(ODDS))
def test_the_tier_one_chance_of_life_is_the_published_weight_share(data, ours, case):
    """The chance of Life tier 1 (+(130-144), weight 1000) from the published table; the tier line of the goal (OR-1)."""
    life = next(r for r in ROWS if r["name"] == "Fecund")
    published = ODDS[case]()[(life["name"], life["level"], life["side"])]
    assert ours[case].marginals()[mod_id_of(data, life)] == published
    assert mod_id_of(data, life) == "IncreasedLife9"


# --- the number of mods ----------------------------------------------------------------------------------


def test_the_alteration_gives_one_or_two_mods_in_the_claimed_ratio(claims):
    """The published 1:1 (claim magic_orbs.magic_mod_count) against the recorded Alteration: the share of belts with two mods."""
    ratio = claims["magic_orbs.magic_mod_count"].value
    record = RECORDED["alteration-r13-belt"]
    two = sum(count for shape, count in record["shapes"].items() if sum(int(x) for x in re.findall(r"\d+", shape)) == 2)
    cell = Cell("alteration-r13-belt", "total", "two mods", record["applied"], two, float(Fraction(ratio[2], ratio[1] + ratio[2])))
    assert not failures([cell], ALPHA), cell.describe()


@pytest.mark.parametrize("case", ["chaos-r13-belt", "essence-r05-ring", "essence-r10-boots", "essence-r11-helmet", "essence-c02-helmet"])
def test_a_rare_reroll_has_four_five_or_six_mods_as_the_wiki_claims(claims, case):
    """The claim affix_count.rare_reroll_ratio (the wiki: 4, 5 or 6 affixes at 8:3:1) against the recorded totals, essences included."""
    ratio = claims["affix_count.rare_reroll_ratio"].value
    record = RECORDED[case]
    totals = {4: 0, 5: 0, 6: 0}
    for shape, count in record["shapes"].items():
        total = sum(int(x) for x in re.findall(r"\d+", shape))
        totals[total] = totals.get(total, 0) + count
    assert set(totals) <= {4, 5, 6}, totals
    whole = sum(ratio.values())
    bad = [
        Cell(case, "total", f"{k} mods", record["applied"], totals[k], ratio[k] / whole)
        for k in (4, 5, 6)
    ]  # fmt: skip
    assert not failures(bad, ALPHA), "\n".join(c.describe() for c in bad)  # three cells, Bonferroni over them


# --- the essence rule -------------------------------------------------------------------------------------


def parse_range(text: str) -> tuple[int, int]:
    low, high = re.search(r"\((\d+)-(\d+)\)", text).groups()
    return int(low), int(high)


def class_effect(name: str, class_word: str) -> str:
    """The text PoEDB prints for `class_word` (a class name of its list, "Rings") in the essence's entry."""
    effects = ESSENCES[name]["effects"]
    match = re.search(rf"[A-Za-z, ]*\b{class_word}\b[A-Za-z, ]*: ([^:]*?)(?= [A-Z][A-Za-z, ]*: |$)", effects)
    assert match, f"{name}: no line for {class_word}"
    return match.group(1)


FORCED_ON = {
    "Deafening Essence of Rage": ("Metadata/Items/Rings/Ring10", "Rings"),
    "Shrieking Essence of Spite": ("Metadata/Items/Armours/Boots/BootsInt9", "Boots"),
    "Shrieking Essence of Loathing": ("Metadata/Items/Armours/Helmets/HelmetDex10", "Helmets"),
    "Deafening Essence of Envy": ("Metadata/Items/Armours/Helmets/HelmetStr10", "Helmets"),
}


@pytest.mark.parametrize("name", sorted(FORCED_ON))
def test_the_guaranteed_mod_has_the_values_poedb_publishes(data, claims, name):
    base, class_word = FORCED_ON[name]
    published = parse_range(class_effect(name, class_word))
    assert published == tuple(claims["essence.poedb_forced_values_of_the_benchmark_routes"].value[name])
    item = Item.build(data, base_id=base, item_level=86, rarity=Rarity.RARE, mods=())
    outcomes = ApplyEssence(name).outcomes(data, item)
    forced = data.mods[outcomes.forced]
    assert len(forced.stats) == 1
    assert (min(forced.stats[0].min, forced.stats[0].max), max(forced.stats[0].min, forced.stats[0].max)) == published


def test_one_guaranteed_property_and_the_level_caps_of_the_low_essences(data, claims):
    """PoEDB: a tier 5-7 essence reforges a rare item with one guaranteed property; a tier 1-4 one only upgrades a normal item, with a level cap."""
    caps = claims["essence.poedb_one_guaranteed_property"].value
    by_name = {essence.name: essence for essence in data.essences.values()}
    for name, entry in ESSENCES.items():
        essence = by_name[name]
        assert essence.level == entry["tier"]  # the record's `level` is the tier (essence.normal_only_up_to_level)
        if entry["tier"] >= 5:
            assert entry["rule"] == "Upgrades a normal item to rare or reforges a rare item, guaranteeing one property"
            assert entry["level_cap"] is None and essence.item_level_restriction is None
        else:
            assert entry["rule"] == "Upgrades a normal item to rare with one guaranteed property"
            assert entry["level_cap"] == caps[entry["tier"]] == essence.item_level_restriction


def test_the_rare_reforge_of_the_high_essences_is_offered_and_the_low_ones_are_not(data):
    from crafting_system.actions.catalog import catalog

    rare = Item.build(data, base_id="Metadata/Items/Armours/Helmets/HelmetDex10", item_level=86, rarity=Rarity.RARE, mods=())
    normal = Item.build(data, base_id="Metadata/Items/Armours/Helmets/HelmetDex10", item_level=86, rarity=Rarity.NORMAL, mods=())
    on_rare = {action.label(data) for action in catalog(data, rare)}
    on_normal = {action.label(data) for action in catalog(data, normal)}
    for name, entry in ESSENCES.items():
        if "Hatred" not in name:
            continue
        assert (name in on_rare) == (entry["tier"] >= 5), name
        assert name in on_normal, name
