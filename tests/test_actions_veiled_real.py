"""The veiled orbs, the unveil and the pick on the real 3.29.3.3 dump (ticket #144); these skip cleanly when the dump is not cached (CI has it).

The figures are those of the veiled research (`research/veiled`, note 2026-10-31-veiled-unveiling.md), computed there from the
pool of `mods.json` by an enumeration of the three-draw tree. The oracle below is that enumeration written again here from
`data.mods` and `data.base_items` (first matching spawn weight of the base, one mod per family, a family on the item out of the
pool), without the code under test; the figures are then pinned to the digits the research gives:

* boots, a prefix veil: any Movement Speed variant 0.942, one named variant 0.314, 0.326 after the Evasion Rating while Focused block;
* helmet, a prefix veil: Area of Effect + 2 gems 0.3717, 0.4375 after the Zombies block (Maximum Zombie and Skeleton);
* wand, a suffix veil: Minions' attack and cast speed 0.194.

The Veiled Exalted Orb's removal is uniform, the metamods included (the 50/50 of R22), and the Attack/Caster metamods protect nothing.
"""

import random
from fractions import Fraction

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import NotApplicableError, OutOfScopeError, Pick, Unveil, VeiledChaosOrb, VeiledExaltedOrb
from crafting_system.items import ExplicitMod, Item, Rarity, tier_table, veiled_placeholder

F = Fraction

BOOTS = "Metadata/Items/Armours/Boots/BootsStr1"  # Iron Greaves
HELMET = "Metadata/Items/Armours/Helmets/HelmetStr1"  # Iron Hat
WAND = "Metadata/Items/Weapons/OneHandWeapons/Wands/Wand1"  # Driftwood Wand

MS_ONSLAUGHT = "JunMasterVeiledMovementVelocityAndOnslaughtOnKill"
MS_AVOID_CHILLED = "JunMasterVeiledMovementVelocityAndCannotBeChilled__"
MS_IF_NOT_HIT = "JunMasterVeiledMovementVelocityAndMovementVelocityIfNotHitRecently"
AOE_2 = "JunMasterVeiledSkillAreaOfEffectPercentAndAreaOfEffectGemLevel"
MINION_SPEED = "JunMasterVeiledMinionAttackAndCastSpeedOnWeapon1h"
EVASION_CRAFT = "JunMasterDodgeChanceDuringFocus1"  # the crafted Evasion Rating while Focused, a prefix
ZOMBIE_CRAFT = "JunMasterMaximumZombieAndSkeleton1"  # the crafted Maximum Zombie and Skeleton, a prefix
LOCK_SUFFIXES = "DexMasterItemGenerationCannotChangeSuffixes"  # a prefix that locks the suffixes
NO_ATTACK = "IntMasterItemGenerationCannotRollAttackAffixes"  # a suffix
LIFE, FIRE, COLD, LIGHTNING = "IncreasedLife8", "FireResist8", "ColdResist8", "LightningResist8"  # tier 1 each on boots
PHYSICAL = "LocalIncreasedPhysicalDamagePercentAndAccuracyRating1"  # a prefix with the attack tag, on a wand


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def low(data, mod_id: str, **flags) -> ExplicitMod:
    mod = data.mods[mod_id]
    return ExplicitMod(mod_id, 1, tuple(min(stat.min, stat.max) for stat in mod.stats), **flags)


def tiered(data, base_id: str, mod_id: str, **flags) -> ExplicitMod:
    mod = data.mods[mod_id]
    tier = tier_table(data, base_id).get(mod_id, 1)
    return ExplicitMod(mod_id, tier, tuple(min(stat.min, stat.max) for stat in mod.stats), **flags)


def with_veil(data, base_id: str, side: str, *mods: ExplicitMod, level: int = 84) -> Item:
    placeholder = veiled_placeholder(data, "VeiledPrefix" if side == "prefix" else "VeiledSuffix")
    return Item.build(data, base_id=base_id, item_level=level, rarity=Rarity.RARE, mods=(placeholder, *mods))


def oracle(
    data, base_id: str, side: str, blocked_families: frozenset[str] = frozenset(), first_family_only: bool = False
) -> dict[frozenset[str], Fraction]:
    """The research's enumeration, written again: {offer (set of mod ids): chance} for the unveil of a `side` placeholder on `base_id`.

    A picked mod takes every family it has out of the pool, or with `first_family_only` (how the research counted) its first only.
    """
    tags = data.base_items[base_id].tags
    pool = []
    for mod in data.mods.values():
        if mod.domain != "unveiled" or mod.generation_type != side:
            continue
        weight = next((entry.weight for entry in mod.spawn_weights if entry.tag in tags), 0)  # the first entry whose tag the base has
        if weight > 0 and not blocked_families & set(mod.families):
            pool.append((mod.id, mod.families, weight))
    out: dict[frozenset[str], Fraction] = {}

    def rec(left, chosen, chance):
        if len(chosen) == 3 or not left:
            out[frozenset(chosen)] = out.get(frozenset(chosen), F(0)) + chance
            return
        total = sum(weight for _, _, weight in left)
        for mod_id, families, weight in left:
            gone = set(families[:1] if first_family_only else families)
            rec([x for x in left if not gone & set(x[1])], [*chosen, mod_id], chance * F(weight, total))

    rec(pool, [], F(1))
    return out


def offers(data, item: Item) -> dict[frozenset[str], Fraction]:
    shown: dict[frozenset[str], Fraction] = {}
    for chance, result in Unveil().outcomes(data, item).results:
        key = frozenset(result.veil_offer)
        shown[key] = shown.get(key, F(0)) + chance
    return shown


def chance_offered(shown, wanted) -> Fraction:
    return sum((chance for offer, chance in shown.items() if any(wanted(mod_id) for mod_id in offer)), F(0))


# --- the research figures ------------------------------------------------------------------------------------------------------


def test_boots_any_movement_speed_variant_is_offered_with_chance_0_942(data):
    shown = offers(data, with_veil(data, BOOTS, "prefix"))
    assert shown == oracle(data, BOOTS, "prefix") and sum(shown.values()) == 1
    assert len(shown) == 22  # the research: 22 distinct offers on the boots prefix pool
    anything = chance_offered(shown, lambda mod_id: mod_id.startswith("JunMasterVeiledMovementVelocity"))
    assert round(float(anything), 3) == 0.942


def test_boots_a_named_movement_speed_variant_has_chance_0_314_and_0_326_with_the_evasion_block(data):
    plain = with_veil(data, BOOTS, "prefix")
    for variant in (MS_ONSLAUGHT, MS_AVOID_CHILLED, MS_IF_NOT_HIT):
        assert round(float(chance_offered(offers(data, plain), lambda m, v=variant: m == v)), 3) == 0.314
    blocked = with_veil(data, BOOTS, "prefix", low(data, EVASION_CRAFT, crafted=True))
    shown = offers(data, blocked)
    assert shown == oracle(data, BOOTS, "prefix", frozenset({"DodgeChanceDuringFocus"}))
    assert round(float(chance_offered(shown, lambda m: m == MS_ONSLAUGHT)), 3) == 0.326
    assert round(float(chance_offered(shown, lambda m: m == MS_AVOID_CHILLED)), 3) == 0.326


def test_helmet_plus_two_area_of_effect_gems_has_chance_0_3717_and_0_4375_with_the_zombies_block(data):
    plain = offers(data, with_veil(data, HELMET, "prefix"))
    assert plain == oracle(data, HELMET, "prefix")
    assert round(float(chance_offered(plain, lambda m: m == AOE_2)), 4) == 0.3717
    blocked = offers(data, with_veil(data, HELMET, "prefix", low(data, ZOMBIE_CRAFT, crafted=True)))
    assert blocked == oracle(data, HELMET, "prefix", frozenset({"MaximumMinionCount"}))
    assert round(float(chance_offered(blocked, lambda m: m == AOE_2)), 4) == 0.4375


def test_wand_minion_attack_and_cast_speed_is_offered_with_chance_0_1996_which_is_the_researchs_0_194_counting_one_family(data):
    # The research's 0.194 counts the first family of a mod only. Four wand suffixes are hybrids (Attack Speed + Dexterity +
    # Intelligence, Crit + Strength + Intelligence, Accuracy + Strength + Dexterity, ...) and share their second families with
    # other options; the game excludes by every family (`Item` refuses an offer with two mods that share one), which is 0.1996.
    shown = offers(data, with_veil(data, WAND, "suffix"))
    assert shown == oracle(data, WAND, "suffix")
    assert round(float(chance_offered(shown, lambda m: m == MINION_SPEED)), 4) == 0.1996
    first_only = oracle(data, WAND, "suffix", first_family_only=True)
    assert round(float(chance_offered(first_only, lambda m: m == MINION_SPEED)), 3) == 0.194


def test_the_legacy_trigger_socketed_spell_mod_of_r07_is_never_offered(data):
    shown = offers(data, with_veil(data, WAND, "suffix"))
    assert all("TriggerSocketedSpellOnSkillUse" not in mod_id for offer in shown for mod_id in offer)


def test_a_pick_lands_the_chosen_mod_at_its_tier_and_lowest_values(data):
    start = with_veil(data, BOOTS, "prefix", tiered(data, BOOTS, FIRE))
    _, offered = next((c, r) for c, r in Unveil().outcomes(data, start).results if MS_ONSLAUGHT in r.veil_offer)
    index = offered.veil_offer.index(MS_ONSLAUGHT) + 1
    ((_, landed),) = Pick(index).outcomes(data, offered).results
    assert {entry.mod_id for entry in landed.mods} == {FIRE, MS_ONSLAUGHT} and landed.veil_offer == ()
    (picked,) = (entry for entry in landed.mods if entry.mod_id == MS_ONSLAUGHT)
    assert picked.values == tuple(min(stat.min, stat.max) for stat in data.mods[MS_ONSLAUGHT].stats)


# --- the Veiled Exalted Orb on the real export ---------------------------------------------------------------------------------


def boots(data, *mods: ExplicitMod) -> Item:
    return Item.build(data, base_id=BOOTS, item_level=84, rarity=Rarity.RARE, mods=mods)


def removed(data, item: Item) -> dict[frozenset[str], Fraction]:
    """What a Veiled Exalted Orb removes, by the set of mod ids left apart from the veil: {mods left: chance}."""
    found: dict[frozenset[str], Fraction] = {}
    for chance, result in VeiledExaltedOrb().outcomes(data, item).results:
        left = frozenset(entry.mod_id for entry in result.mods if data.mods[entry.mod_id].domain != "veiled")
        found[left] = found.get(left, F(0)) + chance
    return found


def test_the_removal_is_uniform_over_the_mods_a_lock_leaves_open_metamods_included_the_fifty_fifty_of_r22(data):
    # the suffixes (fire, cold, lightning) are locked; the prefixes hold the crafted lock and Life: the orb removes the lock or Life
    item = boots(
        data,
        low(data, LOCK_SUFFIXES, crafted=True),
        tiered(data, BOOTS, LIFE),
        tiered(data, BOOTS, FIRE),
        tiered(data, BOOTS, COLD),
        tiered(data, BOOTS, LIGHTNING),
    )
    suffixes = {FIRE, COLD, LIGHTNING}
    assert removed(data, item) == {
        frozenset({LIFE} | suffixes): F(1, 2),
        frozenset({LOCK_SUFFIXES} | suffixes): F(1, 2),
    }
    for chance, result in VeiledExaltedOrb().outcomes(data, item).results:
        assert chance == F(1, 2)
        assert sum(data.mods[entry.mod_id].domain == "veiled" for entry in result.mods) == 1


def test_the_attack_and_caster_metamods_protect_no_mod_from_the_removal(data):
    wand = Item.build(
        data,
        base_id=WAND,
        item_level=84,
        rarity=Rarity.RARE,
        mods=(low(data, NO_ATTACK, crafted=True), tiered(data, WAND, PHYSICAL)),
    )
    assert removed(data, wand) == {frozenset({PHYSICAL}): F(1, 2), frozenset({NO_ATTACK}): F(1, 2)}  # the attack-tagged prefix may go


def test_an_unveil_block_craft_is_the_craftable_version_of_a_veiled_mod_and_refuses_the_veiled_exalted_orb(data):
    item = boots(data, low(data, EVASION_CRAFT, crafted=True), tiered(data, BOOTS, FIRE))
    with pytest.raises(NotApplicableError, match="holds the veiled mod"):
        VeiledExaltedOrb().outcomes(data, item)
    other = boots(data, low(data, "EinharMasterTrapThrowingSpeed1", crafted=True)) if "EinharMasterTrapThrowingSpeed1" in data.mods else None
    if other is not None:  # Einhar's bench makes mods with the stats of some veiled mod: they are not craftable versions
        try:
            VeiledExaltedOrb().outcomes(data, other)
        except NotApplicableError as refusal:
            assert "holds the veiled mod" not in str(refusal)


# --- the Veiled Chaos Orb on the real export -----------------------------------------------------------------------------------


def test_with_the_suffixes_locked_and_full_the_veil_is_forced_onto_the_prefix_as_in_r24(data):
    item = boots(
        data,
        low(data, LOCK_SUFFIXES, crafted=True),
        tiered(data, BOOTS, FIRE),
        tiered(data, BOOTS, COLD),
        tiered(data, BOOTS, LIGHTNING),
    )
    outcomes = VeiledChaosOrb().outcomes(data, item)
    assert [(share, part.forced) for share, part in outcomes.components] == [(F(1), "VeiledPrefix")]
    assert outcomes.chance_all([FIRE, COLD, LIGHTNING]) == 1
    rng = random.Random(144)
    for _ in range(25):
        result = outcomes.sample(rng)
        result.validate(data)
        assert {FIRE, COLD, LIGHTNING} <= {e.mod_id for e in result.mods} and LOCK_SUFFIXES not in {e.mod_id for e in result.mods}


def test_the_veil_takes_either_side_half_and_half_when_both_have_room(data):
    outcomes = VeiledChaosOrb().outcomes(data, boots(data, tiered(data, BOOTS, LIFE), tiered(data, BOOTS, FIRE)))
    assert [(share, part.forced) for share, part in outcomes.components] == [(F(1, 2), "VeiledPrefix"), (F(1, 2), "VeiledSuffix")]


def test_a_jewel_has_no_veiled_pool_and_a_signature_veil_is_out_of_scope(data):
    jewel = next(b for b in data.base_items.values() if b.item_class == "Jewel" and b.release_state == "released" and b.domain == "misc")
    item = Item.build(data, base_id=jewel.id, item_level=84, rarity=Rarity.RARE)
    for action in (VeiledChaosOrb(), VeiledExaltedOrb()):
        with pytest.raises(OutOfScopeError, match="no veiled pool"):
            action.outcomes(data, item)
    signature = next(m.id for m in data.mods.values() if m.domain == "veiled" and m.id.startswith("Haku") and m.generation_type == "prefix")
    haku = Item.build(data, base_id=BOOTS, item_level=84, rarity=Rarity.RARE, mods=(low(data, signature),))
    with pytest.raises(OutOfScopeError, match="signature"):
        Unveil().outcomes(data, haku)
