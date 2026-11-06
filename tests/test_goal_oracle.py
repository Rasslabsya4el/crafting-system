"""The goal oracle on a tiny hand-made export, one test per rule (ticket #411).

No real dump is read here. The export below is a few mods of a made-up ring: a four-tier Life ladder, two bench crafts of Life, an
essence-only Life mod and three single-tier resistances, so each rule of `docs/owner-rules.md` that the oracle implements has a case
whose answer is worked out by hand in the test:

  Life ladder on the ring (spawn on `ring`), tier 1 the highest required level:
      T1 Life4  level 80  (40-49)     T2 Life3  level 60  (30-39)
      T3 Life2  level 30  (20-29)     T4 Life1  level  1  (10-19)
  so at item level 70 the top tier the item level allows is T2 (Life3), and at item level 90 it is T1 (Life4).
"""

import ast
import json
from pathlib import Path

import pytest
from independent.export import ExportMissing
from oracle import goal_oracle as g
from reconcile.export import load_export as load_reconcile_export

ORACLE_DIR = Path(__file__).resolve().parent / "oracle"
RING = "Metadata/Items/Rings/TestRing"
PIN_FILE = Path(__file__).resolve().parents[1] / "src" / "crafting_system" / "data" / "PIN.json"


def mod(mod_id, group, side, level, low, high, *, domain="item", spawn=(("ring", 1000), ("default", 0)), essence=False, stat="base_life", text=None):
    label = text if text is not None else f"+({low}-{high}) to maximum Life"
    return {
        "domain": domain,
        "generation_type": side,
        "groups": [group],
        "type": group,
        "required_level": level,
        "spawn_weights": [{"tag": tag, "weight": weight} for tag, weight in spawn],
        "stats": [{"id": stat, "min": low, "max": high}],
        "text": label,
        "is_essence_only": essence,
    }


PRESENCE_STAT = "local_influence_mod_requires_unique_monster_presence"


def implicit(mod_id, group, generation_type, stats, text, *, domain="item", spawn=(("default", 0),)):
    """An implicit mod of the tiny export: `stats` is a list of (stat id, low, high)."""
    return {
        "domain": domain,
        "generation_type": generation_type,
        "groups": [group],
        "type": group,
        "required_level": 1,
        "spawn_weights": [{"tag": tag, "weight": weight} for tag, weight in spawn],
        "stats": [{"id": stat, "min": low, "max": high} for stat, low, high in stats],
        "text": text,
        "is_essence_only": False,
    }


def eldritch(mod_id, low, high, *, presence=False, side="searing_exarch_implicit", boots=700):
    stats = [("base_shock", low, high)] + ([(PRESENCE_STAT, 1, 1)] if presence else [])
    return implicit(mod_id, "ShockAvoid", side, stats, f"({low}-{high})% chance to Avoid being Shocked", spawn=(("boots", boots), ("default", 0)))


def catalyst(name, description):
    return {"name": name, "item_class": "StackableCurrency", "tags": ["currency"], "domain": "undefined", "properties": {"description": description}}


BOOTS = "Metadata/Items/Armours/Boots/TestBoots"


def tiny_export() -> g.Export:
    mods = {
        "Life1": mod("Life1", "Life", "prefix", 1, 10, 19),
        "Life2": mod("Life2", "Life", "prefix", 30, 20, 29),
        "Life3": mod("Life3", "Life", "prefix", 60, 30, 39),
        "Life4": mod("Life4", "Life", "prefix", 80, 40, 49),
        "LifeCraftLow": mod("LifeCraftLow", "Life", "prefix", 1, 10, 19, domain="crafted", spawn=(("default", 0),)),
        "LifeCraftTop": mod("LifeCraftTop", "Life", "prefix", 1, 30, 39, domain="crafted", spawn=(("default", 0),)),
        "LifeEssence": mod("LifeEssence", "Life", "prefix", 82, 50, 59, essence=True, spawn=(("default", 0),)),
        "Fire1": mod("Fire1", "Fire", "suffix", 1, 5, 9, stat="base_fire", text="+(5-9)% to Fire Resistance"),
        "Cold1": mod("Cold1", "Cold", "suffix", 1, 5, 9, stat="base_cold", text="+(5-9)% to Cold Resistance"),
        "Light1": mod("Light1", "Light", "suffix", 1, 5, 9, stat="base_light", text="+(5-9)% to Lightning Resistance"),
        "Gem1": mod("Gem1", "Gem", "suffix", 1, 1, 1, stat="gem_level", text="+1 to Level of all Test Gems"),
        "Gem2": mod("Gem2", "Gem", "suffix", 50, 2, 2, stat="gem_level", text="+2 to Level of all Test Gems"),
        "LifeRoyale": mod("LifeRoyale", "Life", "prefix", 90, 60, 69),  # a Battle Royale copy: never natural
        # implicits (#416): the ring's own, an Eldritch family of three grades on boots, and its Unique-Presence variant of grade 2
        "RingImplicit1": implicit("RingImplicit1", "RingResist", "unique", [("base_res", 5, 10)], "+(5-10)% to all Elemental Resistances", spawn=()),
        "ShockEldritchImplicit1": eldritch("ShockEldritchImplicit1", 33, 35),
        "ShockEldritchImplicit2": eldritch("ShockEldritchImplicit2", 36, 38),
        "ShockEldritchImplicit3": eldritch("ShockEldritchImplicit3", 39, 41),
        "ShockEldritchImplicitUniquePresence2": eldritch("ShockEldritchImplicitUniquePresence2", 45, 47, presence=True),
        "ShockEldritchImplicitRoyale3": eldritch("ShockEldritchImplicitRoyale3", 39, 41),  # a Battle Royale copy: never a candidate
        "ShockCorruption": implicit("ShockCorruption", "ShockCorrupt", "corrupted", [("base_shock", 10, 20)], "(10-20)% chance to Avoid being Shocked"),
        "EaterWeight0": eldritch("EaterWeight0", 10, 12, side="eater_of_worlds_implicit", boots=0),  # weight 0 on boots: not a candidate
    }
    bases = {
        RING: {
            "name": "Test Ring", "tags": ["ring", "default"], "item_class": "Ring", "domain": "item", "release_state": "released",
            "implicits": ["RingImplicit1"],
        },
        BOOTS: {
            "name": "Test Boots", "tags": ["boots", "default"], "item_class": "Boots", "domain": "item", "release_state": "released",
            "implicits": [],
        },
        "Metadata/Items/Currency/Intrinsic": catalyst("Intrinsic Catalyst", "Adds quality that enhances Attribute modifiers on a ring, amulet or belt\nReplaces other quality types"),
        "Metadata/Items/Currency/Abrasive": catalyst("Abrasive Catalyst", "Adds quality that enhances Attack modifiers on a ring, amulet or belt\nReplaces other quality types"),
        "Metadata/Items/Currency/Tainted": catalyst("Tainted Catalyst", "Applies a random quality type and amount of quality to a Corrupted ring, amulet or belt"),
    }
    bench = [
        {"actions": {"add_explicit_mod": "LifeCraftLow"}, "item_classes": ["Ring", "Amulet"]},
        {"actions": {"add_explicit_mod": "LifeCraftTop"}, "item_classes": ["Ring"]},
        {"actions": {"add_explicit_mod": "LifeCraftTop"}, "item_classes": ["Boots"]},  # not offered for a ring (another option)
        {"actions": {"add_explicit_mod": None}, "item_classes": ["Ring"]},
    ]
    return g.Export(mods, bases, bench)


def target(requirements: str, item_level: int = 70, extra: str = "") -> g.OracleTarget:
    text = f"base: Test Ring\nitem_level: {item_level}\ninfluence: []\n{extra}requirements:\n{requirements}"
    return g.OracleTarget.from_text(text)


def judge(requirements: str, mods: list[tuple], item_level: int = 70, extra: str = "") -> bool:
    """Whether an item of these (mod id, value) pairs meets all the requirements; a mod may carry a third item, fractured."""
    spec = target(requirements, item_level, extra)
    items = tuple(
        g.OMod(entry[0], (entry[1],) if isinstance(entry[1], int) else tuple(entry[1]), len(entry) > 2 and entry[2])
        for entry in mods
    )
    return g.Oracle(tiny_export(), spec).requirements_met(g.OItem(items))


LIFE = "  - family: Life\n"


# --- the natural ladder ---------------------------------------------------------------------------------------------


def test_the_ladder_numbers_tier_1_as_the_highest_required_level_and_leaves_out_what_does_not_spawn():
    export = tiny_export()
    ladder = export.ladders(RING)[("Life", "prefix")]
    assert [(rung.tier, rung.mod_id, rung.level) for rung in ladder] == [(1, "Life4", 80), (2, "Life3", 60), (3, "Life2", 30), (4, "Life1", 1)]
    # crafted, essence-only and Battle Royale copies are not natural; nor is anything with weight 0 on the ring's tags
    assert "LifeCraftLow" not in {rung.mod_id for rung in ladder}
    assert "LifeEssence" not in {rung.mod_id for rung in ladder}
    assert "LifeRoyale" not in {rung.mod_id for rung in ladder}


def test_the_first_matching_spawn_entry_decides_the_weight():
    export = tiny_export()
    first_zero = mod("X", "Life", "prefix", 1, 1, 2, spawn=(("ring", 0), ("default", 1000)))
    assert export.spawn_weight(first_zero, frozenset({"ring", "default"})) == 0
    assert export.spawn_weight(first_zero, frozenset({"default"})) == 1000


def test_the_top_tier_the_item_level_allows():
    export = tiny_export()
    ladder = export.ladders(RING)[("Life", "prefix")]
    assert g.Oracle(export, target(LIFE, 70)).top_tier(ladder) == 2
    assert g.Oracle(export, target(LIFE, 90)).top_tier(ladder) == 1
    assert g.Oracle(export, target(LIFE, 1)).top_tier(ladder) == 4


def test_a_base_is_found_by_its_name_or_its_id():
    export = tiny_export()
    assert export.base_id("Test Ring") == RING and export.base_id(RING) == RING
    with pytest.raises(KeyError):
        export.base_id("No Such Ring")


# --- OR-1: an unstated tier is the top tier the item level allows --------------------------------------------------------


def test_or1_an_unstated_tier_is_the_top_tier_at_the_item_level():
    assert judge(LIFE, [("Life3", 35)], item_level=70)  # T2 is the top tier at item level 70
    assert not judge(LIFE, [("Life2", 29)], item_level=70)  # T3: below the top, at its best roll
    assert not judge(LIFE, [("Life1", 19)], item_level=70)
    assert judge(LIFE, [("Life4", 40)], item_level=90)  # T1 is the top tier at item level 90
    assert not judge(LIFE, [("Life3", 39)], item_level=90)  # the same mod is no longer the top


def test_or1_a_min_tier_is_judged_on_the_ladder_at_that_tier():
    asked = "  - family: Life\n    min_tier: 3\n"
    assert judge(asked, [("Life2", 20)])
    assert judge(asked, [("Life3", 30)])
    assert not judge(asked, [("Life1", 19)])


def test_or1_a_fractured_mod_is_a_rolled_mod():
    assert judge(LIFE, [("Life3", 35, True)])
    assert not judge(LIFE, [("Life2", 25, True)])


def test_or1_a_crafted_mod_is_not_counted_unless_the_requirement_names_it():
    # a craft whose values lie below the top tier's range is not the top tier
    assert not judge(LIFE, [("LifeCraftLow", 19)])
    assert not judge("  - family: Life\n    min_tier: 1\n", [("LifeCraftLow", 19)])
    assert judge("  - family: Life\n    mod: LifeCraftLow\n", [("LifeCraftLow", 10)])  # named exactly: it counts
    # not named: its values are judged on the natural ladder, so a craft inside the top range counts as that tier ...
    assert judge(LIFE, [("LifeCraftTop", 35)])
    # ... unless the requirement refuses crafted mods
    assert not judge("  - family: Life\n    not_crafted: true\n", [("LifeCraftTop", 35)])
    assert judge("  - family: Life\n    not_crafted: true\n", [("Life3", 35)])
    # a value outside every natural range is no tier at all
    assert not judge(LIFE, [("LifeCraftTop", 55)])


def test_or1_the_tier_a_crafted_value_counts_for_depends_on_the_item_level():
    asked = "  - family: Life\n    min_tier: 2\n"
    assert judge(asked, [("LifeCraftTop", 35)], item_level=70)  # 35 is in T2's range (level 60)
    assert not judge(asked, [("LifeCraftTop", 35)], item_level=40)  # T2 needs level 60: at item level 40 no rung holds 35


def test_or1_an_essence_mod_is_not_on_the_ladder_and_counts_only_when_named():
    assert not judge(LIFE, [("LifeEssence", 55)])
    assert judge("  - family: Life\n    mod: LifeEssence\n", [("LifeEssence", 50)])


# --- OR-2: mod: is exactly that mod --------------------------------------------------------------------------------------


def test_or2_mod_is_exactly_that_mod():
    asked = "  - family: Life\n    mod: Life3\n"
    assert judge(asked, [("Life3", 30)])
    assert judge(asked, [("Life3", 39)])  # any roll of it
    assert not judge(asked, [("Life4", 49)])  # a better tier of the family
    assert not judge(asked, [("Life2", 29)])  # a lower tier
    assert not judge(asked, [("LifeCraftTop", 35)])  # the same values, another mod


def test_or2_a_named_mod_still_obeys_not_crafted_and_min_roll():
    assert not judge("  - family: Life\n    mod: LifeCraftLow\n    not_crafted: true\n", [("LifeCraftLow", 15)])
    assert not judge("  - family: Life\n    mod: Life3\n    min_roll: 35\n", [("Life3", 34)])
    assert judge("  - family: Life\n    mod: Life3\n    min_roll: 35\n", [("Life3", 35)])


# --- OR-4: min_roll is a roll with no tier -------------------------------------------------------------------------------


def test_or4_min_roll_with_no_tier_asks_no_tier():
    asked = "  - family: Life\n    min_roll: 25\n"
    assert judge(asked, [("Life2", 25)])  # T3, below the top tier, rolls 25
    assert not judge(asked, [("Life2", 24)])  # one below
    assert judge(asked, [("Life4", 40)])
    assert judge(asked, [("LifeCraftTop", 30)])  # a crafted value that rolls enough is judged by the roll alone


def test_or4_min_roll_by_stat_text_and_a_list_with_a_null():
    by_text = '  - stat: "+# to maximum Life"\n    min_roll: [30]\n'
    assert judge(by_text, [("Life3", 30)])
    assert not judge(by_text, [("Life2", 29)])
    assert judge('  - stat: "+# to maximum Life"\n    min_roll: [null]\n', [("Life1", 10)])


def test_or4_min_roll_with_a_min_tier_asks_both():
    asked = "  - family: Life\n    min_tier: 2\n    min_roll: 35\n"
    assert judge(asked, [("Life3", 35)])
    assert not judge(asked, [("Life3", 34)])  # the tier holds, the roll does not
    assert not judge(asked, [("Life2", 29)])  # the roll cannot hold at tier 3


# --- k-of-n ---------------------------------------------------------------------------------------------------------------


RESISTS = """  - at_least: 2
    of:
      - family: Fire
      - family: Cold
      - family: Light
"""


def test_k_of_n_needs_at_least_k_members():
    assert judge(RESISTS, [("Fire1", 6), ("Cold1", 6)])
    assert judge(RESISTS, [("Fire1", 6), ("Cold1", 6), ("Light1", 6)])
    assert not judge(RESISTS, [("Fire1", 6)])
    assert not judge(RESISTS, [])


def test_k_of_n_members_can_be_groups_and_every_top_level_entry_is_required():
    nested = """  - at_least: 1
    of:
      - family: Life
      - at_least: 2
        of:
          - family: Fire
          - family: Cold
          - family: Light
  - family: Life
    mod: Life3
"""
    assert judge(nested, [("Life3", 30)])  # the Life member and the plain Life3
    assert not judge(nested, [("Fire1", 6), ("Cold1", 6)])  # the inner group holds, but Life3 is missing
    assert judge(nested, [("Life3", 30), ("Fire1", 6), ("Cold1", 6)])


def test_or4_a_stat_text_that_states_its_value_asks_no_top_tier():
    """The V01 case: "+1 to Level of all ..." picks the mod whose text it is; the "+2" mod, the top tier, is another mod."""
    stated = '  - stat: "+1 to Level of all Test Gems"\n'
    assert judge(stated, [("Gem1", 1)])  # not the top tier of the type (Gem2 is), and it counts
    assert not judge(stated, [("Gem2", 2)])  # another text
    assert judge("  - family: Gem\n", [("Gem2", 2)])  # by family with no tier the top tier is asked, as OR-1 says
    assert not judge("  - family: Gem\n", [("Gem1", 1)])
    assert not judge(stated + "    min_tier: 1\n", [("Gem1", 1)])  # a stated tier is still asked


# --- the probes -----------------------------------------------------------------------------------------------------------


def test_the_probes_of_a_requirement():
    spec = target("  - family: Life\n    min_roll: 25\n", 70)
    labels = {(p.kind, p.mod_id, p.values, p.fractured): p for p in g.probe_specs(tiny_export(), spec)}
    # each natural tier at or below the item level, lowest and highest roll
    for mod_id, low, high in (("Life3", 30, 39), ("Life2", 20, 29), ("Life1", 10, 19)):
        assert ("natural", mod_id, (low,), False) in labels
        assert ("natural", mod_id, (high,), False) in labels
    assert not any(p.mod_id == "Life4" for p in labels.values())  # level 80 is above item level 70
    assert labels[("natural", "Life3", (39,), False)].role == "top"
    # a roll one below and at the min_roll, on the rung that holds it
    assert ("natural", "Life2", (24,), False) in labels and ("natural", "Life2", (25,), False) in labels
    # every bench craft offered for a ring whose stats overlap
    assert ("bench", "LifeCraftLow", (10,), False) in labels and ("bench", "LifeCraftTop", (39,), False) in labels
    # a fractured copy of the top tier
    assert ("natural", "Life3", (39,), True) in labels
    # the essence mod appears only when the target names it
    assert not any(p.kind == "essence" for p in labels.values())
    named = g.probe_specs(tiny_export(), target("  - family: Life\n    mod: LifeEssence\n"))
    assert any(p.kind == "essence" and p.mod_id == "LifeEssence" and p.role == "named" for p in named)


# --- implicits, quality and influence (#416) -------------------------------------------------------------------------------
#
# The tiny export has the ring's own implicit RingImplicit1 (+(5-10)%, family RingResist), and for the boots an Eldritch family
# ShockEldritchImplicit1..3 (33-35, 36-38, 39-41; grade = the digit), its Unique-Presence variant of grade 2 (45-47 and a Presence stat),
# a Battle Royale copy, a corrupted mod and a mod of weight 0 on boots. Intrinsic and Abrasive Catalysts add quality on a ring, amulet
# or belt; the Tainted Catalyst "applies a random quality type".

SHOCK_TEXT = '  - stat: "#% chance to Avoid being Shocked"\n'


def boots_target(implicits: str = "", extra: str = "", influence: str = "[]") -> g.OracleTarget:
    block = f"implicits:\n{implicits}" if implicits else ""
    return g.OracleTarget.from_text(f"base: Test Boots\nitem_level: 70\ninfluence: {influence}\n{extra}{block}requirements:\n  - family: Life\n")


def implicit_ok(spec: g.OracleTarget, mod_id: str, values: tuple[int, ...], index: int = 0) -> bool:
    return g.Oracle(tiny_export(), spec).implicit_counts(spec.implicits[index], g.OImplicit(mod_id, values))


def test_the_implicit_candidates_of_a_base_are_its_own_and_the_eldritch_mods_that_spawn_on_its_tags():
    export = tiny_export()
    assert export.implicit_candidates(RING) == ["RingImplicit1"]
    # boots: no own implicit; the three grades and the Presence variant spawn on `boots`; the Royale copy, the corrupted mod and the weight-0 mod do not
    assert export.implicit_candidates(BOOTS) == [
        "ShockEldritchImplicit1", "ShockEldritchImplicit2", "ShockEldritchImplicit3", "ShockEldritchImplicitUniquePresence2",
    ]  # fmt: skip


def test_an_implicit_selector_counts_a_mod_by_family_or_text_and_only_a_mod_of_the_base():
    ring = target(LIFE, extra="implicits:\n  - family: RingResist\n")
    assert implicit_ok(ring, "RingImplicit1", (7,))
    assert not implicit_ok(ring, "ShockEldritchImplicit1", (34,))  # an Eldritch mod does not spawn on a ring's tags
    by_text = boots_target(SHOCK_TEXT)
    for grade, roll in ((1, 34), (2, 37), (3, 40)):
        assert implicit_ok(by_text, f"ShockEldritchImplicit{grade}", (roll,))
    by_family = boots_target("  - family: ShockAvoid\n")
    assert implicit_ok(by_family, "ShockEldritchImplicit2", (37,))
    # not a mod of this base: a Battle Royale copy, a corrupted mod with the same text, a mod of weight 0 on boots
    for other in ("ShockEldritchImplicitRoyale3", "ShockCorruption", "EaterWeight0"):
        assert not implicit_ok(by_text, other, (11,))
    assert not implicit_ok(by_text, "RingImplicit1", (7,))


def test_or2_a_presence_variant_is_counted_only_when_mod_names_it():
    plain = boots_target(SHOCK_TEXT)
    variant = ("ShockEldritchImplicitUniquePresence2", (46, 1))
    assert tiny_export().is_presence_variant(variant[0]) and not tiny_export().is_presence_variant("ShockEldritchImplicit2")
    assert not implicit_ok(plain, *variant)
    assert not implicit_ok(boots_target("  - family: ShockAvoid\n"), *variant)
    named = boots_target(SHOCK_TEXT + f"    mod: {variant[0]}\n")
    assert implicit_ok(named, *variant)
    assert not implicit_ok(named, "ShockEldritchImplicit2", (37,))  # `mod:` is exactly that mod, no other grade of the family


def test_or4_an_implicit_min_roll_is_a_roll_with_no_grade_and_min_grade_is_the_lowest_grade():
    roll = boots_target(SHOCK_TEXT + "    min_roll: 40\n")
    assert implicit_ok(roll, "ShockEldritchImplicit3", (40,)) and implicit_ok(roll, "ShockEldritchImplicit3", (41,))
    assert not implicit_ok(roll, "ShockEldritchImplicit3", (39,))  # one below the roll
    assert not implicit_ok(roll, "ShockEldritchImplicit2", (38,))  # no grade can make up for the roll
    assert not implicit_ok(roll, "ShockEldritchImplicit3", ())  # one value per stat
    grade = boots_target(SHOCK_TEXT + "    min_grade: 3\n")
    assert implicit_ok(grade, "ShockEldritchImplicit3", (39,))
    assert not implicit_ok(grade, "ShockEldritchImplicit2", (38,))
    both = boots_target(SHOCK_TEXT + "    min_grade: 2\n    min_roll: 37\n")
    assert implicit_ok(both, "ShockEldritchImplicit2", (37,)) and not implicit_ok(both, "ShockEldritchImplicit2", (36,))
    ring = target(LIFE, extra="implicits:\n  - family: RingResist\n    min_grade: 1\n")
    assert not implicit_ok(ring, "RingImplicit1", (10,))  # an implicit of the base has grade 0
    listed = target(LIFE, extra="implicits:\n  - family: RingResist\n    min_roll: [8]\n")
    assert implicit_ok(listed, "RingImplicit1", (8,)) and not implicit_ok(listed, "RingImplicit1", (7,))


def test_an_implicit_counts_only_when_the_item_lists_it_and_every_entry_is_asked():
    spec = target(LIFE, extra="implicits:\n  - family: RingResist\n  - family: ShockAvoid\n")
    oracle = g.Oracle(tiny_export(), spec)
    assert not oracle.implicit_met(spec.implicits[0], g.OItem(()))  # a base implicit the item does not list is absent
    both = g.OItem((), (g.OImplicit("RingImplicit1", (6,)),))
    assert oracle.implicit_met(spec.implicits[0], both) and not oracle.implicit_met(spec.implicits[1], both)


def test_the_grade_is_the_digit_that_ends_an_eldritch_id():
    export = tiny_export()
    assert [export.implicit_grade(f"ShockEldritchImplicit{n}") for n in (1, 2, 3)] == [1, 2, 3] and export.implicit_grade("RingImplicit1") == 0
    export.mods["ShockEldritchImplicitX"] = eldritch("ShockEldritchImplicitX", 1, 2)
    with pytest.raises(ValueError, match="grade digit"):
        export.implicit_grade("ShockEldritchImplicitX")


def test_the_catalyst_types_are_the_currencies_that_add_quality_and_the_classes_they_name():
    assert tiny_export().catalyst_types() == {"intrinsic": {"ring", "amulet", "belt"}, "abrasive": {"ring", "amulet", "belt"}}  # no Tainted


def test_quality_of_the_wanted_catalyst_type_and_at_least_the_percent():
    spec = target(LIFE, extra="quality: {type: Intrinsic, min_percent: 20}\n")
    oracle, wanted = g.Oracle(tiny_export(), spec), spec.quality
    assert wanted == g.OQualityReq("intrinsic", 20)  # the type is read as lower case
    assert oracle.quality_met(wanted, g.OQuality("intrinsic", 20)) and oracle.quality_met(wanted, g.OQuality("intrinsic", 25))
    assert not oracle.quality_met(wanted, g.OQuality("intrinsic", 19))
    assert not oracle.quality_met(wanted, g.OQuality("abrasive", 20))  # another catalyst
    assert not oracle.quality_met(wanted, g.OQuality(None, 20))  # plain quality is another kind
    assert not oracle.quality_met(wanted, None)
    plain = target(LIFE, extra="quality: {min_percent: 20}\n")
    assert plain.quality == g.OQualityReq(None, 20)
    assert g.Oracle(tiny_export(), plain).quality_met(plain.quality, g.OQuality(None, 20))
    assert not g.Oracle(tiny_export(), plain).quality_met(plain.quality, g.OQuality("intrinsic", 20))


def test_the_whole_target_needs_the_explicit_mods_the_implicits_and_the_quality_and_does_not_judge_influence():
    """`influence:` is a start input (decided on #416 and #444): it finds the mods that can spawn, and the item carries no influence to judge."""
    spec = g.OracleTarget.from_text(
        "base: Test Ring\nitem_level: 70\ninfluence: [hunter]\nrequirements:\n  - family: Life\n"
        "implicits:\n  - family: RingResist\n    min_roll: 8\nquality: {type: intrinsic, min_percent: 20}\n"
    )
    oracle = g.Oracle(tiny_export(), spec)
    good = g.OItem((g.OMod("Life3", (39,)),), (g.OImplicit("RingImplicit1", (9,)),), g.OQuality("intrinsic", 20))
    assert oracle.target_met(good)  # nothing about the Hunter influence is asked of the finished item
    assert not hasattr(oracle, "influence_met") and not hasattr(good, "influences")
    assert not oracle.target_met(g.OItem((g.OMod("Life2", (29,)),), good.implicits, good.quality))  # a mod below the top tier
    assert not oracle.target_met(g.OItem(good.mods, (g.OImplicit("RingImplicit1", (7,)),), good.quality))
    assert not oracle.target_met(g.OItem(good.mods, good.implicits, g.OQuality("intrinsic", 19)))
    assert not oracle.target_met(g.OItem(good.mods, good.implicits, None))


def test_the_probes_of_an_implicit():
    spec = boots_target(SHOCK_TEXT + "    min_roll: 40\n")
    probes = {(p.mod_id, p.values): p.label for p in g.implicit_probes(tiny_export(), spec)}
    for grade, low, high in ((1, 33, 35), (2, 36, 38), (3, 39, 41)):
        assert (f"ShockEldritchImplicit{grade}", (low,)) in probes and (f"ShockEldritchImplicit{grade}", (high,)) in probes
    # the Presence variant is probed (the oracle says it does not count), the mods that are not the base's are not
    assert ("ShockEldritchImplicitUniquePresence2", (45, 1)) in probes
    assert not any(mod_id in {"ShockEldritchImplicitRoyale3", "ShockCorruption", "EaterWeight0", "RingImplicit1"} for mod_id, _ in probes)
    # a roll one below and at the min_roll, on the grade whose range holds it
    assert ("ShockEldritchImplicit3", (39,)) in probes and ("ShockEldritchImplicit3", (40,)) in probes
    assert not any(label.endswith("min_roll[0]=40") for (mod_id, _), label in probes.items() if mod_id == "ShockEldritchImplicit2")
    assert g.implicit_probes(tiny_export(), boots_target()) == []


def test_the_probes_of_the_quality():
    ring = target(LIFE, extra="quality: {type: intrinsic, min_percent: 20}\n")
    probes = {(p.type, p.percent) for p in g.quality_probes(tiny_export(), ring)}
    assert probes == {(kind, percent) for kind in ("intrinsic", "abrasive") for percent in (1, 19, 20)}  # every catalyst type, one below and at the percent
    boots_plain = boots_target(extra="quality: {min_percent: 20}\n")
    assert {(p.type, p.percent) for p in g.quality_probes(tiny_export(), boots_plain)} == {(None, 1), (None, 19), (None, 20)}
    boots_catalyst = boots_target(extra="quality: {type: intrinsic, min_percent: 20}\n")
    assert g.quality_probes(tiny_export(), boots_catalyst) == []  # boots take no catalyst: nothing could be built, and the leaf shows as unmet
    assert g.quality_probes(tiny_export(), target(LIFE)) == []



# --- what the oracle does not judge ---------------------------------------------------------------------------------------


def test_the_keys_the_oracle_does_not_judge_are_listed():
    plain = target(LIFE)
    assert plain.unjudged == ()
    more = target(LIFE, extra="sockets: {count: 6}\nenchantment: {any_of: []}\nallow_corrupted: true\n")
    assert set(more.unjudged) == {"sockets", "enchantment", "allow_corrupted"}
    assert set(more.unjudged) == set(g.UNJUDGED_KEYS)
    # implicits and quality are judged now (#416), so their keys are not listed; a corrupted implicit is listed, by its path
    judged = target(LIFE, extra="implicits:\n  - family: RingResist\nquality: {type: intrinsic, min_percent: 20}\n")
    assert judged.unjudged == () and len(judged.implicits) == 1 and judged.quality == g.OQualityReq("intrinsic", 20)
    corrupted = target(LIFE, extra="implicits:\n  - family: RingResist\n  - family: ShockCorrupt\n    corrupted: true\n")
    assert corrupted.unjudged == ("implicits[1].corrupted",)
    with pytest.raises(NotImplementedError, match="corrupted implicit is not judged"):
        g.Oracle(tiny_export(), corrupted).implicit_counts(corrupted.implicits[1], g.OImplicit("ShockCorruption", (15,)))


# --- reading and normalising ----------------------------------------------------------------------------------------------


def test_stat_texts_compare_without_ranges_and_markup():
    assert g.normal_text("+(130-144) to maximum Life") == "+# to maximum Life"
    assert g.normal_text("(18-20)% increased Movement Speed\n(6-9)% increased Movement Speed if you haven't been Hit Recently") == (
        "#% increased Movement Speed\n#% increased Movement Speed if you haven't been Hit Recently"
    )
    assert g.normal_text("Gain [Phasing] on Hit with this weapon") == "Gain Phasing on Hit with this weapon"
    assert g.normal_text("2 [ValourFunction|Valour] consumed") == "2 Valour consumed"


def write_version(folder: Path, export: g.Export, *, essences: dict | None = None) -> None:
    folder.mkdir(parents=True)
    (folder / "mods.json").write_text(json.dumps(export.mods), encoding="utf-8")
    (folder / "base_items.json").write_text(json.dumps(export.base_items), encoding="utf-8")
    (folder / "crafting_bench_options.json").write_text(json.dumps(export.bench_options), encoding="utf-8")
    if essences is not None:
        (folder / "essences.json").write_text(json.dumps(essences), encoding="utf-8")


def test_the_export_is_read_from_the_cache_folder_of_the_pin(tmp_path):
    version = json.loads(PIN_FILE.read_text(encoding="utf-8"))["version"]
    export = tiny_export()
    write_version(tmp_path / "repoe-fork" / version, export, essences={"E": {}})
    other = tmp_path / "repoe-fork" / "0.0.0"
    other.mkdir()
    (other / "mods.json").write_text("{}", encoding="utf-8")
    loaded = g.Export.from_cache(tmp_path, pin_file=PIN_FILE)
    assert loaded.mods.keys() == export.mods.keys()
    assert loaded.bench_options == export.bench_options and loaded.essences == {"E": {}}
    assert g.Oracle(loaded, target(LIFE)).base_id == RING
    assert g.Export.from_cache(tmp_path).mods.keys() == export.mods.keys()  # the repo's pin file is the default
    with pytest.raises(ExportMissing, match="2 version folders"):  # two versions and no pin file: it does not guess
        g.Export.from_cache(tmp_path, pin_file=None)


def test_the_export_comes_from_the_cache_dir_of_the_environment_and_a_missing_one_is_export_missing(tmp_path, monkeypatch):
    version = json.loads(PIN_FILE.read_text(encoding="utf-8"))["version"]
    write_version(tmp_path / "repoe-fork" / version, tiny_export())
    monkeypatch.setenv("CRAFTING_CACHE_DIR", str(tmp_path))
    assert g.Export.from_cache().mods.keys() == tiny_export().mods.keys()
    assert g.Export.from_cache().essences == {}  # no essences file: empty, as the oracle read it before
    monkeypatch.setenv("CRAFTING_CACHE_DIR", str(tmp_path / "empty"))
    with pytest.raises(ExportMissing, match="mods.json is not in"):
        g.Export.from_cache()
    with pytest.raises(FileNotFoundError):  # the shared error is still a missing file
        g.Export.from_cache()


def test_the_oracle_and_the_reconciliation_read_one_folder_alike(tmp_path):
    version = json.loads(PIN_FILE.read_text(encoding="utf-8"))["version"]
    write_version(tmp_path / "repoe-fork" / version, tiny_export(), essences={"E": {}})
    oracle_side = g.Export.from_cache(tmp_path)
    reconcile_side = load_reconcile_export(tmp_path)
    assert oracle_side.mods == reconcile_side.mods and oracle_side.base_items == reconcile_side.bases
    assert oracle_side.bench_options == reconcile_side.bench_options and oracle_side.essences == reconcile_side.essences


# --- independence ---------------------------------------------------------------------------------------------------------


SHARED_MODULES = {"independent.ladder", "independent.export"}  # the modules outside this folder that the oracle may import (#419, #432)
SHARED_FILES = [Path(__file__).resolve().parent / "independent" / "ladder.py", Path(__file__).resolve().parent / "independent" / "export.py"]


def imported_modules(source: str) -> set[str]:
    """Every module a source imports; `from independent import x` counts as the module `independent.x`."""
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module == "independent":
            found.update(f"independent.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add(("." * node.level) + (node.module or ""))
    return found


def outside_imports(modules: set[str]) -> set[str]:
    """The absolute imports that are not the standard library modules the oracle uses, `yaml`, or exactly one of the shared modules."""
    allowed = {"json", "os", "re", "dataclasses", "pathlib", "yaml"}
    return {name for name in modules - SHARED_MODULES if not name.startswith(".") and name.split(".")[0] not in allowed}


def sneaky_imports(source: str) -> list[str]:
    """Imports that the plain import scan cannot see: `__import__(...)`, anything named `importlib` or `import_module`,
    `exec` and `eval`, and a relative import that leaves the `oracle` folder (two dots or more, or a sibling that is not there)."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name) and node.id in {"__import__", "importlib", "import_module", "exec", "eval"}:
            found.append(f"line {node.lineno}: uses {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in {"import_module", "__import__", "importlib"}:
            found.append(f"line {node.lineno}: uses .{node.attr}")
        elif isinstance(node, ast.Constant) and node.value in {"__import__", "importlib", "import_module"}:
            found.append(f"line {node.lineno}: names {node.value} as a string")
        elif isinstance(node, ast.Import) and any(alias.name.split(".")[0] == "importlib" for alias in node.names):
            found.append(f"line {node.lineno}: imports importlib")
        elif isinstance(node, ast.ImportFrom) and not node.level and (node.module or "").split(".")[0] == "importlib":
            found.append(f"line {node.lineno}: imports from importlib")
        elif isinstance(node, ast.ImportFrom) and node.level:
            sibling = node.module is None or (ORACLE_DIR / f"{node.module}.py").exists()
            if node.level > 1 or not sibling:
                found.append(f"line {node.lineno}: relative import leaves the oracle folder")
    return found


@pytest.mark.parametrize("source", [path for path in sorted(ORACLE_DIR.glob("*.py"))], ids=lambda path: path.name)
def test_the_oracle_imports_the_standard_library_and_yaml_only(source):
    modules = imported_modules(source.read_text(encoding="utf-8"))
    assert not {name for name in modules if name.split(".")[0] == "crafting_system"}, "the oracle shares no code with the planner"
    assert not outside_imports(modules), "the standard library, yaml and exactly the shared ladder and export modules"
    assert not sneaky_imports(source.read_text(encoding="utf-8"))


def test_the_two_shared_modules_are_the_only_imports_from_outside_the_folder_and_they_are_there():
    assert all(path.is_file() for path in SHARED_FILES)
    assert not outside_imports(imported_modules("from independent import ladder as shared"))
    assert not outside_imports(imported_modules("import independent.ladder"))
    assert not outside_imports(imported_modules("from independent.ladder import natural_ladders"))
    assert not outside_imports(imported_modules("from independent import export as shared_export"))
    assert not outside_imports(imported_modules("import independent.export"))
    assert not outside_imports(imported_modules("from independent.export import load_export"))
    assert not outside_imports(imported_modules("from independent import export, ladder"))


@pytest.mark.parametrize(
    "text",
    [
        "import independent",
        "from independent import other",
        "from independent import ladder, other",
        "from independent.other import x",
        "import independent.other",
        "from independent import *",
        "import reconcile",
        "from reconcile import ladder",
        "import crafting_system",
        "from crafting_system.items import Item",
    ],
)
def test_nothing_else_from_outside_the_folder_is_allowed(text):
    assert outside_imports(imported_modules(text))


def test_the_import_scan_sees_every_way_to_import_the_planner():
    for text in ("import crafting_system", "import crafting_system.items as items", "from crafting_system import items", "from crafting_system.items import Item"):
        assert any(name.split(".")[0] == "crafting_system" for name in imported_modules(text))
    assert not any(name.split(".")[0] == "crafting_system" for name in imported_modules("import json\nfrom pathlib import Path"))


@pytest.mark.parametrize(
    "text",
    [
        "__import__('crafting_system')",
        "import importlib\nimportlib.import_module('crafting_system')",
        "from importlib import import_module",
        "mod = getattr(__builtins__, '__import__')",
        "exec('import crafting_system')",
        "eval('1')",
        "from .. import conftest",
        "from ..goal_oracle_support import x",
        "from .no_such_sibling import x",
    ],
)
def test_the_import_scan_sees_dynamic_and_outside_imports(text):
    assert sneaky_imports(text)


def test_a_sibling_import_inside_the_oracle_folder_is_fine():
    assert not sneaky_imports("from . import goal_oracle\nfrom .goal_oracle import Oracle")
