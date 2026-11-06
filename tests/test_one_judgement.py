"""One judgement of a mod against a requirement leaf (ticket #457, OR-1, OR-2, OR-4).

Each rule has a unit test on a hand-made export: the committed excerpt plus two mods added here, a bench craft of Life
(domain `crafted`) and an essence-only Life mod (spawn weight 0). The natural Life ladder of the excerpt on an amulet is
IncreasedLife3 (tier 1, level 18), IncreasedLife2 (tier 2, level 11), IncreasedLife1 (tier 3, level 5). The tier of a mod
always comes from that ladder in the game data, never from the number stored on the item.

Both callers are checked on every case: `Requirement.is_met_by` (a concrete item) and `status_of` (the planner's leaf).
"""

import copy
import re
import textwrap
from pathlib import Path

import pytest
from repoe_support import game_data_from_raw, raw_fixtures

from crafting_system.abstraction import Goal, Status, status_of
from crafting_system.items import ExplicitMod, Item, Rarity
from crafting_system.targets import TargetError, parse_target

AMULET = "Metadata/Items/Amulets/Amulet1"
LIFE_TOP, LIFE_MID, LIFE_LOW = "IncreasedLife3", "IncreasedLife2", "IncreasedLife1"  # tiers 1, 2, 3
BENCH_LIFE = "BenchLife1"
ESSENCE_LIFE = "LifeEssenceOnly1"
BENCH_GEM = "BenchGemLevel1"
GEM_TEXT = "+1 to Level of all Lightning Skill Gems"


def _data():
    raw = copy.deepcopy(raw_fixtures())
    mods = raw["mods.json"]
    template = mods["JunMaster2AllDamage3"]
    bench = copy.deepcopy(template)
    bench.update(
        {
            "groups": ["IncreasedLife"],
            "type": "BenchLife",
            "required_level": 1,
            "stats": [{"id": "base_maximum_life", "min": 26, "max": 40}],
            "text": "+(26-40) to maximum Life",
            "spawn_weights": [],
        }
    )
    mods[BENCH_LIFE] = bench
    essence = copy.deepcopy(mods["ColdDamagePercentEssence1"])
    essence.update(
        {
            "groups": ["IncreasedLife"],
            "type": "IncreasedLife",
            "generation_type": "prefix",
            "required_level": 63,
            "stats": [{"id": "base_maximum_life", "min": 80, "max": 90}],
            "text": "+(80-90) to maximum Life",
        }
    )
    mods[ESSENCE_LIFE] = essence
    bench_gem = copy.deepcopy(mods["GlobalLightningGemLevel1"])
    bench_gem.update({"domain": "crafted", "type": "BenchGemLevel", "spawn_weights": [], "required_level": 1})
    mods[BENCH_GEM] = bench_gem  # the same text and stats as the natural mod, made at the bench
    return game_data_from_raw(raw)


DATA = _data()


def target(requirement: str, *, level: int = 84):
    text = f"base: Paua Amulet\nitem_level: {level}\nstart: given\nrequirements:\n" + textwrap.indent(textwrap.dedent(requirement), "  ")
    return parse_target(text, DATA, source="t.yaml")


def held(mod_id: str, *, stored_tier: int = 1, values: tuple[int, ...] | None = None, crafted: bool = False) -> Item:
    mod = DATA.mods[mod_id]
    values = values or tuple(max(stat.min, stat.max) for stat in mod.stats)
    entry = ExplicitMod(mod_id, stored_tier, values, crafted=crafted)
    return Item.build(DATA, base_id=AMULET, item_level=84, rarity=Rarity.RARE, mods=(entry,))


def judged(requirement: str, mod_id: str, *, stored_tier: int = 1, values=None, level: int = 84) -> bool:
    """Whether the item holding `mod_id` meets the requirement, by both callers (they must agree)."""
    wanted = target(requirement, level=level)
    item = held(mod_id, stored_tier=stored_tier, values=values, crafted=DATA.mods[mod_id].domain == "crafted")
    entry = item.mods[0]
    by_item = wanted.is_met_by(item)
    leaf = Goal.from_target(wanted).leaves[0]
    by_state = status_of(leaf, entry.mod_id, entry.values, entry.crafted) is Status.PASSING
    assert by_item == by_state
    return by_item


LIFE = "- family: IncreasedLife\n"


def test_an_unstated_tier_is_the_top_tier_the_item_level_allows():
    assert judged(LIFE, LIFE_TOP)
    assert not judged(LIFE, LIFE_MID)
    assert not judged(LIFE, LIFE_LOW)


def test_the_top_tier_follows_the_item_level():
    # at item level 12 the level-18 mod is out of reach, so tier 2 is the top the level allows (a better tier would still count)
    assert judged(LIFE, LIFE_MID, level=12)
    assert not judged(LIFE, LIFE_LOW, level=12)
    assert judged(LIFE, LIFE_TOP, level=12)
    # at item level 4 no rung of the ladder is low enough: nothing is the top tier, so nothing meets the leaf
    assert not judged(LIFE, LIFE_TOP, level=4)


def test_a_bench_craft_does_not_count_without_mod():
    assert not judged(LIFE, BENCH_LIFE)
    assert not judged(LIFE + "  min_tier: 3\n", BENCH_LIFE)
    assert not judged(LIFE + "  min_tier: any\n", BENCH_LIFE)


def test_mod_is_exactly_that_mod_from_any_origin():
    named = f"- family: IncreasedLife\n  mod: {BENCH_LIFE}\n"
    assert judged(named, BENCH_LIFE)
    assert not judged(named, LIFE_TOP)
    exact = f"- family: IncreasedLife\n  mod: {LIFE_MID}\n"
    assert judged(exact, LIFE_MID)
    assert not judged(exact, LIFE_TOP)  # no other tier of the family


def test_min_roll_is_judged_on_the_values_with_no_tier():
    at_least_30 = LIFE + "  min_roll: 30\n"
    assert judged(at_least_30, LIFE_MID, values=(30,))  # tier 2 is not the top tier, and a value is all that is asked
    assert not judged(at_least_30, LIFE_MID, values=(29,))
    assert judged(at_least_30, LIFE_TOP, values=(40,))
    assert not judged(at_least_30, LIFE_LOW, values=(24,))  # the lowest tier cannot roll 30
    assert judged(at_least_30, BENCH_LIFE, values=(30,))  # a bench craft that rolls 30 counts by its value
    assert not judged(at_least_30, BENCH_LIFE, values=(29,))


def test_a_stated_min_tier_asks_that_natural_tier_or_better():
    assert judged(LIFE + "  min_tier: 2\n", LIFE_TOP)
    assert judged(LIFE + "  min_tier: 2\n", LIFE_MID)
    assert not judged(LIFE + "  min_tier: 2\n", LIFE_LOW)
    assert judged(LIFE + "  min_tier: 1\n", LIFE_TOP) and not judged(LIFE + "  min_tier: 1\n", LIFE_MID)


def test_min_tier_any_counts_every_tier_of_the_natural_ladder_only():
    anything = LIFE + "  min_tier: any\n"
    assert judged(anything, LIFE_TOP) and judged(anything, LIFE_MID) and judged(anything, LIFE_LOW)
    assert not judged(anything, BENCH_LIFE)
    assert not judged(anything, ESSENCE_LIFE)
    named = f"- family: IncreasedLife\n  mod: {ESSENCE_LIFE}\n  min_tier: any\n"
    assert judged(named, ESSENCE_LIFE)  # a mod with no natural tier still needs `mod:`


def test_min_tier_other_words_are_refused():
    with pytest.raises(TargetError, match="min_tier"):
        target(LIFE + "  min_tier: some\n")


def test_an_essence_only_mod_has_no_tier_and_meets_no_tier_leaf():
    assert not judged(LIFE, ESSENCE_LIFE)
    assert not judged(LIFE + "  min_tier: 3\n", ESSENCE_LIFE)
    assert judged(f"- family: IncreasedLife\n  mod: {ESSENCE_LIFE}\n", ESSENCE_LIFE)


def test_the_tier_stored_on_the_item_is_never_read():
    # the data says IncreasedLife1 is tier 3 and IncreasedLife3 is tier 1, whatever the item wrote
    assert not judged(LIFE, LIFE_LOW, stored_tier=1)
    assert judged(LIFE, LIFE_TOP, stored_tier=9)
    assert judged(LIFE + "  min_tier: 1\n", LIFE_TOP, stored_tier=5)


def test_not_crafted_keeps_its_meaning():
    named = f"- family: IncreasedLife\n  mod: {BENCH_LIFE}\n  not_crafted: true\n"
    assert not judged(named, BENCH_LIFE)
    assert judged(LIFE + "  not_crafted: true\n", LIFE_TOP)


def test_the_key_that_made_the_top_tier_optional_is_gone():
    with pytest.raises(TargetError, match="tiers_top_at_item_level"):
        parse_target(
            "base: Paua Amulet\nitem_level: 84\ntiers_top_at_item_level: true\nrequirements:\n  - family: IncreasedLife\n",
            DATA,
            source="t.yaml",
        )


# -- the rule is in one place ----------------------------------------------------------------------------------------------


SRC = Path(__file__).resolve().parents[1] / "src" / "crafting_system"
JUDGEMENT_PATH = (
    "abstraction/_state.py",
    "abstraction/_rolls.py",
    "abstraction/_goal.py",
    "targets/model.py",
    "targets/floor.py",
    "targets/parse.py",
    "cli/_offers.py",
    "cli/_route_card.py",
    "items/tiers.py",
)


def test_a_stat_text_that_states_its_value_counts_a_bench_craft_of_the_same_text():
    """Today's behaviour, pinned (issue #503, an owner-rule question): a `stat:` text with no `#` asks no tier, so the leaf counts the mod by its id
    and roll whatever its origin, a bench craft included, as `mod:` does. A text with a `#` ("+(26-40) to maximum Life") asks a tier."""
    wanted = target(f'- stat: "{GEM_TEXT}"\n')
    leaf = wanted.requirements[0]

    assert {BENCH_GEM, "GlobalLightningGemLevel1"} <= leaf.mod_ids and leaf.tier_ok is None
    assert status_of(leaf, BENCH_GEM, (1,), True) is Status.PASSING
    assert status_of(leaf, "GlobalLightningGemLevel1", (1,), False) is Status.PASSING
    assert status_of(target(f'- stat: "{GEM_TEXT}"\n  not_crafted: true\n').requirements[0], BENCH_GEM, (1,), True) is Status.BELOW
    with_hash = target('- stat: "+# to maximum Life"\n').requirements[0]
    assert with_hash.tier_ok is not None and BENCH_LIFE not in with_hash.tier_ok


# the files where a tier may be compared with another tier: the rule itself, and the fixed cap of a vendor recipe (a claim of the recipe,
# not a leaf's tier). A written number is checked against the literal 1 elsewhere, which this scan does not flag.
TIER_COMPARISON_ALLOWED = ("items/tiers.py", "items/vendor_recipes.py")
TIER_NAME = r"[\w.]*tiers?\w*(?:\[[^\]]*\])?"
TIER_LEFT = re.compile(rf"\b{TIER_NAME}\s*(?:<=|>=|<|>)\s*(?![\d=])[\w.(\[]")
TIER_RIGHT = re.compile(rf"(?<![<>=\-])(?:<=|>=|<|>)(?!=)\s*{TIER_NAME}\b")


def test_no_second_copy_of_the_tier_rule_is_in_src():
    """No tier is ordered against a non-literal anywhere in `src/` but in `items/tiers.py` (`accepted_by_tier`, run by the parser and by `Goal.resolved`)
    and the recipe cap of `items/vendor_recipes.py`: any `tier`, `tiers[...]`, `min_tier` or `.tier` on either side of `<`, `<=`, `>` or `>=`."""
    found = []
    for path in sorted(SRC.rglob("*.py")):
        name = path.relative_to(SRC).as_posix()
        if name in TIER_COMPARISON_ALLOWED:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#")[0]
            if TIER_LEFT.search(code) or TIER_RIGHT.search(code):
                found.append(f"{name}:{number}: {code.strip()}")

    assert found == []


def test_the_scan_sees_a_second_copy_when_there_is_one():
    for code in ("if mod.tier > leaf.min_tier:", "return tier <= wish.min_tier", "ok = tiers[mod_id] <= limit", "while limit >= entry.tier:"):
        assert TIER_LEFT.search(code) or TIER_RIGHT.search(code), code
    for code in ("if tier < 1:", "assert x == tier", "return a -> tier"):
        assert not (TIER_LEFT.search(code) or TIER_RIGHT.search(code)), code


def test_the_judgement_path_has_no_default_tier():
    """No `.get(..., 1)` and no literal tier 1 where a mod is judged against a leaf (T4, T14, T15, T16, T23 of the inventory)."""
    default = re.compile(r"\.get\([^()]*,\s*1\)|BENCH_TIER|CRAFTED_TIER|ELEVATED_TIER")
    texts = {name: (SRC / name).read_text(encoding="utf-8") for name in JUDGEMENT_PATH}

    assert {name: default.findall(text) for name, text in texts.items() if default.search(text)} == {}
