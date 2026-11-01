"""The extremes claim of ADR-0023 on the real pools of the Hunter Thicket Bow (ticket #172; part C of the oracle of #130).

The bow (`Bow16`, item level 78) is the R14-like route of the ADR, with Augmentation, Regal, Exalted and Annulment enabled and a
small goal: +1 socketed gems, a Chaos damage hybrid prefix and tier 1 attack speed. A seeded random walk of the exact
abstraction (a Transmutation to a magic item, then the enabled orbs at random) collects the blocks of the spread 1000
coarsening that hold a pooled slot. For each block every member is enumerated, its exact kernel on the real data is pushed
through the block map, and for random continuation values of the successor blocks the backup of every member must lie between
the smallest and the largest backup of the variants (to 1e-12); Annulment must give one pushed kernel on all the members.
Needs the cached dump; skips without it (CI fetches it, ticket #165). Nothing here asserts a time (ADR-0014).
"""

import random
from fractions import Fraction

import pytest
from abstraction_support import real_game_data
from coarse_support import compare_members, compare_variants

from crafting_system.abstraction import Abstraction, Coarsening, Goal, Wanted
from crafting_system.actions import ActionError, AnnulmentOrb, AugmentationOrb, ExaltedOrb, RegalOrb, TransmutationOrb
from crafting_system.items import Influence, Item, Rarity

BASE = "Metadata/Items/Weapons/TwoHandWeapons/Bows/Bow16"
LEVEL = 78
SPREAD = 1000
SEED = 130
BLOCKS = 100  # at least this many blocks that hold a pooled slot
MEMBER_CAP = 24  # a block with more members is left out, so that the enumeration stays small
WALKS, STEPS = 120, 12
ADDITIONS = (AugmentationOrb(), RegalOrb(), ExaltedOrb())
ORBS = (*ADDITIONS, AnnulmentOrb())


@pytest.fixture(scope="module")
def bow():
    data = real_game_data()

    def family(name: str, **limits) -> Wanted:
        return Wanted(frozenset(mod.id for mod in data.mods.values() if mod.families == (name,)), **limits)

    goal = Goal((family("IncreaseSocketedGemLevel"), family("ChaosDamageHybrid"), family("IncreasedAttackSpeed", min_tier=1)))
    ab = Abstraction(data, goal, BASE, LEVEL, ORBS)
    return data, ab, Coarsening.pooling_by_spread(ab, SPREAD)


def sample(data, ab, pooling) -> dict:
    """Blocks (with the exact states a walk met in them) that hold a pooled slot, from seeded random walks of the exact abstraction."""
    rng = random.Random(SEED)
    start = ab.compress(Item.build(data, base_id=BASE, item_level=LEVEL, rarity=Rarity.NORMAL))

    def draw(kernel):
        return rng.choices(list(kernel), weights=[float(chance) for chance in kernel.values()])[0]

    found: dict = {}
    for _ in range(WALKS):
        state = draw(ab.kernel(start, TransmutationOrb()))
        for _ in range(STEPS):
            if ab.is_goal(state):
                break
            block = pooling.coarsen(state)
            if any(slot.kind.startswith("=") for slot in block.slots) and sum(1 for _ in pooling.members(block)) <= MEMBER_CAP:
                found.setdefault(block, set()).add(state)
            try:
                state = draw(ab.kernel(state, rng.choice(ORBS)))
            except ActionError:
                continue
        if len(found) >= BLOCKS + BLOCKS // 10:
            break
    return found


@pytest.fixture(scope="module")
def blocks(bow):
    return sample(*bow)


def test_the_bow_has_pools_of_family_types_of_different_weights(bow):
    _, ab, pooling = bow

    assert len(pooling.groups) >= 2
    families = [family for group in pooling.groups for family in group]
    weights = {pooling.weight_of(family) for family in families}
    assert len(weights) > 3 and all(isinstance(weight, Fraction) for weight in weights)
    kinds = {ab.kind_of(next(mod for mod in ab.data.mods.values() if family in mod.families)) for family in families}
    assert all(kind.startswith("~") for kind in kinds)  # no craft is enabled: every pooled kind is a family type


def test_the_walk_finds_enough_blocks_with_pooled_slots_and_more_than_one_member(bow, blocks):
    _, _, pooling = bow

    assert len(blocks) >= BLOCKS
    assert sum(1 for block in blocks if len(list(pooling.members(block))) > 1) > BLOCKS // 4


@pytest.mark.parametrize("action", ADDITIONS, ids=lambda action: type(action).__name__)
def test_the_backup_of_every_member_lies_between_the_smallest_and_the_largest_over_the_variants_on_the_real_pools(bow, blocks, action):
    _, ab, pooling = bow

    compared = compare_variants(action, ab, pooling, blocks, draws=20, seed=SEED)

    assert compared > 0


def test_annulment_gives_the_same_pushed_kernel_on_every_member_of_a_block_on_the_real_pools(bow, blocks):
    _, ab, pooling = bow

    assert compare_members(AnnulmentOrb(), ab, pooling, blocks) > 0


def test_the_pool_of_an_influenced_start_holds_the_families_of_its_influence_mods(bow):
    data, ab, _ = bow
    plain = Item.build(data, base_id=BASE, item_level=LEVEL, rarity=Rarity.NORMAL)
    hunter = Item.build(data, base_id=BASE, item_level=LEVEL, rarity=Rarity.NORMAL, influences=frozenset({Influence.HUNTER}))

    without = Coarsening.pooling_by_spread(ab, SPREAD, ab.compress(plain))
    with_hunter = Coarsening.pooling_by_spread(ab, SPREAD, ab.compress(hunter))

    assert with_hunter.influences == frozenset({Influence.HUNTER}) and without.influences == frozenset()
    assert len(with_hunter.told_apart) > len(without.told_apart)  # the influence families are told apart by name in the state
    assert sum(len(group) for group in with_hunter.groups) > sum(len(group) for group in without.groups)
