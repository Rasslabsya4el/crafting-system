"""The two Exalted Orbs of R14 and R04 under `Cannot roll Attack Modifiers`, on the real 3.29.3.3 dump (ticket #68).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there, which is the case in CI; the same rules are
tested on the fixture excerpts in `test_actions_metamods.py`.

The guides say the two orbs land the wanted prefixes with certainty (100%), and the pinned data agrees:

* R14 (Hunter Thicket Bow, item level 78; T1 attack speed, the multimod and `Cannot roll Attack Modifiers` fill
  the three suffixes): the attack-tagged prefixes are out of the pool and two prefix families are left, +1 to
  Level of Socketed Gems and the Hunter Chaos Damage over Time prefix, 1,000 each. Orb 1 lands the sockets with
  chance 1/2 and the Chaos Damage over Time prefix with 1/2, so it lands *a* wanted prefix with chance 1; orb 2
  then lands the other with chance 1: both wanted prefixes, chance 1. Without the metamod an Exalted Orb on the
  same bow lands the sockets with chance 100/11333 with the multimod in the third suffix slot (`test_actions_rare_orbs_real.py` pins 100/11333 for the bow with the attack speed alone).
* R04 (Penetrating Arrow Quiver, item level 81; the fractured Essence of Insanity mod, the Rage Strength and
  the additional Arrow, then the metamod): two prefix families are left, Maximum Life (10,000) and Damage with
  Bow Skills (5,000). Orb 1 lands a wanted prefix with chance 1 (Life 2/3, Bow skills 1/3), orb 2 the other with
  chance 1. Without the metamod an Exalted Orb lands one of the two with chance 600/3727 only (16.1%).

One difference with the guide, recorded with its cause: the guide lists "Projectiles Pierce 2 Additional
Targets" among the suffixes; in the 3.29.3.3 data its Essence of Insanity mod (`AdditionalPierceEssence7`) is a
prefix. It fills one of the three prefix slots, so the two Exalted Orbs fill the other two and the route still
works, but the three suffixes it needs are Strength, the additional Arrow and the metamod. The current data wins.
"""

from fractions import Fraction

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import ExaltedOrb
from crafting_system.items import ExplicitMod, Influence, Item, Rarity

NO_ATTACK = "IntMasterItemGenerationCannotRollAttackAffixes"
MULTI = "StrIntMasterItemGenerationCanHaveMultipleCraftedMods"
HUNTER = frozenset({Influence.HUNTER})
T1_ATTACK_SPEED = "LocalIncreasedAttackSpeed5"
PIERCE_2, ROGUE_STRENGTH, ADDITIONAL_ARROW = "AdditionalPierceEssence7", "StrengthEssence7_", "AdditionalArrowQuiver1_"
R14_WANTED = ("IncreaseSocketedGemLevel", "WeaponCasterDamagePrefix")
R04_WANTED = ("IncreasedLife", "DamageWithWeaponTypeSkill")
FAMILY = lambda mod: mod.families[0]  # noqa: E731


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def rolled(data, mod_id: str, **flags) -> ExplicitMod:
    mod = data.mods[mod_id]
    return ExplicitMod(mod_id, 1, tuple(min(s.min, s.max) for s in mod.stats), crafted=mod.domain == "crafted", **flags)


def base_of(data, name: str, id_suffix: str | None = None):
    return next(b for b in data.base_items.values() if b.name == name and (id_suffix is None or b.id.endswith(id_suffix)))


def build(data, base, level, mod_ids, *, fractured=(), influences=frozenset()):
    mods = tuple(rolled(data, m, fractured=m in fractured) for m in mod_ids)
    return Item.build(data, base_id=base.id, item_level=level, rarity=Rarity.RARE, influences=influences, mods=mods)


def r14_bow(data, *, metamod=True):
    mod_ids = (T1_ATTACK_SPEED, MULTI) + ((NO_ATTACK,) if metamod else ())
    return build(data, base_of(data, "Thicket Bow"), 78, mod_ids, influences=HUNTER)


def r04_quiver(data, *, metamod=True):
    mod_ids = (PIERCE_2, ROGUE_STRENGTH, ADDITIONAL_ARROW) + ((NO_ATTACK,) if metamod else ())
    return build(data, base_of(data, "Penetrating Arrow Quiver", "QuiverNew5"), 81, mod_ids, fractured=(PIERCE_2,))


def hand_prefix_weights(data, base, level, extra_tags, blocked, held_families):
    """Per prefix family the summed weight of the mods a base can roll, found from the raw data alone.

    A mod counts when it is of the base's domain, a prefix, within the item level, spawns on the base or the
    influence tags (first matching spawn tag), carries none of the `blocked` tags and is not of a held family;
    its weight is the spawn weight times the first matching generation weight over 100.
    """
    tags = set(base.tags) | set(extra_tags)
    sums: dict[str, Fraction] = {}
    for mod in data.mods.values():
        if mod.domain != base.domain or mod.generation_type != "prefix" or mod.required_level > level:
            continue
        if set(mod.implicit_tags) & blocked or set(mod.families) & held_families:
            continue
        spawn = next((w.weight for w in mod.spawn_weights if w.tag in tags), 0)
        if spawn == 0:
            continue
        factor = next((Fraction(w.weight, 100) for w in mod.generation_weights if w.tag in tags), Fraction(1))
        sums[mod.families[0]] = sums.get(mod.families[0], Fraction(0)) + spawn * factor
    return sums


def hand_two_orbs(weights: dict[str, Fraction], wanted: tuple[str, ...]):
    """Orb 1 draws a family in proportion to its weight, orb 2 draws from the rest: P(orb 1 wanted), P(both wanted)."""
    total = sum(weights.values())
    first = sum(weights[f] for f in wanted) / total
    both = Fraction(0)
    for one in wanted:
        rest = total - weights[one]
        both += weights[one] / total * sum(weights[other] for other in wanted if other != one) / rest
    return first, both


def engine_two_orbs(data, item, wanted):
    """The same two draws through `ExaltedOrb`: the second orb is applied to the item each wanted family left."""
    out = ExaltedOrb().outcomes(data, item)
    first_shown: dict[str, Fraction] = {}
    for outcome, chance in out.distribution(FAMILY).items():
        (family, _), = outcome
        first_shown[family] = first_shown.get(family, Fraction(0)) + chance
    both = Fraction(0)
    for family in wanted:
        mod = next(e.mod for f in out.pool if f.family == family for e in f.mods)
        second = ExaltedOrb().outcomes(data, item.add_mod(data, rolled(data, mod.id))).distribution(FAMILY)
        landed = sum(chance for outcome, chance in second.items() for lab, _ in outcome if lab in wanted)
        both += first_shown[family] * landed
    return sum(first_shown.get(f, Fraction(0)) for f in wanted), both, first_shown


def test_r14_two_exalted_orbs_under_cannot_roll_attack_land_both_wanted_prefixes_with_certainty(data):
    bow = base_of(data, "Thicket Bow")
    weights = hand_prefix_weights(data, bow, 78, ("bow_basilisk",), {"attack"}, set())
    assert {family: int(w) for family, w in weights.items()} == {"IncreaseSocketedGemLevel": 1000, "WeaponCasterDamagePrefix": 1000}

    first, both, shown = engine_two_orbs(data, r14_bow(data), R14_WANTED)

    assert (first, both) == hand_two_orbs(weights, R14_WANTED) == (1, 1)
    assert shown == {"IncreaseSocketedGemLevel": Fraction(1, 2), "WeaponCasterDamagePrefix": Fraction(1, 2)}


def test_r14_without_the_metamod_the_first_orb_lands_the_wanted_prefixes_with_a_small_chance(data):
    bow = r14_bow(data, metamod=False)

    first, _, shown = engine_two_orbs(data, bow, R14_WANTED)

    assert shown["IncreaseSocketedGemLevel"] == Fraction(100, 11333)  # the pinned chance of test_actions_rare_orbs_real.py
    assert first < Fraction(1, 5)  # nowhere near the guide's 100%: the metamod does the forcing


def test_r04_two_exalted_orbs_under_cannot_roll_attack_land_both_wanted_prefixes_with_certainty(data):
    quiver = base_of(data, "Penetrating Arrow Quiver", "QuiverNew5")
    pierce_family = set(data.mods[PIERCE_2].families)
    weights = hand_prefix_weights(data, quiver, 81, (), {"attack"}, pierce_family)
    assert {family: int(w) for family, w in weights.items()} == {"IncreasedLife": 10000, "DamageWithWeaponTypeSkill": 5000}

    first, both, shown = engine_two_orbs(data, r04_quiver(data), R04_WANTED)

    assert (first, both) == hand_two_orbs(weights, R04_WANTED) == (1, 1)
    assert shown == {"IncreasedLife": Fraction(2, 3), "DamageWithWeaponTypeSkill": Fraction(1, 3)}


def test_r04_without_the_metamod_the_first_orb_lands_a_wanted_prefix_with_chance_600_in_3727(data):
    first, _, shown = engine_two_orbs(data, r04_quiver(data, metamod=False), R04_WANTED)

    assert first == Fraction(600, 3727)  # 16.1%
    assert shown["IncreasedLife"] == Fraction(400, 3727) and shown["DamageWithWeaponTypeSkill"] == Fraction(200, 3727)


def test_r04_the_essence_of_insanity_mod_is_a_prefix_in_the_data(data):
    # the guide lists it among the suffixes; the current data wins and the route still works (see the module text)
    assert data.mods[PIERCE_2].generation_type == "prefix"
    assert data.mods[ADDITIONAL_ARROW].generation_type == "suffix" and data.mods[ROGUE_STRENGTH].generation_type == "suffix"
