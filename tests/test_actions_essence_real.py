"""The per-use chance of what R10, R11 and R05 wait for, on the real 3.29.3.3 dump (ticket #55).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there, which is the case in CI.

The pins are exact fractions that the engine gave on the data of 3.29.3.3 (a regression pin: the
independent check is the hand oracle of `test_actions_essence.py` on the fixture, and the sampler
below, which rolls the same essences at random and must agree within five standard errors). What is
counted, on boots, a helmet and a ring built on the first released base of the kind:

* R10: Shrieking Essence of Spite on int boots with fractured Movement Speed; a Life prefix among
  the new mods, and a free suffix left (the forced Intelligence is a suffix, so at most one more).
* R11: Shrieking Essence of Loathing on a dex (evasion) helmet with fractured Chaos Resistance; a
  Life prefix and an evasion prefix (flat or percent, hybrids with stun recovery included, the
  evasion-and-life hybrid not) among the new mods, and a free suffix left (the forced Mana
  Reservation Efficiency and the fractured resistance take two suffixes, so no new suffix).
* R05: Deafening Essence of Rage on a ring with fractured All Attributes; a Life prefix among the
  new mods, on item level 86 and on 75 (the route's).
"""

import random
from collections.abc import Callable
from fractions import Fraction

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import ApplyEssence, NotApplicableError
from crafting_system.items import ExplicitMod, Item, Rarity

BOOTS = "Metadata/Items/Armours/Boots/BootsInt1"
HELMET = "Metadata/Items/Armours/Helmets/HelmetDex1"
RING = "Metadata/Items/Rings/Ring1"
EVASION_FAMILIES = ("DefencesPercent", "DefencesPercentAndStunRecovery", "BaseLocalDefences")

R10_86 = Fraction(40806386989688589108307467555774051017510817486647522261117371, 237749481400932669145910668947160705548914382012474045873950400)
R11_86 = Fraction(85439782498589642193121443228960373519891880384588735638000, 3269485799899161240200858874591841479512550664066337995536027)
R05_86 = Fraction(836710117060224269563585308068889940977950900926219333643869298247247564609, 4130058332783088703905806606461461805618698716555804441934521225952974206200)
R05_75 = Fraction(12688262995061554403570352561962193596454219810391671276103266059706145, 58297250992066574359833700190867486193847550175174683886099559145332674)


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def rare(data, base_id, item_level, fractured_id):
    mod = data.mods[fractured_id]
    low = tuple(min(stat.min, stat.max) for stat in mod.stats)
    return Item.build(
        data, base_id=base_id, item_level=item_level, rarity=Rarity.RARE,
        mods=(ExplicitMod(fractured_id, 1, low, fractured=True),),
    )  # fmt: skip


def labelled(evasion_families=()) -> Callable:
    def label(mod):
        family = mod.families[0]
        if family == "IncreasedLife":
            return "life"
        if family in evasion_families:
            return "evasion"
        return "suffix" if mod.generation_type == "suffix" else "other"

    return label


def exact(outcomes, label, wanted) -> Fraction:
    return sum(
        (p for outcome, p in outcomes.distribution(label).items() if wanted(dict(outcome))), Fraction(0)
    )


def life_and_a_free_suffix(counts):
    return counts.get("life", 0) >= 1 and counts.get("suffix", 0) <= 1


def life_evasion_and_a_free_suffix(counts):
    return counts.get("life", 0) >= 1 and counts.get("evasion", 0) >= 1 and counts.get("suffix", 0) == 0


def life(counts):
    return counts.get("life", 0) >= 1


R10 = ("Shrieking Essence of Spite", BOOTS, 86, "MovementVelocity6", labelled(), life_and_a_free_suffix, R10_86)
R11 = (
    "Shrieking Essence of Loathing", HELMET, 86, "ChaosResist6", labelled(EVASION_FAMILIES),
    life_evasion_and_a_free_suffix, R11_86,
)  # fmt: skip
R05 = ("Deafening Essence of Rage", RING, 86, "AllAttributes7", labelled(), life, R05_86)
R05_ROUTE = ("Deafening Essence of Rage", RING, 75, "AllAttributes7", labelled(), life, R05_75)
ROUTES = {"r10": R10, "r11": R11, "r05": R05, "r05-ilvl-75": R05_ROUTE}


@pytest.mark.parametrize("route", ROUTES.values(), ids=ROUTES.keys())
def test_the_chance_per_use_is_pinned(data, route):
    name, base_id, item_level, fractured_id, label, wanted, pinned = route
    outcomes = ApplyEssence(name).outcomes(data, rare(data, base_id, item_level, fractured_id))

    assert exact(outcomes, label, wanted) == pinned


@pytest.mark.parametrize("route", ROUTES.values(), ids=ROUTES.keys())
def test_the_sampler_agrees_with_the_pinned_chance(data, route):
    name, base_id, item_level, fractured_id, label, wanted, pinned = route
    outcomes = ApplyEssence(name).outcomes(data, rare(data, base_id, item_level, fractured_id))
    rng, runs, hits = random.Random(5), 10000, 0
    for _ in range(runs):
        counts: dict[str, int] = {}
        for entry in outcomes.sample(rng).mods:
            if entry.mod_id != outcomes.forced and not entry.fractured:
                kind = label(data.mods[entry.mod_id])
                counts[kind] = counts.get(kind, 0) + 1
        hits += bool(wanted(counts))
    chance = float(pinned)

    assert abs(hits / runs - chance) < 5 * (chance * (1 - chance) / runs) ** 0.5


def test_the_forced_mods_of_the_three_routes(data):
    forced = {
        name: ApplyEssence(name).outcomes(data, rare(data, base_id, 86, fractured_id)).forced
        for name, base_id, _, fractured_id, *_ in (R10, R11, R05)
    }

    assert forced == {
        "Shrieking Essence of Spite": "Intelligence8",
        "Shrieking Essence of Loathing": "ManaReservationEfficiencyEssence6_",
        "Deafening Essence of Rage": "StrengthEssence7_",
    }


def test_the_caps_of_the_data_are_the_ones_the_rule_names(data):
    caps = {
        (essence.level, essence.item_level_restriction)
        for essence in data.essences.values()
        if 1 <= essence.level <= 8
    }

    assert caps == {(1, 35), (2, 45), (3, 60), (4, 75), (5, None), (6, None), (7, None), (8, None)}


@pytest.mark.parametrize("name", ["Whispering Essence of Hatred", "Shrieking Essence of Spite", "Essence of Horror"])
def test_every_item_class_takes_the_essence_and_the_new_mods_fit_around_the_forced_one(data, name):
    classes = {}
    for base in data.base_items.values():
        if base.domain == "item" and base.release_state == "released":
            classes.setdefault(base.item_class, base.id)
    taken = 0
    for item_class, base_id in sorted(classes.items()):
        item = Item.build(data, base_id=base_id, item_level=86, rarity=Rarity.NORMAL)
        try:
            outcomes = ApplyEssence(name).outcomes(data, item)
        except NotApplicableError as refusal:
            assert "gives no mod on" in str(refusal), (item_class, refusal)
            continue
        taken += 1
        sampled = outcomes.sample(random.Random(1))
        assert outcomes.forced in {entry.mod_id for entry in sampled.mods} and 4 <= len(sampled.mods) <= 6
    assert taken >= 20  # the 22 classes of essences.json, less the ones without a released base
