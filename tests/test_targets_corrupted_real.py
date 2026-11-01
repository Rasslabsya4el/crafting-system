"""Asked and allowed corruption on the real 3.29.3.3 export (ticket #257, ADR-0036, ADR-0037).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with `CRAFTING_CACHE_DIR`). They skip cleanly
when it is not there; CI fetches it (ticket #165).

* A target file with `corrupted: true` parses to the mod ids of the real corrupted pool of a Prismatic Ring at its item level.
* The items module and the pool agree on which corrupted mod a class can get (`fits_corrupted_implicit`).
* Every example target file still parses, with no corrupted key set.
"""

import textwrap
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import corrupted_implicit_pool
from crafting_system.items import ExplicitMod, ImplicitMod, Item, Rarity, fits_corrupted_implicit
from crafting_system.targets import TargetError, load_target, parse_target

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "targets"
PRISMATIC = "Metadata/Items/Rings/Ring8"
RESIST = "V2AllResistancesCorrupted"
COLD_TIERS = ("V2AddedColdDamageCorrupted1", "V2AddedColdDamageCorrupted2", "V2AddedColdDamageCorrupted3")
HEADER = "base: Prismatic Ring\nitem_level: {level}\nrequirements:\n  - family: ColdResistance\n"


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def parse(data, text: str, level: int = 84):
    return parse_target(HEADER.format(level=level) + textwrap.dedent(text), data, source="t.yaml")


def test_a_target_file_with_the_key_parses_to_the_real_corrupted_mods_of_the_ring(data):
    target = parse(
        data,
        """\
        implicits:
          - stat: "+#% to all Elemental Resistances"
            corrupted: true
          - family: AddedColdDamageToSpellsAndAttacks
            corrupted: true
        """,
    )

    resist, cold = target.implicits
    assert resist.mod_ids == {RESIST} and cold.mod_ids == set(COLD_TIERS)
    assert target.asks_corrupted and not target.allow_corrupted


def test_the_ring_implicit_text_without_the_key_is_still_the_implicit_of_the_base_and_not_the_corrupted_mod(data):
    target = parse(data, 'implicits:\n  - stat: "+#% to all Elemental Resistances"\n')

    (wish,) = target.implicits
    assert "AllResistancesImplicitRing1" in wish.mod_ids and RESIST not in wish.mod_ids and not wish.corrupted


def test_the_item_level_gates_the_tiers_at_their_required_level(data):
    asked = 'implicits:\n  - stat: "Adds # to # Cold Damage to Spells and Attacks"\n    corrupted: true\n'

    assert parse(data, asked, level=80).implicits[0].mod_ids == set(COLD_TIERS[:2])  # the third tier needs item level 81
    assert parse(data, asked, level=81).implicits[0].mod_ids == set(COLD_TIERS)
    pool = corrupted_implicit_pool(data, PRISMATIC, 80)
    assert parse(data, asked, level=80).implicits[0].mod_ids <= pool.mod_ids()


def test_error_the_third_cold_tier_at_item_level_80_names_its_level_and_the_nearest_tier(data):
    with pytest.raises(TargetError) as caught:
        parse(
            data,
            'implicits:\n  - stat: "Adds # to # Cold Damage to Spells and Attacks"\n    corrupted: true\n    mod: V2AddedColdDamageCorrupted3\n',
            level=80,
        )

    message = str(caught.value)
    assert message.startswith("t.yaml:8: implicits[0].mod: ") and "needs an item level of 81" in message
    assert "`V2AddedColdDamageCorrupted2`" in message


def test_error_a_misspelt_corrupted_text_names_the_nearest_real_mod(data):
    with pytest.raises(TargetError) as caught:
        parse(data, 'implicits:\n  - stat: "+#% to all Elemental Resistance"\n    corrupted: true\n')

    assert f'`{RESIST}` ("+#% to all Elemental Resistances")' in str(caught.value)


def test_error_two_real_cold_tiers_are_one_mod_group(data):
    with pytest.raises(TargetError) as caught:
        parse(
            data,
            f"implicits:\n  - family: AddedColdDamageToSpellsAndAttacks\n    corrupted: true\n    mod: {COLD_TIERS[0]}\n"
            f"  - family: AddedColdDamageToSpellsAndAttacks\n    corrupted: true\n    mod: {COLD_TIERS[1]}\n",
        )

    message = str(caught.value)
    assert "both of the mod group `AddedColdDamageToSpellsAndAttacks`" in message and "Locus of Corruption" in message


def test_error_the_all_resistances_base_implicit_and_the_corrupted_one_cannot_both_stay_on_a_prismatic_ring(data):
    with pytest.raises(TargetError) as caught:
        parse(data, 'implicits:\n  - family: AllResistances\n  - family: AllResistancesCorrupted\n    corrupted: true\n')

    message = str(caught.value)
    assert "a Prismatic Ring can hold 1 implicit (`AllResistancesImplicitRing1`)" in message and "at most 0 of them stay" in message


def test_the_real_ring_with_the_corrupted_all_resistances_is_a_goal_only_for_a_target_that_asks_or_allows(data):
    ring = Item.build(
        data,
        base_id=PRISMATIC,
        item_level=84,
        rarity=Rarity.RARE,
        corrupted=True,
        mods=(ExplicitMod("ColdResist1", 1, (8,)),),
        implicits=(ImplicitMod(RESIST, 0, (15,)),),
    )
    plain = parse(data, "")
    asking = parse(data, 'implicits:\n  - stat: "+#% to all Elemental Resistances"\n    corrupted: true\n    min_roll: 15\n')
    too_high = parse(data, 'implicits:\n  - stat: "+#% to all Elemental Resistances"\n    corrupted: true\n    min_roll: 16\n')
    allowing = parse(data, "allow_corrupted: true\n")

    assert plain.unmet(ring) == ()  # the ring meets every mod requirement of the plain target
    assert not plain.is_met_by(ring)  # and is still no goal for it
    assert asking.is_met_by(ring) and allowing.is_met_by(ring)
    assert not too_high.is_met_by(ring)  # the roll 15 is below the minimum 16


def test_items_and_the_pool_agree_on_which_corrupted_mod_a_class_can_get(data):
    seen = set()
    for base in data.base_items.values():
        if base.release_state != "released" or base.item_class in seen:
            continue
        seen.add(base.item_class)
        try:
            pool = corrupted_implicit_pool(data, base.id, 100).mod_ids()
        except ValueError:
            pool = frozenset()  # a class with no pool, or a jewel the pool refuses
        fits = {mod.id for mod in data.mods.values() if fits_corrupted_implicit(mod, base)}
        assert fits == pool, base.item_class


def test_every_example_target_file_parses_without_a_corrupted_key(data):
    paths = sorted(EXAMPLES.glob("*.yaml"))

    assert paths
    for path in paths:
        target = load_target(path, data)
        assert target.allow_corrupted is False and not target.takes_corrupted, path.name
        assert not any(wish.corrupted for wish in target.implicits), path.name
        assert target.start_item.corrupted is False, path.name
