"""The metamods on every Harvest reforge of ticket #72: the 16 tagged crafts, the influence reforge, the two likelihood reforges (ticket #68).

Rules (issues #11 and #28): `Prefixes` / `Suffixes Cannot Be Changed` keep the mods of the locked side and count them inside
the total; `Cannot roll Attack Modifiers` filters the first added mod only (D8), the guaranteed mod of a tagged or influence
reforge and the first drawn mod of a likelihood reforge, and only if the reforge leaves the metamod on the item.

The expected numbers come from the brute force of `abstraction_oracle.py` on the small retagged pool of `harvest_reforge_support.py`
(every craft has its own set of tagged mods), fed with what the rules keep: a locked side is handed to the brute force as the
fractured mods of its start item; the filtered first mod is the mixture over the allowed first mods, each then fixed on the
start item. Nothing here reads the engine's metamod code.
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from abstraction_oracle import finished_items, hold_chance
from abstraction_pool import DAMAGE_1, GEM, LEVEL, LIFE_1, MANA_1, RESIST_2
from harvest_reforge_support import ATTACK_SPEED, SPAWNABLE, TABLE, TAGGED_DATA, bow
from items_support import AMULET, DATA
from items_support import roll as fixture_roll

from crafting_system.actions import (
    HarvestReforge,
    HarvestReforgeInfluence,
    HarvestReforgeLikelihood,
    NotApplicableError,
    build_pool,
)
from crafting_system.actions.draw import guaranteed_candidates
from crafting_system.items import ExplicitMod, Item, Rarity

PCBC = "StrMasterItemGenerationCannotChangePrefixes"  # a suffix; locks the prefixes
SCBC = "DexMasterItemGenerationCannotChangeSuffixes"  # a prefix; locks the suffixes
NO_ATTACK = "IntMasterItemGenerationCannotRollAttackAffixes"  # a suffix
NO_CASTER = "StrDexMasterItemGenerationCannotRollCasterAffixes"  # a suffix
MULTI = "StrIntMasterItemGenerationCanHaveMultipleCraftedMods"  # a suffix; the brute force's stand-in for a metamod's slot
WORLD = dataclasses.replace(TAGGED_DATA, mods={**TAGGED_DATA.mods, **{m: DATA.mods[m] for m in (PCBC, SCBC, NO_ATTACK, NO_CASTER, MULTI)}})


def low(mod_id: str):
    return tuple(min(stat.min, stat.max) for stat in WORLD.mods[mod_id].stats)


def mod(mod_id: str, *, fractured=False, crafted=False) -> ExplicitMod:
    return ExplicitMod(mod_id, 1, low(mod_id), fractured=fractured, crafted=crafted)


def meta(mod_id: str) -> ExplicitMod:
    return mod(mod_id, crafted=True)


def world_item(*mods: ExplicitMod, rarity=Rarity.RARE) -> Item:
    return Item.build(WORLD, base_id=AMULET, item_level=LEVEL, rarity=rarity, mods=mods)


def fractured(*ids: str) -> list[ExplicitMod]:
    return [mod(i, fractured=True) for i in ids]


# the item the rules hand to the brute force: only the fractured mods stay, so the kept ones are made fractured
LOCK_STARTS = {
    "prefixes_locked": (  # PCBC (a suffix) keeps the prefixes; the suffix and the metamod are rerolled away
        lambda: world_item(mod(LIFE_1), mod(GEM), mod(RESIST_2), meta(PCBC)),
        lambda: world_item(*fractured(LIFE_1, GEM)),
    ),
    "suffixes_locked": (  # SCBC (a prefix) keeps the suffixes
        lambda: world_item(mod(LIFE_1), mod(RESIST_2), mod(MANA_1), meta(SCBC)),
        lambda: world_item(*fractured(RESIST_2, MANA_1)),
    ),
}


def expected_chances(finished):
    return {mod_id: hold_chance(finished, {mod_id}) for mod_id in SPAWNABLE}


@pytest.mark.parametrize("start", LOCK_STARTS)
@pytest.mark.parametrize("craft", TABLE)
def test_each_tagged_reforge_keeps_the_locked_side_like_the_brute_force_with_those_mods_fractured(craft, start):
    real, oracle_start = (build() for build in LOCK_STARTS[start])
    tag = TABLE[craft][0]
    try:
        expected = expected_chances(finished_items(WORLD, oracle_start, tag))
    except ValueError:
        with pytest.raises(NotApplicableError):
            HarvestReforge(craft).outcomes(WORLD, real)
        return

    outcomes = HarvestReforge(craft).outcomes(WORLD, real)

    assert {e.mod_id for e in outcomes.retained.mods} == {e.mod_id for e in oracle_start.mods}
    assert not outcomes.retained.metamods(WORLD)  # the lock itself is on the other side and goes
    assert {mod_id: outcomes.chance_all([mod_id]) for mod_id in SPAWNABLE} == expected


def first_mod_mixture(craft, kept_fractured, standin, blocked="attack"):
    """The brute-force chances when the first mod is filtered: the allowed tagged mods, then the rest unfiltered.

    `kept_fractured` are the mods that stay (as fractured mods), `standin` the metamod's slot. Returns None when no tagged mod is allowed.
    """
    tag = TABLE[craft][0]
    base = world_item(*fractured(*kept_fractured), mod(standin, fractured=True, crafted=True))
    room = {s: 3 - sum(WORLD.mods[e.mod_id].generation_type == s for e in base.mods) for s in ("prefix", "suffix")}
    allowed = [
        entry
        for family in build_pool(WORLD, base)
        if room[family.side.value] > 0
        for entry in family.mods
        if tag in entry.mod.implicit_tags and blocked not in entry.mod.implicit_tags
    ]
    if not allowed:
        return None
    whole = sum(entry.weight for entry in allowed)
    chances = {mod_id: Fraction(0) for mod_id in SPAWNABLE}
    for entry in allowed:
        after = world_item(*fractured(*kept_fractured, entry.mod.id), mod(standin, fractured=True, crafted=True))
        finished = finished_items(WORLD, after, None)
        for mod_id in SPAWNABLE:
            chances[mod_id] += entry.weight / whole * hold_chance(finished, {mod_id})
    return chances


# SCBC keeps the suffixes, so Cannot roll Attack Modifiers (a suffix) and the resistance stay and the reroll is under the metamod
FILTER_START = lambda: world_item(mod(LIFE_1), mod(RESIST_2), meta(SCBC), meta(NO_ATTACK))  # noqa: E731
CASTER_START = lambda: world_item(mod(LIFE_1), mod(RESIST_2), meta(SCBC), meta(NO_CASTER))  # noqa: E731


@pytest.mark.parametrize("craft", TABLE)
def test_each_tagged_reforge_filters_the_guaranteed_mod_only_under_cannot_roll_caster(craft):
    expected = first_mod_mixture(craft, [RESIST_2], MULTI, "caster")
    start = CASTER_START()
    if expected is None:  # the caster craft: every mod it could guarantee has the caster tag
        with pytest.raises(NotApplicableError):
            HarvestReforge(craft).outcomes(WORLD, start)
        return

    outcomes = HarvestReforge(craft).outcomes(WORLD, start)

    assert {e.mod_id for e in outcomes.retained.mods} == {RESIST_2, NO_CASTER}
    assert outcomes.guaranteed_blocked == {"caster"}
    assert {mod_id: outcomes.chance_all([mod_id]) for mod_id in SPAWNABLE} == expected


@pytest.mark.parametrize("craft", TABLE)
def test_each_tagged_reforge_filters_the_guaranteed_mod_only_under_cannot_roll_attack(craft):
    expected = first_mod_mixture(craft, [RESIST_2], MULTI)
    start = FILTER_START()
    if expected is None:  # the attack craft: every mod it could guarantee has the attack tag
        with pytest.raises(NotApplicableError):
            HarvestReforge(craft).outcomes(WORLD, start)
        return

    outcomes = HarvestReforge(craft).outcomes(WORLD, start)

    assert {e.mod_id for e in outcomes.retained.mods} == {RESIST_2, NO_ATTACK}
    assert outcomes.guaranteed_blocked == {"attack"}
    assert {mod_id: outcomes.chance_all([mod_id]) for mod_id in SPAWNABLE} == expected


def test_the_filter_is_not_a_no_op_for_the_crafts_with_attack_tagged_mods():
    lightning = HarvestReforge("lightning").outcomes(WORLD, FILTER_START())
    plain = HarvestReforge("lightning").outcomes(WORLD, world_item(mod(LIFE_1), mod(RESIST_2), meta(SCBC)))

    assert lightning.chance_all([DAMAGE_1]) != plain.chance_all([DAMAGE_1])
    assert lightning.chance_all([DAMAGE_1]) > 0  # an unfiltered draw after the guaranteed mod can still bring it


def test_a_reforge_that_removes_the_metamod_is_not_filtered():
    only_the_metamod = world_item(mod(LIFE_1), mod(RESIST_2), meta(NO_ATTACK))  # no lock: the reroll drops it
    outcomes = HarvestReforge("lightning").outcomes(WORLD, only_the_metamod)

    assert outcomes.guaranteed_blocked == frozenset()
    assert outcomes.chance_all([DAMAGE_1]) == HarvestReforge("lightning").outcomes(WORLD, world_item(mod(LIFE_1), mod(RESIST_2))).chance_all([DAMAGE_1])


# --- the influence reforge ------------------------------------------------------------------------------------


def hunter_bow(*mods):
    return bow(*mods)


def test_the_influence_reforge_keeps_the_locked_side_and_counts_it_inside_the_total():
    prefixes = (fixture_roll("LocalAddedFireDamageTwoHand1"), fixture_roll("LocalAddedColdDamageTwoHand1"))
    start = hunter_bow(*prefixes, fixture_roll(ATTACK_SPEED), fixture_roll(PCBC, crafted=True))

    outcomes = HarvestReforgeInfluence().outcomes(DATA, start)

    assert {e.mod_id for e in outcomes.retained.mods} == {e.mod_id for e in prefixes}
    assert outcomes.guaranteed_blocked == frozenset()
    sizes = {len(outcomes.retained.mods) + sum(count for _, count in o) for o in outcomes.distribution(lambda m: m.id)}
    assert sizes == {4, 5, 6}  # the kept two count inside the 4, 5 or 6, and so does the guaranteed mod


def under_attack_metamod():
    # SCBC keeps the suffixes: the attack speed and Cannot roll Attack Modifiers stay
    return hunter_bow(fixture_roll(ATTACK_SPEED), fixture_roll(SCBC, crafted=True), fixture_roll(NO_ATTACK, crafted=True))


def test_the_influence_reforge_is_refused_when_every_hunter_mod_has_the_attack_tag():
    hunter = [m for m in DATA.mods.values() if m.id.startswith(("LocalAddedChaosDamageAndPenetrationInfluence", "AddedColdDamagePerDexterityInfluence", "ArmourPenetrationTwoHandWeaponInfluence", "ChanceToIntimidate"))]
    assert hunter and all("attack" in m.implicit_tags for m in hunter)  # the fixture bow's Hunter mods all do

    with pytest.raises(NotApplicableError, match="influence"):
        HarvestReforgeInfluence().outcomes(DATA, under_attack_metamod())


def test_the_influence_reforge_filters_the_guaranteed_mod_only_under_cannot_roll_attack():
    # the Armour Penetration mods lose the attack tag here, so they are the only influence mods the first draw may take
    loosened = {
        mod_id: dataclasses.replace(m, implicit_tags=tuple(t for t in m.implicit_tags if t != "attack"))
        if m.id.startswith("ArmourPenetrationTwoHandWeaponInfluence")
        else m
        for mod_id, m in DATA.mods.items()
    }
    data = dataclasses.replace(DATA, mods=loosened)

    outcomes = HarvestReforgeInfluence().outcomes(data, under_attack_metamod())

    assert {e.mod_id for e in outcomes.retained.mods} == {ATTACK_SPEED, NO_ATTACK}
    assert outcomes.guaranteed_blocked == {"attack"}
    candidates = guaranteed_candidates(outcomes.pool, outcomes.free, outcomes.tag, outcomes.guaranteed_blocked)
    assert {entry.mod.id for _, entry in candidates} == {
        "ArmourPenetrationTwoHandWeaponInfluence1_",
        "ArmourPenetrationTwoHandWeaponInfluence2_",
    }  # at item level 78; the other Hunter mods are attack-tagged, the unfiltered pool still holds them
    assert any("attack" in e.mod.implicit_tags for f in outcomes.pool for e in f.mods if f.family == "ChaosDamageHybrid")
    for seed in range(15):
        result = outcomes.sample(random.Random(seed))
        assert {ATTACK_SPEED, NO_ATTACK} <= {e.mod_id for e in result.mods} and SCBC not in {e.mod_id for e in result.mods}
        assert {"ArmourPenetrationTwoHandWeaponInfluence1_", "ArmourPenetrationTwoHandWeaponInfluence2_"} & {e.mod_id for e in result.mods}


# --- the likelihood reforges ----------------------------------------------------------------------------------


def weighed(oracle_start, real, factor):
    """The pool of the brute force: built for the start that keeps only fractured mods, the families `real` holds weighed by hand."""
    held = {f for e in real.mods for f in WORLD.mods[e.mod_id].families}
    return tuple(
        dataclasses.replace(
            family,
            mods=tuple(dataclasses.replace(e, weight=e.weight * (factor if family.family in held else 1)) for e in family.mods),
        )
        for family in build_pool(WORLD, oracle_start)
    )


@pytest.mark.parametrize("more", [True, False], ids=["more", "less"])
@pytest.mark.parametrize("start", LOCK_STARTS)
def test_a_likelihood_reforge_keeps_the_locked_side_like_the_brute_force(start, more):
    real, oracle_start = (build() for build in LOCK_STARTS[start])
    factor = Fraction(90) if more else Fraction(1, 90)
    totals = {max(len(real.mods), 4): Fraction(1)}  # the item held 4 mods
    expected = expected_chances(finished_items(WORLD, oracle_start, None, pool=weighed(oracle_start, real, factor), totals=totals))

    outcomes = HarvestReforgeLikelihood(more).outcomes(WORLD, real)

    assert {e.mod_id for e in outcomes.retained.mods} == {e.mod_id for e in oracle_start.mods}
    assert {mod_id: outcomes.chance_all([mod_id]) for mod_id in SPAWNABLE} == expected


@pytest.mark.parametrize("more", [True, False], ids=["more", "less"])
def test_a_likelihood_reforge_filters_the_first_mod_only_under_cannot_roll_attack(more):
    real = FILTER_START()  # SCBC keeps the suffixes; held: life, resistance
    factor = Fraction(90) if more else Fraction(1, 90)
    total = {max(len(real.mods), 4): Fraction(1)}
    base = world_item(*fractured(RESIST_2), mod(MULTI, fractured=True, crafted=True))
    first = [
        (family.family, e)
        for family in weighed(base, real, factor)
        if 3 - sum(WORLD.mods[x.mod_id].generation_type == family.side.value for x in base.mods) > 0
        for e in family.mods
        if "attack" not in e.mod.implicit_tags
    ]
    whole = sum(e.weight for _, e in first)
    chances = {mod_id: Fraction(0) for mod_id in SPAWNABLE}
    for _, e in first:
        after = world_item(*fractured(RESIST_2, e.mod.id), mod(MULTI, fractured=True, crafted=True))
        finished = finished_items(WORLD, after, None, pool=weighed(after, real, factor), totals=total)
        for mod_id in SPAWNABLE:
            chances[mod_id] += e.weight / whole * hold_chance(finished, {mod_id})

    outcomes = HarvestReforgeLikelihood(more).outcomes(WORLD, real)

    assert {e.mod_id for e in outcomes.retained.mods} == {RESIST_2, NO_ATTACK}
    assert outcomes.guaranteed_blocked == {"attack"}
    assert {mod_id: outcomes.chance_all([mod_id]) for mod_id in SPAWNABLE} == chances
    assert outcomes.chance_all([DAMAGE_1]) > 0  # an attack-tagged mod still comes after the first draw


@pytest.mark.parametrize("more", [True, False], ids=["more", "less"])
def test_a_likelihood_reforge_draws_nothing_when_the_kept_mods_fill_the_total(more):
    # both locks keep all five mods, so the five held mods are the total and the attack filter has no draw to filter
    full = world_item(mod(LIFE_1), mod(GEM), meta(SCBC), meta(PCBC), meta(NO_ATTACK))

    outcomes = HarvestReforgeLikelihood(more).outcomes(WORLD, full)

    assert outcomes.retained == full
    assert {len(outcomes.retained.mods) + sum(count for _, count in o) for o in outcomes.distribution(lambda m: m.id)} == {5}


def test_a_likelihood_reforge_is_refused_when_the_attack_filter_leaves_no_first_mod():
    only_attack = {
        mod_id: dataclasses.replace(m, implicit_tags=(*m.implicit_tags, "attack")) if m.domain == "item" else m
        for mod_id, m in WORLD.mods.items()
    }
    data = dataclasses.replace(WORLD, mods=only_attack)

    with pytest.raises(NotApplicableError, match="Attack/Caster"):
        HarvestReforgeLikelihood(True).outcomes(data, FILTER_START())
