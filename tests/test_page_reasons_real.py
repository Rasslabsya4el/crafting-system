"""What an unasked crafted mod does, read on the real 3.29.3.3 dump (#1629, #1632): the rules `_route_purpose` says on the route page.

These need the cached dump and skip cleanly without it.

* R11 (#1629, card 3 of the craft board): `+(50-75) to Armour` on a Lion Pelt of item level 85 holding Life tier 1, the fractured Chaos
  Resistance, the essence's Mana Reservation and a Cold Resistance. Its family `BaseLocalDefences` is the natural `+# to Evasion Rating`'s
  (8000), so the Exalted Orb draws from 21,275 instead of 29,275: `#% increased Evasion Rating` 7000/29,275 -> 7000/21,275 (hand figures of
  #1282, Craft of Exile 0.2345 -> 0.332).
* R14 (#1632): `Cannot roll Attack Modifiers` on the Hunter Thicket Bow holding tier 1 Attack Speed and the multimod: an Orb of Annulment
  never takes the attack-tagged Attack Speed while it is on (claim `metamods.annulment_respects_locks_and_tags`) and takes it without.
* R04: the same lock on the Penetrating Arrow Quiver: the Exalted Orb lands Life 2/3 with it (`test_actions_metamods_real.py`), far less
  without.
"""

from fractions import Fraction

import pytest
from abstraction_support import real_game_data
from test_actions_metamods_real import MULTI, NO_ATTACK, T1_ATTACK_SPEED, r04_quiver, r14_bow, rolled

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import AnnulmentOrb, BenchCraft, ExaltedOrb
from crafting_system.cli._route_purpose import blocks, chances, without
from crafting_system.items import Item, Rarity

LION_PELT = "Metadata/Items/Armours/Helmets/HelmetDex10"
ARMOUR = "EinharMasterFlatArmour1"


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def of_family(data, family: str, text: str = "") -> frozenset[str]:
    return frozenset(
        mod.id for mod in data.mods.values() if mod.families == (family,) and mod.domain == "item" and text in (mod.text or "")
    )


def test_r11_the_armour_craft_names_the_flat_evasion_family_and_the_exalt_finds_evasion_percent_7000_of_21275_not_29275(data):
    pelt = Item.build(
        data, base_id=LION_PELT, item_level=85, rarity=Rarity.RARE,
        mods=(rolled(data, "IncreasedLife9"), rolled(data, "ChaosResist6", fractured=True), rolled(data, "ManaReservationEfficiencyEssence6_"), rolled(data, "ColdResist5")),
    )  # fmt: skip
    crafted = Item.build(data, base_id=LION_PELT, item_level=85, rarity=Rarity.RARE, mods=(*pelt.mods, rolled(data, ARMOUR)))
    goal = Goal((Wanted(of_family(data, "DefencesPercent", "Evasion")),))
    ab = Abstraction(data, goal, LION_PELT, 85, [ExaltedOrb(), BenchCraft(ARMOUR)])

    on = ab.compress(crafted)
    assert without(on, ARMOUR) == ab.compress(pelt)  # the item had the craft not been made
    assert chances(ab, on, ExaltedOrb())[0][0] == pytest.approx(float(Fraction(7000, 21275)), rel=1e-12)
    assert chances(ab, without(on, ARMOUR), ExaltedOrb())[0][0] == pytest.approx(float(Fraction(7000, 29275)), rel=1e-12)
    assert blocks(data, LION_PELT, 85, ARMOUR) == (
        "it is of one family with +# to Evasion Rating: an item holds one mod of a family, so while this craft is on, it cannot be added"
    )


def test_r14_under_the_attack_lock_an_annulment_never_takes_the_attack_speed_and_takes_it_without(data):
    bow = r14_bow(data)
    goal = Goal((Wanted(frozenset({T1_ATTACK_SPEED})),))
    ab = Abstraction(data, goal, bow.base_id, bow.item_level, [AnnulmentOrb(), ExaltedOrb()], metamods=True)

    on = ab.compress(bow)
    assert chances(ab, on, AnnulmentOrb())[1][0] == 0
    assert chances(ab, without(on, NO_ATTACK), AnnulmentOrb())[1][0] == pytest.approx(1 / 2)  # the Attack Speed or the multimod
    assert blocks(data, bow.base_id, bow.item_level, NO_ATTACK).startswith("while it is on, no attack mod is added")


def test_r04_under_the_attack_lock_the_exalt_lands_life_two_thirds_and_far_less_without(data):
    quiver = r04_quiver(data)
    goal = Goal((Wanted(of_family(data, "IncreasedLife")),))
    ab = Abstraction(data, goal, quiver.base_id, quiver.item_level, [ExaltedOrb()], metamods=True)

    on = ab.compress(quiver)
    with_lock, bare = chances(ab, on, ExaltedOrb())[0][0], chances(ab, without(on, NO_ATTACK), ExaltedOrb())[0][0]
    assert with_lock == pytest.approx(2 / 3) and bare < with_lock / 2
    assert MULTI not in {mod.mod_id for mod in quiver.mods}  # the quiver holds one crafted mod: the item without it is one the game can have


def test_r11_a_bench_fire_resistance_below_the_tier_asked_is_said_to_be_no_step_toward_the_target(data):
    """R11 (#1645 point 2): the bench's +(16-20)% to Fire Resistance fills the last suffix; the target asks (29-35)% or better (FireResist6 and
    up, hand-picked here), so the craft is a stand-in for its slot, not the target's mod. A craft of another family says nothing of it."""
    from types import SimpleNamespace

    from crafting_system.cli._route_purpose import below_target

    asked = frozenset(mod.id for mod in data.mods.values() if mod.id in ("FireResist6", "FireResist7", "FireResist8"))
    ab = Abstraction(data, Goal((Wanted(asked),)), LION_PELT, 85, [ExaltedOrb(), BenchCraft("HelenaMasterFireResist1")])
    view = SimpleNamespace(data=data, ab=ab)
    said = below_target(view, "HelenaMasterFireResist1")
    assert said == (
        "it is not the +#% to Fire Resistance the target asks (+(36-41)% to Fire Resistance or better): this craft is a lower roll of its family, "
        "so it only holds the slot until a step takes it off"
    )
    assert below_target(view, ARMOUR) is None


def test_a_veiled_mod_is_drawn_on_a_card_as_the_game_names_it(data):
    """#1644: after a Veiled Chaos Orb R24's card drew the veiled prefix as "any mod"; it is "Veiled Prefix" (the game's words)."""
    from crafting_system.abstraction import Slot, Status
    from crafting_system.cli._route_card import _StateReader
    from crafting_system.items import Side

    goal = Goal((Wanted(of_family(data, "DefencesPercent", "Evasion")),))
    reader = _StateReader(Abstraction(data, goal, LION_PELT, 85, [ExaltedOrb()]))
    row = reader.family(Slot(Side.PREFIX, "VeiledPrefix", (Status.ABSENT,)))

    assert (row.text, row.marks) == ("Veiled Prefix", ("veiled",))
