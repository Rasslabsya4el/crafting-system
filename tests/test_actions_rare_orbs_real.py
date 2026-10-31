"""The published odds of R04 and R14 on the real 3.29.3.3 dump: Exalted, Annulment and Fracturing Orb, influenced pools (ticket #67).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there, which is the case in CI; the same
rules are tested on the fixture excerpts in `test_actions_influence.py` and the three action tests.

* R14 (Hunter Thicket Bow, item level 78): the pool of the influenced bow, summed per side by an
  independent walk of the raw weights, joins nine Hunter-only families (and 1,000 of weight to a family
  that has mods without the tag) and leaves the ordinary weights as they were; an Exalted Orb on the
  bow with the T1 attack speed lands +1 to Level of Socketed Gems with the chance the pool says; an
  Orb of Annulment takes the attack speed off a 3-mod bow with chance 1/3 and off a 2-mod bow with 1/2.
* R04 (Penetrating Arrow Quiver, item level 81): a Fracturing Orb fractures the wanted mod of a 4-mod
  quiver with chance 25%.
"""

from fractions import Fraction

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import AnnulmentOrb, ExaltedOrb, FracturingOrb, build_pool
from crafting_system.items import ExplicitMod, Influence, Item, Rarity

BOW_NAME, QUIVER_NAME = "Thicket Bow", "Penetrating Arrow Quiver"
T1_ATTACK_SPEED = "LocalIncreasedAttackSpeed5"  # (17-19)% increased Attack Speed, tier 1, weight 500
SOCKETS = "LocalIncreaseSocketedGemLevel1"  # +1 to Level of Socketed Gems, weight 1000
HUNTER_MOD = "LocalAddedChaosDamageAndPenetrationInfluence3"  # level 74, weight 400
HUNTER = frozenset({Influence.HUNTER})

PLAIN_POOL = {"prefix": 52930, "suffix": 55200}  # summed by the hand walk below
HUNTER_POOL = {"prefix": 58930, "suffix": 59400}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def base_of(data, name: str, domain_tag: str):
    return next(base for base in data.base_items.values() if base.name == name and domain_tag in base.tags)


def rolled(data, mod_id: str) -> ExplicitMod:
    return ExplicitMod(mod_id, 1, tuple(min(s.min, s.max) for s in data.mods[mod_id].stats))


def bow(data, *mod_ids, influences=HUNTER, rarity=Rarity.RARE):
    base = base_of(data, BOW_NAME, "bow")
    return Item.build(
        data, base_id=base.id, item_level=78, rarity=rarity, influences=influences,
        mods=tuple(rolled(data, mod_id) for mod_id in mod_ids),
    )  # fmt: skip


def hand_pool(data, base, level, extra_tags=()):
    """Per side the sum of the weights of the mods a base can roll: first matching spawn tag, then the generation weight over 100."""
    tags = set(base.tags) | set(extra_tags)
    sums = {"prefix": Fraction(0), "suffix": Fraction(0)}
    for mod in data.mods.values():
        if mod.domain != base.domain or mod.generation_type not in sums or mod.required_level > level:
            continue
        spawn = next((w.weight for w in mod.spawn_weights if w.tag in tags), 0)
        if spawn == 0:
            continue
        factor = next((Fraction(w.weight, 100) for w in mod.generation_weights if w.tag in tags), Fraction(1))
        sums[mod.generation_type] += spawn * factor
    return sums


def test_the_plain_bow_pool_is_pinned_by_the_hand_walk(data):
    sums = hand_pool(data, base_of(data, BOW_NAME, "bow"), 78)

    assert {side: int(total) for side, total in sums.items()} == PLAIN_POOL


def test_the_hunter_bow_pool_is_pinned_by_the_hand_walk(data):
    sums = hand_pool(data, base_of(data, BOW_NAME, "bow"), 78, ("bow_basilisk",))

    assert {side: int(total) for side, total in sums.items()} == HUNTER_POOL


def test_the_engine_pool_of_the_hunter_bow_equals_the_hand_walk(data):
    for item, expected in ((bow(data, influences=frozenset()), PLAIN_POOL), (bow(data), HUNTER_POOL)):
        pool = build_pool(data, item)
        assert {side: int(sum(f.weight for f in pool if f.side.value == side)) for side in expected} == expected


def test_the_hunter_tag_adds_families_and_leaves_the_ordinary_weights_alone(data):
    plain = {f.family: f.weight for f in build_pool(data, bow(data, influences=frozenset()))}
    hunter = {f.family: f.weight for f in build_pool(data, bow(data))}

    assert len(plain) == 25 and len(hunter) == 34
    only_hunter = set(hunter) - set(plain)
    assert len(only_hunter) == 9 and sum(hunter[name] for name in only_hunter) == 9200
    # the other 1,000 of the Hunter weight sits in mods of families the plain bow has too
    assert sum(hunter.values()) - sum(plain.values()) == 10200
    assert all(hunter[name] >= plain[name] for name in plain)


def test_r14_an_exalted_orb_on_the_hunter_bow_with_the_t1_attack_speed_lands_the_sockets_with_the_pinned_chance(data):
    outcomes = ExaltedOrb().outcomes(data, bow(data, T1_ATTACK_SPEED))
    family_weight = 5000  # the attack speed family, out of the pool
    expected = Fraction(1000, sum(HUNTER_POOL.values()) - family_weight)

    assert outcomes.chance_all([T1_ATTACK_SPEED, SOCKETS]) == expected == Fraction(100, 11333)
    plain = ExaltedOrb().outcomes(data, bow(data, T1_ATTACK_SPEED, influences=frozenset()))
    assert plain.chance_all([SOCKETS]) == Fraction(1000, sum(PLAIN_POOL.values()) - family_weight) == Fraction(100, 10313)


def test_r14_a_hunter_mod_is_drawable_by_an_exalted_orb_only_on_the_influenced_bow(data):
    hunter = ExaltedOrb().outcomes(data, bow(data, T1_ATTACK_SPEED))
    plain = ExaltedOrb().outcomes(data, bow(data, T1_ATTACK_SPEED, influences=frozenset()))

    assert hunter.chance_all([HUNTER_MOD]) == Fraction(400, sum(HUNTER_POOL.values()) - 5000)
    assert plain.chance_all([HUNTER_MOD]) == 0


def test_r14_annulment_takes_the_attack_speed_off_a_three_mod_bow_with_chance_one_third(data):
    outcomes = AnnulmentOrb().outcomes(data, bow(data, T1_ATTACK_SPEED, SOCKETS, HUNTER_MOD))

    assert 1 - outcomes.chance_all([T1_ATTACK_SPEED]) == Fraction(1, 3)


def test_r14_annulment_takes_the_attack_speed_off_a_two_mod_bow_with_chance_one_half(data):
    outcomes = AnnulmentOrb().outcomes(data, bow(data, T1_ATTACK_SPEED, SOCKETS))

    assert 1 - outcomes.chance_all([T1_ATTACK_SPEED]) == Fraction(1, 2)


def test_r04_a_fracturing_orb_fractures_the_wanted_mod_of_a_four_mod_quiver_with_chance_twenty_five_percent(data):
    quiver = next(base for base in data.base_items.values() if base.name == QUIVER_NAME and base.id.endswith("QuiverNew5"))
    wanted = "AdditionalArrowQuiver1_"
    mods = ("IncreasedLife1", "DamageWithBowSkills1", "Dexterity1", wanted)
    item = Item.build(data, base_id=quiver.id, item_level=81, rarity=Rarity.RARE, mods=tuple(rolled(data, mod_id) for mod_id in mods))
    outcomes = FracturingOrb().outcomes(data, item)

    fractured = sum(c for c, result in outcomes.results if any(e.mod_id == wanted and e.fractured for e in result.mods))
    assert fractured == Fraction(1, 4)
    assert all(sum(c for c, r in outcomes.results if any(e.mod_id == mod_id and e.fractured for e in r.mods)) == Fraction(1, 4) for mod_id in mods)
