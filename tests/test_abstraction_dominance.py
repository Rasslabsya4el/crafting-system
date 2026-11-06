"""The influence crafts in the compressed state: influenced mods told apart, Elevated tiers (ticket #155, ADR-0030, ADR-0019).

The data is the Contract Helmet of `influence_support.py` cut down to the influence mods and a few ordinary ones, plus a family that holds ordinary and
influence mods together (the real data has 268 such families of 358 with an influence mod), an Elevated mod of it, and a mod that is ordinary until the
item gets the Elder influence.

* layer 1 (ADR-0019): for every concrete item that the Orb of Dominance, the influenced Exalted Orbs, the beast recipes and the Awakener's Orb reach from
  several starts, the kernel of the item's state equals the finished items of the action on it, compressed one by one and added up exactly
  (`abstraction_b2_support.check_layer_1`), for goals that name influence mods, their Elevated versions and a tier of a mixed family;
* the Elevated tier: a top-tier mod becomes its Elevated version in the state, an Elevated mod stays one, and a requirement of the best tier is met by it;
* what the state holds: an influence mod is the kind `$<mod id>` (also when its family holds ordinary mods), an ordinary mod of that family is not, and an
  item with no influence has the states it had;
* a mod that becomes an influence mod when the item gets an influence is read again by the kept slot (`Abstraction._reread`).
"""

import dataclasses

import pytest
from abstraction_b2_support import check_layer_1, closure, real_graph
from influence_support import (
    ELDER_P,
    ELDER_P_MAVEN,
    ELDER_S,
    ELDER_S_MAVEN,
    ELEVATED,
    HELMET,
    HUNTER_S,
    INFLUENCE_DATA,
    OLD,
    P1,
    P2,
    P3,
    P3_MAVEN,
    PLAIN,
    S1,
    S2,
    S2_MAVEN,
    helmet,
    roll,
)

from crafting_system.abstraction import Abstraction, Goal, Status, Wanted
from crafting_system.actions import (
    AnnulmentOrb,
    AwakenersOrb,
    BeastInfluenceRecipe,
    InfluencedExaltedOrb,
    NotApplicableError,
    OrbOfDominance,
    OutOfScopeError,
)
from crafting_system.data import Weight
from crafting_system.items import Influence, Rarity

SHAPER, ELDER = Influence.SHAPER, Influence.ELDER
LEVEL = 84
LOCK_SUFFIXES = "DexMasterItemGenerationCannotChangeSuffixes"  # a crafted prefix: the suffixes cannot be changed
LOCK_PREFIXES = "StrMasterItemGenerationCannotChangePrefixes"  # a crafted suffix: the prefixes cannot be changed

# a prefix family with an ordinary mod and two Shaper mods, as the real data has them; the Elevated version of its best Shaper mod
MIXED = "ContractHelmetMixed"
MIX_O, MIX_S1, MIX_S2, MIX_S2_MAVEN = "ContractHelmetMixedO1", "ContractHelmetMixedS1", "ContractHelmetMixedS2", "ContractHelmetMixedS2Maven"
ODD = "ContractHelmetOdd1"  # a suffix with the Elder tag before the default one: ordinary on a plain item, an Elder mod (weight 0) once the item is Elder
ELEVATED_ALL = (*ELEVATED, (MIX_S2, MIX_S2_MAVEN))


def build_data():
    base = INFLUENCE_DATA.mods
    template, suffix_template = base[PLAIN], base[S1]

    def prefix(mod_id, level, weights):
        return dataclasses.replace(
            template, id=mod_id, name="Mixed", type=MIXED, families=(MIXED,), required_level=level, spawn_weights=weights, generation_weights=()
        )

    mods = {
        MIX_O: prefix(MIX_O, 1, (Weight("helmet", 1000), Weight("default", 0))),
        MIX_S1: prefix(MIX_S1, 68, (Weight("helmet_shaper", 300), Weight("default", 0))),
        MIX_S2: prefix(MIX_S2, 80, (Weight("helmet_shaper", 200), Weight("default", 0))),
    }
    mods[MIX_S2_MAVEN] = dataclasses.replace(
        mods[MIX_S2], id=MIX_S2_MAVEN, name="Elevated Mixed", type=MIXED + "Maven", required_level=90, spawn_weights=(Weight("helmet_shaper", 0), Weight("default", 0))
    )
    mods[ODD] = dataclasses.replace(
        suffix_template, id=ODD, name="Odd", type="ContractHelmetOdd", families=("ContractHelmetOdd",), required_level=1,
        spawn_weights=(Weight("helmet_elder", 0), Weight("default", 800)), generation_weights=(),
    )
    keep = {
        PLAIN, P1, P2, P3, S1, S2, OLD, ELDER_S, ELDER_P, HUNTER_S, P3_MAVEN, S2_MAVEN, ELDER_S_MAVEN, ELDER_P_MAVEN, LOCK_SUFFIXES, LOCK_PREFIXES,
    }
    return dataclasses.replace(INFLUENCE_DATA, mods={**{mod_id: base[mod_id] for mod_id in keep}, **mods})


DATA = build_data()
DOMINANCE = OrbOfDominance(elevated=ELEVATED_ALL)
EXALTED = (InfluencedExaltedOrb(SHAPER), InfluencedExaltedOrb(ELDER))
RECIPES = (BeastInfluenceRecipe(SHAPER), BeastInfluenceRecipe(ELDER))
AWAKENERS = (AwakenersOrb(HELMET, LEVEL, ELDER, ELDER_S), AwakenersOrb(HELMET, LEVEL, SHAPER, P3))

TOP_PREFIX = Wanted(frozenset({P3, P3_MAVEN}))  # the best Shaper prefix, or the Elevated one
SHAPER_SUFFIX = Wanted(frozenset({S2, S2_MAVEN}))
ELDER_SUFFIX = Wanted(frozenset({ELDER_S, ELDER_S_MAVEN}))
# tier 1 of the mixed family: the best Shaper mod. Its Elevated version has no natural tier (OR-1), so a tier leaf does not count it.
MIXED_BEST = Wanted(frozenset({MIX_S1, MIX_S2, MIX_S2_MAVEN}), min_tier=1, tier_ok=frozenset({MIX_S2}))
GOAL = Goal((TOP_PREFIX, SHAPER_SUFFIX, ELDER_SUFFIX, MIXED_BEST))


def rolled(mod_id: str, tier: int | None = None, **flags):
    """A mod at the tier of its table (that of the item's influences: the tests below give each item the tier it has there)."""
    return roll(mod_id, tier, DATA, **flags)


def item(*mods, influences=(), rarity=Rarity.RARE, **fields):
    return helmet(*mods, level=LEVEL, rarity=rarity, data=DATA, influences=frozenset(influences), **fields)


def ability(actions, goal=GOAL, **options) -> Abstraction:
    return Abstraction(DATA, goal, HELMET, LEVEL, actions, **options)


def starts() -> dict:
    return {
        "two_shaper": item(rolled(P1, 3), rolled(S1, 2), influences={SHAPER}),
        "three": item(rolled(P2, 2), rolled(S1, 2), rolled(ELDER_S, 1), influences={SHAPER, ELDER}),
        "top_and_elevated": item(rolled(P3, 1), rolled(S2_MAVEN, 1), rolled(PLAIN, 1), influences={SHAPER}),
        "mixed_both": item(rolled(MIX_O, 3), rolled(S1, 2), rolled(P1, 3), influences={SHAPER}),
        "mixed_shaper": item(rolled(MIX_S1, 2), rolled(S1, 2), rolled(PLAIN, 1), influences={SHAPER}),
        "mixed_top": item(rolled(MIX_S2, 1), rolled(S1, 2), rolled(ELDER_S, 1), influences={SHAPER, ELDER}),
        "plain": item(rolled(PLAIN, 1), rolled(MIX_O, 3)),
        "elder_one": item(rolled(PLAIN, 1), rolled(ELDER_P, 1), influences={ELDER}),
        "odd": item(rolled(ODD, 1), rolled(PLAIN, 1)),
        "magic": item(rolled(P1, 3), rolled(S1, 2), influences={SHAPER}, rarity=Rarity.MAGIC),
    }


def starts_with_locks() -> dict:
    return {
        "lock_on_suffixes": item(rolled(P1, 3), rolled(S1, 2), rolled(ELDER_S, 1), rolled(LOCK_SUFFIXES, 1, crafted=True), influences={SHAPER, ELDER}),
        "lock_on_prefixes": item(rolled(P2, 2), rolled(ELDER_P, 1), rolled(S1, 2), rolled(LOCK_PREFIXES, 1, crafted=True), influences={SHAPER, ELDER}),
    }


def sweep(found: Abstraction, items, actions) -> dict:
    applied = {action: 0 for action in actions}
    for held in items:
        for action in actions:
            applied[action] += check_layer_1(found, DATA, held, action)
    return applied


# --- layer 1 -------------------------------------------------------------------------------------------------------------


def test_layer_1_of_the_orb_of_dominance_on_every_item_it_and_an_annulment_reach():
    actions = (DOMINANCE, AnnulmentOrb())
    found = ability(actions)
    items = closure(DATA, starts().values(), actions, limit=200)
    applied = sweep(found, items, actions)
    assert all(applied.values()), applied
    assert any(S2_MAVEN in {m.mod_id for m in held.mods} or P3_MAVEN in {m.mod_id for m in held.mods} for held in items)
    assert any(MIX_S2_MAVEN in {m.mod_id for m in held.mods} for held in items)  # the mixed family's Shaper mods are upgraded too


def test_layer_1_of_the_orb_of_dominance_beside_a_lock():
    actions = (DOMINANCE, AnnulmentOrb())
    found = ability(actions, metamods=True)
    items = closure(DATA, starts_with_locks().values(), actions, limit=120)
    applied = sweep(found, items, actions)
    assert all(applied.values()), applied
    assert any(any(m.crafted for m in held.mods) for held in items)  # the locks stay on the items


def test_layer_1_of_every_influence_craft_together():
    actions = (DOMINANCE, *EXALTED, *RECIPES, *AWAKENERS)
    found = ability(actions)
    assert found.tells_influenced
    items = closure(DATA, starts().values(), actions, limit=150)
    applied = sweep(found, items, actions)
    assert all(applied.values()), applied
    assert any(len(held.influences) == 2 for held in items)  # the Awakener's Orb and the orbs reach items of two influences


@pytest.mark.parametrize("goal", [Goal((TOP_PREFIX,)), Goal((MIXED_BEST, ELDER_SUFFIX)), Goal((Wanted(frozenset({P1, P2, P3, P3_MAVEN}), min_tier=2, tier_ok=frozenset({P2, P3})),))], ids=["one", "mixed_tier", "tier_two"])
def test_layer_1_for_other_goals(goal):
    actions = (DOMINANCE, *EXALTED, RECIPES[0])
    found = ability(actions, goal)
    items = closure(DATA, starts().values(), actions, limit=100)
    applied = sweep(found, items, actions)
    assert all(applied.values()), applied


# --- the Elevated tier ---------------------------------------------------------------------------------------------------


def test_a_top_tier_mod_becomes_its_elevated_version_and_that_no_longer_meets_a_tier_leaf():
    found = ability((DOMINANCE,), Goal((MIXED_BEST,)))
    start = found.compress(item(rolled(MIX_S2, 1), rolled(S1, 2), influences={SHAPER}))
    assert start.status == (Status.PASSING,)
    after = found.kernel(start, DOMINANCE)  # removed S1 and upgraded the mixed top mod, or the other way round
    assert sorted(float(chance) for chance in after.values()) == [0.5, 0.5]
    elevated = [state for state in after if any(slot.kind == f"${MIX_S2_MAVEN}" for slot in state.slots)]
    assert len(elevated) == 1 and elevated[0].status == (Status.BELOW,)  # an Elevated mod has no natural tier: it meets a tier leaf only by `mod:`
    named = ability((DOMINANCE,), Goal((Wanted(frozenset({MIX_S2_MAVEN})),)))  # `mod:` names it: no tier is asked
    assert [state.status for state in named.kernel(named.compress(item(rolled(MIX_S2, 1), rolled(S1, 2), influences={SHAPER})), DOMINANCE)
            if any(slot.kind == f"${MIX_S2_MAVEN}" for slot in state.slots)] == [(Status.PASSING,)]
    # an Elevated mod is upgraded to itself: the pick is still uniform and the state does not change
    held = found.compress(item(rolled(MIX_S2_MAVEN, 1), rolled(S1, 2), influences={SHAPER}))
    assert f"${MIX_S2_MAVEN}" in {slot.kind for slot in held.slots}
    again = found.kernel(held, DOMINANCE)  # S1 removed and the Elevated mod stays, or the Elevated mod removed and S1 upgraded to S2
    assert {tuple(slot.kind for slot in state.slots) for state in again} == {(f"${MIX_S2_MAVEN}",), (f"${S2}",)}


def test_the_elevated_tier_is_the_same_in_the_item_the_orb_makes_and_in_the_state_that_rebuilds_it():
    found = ability((DOMINANCE,), Goal((Wanted(frozenset({P3_MAVEN})),)))  # the Elevated mod named, no tier asked
    start = item(rolled(P3, 1), rolled(S1, 2), influences={SHAPER})
    for chance, result in DOMINANCE.outcomes(DATA, start).results:
        state = found.compress(result)
        rebuilt, _ = found._item_of(state, False)
        assert {m.mod_id: m.tier for m in rebuilt.mods} == {m.mod_id: m.tier for m in result.mods}
        assert found.compress(rebuilt) == state
    assert found.kernel(found.compress(start), DOMINANCE)  # a state that holds the Elevated mod exists
    assert {state.status for state in found.kernel(found.compress(start), DOMINANCE)} == {(Status.ABSENT,), (Status.PASSING,)}


def test_a_roll_limit_on_an_elevated_mod_is_refused_where_dominance_may_pick_it():
    """An Elevated mod that is picked has its values rolled afresh, which the state cannot hold: under a roll limit the kernel refuses, as for an Awakener's kept mod."""
    held = item(rolled(S2_MAVEN, 1), rolled(P1, 3), influences={SHAPER})
    limited = ability((DOMINANCE,), Goal((Wanted(frozenset({S2_MAVEN}), min_roll=(11,)),)))
    with pytest.raises(OutOfScopeError, match="roll"):
        limited.kernel(limited.compress(held), DOMINANCE)
    no_elevated = item(rolled(S2, 1), rolled(P1, 3), influences={SHAPER})
    with pytest.raises(OutOfScopeError, match="new mod"):  # the Elevated mod the orb puts on the item is a fixed-result new mod: refused as any
        limited.kernel(limited.compress(no_elevated), DOMINANCE)
    plain = ability((DOMINANCE,), Goal((Wanted(frozenset({S2_MAVEN})),)))
    assert plain.kernel(plain.compress(held), DOMINANCE)


# --- what the state holds ------------------------------------------------------------------------------------------------


def test_an_influence_mod_is_a_kind_of_its_own_and_an_ordinary_mod_of_its_family_is_not():
    found = ability((DOMINANCE,))
    state = found.compress(starts()["mixed_both"])
    kinds = sorted(slot.kind for slot in state.slots)
    assert kinds == sorted(["", f"${S1}", f"${P1}"])  # the ordinary mod of the mixed family is alike with any ordinary mod; the two influence mods are named
    other = found.compress(item(rolled(MIX_S1, 2), rolled(S1, 2), rolled(P1, 3), influences={SHAPER}))
    assert sorted(slot.kind for slot in other.slots) == sorted([f"${MIX_S1}", f"${S1}", f"${P1}"])
    assert state != other
    rebuilt, _ = found._item_of(state, False)
    assert sorted(m.mod_id for m in rebuilt.mods) == sorted([PLAIN, S1, P1])  # the representative of the ordinary slot is an ordinary mod, not a Shaper one
    assert found.compress(rebuilt) == state


def test_an_item_with_no_influence_has_no_influence_mod_and_the_states_it_had():
    with_reader, without = ability((DOMINANCE,)), ability((AnnulmentOrb(),))
    plain = starts()["plain"]
    assert not any(slot.kind.startswith("$") for slot in with_reader.compress(plain).slots)
    assert with_reader.compress(plain).flags == without.compress(plain).flags
    # a model with only the orbs that put influence mods on an item names none of them
    only_makers = ability((*EXALTED, *RECIPES))
    assert not only_makers.tells_influenced
    assert not any(slot.kind.startswith("$") for slot in only_makers.compress(starts()["two_shaper"]).slots)


def test_dominance_alone_counts_the_ordinary_mods_by_side_only():
    found = ability((DOMINANCE,))
    one = found.compress(item(rolled(P1, 3), rolled(S1, 2), rolled(PLAIN, 1), influences={SHAPER}))
    two = found.compress(item(rolled(P1, 3), rolled(S1, 2), rolled(MIX_O, 3), influences={SHAPER}))
    assert one == two


def test_the_orb_is_refused_where_the_game_refuses_it():
    found = ability((DOMINANCE,))
    for name in ("plain", "elder_one", "odd"):
        with pytest.raises(NotApplicableError):
            DOMINANCE.outcomes(DATA, starts()[name])
        with pytest.raises(NotApplicableError):
            found.kernel(found.compress(starts()[name]), DOMINANCE)


# --- a mod that becomes an influence mod with the item's next influence ----------------------------------------------------------


def test_a_kept_mod_that_the_new_influence_makes_an_influence_mod_is_read_again():
    """The Odd suffix has the Elder tag before the default one: ordinary on this plain item, an influence mod (no tier: weight 0) once an Elder orb has run.

    The Elder orb keeps it, so its slot must be the kind `$` of the result's context or the state is not the one of the item (layer 1 above does not
    reach this item from its starts except through the orb, so it is asserted here too).
    """
    actions = (InfluencedExaltedOrb(ELDER), DOMINANCE)
    found = ability(actions)
    start = starts()["odd"]
    assert not any(slot.kind.startswith("$") for slot in found.compress(start).slots)  # ordinary while the item has no influence
    kernel = found.kernel(found.compress(start), actions[0])
    assert kernel and all(f"${ODD}" in {slot.kind for slot in state.slots} for state in kernel)
    items = closure(DATA, [start], actions, limit=60)
    for held in items:
        for action in actions:
            check_layer_1(found, DATA, held, action)
    after_orb = [held for held in items if ELDER in held.influences]
    assert after_orb
    with pytest.raises(OutOfScopeError):  # Odd is an Elder mod of no tier now: the orb cannot name its upgrade, for the item and for the state alike
        DOMINANCE.outcomes(DATA, after_orb[0])
    with pytest.raises(OutOfScopeError):
        found.kernel(found.compress(after_orb[0]), DOMINANCE)


# --- the graph -------------------------------------------------------------------------------------------------------------


def test_the_pilot_count_of_a_model_with_dominance_equals_the_graph_the_kernels_make():
    actions = (DOMINANCE, AnnulmentOrb(), InfluencedExaltedOrb(ELDER))
    found = ability(actions)
    start = found.compress(starts()["three"])
    seen, transitions = real_graph(found, [start], actions)
    pilot = found.estimate([start], actions)
    assert (pilot.states, pilot.transitions) == (len(seen), transitions) and pilot.states > 5
