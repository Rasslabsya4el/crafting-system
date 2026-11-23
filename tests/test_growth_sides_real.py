"""The side of a wanted mod as the growth's table reads it, on the real 3.29.3.3 dump (ticket #1502). Skips without the cached dump.

The target is X1 of board #1434's unseen crafts (the +2 physical spell wand of the research note's R16): a normal Imbued Wand that wants
+1 to all Spell gems and +1 to Physical Spell gems (two prefixes) and "+#% to Physical Damage over Time Multiplier" of tier 2 or better,
written as a stat. That stat is a suffix on a wand and a prefix of other bases (`PhysicalDamageOverTimeMultiplier1h1` to `1h5`), so
read over every mod that carries it the requirement had no side, and the lock role never saw that the wand waits on both sides.
"""

from pathlib import Path

from abstraction_support import real_game_data

from crafting_system.abstraction._goal import Goal
from crafting_system.planner import _growth
from crafting_system.planner._plan import cheapest_per_class, offers_for, price_offers, with_methods
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "references-allflame-2026-07-31.json"
X1 = """\
base: Imbued Wand
item_level: 84
influence: []
requirements:
  - family: IncreaseSocketedGemLevel
    mod: GlobalSpellGemsLevel1
  - family: IncreaseSpecificSocketedGemLevel
    mod: GlobalPhysicalSpellGemsLevel1
  - stat: "+#% to Physical Damage over Time Multiplier"
    min_tier: 2
    not_crafted: true
start_item:
  rarity: normal
start: bought
"""
METHODS = ("bench-craft", "harvest-reforge", "alteration-orb", "transmutation-orb", "regal-orb", "chaos-orb")


def test_x1_s_damage_over_time_multiplier_is_a_suffix_and_the_lock_role_names_the_prefix_lock_and_harvest_reforge_physical(tmp_path):
    data = real_game_data()
    path = tmp_path / "x1.yaml"
    path.write_text(X1, encoding="utf-8")
    target = with_methods(load_target(path, data), METHODS)
    goal = Goal.from_target(target)
    dot = goal.leaves[2]
    # the stat is carried by prefixes of other bases: read over every mod that passes it, it has both sides
    assert {data.mods[mod_id].generation_type for mod_id in dot.mod_ids if mod_id in data.mods} >= {"prefix", "suffix"}
    priced, _dropped = price_offers(offers_for(data, goal, target.base_id, target.start_item, target.actions).offers, load_price_file(PRICES), "test")
    priced, _same = cheapest_per_class(priced)
    table = _growth.growth_table(data, goal, target, priced, None)
    assert table.open == (0, 1, 2)
    # read among the mods the wand can hold (its pool, the bench's and the unveil's mods for it), the multiplier is a suffix
    assert [table.side_of(leaf) for leaf in table.open] == ["prefix", "prefix", "suffix"]
    # so the step that waits for the three open mods waits on both sides, and the lock role names the guide's last step: the prefix lock
    # and Harvest Reforge Physical under it
    named = {table.entries[position].label for position in table.lock_roles(set(table.open), frozenset(table.views), frozenset())}
    assert {"Bench craft Prefixes Cannot Be Changed", "Harvest Reforge Physical"} <= named
