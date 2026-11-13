"""The Orb of Unravelling on the real 3.29.3.3 dump (ticket #281, ADR-0044); these skip cleanly when the dump is not cached (CI has it).

The expected numbers are the post's and the sheet's (ADR-0044, "Tests that are published numbers"), typed here:

* a Turquoise Amulet of item level 86: the suffix pool weighs 125,250 (the sheet's own total, quoted in the claim
  `memory_strands.unravelling_chance_model`), and each attribute has nine tiers of weight 1,000 (`Strength1` at level 1 up to `Strength9` at
  82). A T9 attribute mod rises for certain at 32 strands (310 of 310) and with 31 x 8,000 / 250,500 = 99.0% at 31 (14 of 15);
* a Driftwood Wand of item level 84 holding the T4 lightning damage to spells (`SpellAddedLightningDamage6`, weight 800; above it
  `SpellAddedLightningDamage7` 800, `8` 250, `9` 60): a raised mod ends at T3 / T2 / T1 with 75.0 / 20.95 / 4.05% (the plan, reading B)
  and 81.08 / 16.89 / 2.03% under reading A;
* a Hunter Turquoise Amulet of item level 86: the influence mod `FireDamageOverTimeMultiplierInfluence1_` (level 68) can only rise to
  `FireDamageOverTimeMultiplierInfluence2` (level 80), never to the Elevated `FireDamageOverTimeMultiplierUber1___` or `Uber2` (weight 0 in
  the pool), and `Influence2` is the top of its table; the essence-only `AdditionalPierceEssence5` (level 1, weight 0) is never raised,
  though its type holds the influence tier `AdditionalPierceInfluence1` above it.
"""

from fractions import Fraction

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import Destination, NotApplicableError, OrbOfUnravelling
from crafting_system.items import ExplicitMod, Influence, Item, Rarity

ORB = OrbOfUnravelling()


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def _base(data, name: str) -> str:
    return next(base.id for base in data.base_items.values() if base.name == name and base.domain == "item")


def _lowest(data, mod_id: str) -> ExplicitMod:
    return ExplicitMod(mod_id, tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats))


def _item(data, base: str, level: int, *mod_ids: str, strands: int, influences=frozenset()) -> Item:
    return Item.build(
        data, base_id=_base(data, base), item_level=level, rarity=Rarity.RARE, mods=tuple(_lowest(data, mod_id) for mod_id in mod_ids),
        memory_strands=strands, influences=influences,
    )


@pytest.mark.parametrize("attribute", ["Strength", "Dexterity", "Intelligence"])
def test_t9_attributes_on_an_amulet_rise_for_certain_at_32_and_99_percent_at_31(data, attribute: str) -> None:
    for strands, chance in ((32, Fraction(1)), (31, Fraction(31 * 8000, 2 * 125250)), (15, Fraction(15 * 8000, 2 * 125250))):
        (entry, found, _), = ORB.eligible(data, _item(data, "Turquoise Amulet", 86, f"{attribute}1", strands=strands))
        assert entry.mod_id == f"{attribute}1"
        assert found == chance
    at_31 = ORB.eligible(data, _item(data, "Turquoise Amulet", 86, f"{attribute}1", strands=31))[0][1]
    assert round(float(at_31), 2) == 0.99
    outcomes = ORB.outcomes(data, _item(data, "Turquoise Amulet", 86, f"{attribute}1", strands=32))
    assert all(f"{attribute}1" not in {entry.mod_id for entry in item.mods} for _, item in outcomes.given.results)  # 310 of 310


@pytest.mark.parametrize(
    ("reading", "expected"),
    [(Destination.CUMULATIVE, (4.05, 20.95, 75.0)), (Destination.RANK, (2.03, 16.89, 81.08))],
)
def test_the_wand_case(data, reading: Destination, expected) -> None:
    item = _item(data, "Driftwood Wand", 84, "SpellAddedLightningDamage6", strands=100)
    (_, chance, targets), = OrbOfUnravelling(reading).eligible(data, item)
    assert 0 < chance <= 1
    assert [target.id for target, _ in targets] == ["SpellAddedLightningDamage9", "SpellAddedLightningDamage8", "SpellAddedLightningDamage7"]
    assert tuple(round(float(share) * 100, 2) for _, share in targets) == expected
    results = {next(iter({e.mod_id for e in item.mods})): share for share, item in OrbOfUnravelling(reading).outcomes(data, item).given.results}
    assert tuple(round(float(results[f"SpellAddedLightningDamage{tier}"] / chance) * 100, 2) for tier in (9, 8, 7)) == expected  # given a rise


def test_an_influence_mod_is_never_raised_to_its_elevated_form(data) -> None:
    hunter = frozenset({Influence.HUNTER})
    low = _item(data, "Turquoise Amulet", 86, "FireDamageOverTimeMultiplierInfluence1_", strands=100, influences=hunter)
    finals = {entry.mod_id for _, item in ORB.outcomes(data, low).given.results for entry in item.mods}
    assert finals == {"FireDamageOverTimeMultiplierInfluence1_", "FireDamageOverTimeMultiplierInfluence2"}  # stays, or the regular tier above
    top = _item(data, "Turquoise Amulet", 86, "FireDamageOverTimeMultiplierInfluence2", strands=100, influences=hunter)
    with pytest.raises(NotApplicableError, match="higher tier"):
        ORB.outcomes(data, top)


def test_an_essence_only_mod_is_never_raised(data) -> None:
    hunter = frozenset({Influence.HUNTER})
    item = _item(data, "Turquoise Amulet", 86, "AdditionalPierceEssence5", "Strength1", strands=10, influences=hunter)
    (entry, _, _), = ORB.eligible(data, item)
    assert entry.mod_id == "Strength1"
    assert all("AdditionalPierceEssence5" in {e.mod_id for e in found.mods} for _, found in ORB.outcomes(data, item).given.results)
