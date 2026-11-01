"""The Awakener's Orb on the real 3.29.3.3 dump: R18's Assassin's Mark mod, looked up and its mod group recorded (ticket #213).

R18 (a Crusader %ES ring and a Shaper ring that holds only the Assassin's Mark influence mod) was written for 3.13, and its
note says the Assassin's Mark text may differ from the current mod pool. This reads the pool: the mods of the Shaper ring with
that text, their mod group, and what the orb does with them. The tests need the cached dump and skip cleanly when it is not
there (CI fetches it, ticket #165).
"""

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import AwakenersOrb, Reading, catalog
from crafting_system.items import ExplicitMod, Influence, Item, Rarity

RING = "Metadata/Items/Rings/Ring15"  # an Unset Ring
LEVEL = 84
CONFLICT = "awakener.group_conflict"

CRUSADER_ES = "GlobalEnergyShieldPercentInfluence3"  # (13-15)% increased maximum Energy Shield, the T1 Crusader prefix of a ring
CRUSADER_CONDUCTIVITY = "CurseOnHitConductivityInfluence2___"
ASSASSINS_MARK_12 = {"CurseOnHitAssassinsMarkUber2", "CurseOnHitAssassinsMarkNewUber2"}  # "Trigger Level 12 Assassin's Mark ..."
ASSASSINS_MARK_8 = {"CurseOnHitAssassinsMarkUber1", "CurseOnHitAssassinsMarkNewUber1"}
MARK_GROUP = ("CurseOnHitLevel",)


@pytest.fixture(scope="module")
def real():
    return real_game_data()


def ring(real, *mod_ids: str, influence: Influence) -> Item:
    mods = tuple(ExplicitMod(mod_id, 1, tuple(min(stat.min, stat.max) for stat in real.mods[mod_id].stats)) for mod_id in mod_ids)
    return Item.build(real, base_id=RING, item_level=LEVEL, rarity=Rarity.RARE, mods=mods, influences=frozenset({influence}))


def shaper_marks(real):
    """The mods of a Shaper ring whose text is an Assassin's Mark trigger: found by their text and the Shaper ring tag."""
    return {
        mod.id: mod
        for mod in real.mods.values()
        if mod.domain == "item"
        and mod.generation_type == "suffix"
        and "Assassin's Mark" in (mod.text or "")
        and any(entry.tag == "ring_shaper" for entry in mod.spawn_weights)
    }


def test_the_assassins_mark_mods_of_a_shaper_ring_are_four_and_share_the_mod_group_curse_on_hit_level(real):
    marks = shaper_marks(real)
    assert set(marks) == ASSASSINS_MARK_12 | ASSASSINS_MARK_8
    for mod in marks.values():
        assert mod.families == MARK_GROUP  # the mod group, recorded
        assert [(entry.tag, entry.weight) for entry in mod.spawn_weights][0] == ("ring_shaper", 0)  # an influence mod that no draw gives
    assert {mod.id for mod in marks.values() if mod.text.startswith("Trigger Level 12 Assassin's Mark")} == ASSASSINS_MARK_12
    assert {mod.required_level for mod in marks.values() if mod.id in ASSASSINS_MARK_12} == {80}
    assert {mod.type for mod in marks.values()} == {"CurseOnHitCriticalWeakness", "TriggerOnRareAssassinsMark"}


def test_every_curse_on_hit_influence_mod_of_a_ring_is_of_that_mod_group(real):
    for mod in real.mods.values():
        if mod.id.startswith("CurseOnHit") and any(entry.tag.startswith("ring_") and entry.tag != "ring" for entry in mod.spawn_weights):
            assert mod.families == MARK_GROUP, mod.id  # Conductivity (Crusader), Flammability (Warlord) and the marks all conflict


def test_a_shaper_donor_can_hold_the_assassins_mark_mod_and_the_orb_is_offered_for_it(real):
    receiver = ring(real, CRUSADER_ES, influence=Influence.CRUSADER)
    offered = {
        action.donor_mod
        for action in catalog(real, receiver)
        if isinstance(action, AwakenersOrb) and action.donor_influence is Influence.SHAPER
    }
    assert ASSASSINS_MARK_12 | ASSASSINS_MARK_8 <= offered
    action = AwakenersOrb(RING, LEVEL, Influence.SHAPER, "CurseOnHitAssassinsMarkNewUber2")
    assert action.label(real) == "Awakener's Orb with a shaper donor of Trigger Level 12 Assassin's Mark when you Hit a Rare or Unique Enemy and have no Mark"
    (need,) = action.inputs(real, receiver)
    assert [entry.mod_id for entry in need.want.mods] == ["CurseOnHitAssassinsMarkNewUber2"] and need.want.influences == {Influence.SHAPER}


def test_r18_carries_both_wanted_mods_over_and_the_readings_agree_because_the_groups_differ(real):
    receiver = ring(real, CRUSADER_ES, influence=Influence.CRUSADER)  # exactly one influenced mod, as R18 asks of each input
    for donor_mod in sorted(ASSASSINS_MARK_12):
        action = AwakenersOrb(RING, LEVEL, Influence.SHAPER, donor_mod)
        results = [action.outcomes_under(real, receiver, Reading.of({CONFLICT: name})) for name in ("receiver", "donor")]
        for outcomes in results:
            ((share, part),) = outcomes.components
            assert share == 1 and {entry.mod_id for entry in part.retained.mods} == {CRUSADER_ES, donor_mod}
            assert part.retained.influences == {Influence.CRUSADER, Influence.SHAPER} and part.retained.rarity is Rarity.RARE
            assert outcomes.chance_all([CRUSADER_ES, donor_mod]) == 1
        assert [ [e.mod_id for e in part.retained.mods] for _, part in results[0].components] == [
            [e.mod_id for e in part.retained.mods] for _, part in results[1].components
        ]


def test_a_receiver_that_holds_a_curse_on_hit_mod_meets_the_mark_in_a_group_conflict(real):
    receiver = ring(real, CRUSADER_CONDUCTIVITY, influence=Influence.CRUSADER)
    action = AwakenersOrb(RING, LEVEL, Influence.SHAPER, "CurseOnHitAssassinsMarkNewUber2")
    kept = {}
    for name in ("receiver", "donor"):
        ((_, part),) = action.outcomes_under(real, receiver, Reading.of({CONFLICT: name})).components
        kept[name] = [entry.mod_id for entry in part.retained.mods]
        assert part.retained.influences == {Influence.CRUSADER, Influence.SHAPER}  # the donor's influence comes over either way
    assert kept == {"receiver": [CRUSADER_CONDUCTIVITY], "donor": ["CurseOnHitAssassinsMarkNewUber2"]}
