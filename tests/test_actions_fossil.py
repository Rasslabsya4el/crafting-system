"""Fossils in a Chaotic resonator as exact actions, against the hand oracle (ticket #61).

The oracle (`fossil_oracle.py`) walks every draw order by hand from a literal table of the final weight
of every mod. Each case here works that table out on paper from the base weights and the tag weights of
the fossils (the arithmetic is in the comment of the case), so the code under test never marks its own
homework.

The world is a small synthetic one, built from the repoe fixture format: boots (and gloves and a jewel)
in the domain `item`, 13 pool mods in 10 families with the tags and levels typed below, the fossil
records and corrupted essences each case needs. Item level 86 lets every pool mod through. The tag
weights of the fossils are the test's own (Scorched and Frigid follow the real ones).
"""

import copy
import dataclasses
import random
from fractions import Fraction

import pytest
from fossil_oracle import PREFIX, SUFFIX, chance_all, distribution, mix
from repoe_support import game_data_from_raw, no_network, raw_fixtures  # noqa: F401

from crafting_system.actions import (
    ApplyFossils,
    FossilOutcomes,
    Fractured,
    NotApplicableError,
    OutOfScopeError,
    fossil_actions,
    usable_fossils,
)
from crafting_system.items import ExplicitMod, Influence, Item, Rarity, Side

# ---------------------------------------------------------------------------------------------
# the world

BOOTS = "Metadata/Items/Armours/Boots/TestBoots"
GLOVES = "Metadata/Items/Armours/Gloves/TestGloves"
JEWEL = "Metadata/Items/Jewels/TestJewel"

# mod id, family, side, required level, base weight, implicit tags (all in the domain item)
POOL_MODS = [
    ("FireA", "FireDmg", PREFIX, 10, 1000, ["fire", "damage"]),
    ("FireB", "FireDmg", PREFIX, 50, 500, ["fire", "damage"]),
    ("LifeA", "Life", PREFIX, 20, 1000, ["resource", "life"]),
    ("LifeB", "Life", PREFIX, 80, 500, ["resource", "life"]),
    ("BareA", "Bare", PREFIX, 40, 1000, []),
    ("BareB", "Bare", PREFIX, 80, 500, []),
    ("RarityA", "Rarity", PREFIX, 30, 1000, ["drop"]),
    ("FireResA", "FireRes", SUFFIX, 1, 1000, ["elemental", "fire", "resistance"]),
    ("ColdResA", "ColdRes", SUFFIX, 1, 1000, ["elemental", "cold", "resistance"]),
    ("MinionA", "Minion", SUFFIX, 30, 1000, ["minion", "aura"]),
    ("BleedPhysA", "BleedPhys", SUFFIX, 20, 1000, ["physical", "ailment", "bleed"]),
    ("BleedAtkA", "BleedAtk", SUFFIX, 20, 1000, ["attack", "bleed"]),
    ("CasterA", "Caster", SUFFIX, 20, 1000, ["caster"]),
]
BASE = {mod: weight for mod, _, _, _, weight, _ in POOL_MODS}
LAYOUT = {mod: (family, side) for mod, family, side, _, _, _ in POOL_MODS}
LAYOUT["DelveGemA"] = (
    "GemDelve",
    SUFFIX,
)  # joins the pool with the Faceted Fossil only

FORCED = (
    "AbyssSocketA"  # the suffix of the Hollow Fossil: a delve mod above the item level
)
GLYPHIC_MODS = ["GlyA", "GlyB", "GlyC", "GlyD", "GlyX"]
EVERY_MOD = [*BASE, "DelveGemA", FORCED, *GLYPHIC_MODS]
JOINT = [
    ["FireA", "LifeA"],
    ["FireResA", "MinionA"],
    ["LifeA", "LifeB"],
    ["FireResA", "CasterA", "BareA"],
    ["BleedPhysA", "BleedAtkA", "RarityA"],
]
OUTCOME_RECORD = "Metadata/Items/Currency/CurrencyDelveCraftingRandomFossilOutcome"


def raw_mod(family, side, level, tags, spawn, domain="item", essence_only=False):
    return {
        "adds_tags": [],
        "domain": domain,
        "generation_type": side,
        "generation_weights": [],
        "grants_effects": [],
        "groups": [family],
        "implicit_tags": tags,
        "is_essence_only": essence_only,
        "name": family,
        "required_level": level,
        "spawn_weights": spawn,
        "stats": [{"id": "test_stat", "max": 10, "min": 5}],
        "text": family,
        "type": family,
        "gold_value": None,
    }


def raw_fossil(name, positive=None, negative=None, **fields):
    record = {
        "added_mods": [],
        "allowed_tags": [],
        "blocked_descriptions": {},
        "changes_quality": False,
        "corrupted_essence_chance": 0,
        "descriptions": {},
        "forbidden_tags": [],
        "forced_mods": [],
        "mirrors": False,
        "name": name,
        "negative_mod_weights": [
            {"tag": t, "weight": w} for t, w in (negative or {}).items()
        ],
        "positive_mod_weights": [
            {"tag": t, "weight": w} for t, w in (positive or {}).items()
        ],
        "rolls_lucky": False,
        "rolls_white_sockets": False,
        "sell_price_mods": [],
    }
    record.update(fields)
    return record


def fossil_id(name):
    return "Metadata/Items/Currency/CurrencyDelveCrafting" + name.removesuffix(
        " Fossil"
    )


def raw_essence(name, corruption_only, mods):
    return {
        "item_level_restriction": None,
        "level": 8,
        "mods": mods,
        "name": name,
        "spawn_level_min": 0,
        "type": {"is_corruption_only": corruption_only, "tier": 6},
    }


# name: (positive tag weights, negative tag weights, other record fields)
FOSSILS = {
    "Scorched Fossil": ({"fire": 1000}, {"cold": 0}, {}),
    "Frigid Fossil": ({"cold": 1000}, {"fire": 0}, {}),
    "Elemental Fossil": ({"elemental": 1000}, {}, {}),
    "Serrated Fossil": ({"attack": 1000}, {}, {}),
    "Jagged Fossil": ({"physical": 1000}, {}, {}),
    "Smooth Fossil": ({}, {"physical": 0}, {}),
    "Bound Fossil": ({"minion": 1000, "aura": 1000}, {}, {}),
    "Lucent Fossil": ({"life": 600}, {"damage": 15}, {}),
    "Pale Fossil": ({}, {"damage": 50}, {}),
    "Dull Fossil": ({"attribute": 500}, {}, {}),
    "Corroded Fossil": ({"bleed": 1000, "poison": 1000}, {"elemental": 0}, {}),
    "Opulent Fossil": ({"drop": 1000}, {}, {}),
    "Sanctified Fossil": ({}, {}, {"rolls_lucky": True}),
    # the legacy fields of the Tangled Fossil must be ignored
    "Tangled Fossil": (
        {},
        {},
        {"added_mods": ["DelveGemA"], "corrupted_essence_chance": 100},
    ),
    "Faceted Fossil": ({"gem": 1000}, {}, {"added_mods": ["DelveGemA"]}),
    "Hollow Fossil": ({}, {}, {"forced_mods": [FORCED], "allowed_tags": ["boots"]}),
    "Glyphic Fossil": ({}, {}, {"corrupted_essence_chance": 100}),
    "Fractured Fossil": ({}, {}, {}),
    "Bloodstained Fossil": ({}, {}, {}),
    "Gloveless Fossil": ({}, {}, {"forbidden_tags": ["gloves"]}),
}
# the outcome records of the Tangled Fossil: no name, one boost (x30) and one block each
OUTCOMES = {
    "1": ({"fire": 3000}, {"cold": 0}),
    "1 again": (
        {"fire": 3000},
        {"cold": 0},
    ),  # the same pool as the first: one component
    "2": ({"life": 3000}, {"fire": 0}),
    "3": ({"caster": 3000}, {"minion": 0}),
}


def build_world():
    raw = copy.deepcopy(raw_fixtures())
    template = next(iter(raw["base_items.json"].values()))
    raw["base_items.json"] = {}
    for base_id, name, item_class, tag in (
        (BOOTS, "Test Boots", "Boots", "boots"),
        (GLOVES, "Test Gloves", "Gloves", "gloves"),
        (JEWEL, "Test Jewel", "Jewel", "jewel"),
    ):
        record = copy.deepcopy(template)
        record.update(name=name, item_class=item_class, tags=[tag, "armour", "default"])
        raw["base_items.json"][base_id] = record

    def default(weight):
        return [{"tag": "default", "weight": weight}]

    mods = {
        mod: raw_mod(family, side, level, tags, default(weight))
        for mod, family, side, level, weight, tags in POOL_MODS
    }
    mods["DelveGemA"] = raw_mod(
        "GemDelve",
        SUFFIX,
        1,
        ["attribute", "gem"],
        [{"tag": "boots", "weight": 1000}, {"tag": "default", "weight": 0}],
        domain="delve",
    )
    mods[FORCED] = raw_mod("AbyssSocket", SUFFIX, 90, [], default(0), domain="delve")
    for mod, side, tags in (
        ("GlyA", SUFFIX, ["fire"]),
        ("GlyB", PREFIX, ["cold"]),
        ("GlyC", PREFIX, []),
        ("GlyD", PREFIX, ["life"]),
        ("GlyX", PREFIX, ["fire"]),
    ):
        mods[mod] = raw_mod(
            "Family" + mod, side, 90, tags, default(0), essence_only=True
        )
    for mod, side, family in (
        ("MetaNoSuffixChange", PREFIX, "ItemGenerationCannotChangeSuffixes"),
        ("MetaNoAttack", SUFFIX, "ItemGenerationCannotRollAttackAffixes"),
        ("MetaMulti", SUFFIX, "ItemGenerationCanHaveMultipleCraftedMods"),
    ):
        mods[mod] = raw_mod(family, side, 1, [], [], domain="crafted")
    raw["mods.json"] = mods
    fossils = {
        fossil_id(name): raw_fossil(name, positive, negative, **fields)
        for name, (positive, negative, fields) in FOSSILS.items()
    }
    for number, (positive, negative) in OUTCOMES.items():
        fossils[OUTCOME_RECORD + number.replace(" ", "")] = raw_fossil(
            "", positive, negative
        )
    raw["fossils.json"] = fossils
    raw["essences.json"] = {
        "Metadata/Items/Currency/CurrencyEssenceAlpha": raw_essence("Essence of Alpha", True, {"Boots": "GlyA"}),
        "Metadata/Items/Currency/CurrencyEssenceBeta": raw_essence("Essence of Beta", True, {"Boots": "GlyB"}),
        "Metadata/Items/Currency/CurrencyEssenceGamma": raw_essence("Essence of Gamma", True, {"Boots": "GlyC"}),
        # a corrupted essence that lists nothing for boots, and an ordinary one that lists GlyX
        "Metadata/Items/Currency/CurrencyEssenceDelta": raw_essence("Essence of Delta", True, {"Boots": None, "Gloves": "GlyD"}),
        "Metadata/Items/Currency/CurrencyEssenceEpsilon": raw_essence("Essence of Epsilon", False, {"Boots": "GlyX"}),
    }  # fmt: skip
    return game_data_from_raw(raw)


DATA = build_world()


def roll(mod_id, **flags):
    return ExplicitMod(mod_id, 1, (5,), **flags)


def boots(*mods, rarity=Rarity.RARE, base=BOOTS, **fields):
    fields.setdefault("item_level", 86)
    return Item.build(DATA, base_id=base, rarity=rarity, mods=mods, **fields)


def with_fossils(*names):
    """The world with only the fossils `names` (and no outcome record)."""
    kept = {k: v for k, v in DATA.fossils.items() if v.name in names}
    return dataclasses.replace(DATA, fossils=kept)


def outcomes_of(*names, item=None, data=DATA):
    return ApplyFossils(names).outcomes(data, item or boots())


# ---------------------------------------------------------------------------------------------
# the expectations: final weights by hand, and a component (probability, pool, kept sides, held mods)


def pool(**final):
    """The pool of a case: the base weights, with the final weight of the named mods set (0 drops a mod)."""
    weights = {**BASE, **final}
    result = {}
    for mod, weight in weights.items():
        if weight:
            family, side = LAYOUT[mod]
            result.setdefault(family, (side, {}))[1][mod] = Fraction(weight)
    return result


def component(expected, probability=1, kept=(), held=()):
    return (Fraction(probability), expected, tuple(kept), tuple(held))


def side_of(expected):
    return lambda family: expected[family][0]


def expected_distribution(components):
    return mix(
        [
            (
                p,
                distribution(
                    expected, side_of(expected), tuple((side, side) for side in kept)
                ),
            )
            for p, expected, kept, _ in components
        ]
    )


def expected_chance(components, targets):
    total = Fraction(0)
    for p, expected, kept, held in components:
        wanted = [mod for mod in targets if mod not in held]
        total += p * chance_all(expected, wanted, kept)
    return total


def assert_matches_oracle(outcomes, components):
    """Every single mod, a few joint sets and the distribution of the sides equal the oracle, exactly."""
    assert type(outcomes) is FossilOutcomes
    assert sum(p for p, _ in outcomes.components) == 1
    for mod in EVERY_MOD:
        assert outcomes.chance_all([mod]) == expected_chance(components, [mod]), mod
    for targets in JOINT:
        assert outcomes.chance_all(targets) == expected_chance(components, targets), (
            targets
        )
    seen = outcomes.distribution(lambda mod: mod.generation_type)
    assert dict(seen) == expected_distribution(components)


SANCTIFIED = {
    # base weight x (1 + (required level - 40) / 100)
    "FireA": 700,  # level 10: 1000 x 7/10
    "FireB": 550,  # level 50: 500 x 11/10
    "LifeA": 800,  # level 20: 1000 x 4/5
    "LifeB": 700,  # level 80: 500 x 7/5
    "BareA": 1000,  # level 40: 1000 x 1
    "BareB": 700,  # level 80: 500 x 7/5
    "RarityA": 900,  # level 30: 1000 x 9/10
    "FireResA": 610,  # level 1: 1000 x 61/100
    "ColdResA": 610,
    "MinionA": 900,  # level 30
    "BleedPhysA": 800,  # level 20
    "BleedAtkA": 800,
    "CasterA": 800,
}
SCORCHED = {
    "FireA": 10000,
    "FireB": 5000,
    "FireResA": 10000,
    "ColdResA": 0,
}  # fire x10, cold blocked
OPULENT = {"BareA": 0, "BareB": 0, "RarityA": 10000}  # tagless dropped, drop x10

CASES = [
    # fire x10 on the fire mods (1000 x 10, 500 x 10), cold blocked (weight 0)
    pytest.param(("Scorched Fossil",), SCORCHED, id="one-fossil-boost-and-block"),
    # FireResA carries fire and elemental: 1000 x (10 + 10) = 20000; FireA only fire: 1000 x 10;
    # ColdResA is blocked by the cold block of Scorched whatever Elemental gives it
    pytest.param(
        ("Scorched Fossil", "Elemental Fossil"),
        {"FireA": 10000, "FireB": 5000, "FireResA": 20000, "ColdResA": 0},
        id="two-boosts-are-summed",
    ),
    # Scorched blocks cold and Frigid blocks fire: the fire and cold mods are all gone
    pytest.param(
        ("Scorched Fossil", "Frigid Fossil"),
        {"FireA": 0, "FireB": 0, "FireResA": 0, "ColdResA": 0},
        id="opposing-fossils-block-both",
    ),
    # damage is cut twice: 1000 x 15/100 x 50/100 = 75 and 500 x 3/40 = 37.5 (kept exact);
    # life x6: 6000 and 3000
    pytest.param(
        ("Lucent Fossil", "Pale Fossil"),
        {"FireA": 75, "FireB": Fraction(75, 2), "LifeA": 6000, "LifeB": 3000},
        id="cuts-multiply-and-weights-stay-exact",
    ),
    # FireA: boost fire x10, cut damage x0.15 = x1.5 -> 1500, FireB 750; FireResA has no damage tag: 10000;
    # life x6: 6000, 3000; ColdResA blocked
    pytest.param(
        ("Scorched Fossil", "Lucent Fossil"),
        {
            "FireA": 1500,
            "FireB": 750,
            "FireResA": 10000,
            "ColdResA": 0,
            "LifeA": 6000,
            "LifeB": 3000,
        },
        id="boost-and-cut-on-one-mod",
    ),
    # MinionA carries minion and aura, both boosted by Bound: 1000 x (10 + 10) = 20000
    pytest.param(
        ("Bound Fossil",), {"MinionA": 20000}, id="one-fossil-two-matching-tags"
    ),
    # Corroded: bleed x10 and elemental blocked (FireResA, ColdResA gone). BleedPhysA (physical, ailment,
    # bleed): the bleed term 10 only, the physical x10 of Jagged is covered: 10000, not 20000.
    # BleedAtkA (attack, bleed): bleed 10, Jagged does not apply: 10000
    pytest.param(
        ("Corroded Fossil", "Jagged Fossil"),
        {"FireResA": 0, "ColdResA": 0, "BleedPhysA": 10000, "BleedAtkA": 10000},
        id="corroded-covers-the-physical-boost",
    ),
    # BleedAtkA: bleed 10 + attack 10 (attack is not a covered tag) = 20000; BleedPhysA: bleed only 10000
    pytest.param(
        ("Corroded Fossil", "Serrated Fossil"),
        {"FireResA": 0, "ColdResA": 0, "BleedPhysA": 10000, "BleedAtkA": 20000},
        id="corroded-keeps-the-attack-boost",
    ),
    # Smooth blocks physical: BleedPhysA is gone though Corroded boosts bleed; BleedAtkA: 10000
    pytest.param(
        ("Corroded Fossil", "Smooth Fossil"),
        {"FireResA": 0, "ColdResA": 0, "BleedPhysA": 0, "BleedAtkA": 10000},
        id="a-block-beats-corroded",
    ),
    # Opulent: BareA and BareB (no tags) gone, RarityA (drop) x10
    pytest.param(("Opulent Fossil",), OPULENT, id="opulent-drops-the-tagless"),
    pytest.param(
        ("Opulent Fossil", "Scorched Fossil"),
        {**OPULENT, **SCORCHED},
        id="opulent-with-another-fossil",
    ),
    pytest.param(("Sanctified Fossil",), SANCTIFIED, id="sanctified-level-factor"),
    # the level factor multiplies the whole weight: FireA 1000 x 10 x 7/10 = 7000, FireB 500 x 10 x 11/10
    # = 5500, FireResA 1000 x 10 x 61/100 = 6100, ColdResA stays blocked
    pytest.param(
        ("Sanctified Fossil", "Scorched Fossil"),
        {**SANCTIFIED, "FireA": 7000, "FireB": 5500, "FireResA": 6100, "ColdResA": 0},
        id="sanctified-multiplies-the-whole-weight",
    ),
    # a mod of another domain joins the pool with the weight 1000 and takes the gem x10
    pytest.param(
        ("Faceted Fossil",),
        {"DelveGemA": 10000},
        id="faceted-adds-a-mod-with-the-boost",
    ),
    # DelveGemA carries attribute and gem: 1000 x (10 from Faceted + 5 from Dull) = 15000
    pytest.param(
        ("Faceted Fossil", "Dull Fossil"),
        {"DelveGemA": 15000},
        id="other-fossils-weigh-the-added-mod",
    ),
    # a fossil without tag weights changes nothing
    pytest.param(("Gloveless Fossil",), {}, id="a-fossil-without-weights"),
]


@pytest.mark.parametrize(("names", "final"), CASES)
def test_a_resonator_matches_the_hand_oracle(names, final):
    outcomes = outcomes_of(*names)

    assert_matches_oracle(outcomes, [component(pool(**final))])
    assert len(outcomes.components) == 1


def test_the_chance_is_an_exact_fraction_and_the_distribution_sums_to_one():
    outcomes = outcomes_of("Lucent Fossil", "Pale Fossil")

    assert type(outcomes.chance_all(["FireA"])) is Fraction
    assert sum(outcomes.distribution(lambda mod: mod.generation_type).values()) == 1


def test_a_blocked_mod_never_appears_and_the_boost_does_not_depend_on_the_order_of_names():
    first = outcomes_of("Scorched Fossil", "Elemental Fossil")
    second = outcomes_of("Elemental Fossil", "Scorched Fossil")

    assert first.chance_all(["ColdResA"]) == 0
    assert first.chance_all(["FireResA"]) == second.chance_all(["FireResA"]) > 0


def test_a_fossil_is_found_by_its_record_id_as_well():
    by_id = ApplyFossils((fossil_id("Scorched Fossil"),)).outcomes(DATA, boots())

    assert_matches_oracle(by_id, [component(pool(**SCORCHED))])


# a Tangled Fossil -------------------------------------------------------------------------

TANGLED_ONE = {
    "FireA": 30000,
    "FireB": 15000,
    "FireResA": 30000,
    "ColdResA": 0,
}  # fire x30, cold blocked
TANGLED_TWO = {
    "LifeA": 30000,
    "LifeB": 15000,
    "FireA": 0,
    "FireB": 0,
    "FireResA": 0,
}  # life x30, fire blocked
TANGLED_THREE = {"CasterA": 30000, "MinionA": 0}  # caster x30, minion blocked


def test_a_tangled_fossil_is_the_uniform_mixture_of_its_outcome_records():
    # four records: the first two have the same pool, so three components of 1/2, 1/4 and 1/4
    outcomes = outcomes_of("Tangled Fossil")

    components = [
        component(pool(**TANGLED_ONE), Fraction(2, 4)),
        component(pool(**TANGLED_TWO), Fraction(1, 4)),
        component(pool(**TANGLED_THREE), Fraction(1, 4)),
    ]
    assert_matches_oracle(outcomes, components)
    assert sorted(p for p, _ in outcomes.components) == [
        Fraction(1, 4),
        Fraction(1, 4),
        Fraction(1, 2),
    ]


def test_a_tangled_fossil_adds_to_the_boost_of_another_fossil_and_a_block_wins():
    outcomes = outcomes_of("Tangled Fossil", "Scorched Fossil")

    components = [
        # fire: 10 from Scorched + 30 from the record = 40; cold blocked by both
        component(
            pool(FireA=40000, FireB=20000, FireResA=40000, ColdResA=0), Fraction(2, 4)
        ),
        # the record blocks fire though Scorched boosts it; life x30; cold blocked by Scorched
        component(pool(**{**TANGLED_TWO, "ColdResA": 0}), Fraction(1, 4)),
        # Scorched alone on the fire and cold mods, caster x30, minion blocked
        component(pool(**{**SCORCHED, **TANGLED_THREE}), Fraction(1, 4)),
    ]
    assert_matches_oracle(outcomes, components)
    assert len(outcomes.components) == 3


def test_a_tangled_fossil_ignores_its_own_added_mods_and_forces_nothing():
    outcomes = outcomes_of("Tangled Fossil")

    assert outcomes.chance_all(["DelveGemA"]) == 0  # its legacy added_mods
    assert all(
        outcomes.chance_all([mod]) == 0 for mod in GLYPHIC_MODS
    )  # its legacy essence chance


def test_a_tangled_outcome_record_is_not_a_fossil_to_socket():
    with pytest.raises(ValueError, match="no fossil"):
        ApplyFossils((OUTCOME_RECORD + "1",)).outcomes(DATA, boots())


def test_a_tangled_fossil_without_outcome_records_is_out_of_scope():
    data = dataclasses.replace(
        DATA, fossils={k: v for k, v in DATA.fossils.items() if v.name}
    )

    with pytest.raises(OutOfScopeError, match="outcome records"):
        outcomes_of("Tangled Fossil", data=data)


# a Hollow Fossil --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("names", "final"),
    [(("Hollow Fossil",), {}), (("Hollow Fossil", "Scorched Fossil"), SCORCHED)],
    ids=["hollow", "hollow-with-scorched"],
)
def test_a_hollow_fossil_forces_a_suffix_that_counts_inside_the_total(names, final):
    outcomes = outcomes_of(*names)

    # a suffix is kept: 3, 4 or 5 mods are drawn (totals 4, 5, 6), and the forced mod is on the item
    assert_matches_oracle(
        outcomes, [component(pool(**final), kept=[SUFFIX], held=[FORCED])]
    )
    assert outcomes.chance_all([FORCED]) == 1
    sizes = {}
    for outcome, chance in outcomes.distribution(lambda mod: "new").items():
        size = sum(count for _, count in outcome)
        sizes[size] = sizes.get(size, 0) + chance
    assert sizes == {3: Fraction(8, 12), 4: Fraction(3, 12), 5: Fraction(1, 12)}


def test_the_forced_mod_of_a_hollow_fossil_is_on_the_item_whatever_else_is_drawn():
    outcomes = outcomes_of("Hollow Fossil")

    assert outcomes.chance_all([FORCED, "FireA"]) == outcomes.chance_all(["FireA"])
    assert FORCED not in {
        label for o in outcomes.distribution(lambda m: m.id) for label, _ in o
    }


def test_a_hollow_fossil_is_refused_on_a_base_without_its_allowed_tag():
    with pytest.raises(NotApplicableError, match="Hollow Fossil"):
        outcomes_of("Hollow Fossil", item=boots(base=GLOVES))


def test_a_fossil_is_refused_on_a_base_with_one_of_its_forbidden_tags():
    with pytest.raises(NotApplicableError, match="Gloveless Fossil"):
        outcomes_of("Gloveless Fossil", item=boots(base=GLOVES))
    assert outcomes_of("Gloveless Fossil").chance_all(["FireA"]) == chance_all(
        pool(), ["FireA"]
    )


# a Glyphic Fossil -------------------------------------------------------------------------

THIRD = Fraction(1, 3)
GLYPHIC_CASES = [
    # candidates: GlyA (fire) 1000 x 10, GlyB (cold) blocked, GlyC (no tags) 1000 -> 10/11 and 1/11
    pytest.param(
        ("Glyphic Fossil", "Scorched Fossil"),
        SCORCHED,
        [(Fraction(10, 11), "GlyA", SUFFIX), (Fraction(1, 11), "GlyC", PREFIX)],
        id="tag-factors-decide",
    ),
    # Opulent drops the tagless mods from the pool, not from the Glyphic draw: 1000 each, a third each
    pytest.param(
        ("Glyphic Fossil", "Opulent Fossil"),
        OPULENT,
        [(THIRD, "GlyA", SUFFIX), (THIRD, "GlyB", PREFIX), (THIRD, "GlyC", PREFIX)],
        id="opulent-does-not-apply-to-the-draw",
    ),
    # the level factor of Sanctified is not applied to the draw either
    pytest.param(
        ("Glyphic Fossil", "Sanctified Fossil"),
        SANCTIFIED,
        [(THIRD, "GlyA", SUFFIX), (THIRD, "GlyB", PREFIX), (THIRD, "GlyC", PREFIX)],
        id="sanctified-does-not-apply-to-the-draw",
    ),
]


@pytest.mark.parametrize(("names", "final", "choices"), GLYPHIC_CASES)
def test_a_glyphic_fossil_forces_one_corrupted_essence_mod(names, final, choices):
    outcomes = outcomes_of(*names)

    components = [
        component(pool(**final), probability, kept=[side], held=[forced])
        for probability, forced, side in choices
    ]
    assert_matches_oracle(outcomes, components)
    assert len(outcomes.components) == len(choices)
    for probability, forced, _ in choices:
        assert (
            outcomes.chance_all([forced]) == probability
        )  # above the item level, still on it
    assert outcomes.chance_all(["GlyX"]) == outcomes.chance_all(["GlyD"]) == 0


def test_a_glyphic_fossil_takes_the_mod_the_essences_list_for_the_item_class():
    outcomes = outcomes_of("Glyphic Fossil", item=boots(base=GLOVES))

    assert outcomes.chance_all(["GlyD"]) == 1
    assert outcomes.chance_all(["GlyA"]) == 0
    assert len(outcomes.components) == 1


def test_a_glyphic_fossil_alone_gives_each_candidate_the_same_chance():
    outcomes = outcomes_of("Glyphic Fossil")

    assert [outcomes.chance_all([mod]) for mod in ("GlyA", "GlyB", "GlyC")] == [
        THIRD
    ] * 3


# a Fractured Fossil -----------------------------------------------------------------------


def test_a_fractured_fossil_fractures_one_finished_mod_uniformly():
    outcomes = outcomes_of("Fractured Fossil")
    expected = pool()

    seen = outcomes.distribution(lambda mod: mod.generation_type)
    assert dict(seen) == distribution(expected, side_of(expected), (), Fractured)
    assert all(sum(1 for lab, _ in o if isinstance(lab, Fractured)) == 1 for o in seen)
    assert sum(seen.values()) == 1
    # the reroll itself is the plain one
    assert outcomes.chance_all(["FireA"]) == chance_all(pool(), ["FireA"])


def test_a_fractured_fossil_with_another_fossil_uses_its_weights():
    outcomes = outcomes_of("Fractured Fossil", "Scorched Fossil")
    expected = pool(**SCORCHED)

    seen = outcomes.distribution(lambda mod: mod.generation_type)
    assert dict(seen) == distribution(expected, side_of(expected), (), Fractured)
    assert outcomes.chance_all(["ColdResA"]) == 0


def test_a_fractured_fossil_can_fracture_the_forced_mod():
    outcomes = outcomes_of("Fractured Fossil", "Hollow Fossil")
    expected = pool()

    def label(mod):
        return "forced" if mod.id == FORCED else "drawn"

    seen = outcomes.distribution(label)
    want = distribution(
        expected, lambda family: "drawn", ((SUFFIX, "forced"),), Fractured
    )
    assert dict(seen) == want
    # the forced mod is among 4, 5 or 6 mods: 8/12 x 1/4 + 3/12 x 1/5 + 1/12 x 1/6
    forced_fractured = sum(c for o, c in seen.items() if (Fractured("forced"), 1) in o)
    assert forced_fractured == Fraction(83, 360)


def test_a_fractured_fossil_refuses_an_item_with_a_fractured_mod_or_an_influence():
    with pytest.raises(NotApplicableError, match="fractured or an influenced"):
        outcomes_of("Fractured Fossil", item=boots(roll("LifeA", fractured=True)))
    influenced = dataclasses.replace(boots(), influences=frozenset({Influence.SHAPER}))
    with pytest.raises(NotApplicableError, match="fractured or an influenced"):
        outcomes_of("Fractured Fossil", item=influenced)


# fractured mods of the item ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("names", "final", "kept"),
    [
        (("Scorched Fossil",), SCORCHED, [PREFIX]),
        (("Hollow Fossil",), {}, [PREFIX, SUFFIX]),
    ],
    ids=["scorched", "hollow"],
)
def test_fractured_mods_stay_and_count_inside_the_total(names, final, kept):
    item = boots(roll("LifeA", fractured=True))
    final = {
        **final,
        "LifeA": 0,
        "LifeB": 0,
    }  # the family of the fractured mod is out of the pool

    outcomes = outcomes_of(*names, item=item)

    held = ["LifeA", *([FORCED] if "Hollow Fossil" in names else [])]
    assert_matches_oracle(outcomes, [component(pool(**final), kept=kept, held=held)])
    assert outcomes.chance_all(["LifeA"]) == 1
    assert outcomes.chance_all(["LifeB"]) == 0


# refusals ---------------------------------------------------------------------------------


@pytest.mark.parametrize("rarity", [Rarity.NORMAL, Rarity.MAGIC])
def test_a_resonator_works_on_a_rare_item_only(rarity):
    mods = (roll("LifeA"),) if rarity is Rarity.MAGIC else ()
    with pytest.raises(NotApplicableError, match="rare"):
        outcomes_of("Scorched Fossil", item=boots(*mods, rarity=rarity))


def test_a_corrupted_item_takes_no_resonator():
    with pytest.raises(NotApplicableError, match="corrupted"):
        outcomes_of(
            "Scorched Fossil", item=dataclasses.replace(boots(), corrupted=True)
        )


@pytest.mark.parametrize("metamod", ["MetaNoSuffixChange", "MetaNoAttack"])
def test_an_item_with_a_metamod_is_refused(metamod):
    with pytest.raises(NotApplicableError, match="metamod"):
        outcomes_of("Scorched Fossil", item=boots(roll(metamod, crafted=True)))


def test_an_item_with_the_multimod_is_not_refused_and_the_reroll_removes_it():
    plain = outcomes_of("Scorched Fossil", item=boots(roll("LifeA")))
    with_multimod = outcomes_of("Scorched Fossil", item=boots(roll("LifeA"), roll("MetaMulti", crafted=True)))

    assert [(chance, part.retained) for chance, part in with_multimod.components] == [
        (chance, part.retained) for chance, part in plain.components
    ]
    assert "MetaMulti" not in {entry.mod_id for entry in with_multimod.sample(random.Random(2)).mods}


def test_a_not_applicable_error_comes_before_an_out_of_scope_one():
    item = dataclasses.replace(
        boots(), corrupted=True, influences=frozenset({Influence.HUNTER})
    )

    with pytest.raises(NotApplicableError):
        outcomes_of("Scorched Fossil", item=item)


def test_a_bloodstained_fossil_is_out_of_scope_alone_and_in_a_set():
    for names in (("Bloodstained Fossil",), ("Scorched Fossil", "Bloodstained Fossil")):
        with pytest.raises(OutOfScopeError, match="corrupt"):
            outcomes_of(*names)


def test_hollow_and_glyphic_in_one_resonator_are_out_of_scope():
    for names in (
        ("Hollow Fossil", "Glyphic Fossil"),
        ("Hollow Fossil", "Glyphic Fossil", "Scorched Fossil"),
    ):
        with pytest.raises(OutOfScopeError, match="Hollow and Glyphic"):
            outcomes_of(*names)


def test_a_jewel_takes_a_fossil_with_the_capacity_of_a_jewel():
    (_, part), = outcomes_of("Scorched Fossil", item=boots(base=JEWEL)).components

    assert part.free == {Side.PREFIX: 2, Side.SUFFIX: 2}  # jewel.fossils_work_on_jewels, affix_count.rare_jewel_max_per_side


def test_the_fractured_fossil_works_on_a_jewel():
    assert outcomes_of("Fractured Fossil", item=boots(base=JEWEL)).fractures  # jewel.fracturing_orb_works_on_jewels


def test_a_cluster_jewel_is_out_of_scope():
    cluster = dataclasses.replace(DATA.base_items[JEWEL], domain="affliction_jewel")
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, JEWEL: cluster})

    with pytest.raises(OutOfScopeError, match="cluster jewel"):
        outcomes_of("Scorched Fossil", item=boots(base=JEWEL), data=data)


def test_an_influenced_item_takes_a_fossil():
    influenced = dataclasses.replace(boots(), influences=frozenset({Influence.ELDER}))

    assert {part.retained.influences for _, part in outcomes_of("Scorched Fossil", item=influenced).components} == {influenced.influences}


def test_an_unknown_fossil_name_is_a_value_error():
    with pytest.raises(ValueError, match="no fossil 'Nothing Fossil'"):
        outcomes_of("Scorched Fossil", "Nothing Fossil")


def test_the_same_fossil_by_name_and_by_record_id_is_a_repeat():
    with pytest.raises(ValueError, match="twice"):
        outcomes_of("Scorched Fossil", fossil_id("Scorched Fossil"))


@pytest.mark.parametrize(
    "names",
    [(), ("a", "b", "c", "d", "e"), ("a", "b", "a"), "Scorched Fossil", ("a", "")],
)
def test_a_set_of_no_five_or_repeated_fossils_is_refused_at_construction(names):
    with pytest.raises(ValueError):
        ApplyFossils(names)


# the action itself ------------------------------------------------------------------------


def test_the_names_are_sorted_so_the_order_does_not_matter():
    first = ApplyFossils(("Scorched Fossil", "Frigid Fossil"))
    second = ApplyFossils.of("Frigid Fossil", "Scorched Fossil")

    assert first.fossils == ("Frigid Fossil", "Scorched Fossil")
    assert first == second and hash(first) == hash(second)
    assert {first: 1}[second] == 1
    assert first != ApplyFossils(("Frigid Fossil",))


def test_the_action_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        ApplyFossils(("Scorched Fossil",)).fossils = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    ("count", "resonator"),
    [(1, "Primitive"), (2, "Potent"), (3, "Powerful"), (4, "Prime")],
)
def test_the_resonator_follows_from_the_number_of_fossils(count, resonator):
    action = ApplyFossils(tuple("fossil " + "abcd"[i] for i in range(count)))

    assert action.resonator == f"{resonator} Chaotic Resonator"


# the actions an item could take -----------------------------------------------------------

SMALL = with_fossils(
    "Scorched Fossil",
    "Hollow Fossil",
    "Glyphic Fossil",
    "Fractured Fossil",
    "Bloodstained Fossil",
)


def sizes(actions):
    counts = {}
    for action in actions:
        counts[len(action.fossils)] = counts.get(len(action.fossils), 0) + 1
    return counts


def test_the_usable_fossils_of_a_clean_rare_boots_leave_out_bloodstained():
    assert set(usable_fossils(SMALL, boots())) == {
        "Scorched Fossil",
        "Hollow Fossil",
        "Glyphic Fossil",
        "Fractured Fossil",
    }
    assert "Tangled Fossil" in usable_fossils(DATA, boots())
    assert "" not in usable_fossils(DATA, boots())  # the outcome records are no fossils


def test_every_set_of_one_to_four_usable_fossils_is_listed_without_hollow_with_glyphic():
    actions = fossil_actions(SMALL, boots())

    # 4 fossils: 4 singles, 6 - 1 pairs, 4 - 2 triples, and the only set of four holds both
    assert sizes(actions) == {1: 4, 2: 5, 3: 2}
    assert len(set(actions)) == len(actions) == 11
    assert not any(
        {"Hollow Fossil", "Glyphic Fossil"} <= set(a.fossils) for a in actions
    )
    assert not any("Bloodstained Fossil" in a.fossils for a in actions)
    for action in actions:
        assert action.outcomes(SMALL, boots()).chance_all(["FireA"]) >= 0


def test_a_fractured_item_leaves_the_fractured_fossil_out():
    item = boots(roll("LifeA", fractured=True))

    assert set(usable_fossils(SMALL, item)) == {
        "Scorched Fossil",
        "Hollow Fossil",
        "Glyphic Fossil",
    }
    assert sizes(fossil_actions(SMALL, item)) == {1: 3, 2: 2}


def test_gloves_leave_the_hollow_fossil_out():
    item = boots(base=GLOVES)

    assert set(usable_fossils(SMALL, item)) == {
        "Scorched Fossil",
        "Glyphic Fossil",
        "Fractured Fossil",
    }
    assert sizes(fossil_actions(SMALL, item)) == {1: 3, 2: 3, 3: 1}


def test_an_item_that_takes_no_resonator_has_no_fossil_and_no_action():
    item = boots(rarity=Rarity.NORMAL)

    assert usable_fossils(SMALL, item) == []
    assert fossil_actions(SMALL, item) == []


def test_a_jewel_has_the_fossils_the_fractured_one_included():
    names = usable_fossils(SMALL, boots(base=JEWEL))

    assert "Scorched Fossil" in names and "Fractured Fossil" in names


def test_a_corrupted_item_has_no_fossil_and_no_action():
    item = dataclasses.replace(boots(), corrupted=True)

    assert usable_fossils(SMALL, item) == []
    assert fossil_actions(SMALL, item) == []


# the sampler follows the exact chances ----------------------------------------------------

RUNS = 4000


def agrees(hits, exact, runs=RUNS):
    exact = float(exact)
    return abs(hits / runs - exact) < 5 * (exact * (1 - exact) / runs) ** 0.5


def ids(item):
    return {m.mod_id for m in item.mods}


def test_the_sampler_frequency_follows_the_oracle_chance():
    outcomes = outcomes_of("Scorched Fossil")
    rng = random.Random(61)
    samples = [ids(outcomes.sample(rng)) for _ in range(RUNS)]

    for target in ("FireA", "BareA", "CasterA"):
        exact = chance_all(pool(**SCORCHED), [target])
        assert agrees(sum(target in s for s in samples), exact), target
    assert not any("ColdResA" in s for s in samples)


def test_the_sampler_of_a_tangled_fossil_follows_the_mixture():
    outcomes = outcomes_of("Tangled Fossil")
    components = [
        component(pool(**TANGLED_ONE), Fraction(2, 4)),
        component(pool(**TANGLED_TWO), Fraction(1, 4)),
        component(pool(**TANGLED_THREE), Fraction(1, 4)),
    ]
    rng = random.Random(62)

    hits = sum("FireA" in ids(outcomes.sample(rng)) for _ in range(RUNS))

    assert agrees(hits, expected_chance(components, ["FireA"]))


def test_every_sample_of_a_hollow_fossil_holds_the_forced_mod_and_four_to_six_mods():
    outcomes = outcomes_of("Hollow Fossil")
    rng = random.Random(63)

    for _ in range(300):
        result = outcomes.sample(rng)
        assert FORCED in ids(result) and 4 <= len(result.mods) <= 6
        assert result.rarity is Rarity.RARE


def test_the_sampler_of_a_glyphic_fossil_follows_the_choice_of_the_forced_mod():
    outcomes = outcomes_of("Glyphic Fossil", "Scorched Fossil")
    rng = random.Random(64)
    samples = [ids(outcomes.sample(rng)) for _ in range(RUNS)]

    assert agrees(sum("GlyA" in s for s in samples), Fraction(10, 11))
    assert all(("GlyA" in s) != ("GlyC" in s) for s in samples)
    assert all("GlyB" not in s and "ColdResA" not in s for s in samples)


def test_a_sample_of_a_fractured_fossil_has_exactly_one_more_fractured_mod():
    outcomes = outcomes_of("Fractured Fossil", "Hollow Fossil")
    rng = random.Random(65)
    forced = 0

    for _ in range(RUNS):
        result = outcomes.sample(rng)
        assert len(result.fractured_mods) == 1 and FORCED in ids(result)
        forced += result.fractured_mods[0].mod_id == FORCED

    assert agrees(forced, Fraction(83, 360))
