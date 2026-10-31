"""The Harvest reforges beyond Lightning: the other 15 tagged crafts, the influence reforge and the two likelihood reforges (ticket #72).

Every expected number is written here from the wiki table and the rules, not read from the registry:

* the 16 tagged crafts: tag and lifeforce cost typed from the wiki table (`List of harvest crafting options`),
  the chances against the brute force of `abstraction_oracle.py` on the small amulet pool, whose mods get a
  hand-assigned tag per craft (`TAGGED`), so that every craft has its own set of tagged mods;
* the influence reforge: the fixture Thicket Bow with the Hunter influence and the hand table of
  `influence_oracle.py` (the Hunter mods do not carry the `influence_mod` tag of the data);
* the likelihood reforges: a five-family toy pool whose answer is a closed formula, and the small pool
  against the brute force with the held families weighed by hand.
"""

import dataclasses
from fractions import Fraction

import pytest
from abstraction_oracle import finished_items, hold_chance
from abstraction_pool import (
    COLD_RESIST,
    DAMAGE_1,
    FIRE_GEM,
    FIRE_RESIST,
    GEM,
    LEVEL,
    LIFE_1,
    LIFE_2,
    MANA_1,
    MANA_2,
    RESIST_1,
    SMALL,
    fractured_item,
    roll,
    small_item,
)
from harvest_reforge_support import (
    ATTACK_SPEED,
    HUNTER,
    INFLUENCE_COST,
    LIKELIHOOD_COST,
    LIKELIHOOD_STARTS,
    SPAWNABLE,
    STARTS,
    TABLE,
    TAGGED,
    TAGGED_DATA,
    RANCOUR,
    bow,
    held_weighted_pool,
    start_of,
)
from influence_oracle import families
from items_support import AMULET, DATA
from items_support import roll as fixture_roll

from crafting_system.actions import (
    HarvestReforge,
    HarvestReforgeInfluence,
    HarvestReforgeLikelihood,
    NotApplicableError,
    build_pool,
    catalog,
    kinds,
)
from crafting_system.data import Weight
from crafting_system.items import Influence, Rarity
from crafting_system.rules import get_rule

# --- the 16 tagged crafts --------------------------------------------------------------------------


def test_the_sixteen_crafts_are_the_wiki_table():
    assert set(get_rule("harvest_reforge.tagged_rare_reforge_exists").value) == set(TABLE)
    for craft, (tag, cost) in TABLE.items():
        assert dict(get_rule("harvest_reforge.lifeforce_cost").value[craft]) == cost, craft
        action = HarvestReforge(craft)
        assert action.resources() == cost, craft
        assert action.label() == f"Harvest Reforge {craft.title()}"
        assert get_rule("harvest_reforge.tagged_rare_reforge_exists").value[craft] == tag, craft


def test_five_crafts_take_rancour_and_the_rest_do_not():
    assert {craft for craft, (_, cost) in TABLE.items() if RANCOUR in cost} == {
        "minion", "elemental", "attribute", "mana", "drop",
    }  # fmt: skip
    assert {craft for craft in TABLE if RANCOUR in HarvestReforge(craft).resources()} == {
        "minion", "elemental", "attribute", "mana", "drop",
    }  # fmt: skip


@pytest.mark.parametrize("name", ["", "Lightning", "influence", "more", "defences", "randomise"])
def test_a_craft_that_does_not_exist_is_refused_at_construction(name):
    with pytest.raises(ValueError, match="no Harvest reforge"):
        HarvestReforge(name)


def test_the_catalog_lists_the_sixteen_crafts_for_a_rare_item():
    members = [action for entry in kinds() if entry.name == "harvest-reforge" for action in entry.members(SMALL, start_of("plain"))]
    assert sorted(members, key=lambda a: a.tag) == sorted((HarvestReforge(craft) for craft in TABLE), key=lambda a: a.tag)
    assert members[0] == HarvestReforge("lightning")  # the first offer stays what it was before the other crafts came
    assert HarvestReforge("lightning") in catalog(SMALL, start_of("plain"))


@pytest.mark.parametrize("craft", TABLE)
@pytest.mark.parametrize("start", STARTS)
def test_each_craft_equals_the_brute_force(craft, start):
    tag = TABLE[craft][0]
    item_ = start_of(start)
    outcomes = HarvestReforge(craft).outcomes(TAGGED_DATA, item_)
    expected = finished_items(TAGGED_DATA, item_, tag)

    for mod_id in SPAWNABLE:
        assert hold_chance(expected, {mod_id}) == outcomes.chance_all([mod_id]), (craft, mod_id)
    tagged_held = sum(
        (chance for result, chance in expected if any(tag in TAGGED_DATA.mods[e.mod_id].implicit_tags and not e.fractured for e in result.mods)),
        Fraction(0),
    )
    assert tagged_held == 1  # the guaranteed mod is on every finished item


@pytest.mark.parametrize("craft", ["fire", "mana", "speed", "elemental"])
def test_with_five_mods_fractured_only_the_guaranteed_mod_is_drawn_in_proportion_to_its_weight(craft):
    """Five fractured mods fill the total of 4, 5 and 6 on their own, so the one draw left is the guaranteed one.

    The fractured mods are three prefixes (the damage, life and gem-level families, the last blocked) and two
    suffixes (cold and lightning resistance); the one open slot is a suffix, and the families that fit it are
    Fire Resistance (1000) and Mana Leech (1000 and 1000). The tagged ones among them are drawn in proportion to
    their weight, by hand.
    """
    kept = fractured_item(GEM, DAMAGE_1, LIFE_1, COLD_RESIST, RESIST_1)
    candidates = {FIRE_RESIST: 1000, MANA_1: 1000, MANA_2: 1000}
    tagged = {mod_id: weight for mod_id, weight in candidates.items() if mod_id in TAGGED[craft]}
    assert tagged, craft
    outcomes = HarvestReforge(craft).outcomes(TAGGED_DATA, kept)
    whole = sum(tagged.values())
    for mod_id in candidates:
        want = Fraction(tagged[mod_id], whole) if mod_id in tagged else Fraction(0)
        assert outcomes.chance_all([mod_id]) == want, (craft, mod_id)


def test_a_craft_is_refused_when_every_tagged_mod_is_blocked():
    # critical is on the lightning gem mod and Life 1: fractured Life 2 and the gem family leave nothing
    blocked = fractured_item(LIFE_2, FIRE_GEM)
    with pytest.raises(NotApplicableError, match="critical"):
        HarvestReforge("critical").outcomes(TAGGED_DATA, blocked)
    # a craft nothing in the pool carries
    untagged = dataclasses.replace(
        TAGGED_DATA, mods={k: dataclasses.replace(m, implicit_tags=()) for k, m in TAGGED_DATA.mods.items()}
    )
    with pytest.raises(NotApplicableError):
        HarvestReforge("fire").outcomes(untagged, small_item())


@pytest.mark.parametrize("craft", ["fire", "defence", "drop"])
def test_every_craft_refuses_magic_normal_and_corrupted_items(craft):
    action = HarvestReforge(craft)
    for rarity in (Rarity.NORMAL, Rarity.MAGIC):
        with pytest.raises(NotApplicableError):
            action.outcomes(TAGGED_DATA, small_item(rarity=rarity))
    with pytest.raises(NotApplicableError):
        action.outcomes(TAGGED_DATA, small_item(corrupted=True))


def test_the_defence_craft_guarantees_the_defences_tag_of_the_data():
    assert HarvestReforge("defence").adds().tag == "defences"
    assert HarvestReforge("fire").adds().tag == "fire"


# --- the influence reforge ---------------------------------------------------------------------------

def test_the_influence_reforge_costs_five_thousand_primal_and_one_sacred():
    assert HarvestReforgeInfluence().resources() == INFLUENCE_COST
    assert HarvestReforgeInfluence().label() == "Harvest Reforge Influence"


def test_with_five_mods_fractured_the_one_open_suffix_is_a_hunter_suffix_one_third_each():
    """Fractured: Fire and Cold Damage and a bow gem level (prefixes, 3 in all), Attack Speed 5 and Additional Arrows 1.

    The total of 4, 5 or 6 is met by these five (and the guaranteed one), so exactly one mod is drawn, into the
    one open suffix. At item level 78 the Hunter suffix mods are Armour Penetration 1 and 2 and Chance to
    Intimidate 1 (500 each; Intimidate 2 needs 81): one third each, by hand.
    """
    kept = bow(
        fixture_roll("LocalAddedFireDamageTwoHand1", fractured=True),
        fixture_roll("LocalAddedColdDamageTwoHand1", fractured=True),
        fixture_roll("LocalIncreaseSocketedBowGemLevel1", fractured=True),
        fixture_roll(ATTACK_SPEED, fractured=True),
        fixture_roll("AdditionalArrowBow1_", fractured=True),
    )
    outcomes = HarvestReforgeInfluence().outcomes(DATA, kept)
    hunter_suffixes = (
        "ArmourPenetrationTwoHandWeaponInfluence1_",
        "ArmourPenetrationTwoHandWeaponInfluence2_",
        "ChanceToIntimidateOnHitWeaponInfluence1",
    )
    for mod_id in hunter_suffixes:
        assert outcomes.chance_all([mod_id]) == Fraction(1, 3), mod_id
    assert outcomes.chance_all(["ChanceToIntimidateOnHitWeaponInfluence2"]) == 0


def test_a_hunter_only_family_is_on_every_finished_bow():
    outcomes = HarvestReforgeInfluence().outcomes(DATA, bow())
    hunter_only = {"ChaosDamageHybrid", "AddedColdDamagePerDexterity", "ArmourPenetration", "ChanceToIntimidateOnHit"}
    assert hunter_only <= set(families(78, True))
    without = sum(
        (
            chance
            for outcome, chance in outcomes.distribution(lambda mod: mod.families[0] in hunter_only).items()
            if not any(label for label, _ in outcome)
        ),
        Fraction(0),
    )
    assert without == 0


def test_the_hunter_mods_are_the_influence_mods_though_the_data_does_not_tag_them():
    hunter_mod = DATA.mods["LocalAddedChaosDamageAndPenetrationInfluence1"]
    assert "influence_mod" not in hunter_mod.implicit_tags
    HarvestReforgeInfluence().outcomes(DATA, bow())  # does not refuse for lack of a tagged mod


def test_the_influence_reforge_keeps_a_fractured_mod():
    outcomes = HarvestReforgeInfluence().outcomes(DATA, bow(fixture_roll(ATTACK_SPEED, fractured=True)))
    assert outcomes.chance_all([ATTACK_SPEED]) == 1


def test_an_item_without_influence_is_refused():
    with pytest.raises(NotApplicableError, match="no influence"):
        HarvestReforgeInfluence().outcomes(DATA, bow(influences=frozenset()))
    assert list(kind_members(bow(influences=frozenset()))) == []
    assert list(kind_members(bow())) == [HarvestReforgeInfluence()]


def kind_members(item_):
    return [a for entry in kinds() if entry.name == "harvest-reforge-influence" for a in entry.members(DATA, item_)]


@pytest.mark.parametrize("rarity", [Rarity.NORMAL, Rarity.MAGIC])
def test_the_influence_reforge_refuses_unrare_and_corrupted_items(rarity):
    with pytest.raises(NotApplicableError):
        HarvestReforgeInfluence().outcomes(DATA, bow(rarity=rarity))
    with pytest.raises(NotApplicableError):
        HarvestReforgeInfluence().outcomes(DATA, bow(corrupted=True))


def test_with_two_influences_the_mods_of_both_are_influence_mods():
    two = frozenset({Influence.HUNTER, Influence.SHAPER})
    one = HarvestReforgeInfluence().outcomes(DATA, bow(influences=HUNTER))
    both = HarvestReforgeInfluence().outcomes(DATA, bow(influences=two))

    def marked(out):
        return {e.mod.id for f in out.pool for e in f.mods if "influence" in e.mod.implicit_tags}

    assert marked(one) <= marked(both)  # the fixture has no Shaper bow mod; the exact weight of both is in the real-dump test
    assert marked(one)  # the Hunter mods are marked, whatever the data says of them


# --- the likelihood reforges ------------------------------------------------------------------------


def toy_data():
    """Five mods of five families, one weight each: three suffixes and two prefixes, so no side can fill."""
    chosen = (GEM, LIFE_1, RESIST_1, COLD_RESIST, MANA_1)
    mods = {
        mod_id: dataclasses.replace(
            SMALL.mods[mod_id], spawn_weights=(Weight("amulet", 1), Weight("default", 0)), required_level=1
        )
        for mod_id in chosen
    }
    return dataclasses.replace(SMALL, mods=mods)


TOY = toy_data()


def toy_item(*mod_ids, fractured=()):
    from crafting_system.items import ExplicitMod, Item

    mods = tuple(
        ExplicitMod(mod_id, 1, tuple(min(s.min, s.max) for s in TOY.mods[mod_id].stats), fractured=mod_id in fractured)
        for mod_id in mod_ids
    )
    return Item.build(TOY, base_id=AMULET, item_level=LEVEL, rarity=Rarity.RARE, mods=mods)


def test_the_likelihood_reforges_cost_two_hundred_wild_lifeforce():
    for more in (True, False):
        assert HarvestReforgeLikelihood(more).resources() == LIKELIHOOD_COST
    assert HarvestReforgeLikelihood(True).label() == "Harvest Reforge More Likely"
    assert HarvestReforgeLikelihood(False).label() == "Harvest Reforge Less Likely"


@pytest.mark.parametrize(
    ("more", "weight"), [(True, Fraction(90)), (False, Fraction(1, 90))], ids=["more", "less"]
)
def test_the_held_family_is_left_out_with_the_closed_form_chance(more, weight):
    """Four of five one-weight families are drawn (the total is the floor of 4): the held one is left out when it is last.

    The chance that a family of weight w is the last of the five in successive weighted draws, the others weighing 1,
    is 4! / ((w+4)(w+3)(w+2)(w+1)) written as the product of the other four being drawn first.
    """
    start = toy_item(GEM)
    outcomes = HarvestReforgeLikelihood(more).outcomes(TOY, start)
    left_out = Fraction(1)
    others = 4
    for step in range(4):
        left_out *= Fraction(others - step) / (weight + others - step)
    expected_held = 1 - left_out

    assert outcomes.totals == {4: 1}
    assert outcomes.chance_all([GEM]) == expected_held


def test_more_likely_raises_and_less_likely_lowers_the_chance_of_a_held_mod():
    start = toy_item(GEM)
    more = HarvestReforgeLikelihood(True).outcomes(TOY, start).chance_all([GEM])
    less = HarvestReforgeLikelihood(False).outcomes(TOY, start).chance_all([GEM])
    # four draws of five equal families would hold each family with chance 4/5
    assert less < Fraction(4, 5) < more


def test_a_family_the_item_does_not_hold_keeps_its_plain_weight():
    outcomes = HarvestReforgeLikelihood(True).outcomes(TOY, toy_item(GEM))
    weights = {family.family: family.weight for family in outcomes.pool}
    held = TOY.mods[GEM].families[0]
    assert weights[held] == 90
    assert {w for name, w in weights.items() if name != held} == {1}


def test_the_boost_covers_every_mod_of_the_family_and_a_fractured_or_crafted_mod_too():
    start = fractured_item(RESIST_1)
    outcomes = HarvestReforgeLikelihood(True).outcomes(SMALL, start)
    plain = {family.family: family.weight for family in build_pool(SMALL, start.changed(SMALL, mods=()))}
    resist = SMALL.mods[RESIST_1].families[0]
    assert resist not in {family.family for family in outcomes.pool}  # the fractured family is out of the pool as always
    assert {f.family: f.weight for f in outcomes.pool if f.family != resist} == {
        name: weight for name, weight in plain.items() if name != resist
    }


@pytest.mark.parametrize(
    ("junk", "fractured", "total"),
    [
        ((), (), 4),
        ((GEM, LIFE_1), (), 4),
        ((GEM, LIFE_1, RESIST_1, COLD_RESIST), (), 4),
        ((GEM, LIFE_1, RESIST_1, COLD_RESIST, MANA_1), (), 5),
        ((GEM, LIFE_1, DAMAGE_1, RESIST_1, COLD_RESIST, FIRE_RESIST), (), 6),
        ((GEM, LIFE_1), (RESIST_1,), 4),
        ((GEM, LIFE_1, DAMAGE_1, COLD_RESIST, FIRE_RESIST), (RESIST_1,), 6),
    ],
)
def test_the_reforge_draws_as_many_mods_as_the_item_held_and_at_least_four(junk, fractured, total):
    start = small_item(*(roll(m) for m in junk), *(roll(m, fractured=True) for m in fractured))
    for more in (True, False):
        outcomes = HarvestReforgeLikelihood(more).outcomes(SMALL, start)
        assert outcomes.totals == {total: 1}
        assert len(outcomes.retained.mods) == len(fractured)


@pytest.mark.parametrize("more", [True, False], ids=["more", "less"])
@pytest.mark.parametrize("start", LIKELIHOOD_STARTS)
def test_the_likelihood_reforge_equals_the_brute_force(start, more):
    start_item = LIKELIHOOD_STARTS[start]()
    factor = Fraction(90) if more else Fraction(1, 90)
    totals = {max(len(start_item.mods), 4): Fraction(1)}
    expected = finished_items(SMALL, start_item, None, pool=held_weighted_pool(SMALL, start_item, factor), totals=totals)

    outcomes = HarvestReforgeLikelihood(more).outcomes(SMALL, start_item)
    for mod_id in SPAWNABLE:
        assert hold_chance(expected, {mod_id}) == outcomes.chance_all([mod_id]), mod_id


def test_a_full_item_is_never_left_with_fewer_mods_while_the_pool_has_a_family_for_each_slot():
    start = LIKELIHOOD_STARTS["six"]()
    outcomes = HarvestReforgeLikelihood(True).outcomes(SMALL, start)
    sizes = {len(outcomes.retained.mods) + sum(count for _, count in outcome) for outcome in outcomes.distribution(lambda mod: mod.id)}
    assert sizes == {6}


@pytest.mark.parametrize("more", [True, False])
def test_the_likelihood_reforge_refuses_what_the_other_reforges_refuse(more):
    action = HarvestReforgeLikelihood(more)
    for rarity in (Rarity.NORMAL, Rarity.MAGIC):
        with pytest.raises(NotApplicableError):
            action.outcomes(SMALL, small_item(rarity=rarity))
    with pytest.raises(NotApplicableError):
        action.outcomes(SMALL, small_item(corrupted=True))
    assert [a for entry in kinds() if entry.name == "harvest-reforge-likelihood" for a in entry.members(SMALL, small_item())] == [
        HarvestReforgeLikelihood(True),
        HarvestReforgeLikelihood(False),
    ]
