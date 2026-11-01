"""What the veiled orbs, the unveil and the pick declare about Memory Strands (ticket #284, B5-11a, ADR-0041).

"Done when" and where it is shown:

* the claim for each declaration: `test_each_declaration_cites_its_claims_and_the_claims_of_the_action_do_not_list_them`;
* the spend of the Veiled Chaos Orb is applied (a `Spent`, 0 to 80, the cut pool of its count, the placeholder still forced):
  `test_a_veiled_chaos_orb_on_a_stranded_item_spends_uniformly_on_0_to_80`, `..._draws_from_the_cut_pool_...`;
* the spend is absent for the Veiled Exalted Orb, the unveil and the pick: `test_the_exalted_the_unveil_and_the_pick_spend_nothing_...`.

The items are the amulet of the contract fixtures with the hand-written veiled mods of `veiled_support`.
"""

import dataclasses
import random
from fractions import Fraction

import pytest
from abstraction_pool import LIFE_1, RESIST_2
from contract_support import CONTRACT_DATA as DATA, TIERS, _item
from veiled_support import ARMOUR, LIFE_1 as VEIL_LIFE_1, MANA, PLACEHOLDER_PREFIX

from crafting_system.actions import Pick, Spent, SpendLaw, StrandUse, Unveil, VeiledChaosOrb, VeiledExaltedOrb, strands_after
from crafting_system.actions.cut import Cut
from crafting_system.actions.pool import build_pool
from crafting_system.items import ExplicitMod, Item, Rarity, veiled_placeholder

ONE = Fraction(1)
CHAOS_CLAIMS = frozenset(
    {
        "affix_pool.no_memory_strands", "memory_strands.rollable_tiers", "memory_strands.cull_counts_eligible_tiers",
        "memory_strands.zero_is_no_cull", "memory_strands.cut_uses_strands_before_spend", "memory_strands.weights_of_kept_tiers",
        "memory_strands.spend_law_uniform", "memory_strands.spend_ranges_special_orbs", "memory_strands.cut_follows_spend_table",
    }
)  # fmt: skip


def rolled(mod_id: str) -> ExplicitMod:
    mod = DATA.mods[mod_id]
    return ExplicitMod(mod_id, TIERS.get(mod_id, 1), tuple(min(stat.min, stat.max) for stat in mod.stats))


def rare(*mods: ExplicitMod, **fields) -> Item:
    return _item(Rarity.RARE, *mods, **fields)


def with_count(item: Item, count: int) -> Item:
    return dataclasses.replace(item, memory_strands=count)


def without_count(item: Item) -> Item:
    return with_count(item, 0)


def plain_rare() -> Item:
    return rare(rolled(LIFE_1), rolled(RESIST_2))


def with_placeholder() -> Item:
    return rare(rolled(RESIST_2), veiled_placeholder(DATA, PLACEHOLDER_PREFIX))


def with_offer() -> Item:
    return rare(rolled(RESIST_2), veiled_placeholder(DATA, PLACEHOLDER_PREFIX), veil_offer=(ARMOUR, VEIL_LIFE_1, MANA))


# --- the Veiled Chaos Orb: cuts, spends 0 to 80 ----------------------------------------------------------------------------


@pytest.mark.parametrize("strands", [1, 30, 80, 100])
def test_a_veiled_chaos_orb_on_a_stranded_item_spends_uniformly_on_0_to_80(strands):
    item = with_count(plain_rare(), strands)

    result = VeiledChaosOrb().outcomes(DATA, item)

    assert isinstance(result, Spent)
    assert dict(result.strands_after) == dict(SpendLaw.uniform(80).after(strands, len(item.mods)))
    assert strands_after(result, strands) == result.strands_after
    assert sum(result.strands_after.values()) == ONE
    assert min(result.strands_after) == max(0, strands - 80) and max(result.strands_after) == strands
    rng = random.Random(7)
    for _ in range(40):
        finished = result.sample(rng)
        assert finished.memory_strands in result.strands_after
        assert any(DATA.mods[entry.mod_id].domain == "veiled" for entry in finished.mods)  # the placeholder is there


def test_a_veiled_chaos_orb_draws_from_the_cut_pool_of_its_count_and_the_placeholder_is_still_forced():
    item = with_count(plain_rare(), 60)

    result = VeiledChaosOrb().outcomes(DATA, item)

    plain = VeiledChaosOrb().outcomes(DATA, without_count(item))
    assert len(result.components) == len(plain.components) == 2  # the two sides have room: prefix or suffix, 1/2 each
    for (share, part), (plain_share, plain_part) in zip(result.components, plain.components, strict=True):
        assert share == plain_share == Fraction(1, 2)
        assert part.pool == build_pool(DATA, part.retained, cut=Cut(60))
        assert part.pool != build_pool(DATA, part.retained)  # the cut bites at 60 strands
        assert plain_part.pool == build_pool(DATA, plain_part.retained)
        assert part.forced == plain_part.forced and DATA.mods[part.forced].domain == "veiled"  # not cut, not drawn: the placeholder
        assert part.forced in {entry.mod_id for entry in part.retained.mods}
        assert {entry.mod_id for entry in part.retained.mods} - {part.forced} == {entry.mod_id for entry in plain_part.retained.mods} - {plain_part.forced}
    assert dict(result.distribution(lambda mod: mod.id)) != dict(plain.distribution(lambda mod: mod.id))  # a cut pool draws other mods


def test_the_offer_cleared_by_the_veiled_chaos_orb_does_not_change_the_count():
    stranded = with_count(with_offer(), 25)

    result = VeiledChaosOrb().outcomes(DATA, stranded)

    assert isinstance(result, Spent) and result.before == 25
    assert all(part.retained.memory_strands == 25 and not part.retained.veil_offer for _, part in result.components)
    assert all(part.pool == build_pool(DATA, part.retained, cut=Cut(25)) for _, part in result.components)


# --- the Veiled Exalted Orb, the unveil and the pick: neither cut nor spend ------------------------------------------------


@pytest.mark.parametrize("strands", [1, 40, 100])
@pytest.mark.parametrize(
    ("action", "start"),
    [
        (VeiledExaltedOrb(), plain_rare), (Unveil(), with_placeholder), (Pick(1), with_offer), (Pick(3), with_offer),
    ],
    ids=["veiled-exalted", "unveil", "pick-1", "pick-3"],
)  # fmt: skip
def test_the_exalted_the_unveil_and_the_pick_spend_nothing_and_keep_the_count(action, start, strands):
    base = start()
    stranded = with_count(base, strands)

    result = action.outcomes(DATA, stranded)
    plain = action.outcomes(DATA, base)

    assert not isinstance(result, Spent)
    assert strands_after(result, strands) == {strands: ONE}
    assert [chance for chance, _ in result.results] == [chance for chance, _ in plain.results]
    assert all(item.memory_strands == strands for _, item in result.results)  # the count stays
    assert [without_count(item) for _, item in result.results] == [item for _, item in plain.results]  # and nothing else differs
    assert dict(result.distribution(lambda mod: mod.id)) == dict(plain.distribution(lambda mod: mod.id))
    assert result.sample(random.Random(3)).memory_strands == strands


def test_the_unveil_can_finish_on_a_stranded_item():
    item = with_count(with_placeholder(), 50)

    offered = random.Random(1)
    drawn = Unveil().outcomes(DATA, item).sample(offered)
    picked = Pick(1).outcomes(DATA, drawn).sample(offered)

    assert drawn.veil_offer and picked.memory_strands == 50
    assert not any(DATA.mods[entry.mod_id].domain == "veiled" for entry in picked.mods)


# --- the claims -----------------------------------------------------------------------------------------------------------


def test_each_declaration_cites_its_claims_and_the_claims_of_the_action_do_not_list_them():
    chaos = VeiledChaosOrb().strand_use(DATA)
    exalted = VeiledExaltedOrb().strand_use(DATA)

    assert isinstance(chaos, StrandUse) and chaos.cuts is True and chaos.spend == SpendLaw.uniform(80)
    assert chaos.claims == CHAOS_CLAIMS
    assert isinstance(exalted, StrandUse) and exalted.cuts is False and exalted.spend is None
    assert exalted.claims == {"memory_strands.not_spent_by", "memory_strands.cut_follows_spend_table"}
    for action in (Unveil(), Pick(1), Pick(2), Pick(3)):
        use = action.strand_use(DATA)
        assert isinstance(use, StrandUse) and use.cuts is False and use.spend is None
        assert use.claims == {"memory_strands.cut_follows_spend_table"}
    for action, use_claims in (
        (VeiledChaosOrb(), CHAOS_CLAIMS),
        (VeiledExaltedOrb(), {"memory_strands.not_spent_by", "memory_strands.cut_follows_spend_table"}),
        (Unveil(), {"memory_strands.cut_follows_spend_table"}),
        (Pick(2), {"memory_strands.cut_follows_spend_table"}),
    ):
        assert action.strand_claims(DATA) == use_claims
        assert not action.claims(DATA) & use_claims  # the strand claims are `strand_claims`, never `claims`
        assert action.claims(DATA)  # and the claims of the rules of the file stay
