"""The coarse state on the real R05 ring: the block counts of ADR-0023 (ticket #125). Needs the cached dump; skips without it (CI fetches it, ticket #165).

R05 is a ring (item level 86) with a fractured All Attributes, the goal Life and the forced Strength of the
Deafening Essence of Rage, and every ring craft of the bench (141 in 3.29.3.3) with Remove Crafted Mods enabled.
The exact state graph had 13,172 states (14,350 since ticket #68) and took 906 s to build (ADR-0023, measured). The coarse blocks are
found here without it: breadth-first from the start through the kernels of the lower model (goals are not expanded, as in
the graph), one representative member each. The numbers of ADR-0023 are counts of the exact states' images, and the lower model reaches the same
blocks. The counts do not depend on the machine; the time is reported by the run and never asserted (ADR-0014).

The counts of ADR-0023 (365, 1,582, 4,295) were measured while a state holding the multimod "Can have up to 3 Crafted Modifiers"
was a dead end (every action refused it as out of scope). Since ticket #68 the multimod lifts the limit of crafted mods to three, so
the crafts that follow it are reachable: 738, 2,129 and 5,081 blocks. Without the multimod craft the one-group count is 358.
"""

import pytest
from abstraction_support import real_game_data

from crafting_system.abstraction import Abstraction, Coarsening, Goal, Wanted
from crafting_system.actions import ApplyEssence, RemoveCraftedMods
from crafting_system.actions.bench import bench_crafts
from crafting_system.items import ExplicitMod, Item, Rarity

BASE = "Metadata/Items/Rings/Ring1"
LEVEL = 86
FRACTURED, FORCED = "AllAttributes7", "StrengthEssence7_"
ESSENCE = ApplyEssence("Deafening Essence of Rage")


@pytest.fixture(scope="module")
def r05():
    data = real_game_data()
    item_class = data.base_items[BASE].item_class
    crafts = [craft for craft in bench_crafts(data) if item_class in craft.option(data).item_classes]
    life = Wanted(frozenset(mod.id for mod in data.mods.values() if mod.families == ("IncreasedLife",)))
    ab = Abstraction(data, Goal((life, Wanted(frozenset({FORCED})))), BASE, LEVEL, [RemoveCraftedMods(), *crafts])
    low = tuple(min(stat.min, stat.max) for stat in data.mods[FRACTURED].stats)
    start = Item.build(
        data, base_id=BASE, item_level=LEVEL, rarity=Rarity.RARE, mods=(ExplicitMod(FRACTURED, 1, low, fractured=True),)
    )
    return ab, ab.compress(start), [ESSENCE, RemoveCraftedMods(), *crafts]


def test_there_are_141_ring_crafts_and_the_goal_keeps_two_of_the_told_apart_families_exact(r05):
    ab, start, offers = r05

    pooling = Coarsening.pooling_irrelevant(ab, None, start)

    assert len(offers) - 2 == 141
    assert pooling.relevant_families & pooling.told_apart == {"IncreasedLife", "Strength"}
    assert sum(len(group) for group in pooling.groups) == 20  # the fractured All Attributes family is left out


@pytest.mark.parametrize(("size", "blocks"), [(None, 738), (8, 2129), (4, 5081)], ids=["one_group", "groups_of_8", "groups_of_4"])
def test_the_irrelevant_families_pooled_give_the_blocks_of_the_adr(r05, size, blocks):
    ab, start, offers = r05
    pooling = Coarsening.pooling_irrelevant(ab, size, start)

    reached = pooling.reachable([pooling.coarsen(start)], offers, "lower", stop_at_goal=True)

    assert len(reached) == blocks
