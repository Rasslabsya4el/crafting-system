"""The pool of an influenced item: its influence tags join the tags of the base (ticket #67).

The fixture excerpt holds a Thicket Bow and eight families of its pool, four plain and four
Hunter-only, and two older bow mods (a fire and a cold prefix); `influence_oracle.py` types their weights by hand. R14's bow is the Hunter Thicket Bow at item level 78.
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from influence_oracle import LEVELS, families
from items_support import DATA, item, roll
from magic_oracle import draw_sets

from crafting_system.actions import (
    AlterationOrb,
    ChaosOrb,
    ExaltedOrb,
    OutOfScopeError,
    RegalOrb,
    build_pool,
)
from crafting_system.actions.pool import item_tags, tiers_of
from crafting_system.items import Influence, Rarity, tier_table

BOW = "Metadata/Items/Weapons/TwoHandWeapons/Bows/Bow16"
ATTACK_SPEED, SOCKET, BOW_GEM = "LocalIncreasedAttackSpeed5", "LocalIncreaseSocketedGemLevel1", "LocalIncreaseSocketedBowGemLevel1"
HUNTER_MOD = "LocalAddedChaosDamageAndPenetrationInfluence1"
BY_FAMILY = lambda mod: mod.families[0]  # noqa: E731
HUNTER = frozenset({Influence.HUNTER})


def bow(*mods, level=78, rarity=Rarity.RARE, influences=frozenset()):
    return item(*mods, base_id=BOW, item_level=level, rarity=rarity, influences=influences)


def pool_table(item_):
    return {entry.family: (entry.side.value, int(entry.weight)) for entry in build_pool(DATA, item_)}


def seen(outcomes) -> dict[frozenset[str], Fraction]:
    result: dict[frozenset[str], Fraction] = {}
    for outcome, chance in outcomes.distribution(BY_FAMILY).items():
        assert all(count == 1 for _, count in outcome)
        key = frozenset(family for family, _ in outcome)
        result[key] = result.get(key, Fraction(0)) + chance
    return result


def test_the_tags_of_an_influenced_item_are_the_tags_of_its_base_and_one_per_influence():
    base_tags = DATA.base_items[BOW].tags

    assert item_tags(DATA, bow()) == base_tags
    assert item_tags(DATA, bow(influences=HUNTER)) == (*base_tags, "bow_basilisk")
    assert item_tags(DATA, bow(influences=frozenset({Influence.SHAPER, Influence.HUNTER}))) == (
        *base_tags,
        "bow_basilisk",
        "bow_shaper",
    )


@pytest.mark.parametrize("level", LEVELS)
def test_the_plain_pool_of_the_bow_matches_the_hand_table(level):
    assert pool_table(bow(level=level)) == dict(families(level, False))


@pytest.mark.parametrize("level", LEVELS)
def test_the_hunter_pool_of_the_bow_matches_the_hand_table(level):
    assert pool_table(bow(level=level, influences=HUNTER)) == dict(families(level, True))


def test_a_required_level_equal_to_the_item_level_is_allowed_on_an_influenced_item():
    # Chance to Intimidate on Hit 1 needs level 78: out at 77, in at 78
    assert "ChanceToIntimidateOnHit" not in pool_table(bow(level=77, influences=HUNTER))
    assert pool_table(bow(level=78, influences=HUNTER))["ChanceToIntimidateOnHit"] == ("suffix", 500)


def test_the_influence_mods_join_the_pool_and_the_ordinary_weights_do_not_change():
    plain, hunter = pool_table(bow()), pool_table(bow(influences=HUNTER))

    assert {name: value for name, value in hunter.items() if name in plain} == plain
    assert sorted(set(hunter) - set(plain)) == [
        "AddedColdDamagePerDexterity",
        "ArmourPenetration",
        "ChanceToIntimidateOnHit",
        "ChaosDamageHybrid",
    ]


def test_an_influence_without_mods_on_the_class_leaves_the_pool_as_it_is():
    # the excerpt holds no Shaper mod of the bow class, so the pool stays the plain one
    assert pool_table(bow(influences=frozenset({Influence.SHAPER}))) == pool_table(bow())


def test_two_influences_add_both_tags():
    both = bow(influences=frozenset({Influence.HUNTER, Influence.SHAPER}))

    assert pool_table(both) == pool_table(bow(influences=HUNTER))


def test_a_class_with_no_influence_class_key_is_out_of_scope():
    sword = dataclasses.replace(DATA.base_items[BOW], item_class="Thrusting One Hand Sword")
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, BOW: sword})

    with pytest.raises(OutOfScopeError, match=r"Thrusting One Hand Sword.*influence class key"):
        item_tags(data, bow(influences=HUNTER))
    assert item_tags(data, bow()) == sword.tags  # without an influence nothing is asked of the class key


@pytest.mark.parametrize("level", [78, 86])
def test_an_exalted_orb_on_the_hunter_bow_matches_the_hand_oracle(level):
    present = {"IncreasedAttackSpeed": "suffix", "IncreaseSocketedGemLevel": "prefix"}
    item_ = bow(roll(ATTACK_SPEED), roll(SOCKET), level=level, influences=HUNTER)

    assert seen(ExaltedOrb().outcomes(DATA, item_)) == draw_sets(families(level, True), present, 3, 1)


def test_the_hunter_mods_make_up_their_share_of_one_exalted_orb():
    item_ = bow(roll(ATTACK_SPEED), roll(SOCKET), influences=HUNTER)
    pool = families(78, True)
    whole = sum(weight for name, (_, weight) in pool.items() if name not in ("IncreasedAttackSpeed", "IncreaseSocketedGemLevel"))
    hunter_only = 1700 + 200 + 1000 + 500  # the four Hunter-only families
    label = lambda mod: "hunter" if "Influence" in mod.id else None  # noqa: E731

    assert ExaltedOrb().outcomes(DATA, item_).distribution(label)[frozenset({("hunter", 1)})] == Fraction(hunter_only, whole)
    assert whole == 15200 - 5000 - 1000


def test_the_hunter_mod_can_be_the_target_of_an_exalted_orb():
    item_ = bow(roll(ATTACK_SPEED), roll(SOCKET), influences=HUNTER)
    outcomes = ExaltedOrb().outcomes(DATA, item_)

    # 500 of the 9200 left (15200 less 5000 attack speed and 1000 sockets); only the first Chaos mod is asked for
    assert outcomes.chance_all([HUNTER_MOD]) == Fraction(500, 9200)
    plain = ExaltedOrb().outcomes(DATA, bow(roll(ATTACK_SPEED), roll(SOCKET)))
    assert plain.chance_all([HUNTER_MOD]) == 0


def test_a_hunter_mod_can_be_rolled_by_a_chaos_orb_and_by_the_magic_orbs():
    hunter_rare = bow(roll(ATTACK_SPEED), roll(SOCKET), roll(BOW_GEM), roll("AdditionalArrowBow1_"), influences=HUNTER)

    assert ChaosOrb().outcomes(DATA, hunter_rare).chance_all([HUNTER_MOD]) > 0
    assert AlterationOrb().outcomes(DATA, bow(roll(ATTACK_SPEED), rarity=Rarity.MAGIC, influences=HUNTER)).chance_all([HUNTER_MOD]) > 0
    assert RegalOrb().outcomes(DATA, bow(roll(ATTACK_SPEED), rarity=Rarity.MAGIC, influences=HUNTER)).chance_all([HUNTER_MOD]) > 0
    plain = bow(roll(ATTACK_SPEED), roll(SOCKET), roll(BOW_GEM), roll("AdditionalArrowBow1_"))
    assert ChaosOrb().outcomes(DATA, plain).chance_all([HUNTER_MOD]) == 0


def test_a_drawn_hunter_mod_gets_its_tier_among_the_mods_of_its_type():
    item_ = bow(roll(ATTACK_SPEED), roll(SOCKET), influences=HUNTER)
    tiers = tiers_of(DATA, item_)

    # Chaos Damage Hybrid 1 to 5, required levels 68 to 80: five tiers, the highest level is tier 1
    assert [tiers[f"LocalAddedChaosDamageAndPenetrationInfluence{n}"] for n in (1, 2, 3, 4, 5)] == [5, 4, 3, 2, 1]
    assert tiers_of(DATA, bow()) == tier_table(DATA, BOW)
    assert HUNTER_MOD not in tier_table(DATA, BOW)


def test_the_sampler_draws_the_hunter_mod_with_its_chance_and_its_tier():
    item_ = bow(roll(ATTACK_SPEED), roll(SOCKET), influences=HUNTER)
    outcomes = ExaltedOrb().outcomes(DATA, item_)
    rng, runs, hits = random.Random(7), 4000, 0
    for _ in range(runs):
        drawn = outcomes.sample(rng)
        drawn.validate(DATA)
        assert drawn.influences == HUNTER
        for entry in drawn.mods:
            if entry.mod_id == HUNTER_MOD:
                hits += 1
                assert entry.tier == 5
    chance = 500 / 9200
    assert abs(hits / runs - chance) < 5 * (chance * (1 - chance) / runs) ** 0.5


def test_the_retained_item_keeps_its_influences():
    outcomes = ExaltedOrb().outcomes(DATA, bow(roll(ATTACK_SPEED), roll(SOCKET), influences=HUNTER))

    assert outcomes.retained.influences == HUNTER
