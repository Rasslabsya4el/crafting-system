"""Layer 1 (ADR-0019) for the rerolls under the five metamods on the fixture Thicket Bow (ticket #69).

A Chaos Orb and a tagged Harvest reforge keep the fractured mods and every mod of a side that `Prefixes` or `Suffixes
Cannot Be Changed` locks, count them inside the total of 4, 5 or 6 mods and draw the rest; `Cannot roll Attack` and
`Caster Modifiers` filter the draws only when the reroll leaves the metamod on the item (a Chaos Orb), and the
guaranteed mod only on a reforge. Each kernel is compared with the brute force of `abstraction_metamod_oracle.py` on
concrete bows with each metamod, with two or three together, and with a fractured metamod; the state that holds a
lock gives a reroll that keeps the locked side. An `Abstraction` with `metamods=True` models all that; without the flag
an item that holds a lock or a tag metamod is out of scope, and an enabled action that adds one turns the flag on.
Where the game refuses a reforge (no tagged mod can come first) the kernel must refuse it too.
"""

from collections import Counter

import pytest
from abstraction_metamod_oracle import annulled, closure, crafted, exalted, rerolled
from abstraction_removals_support import (
    AS_5,
    BLOCKING,
    COMBOS,
    FIRE,
    FIRE_RES,
    METAMODS,
    NA,
    PL,
    SL,
    SOCKET,
    SOCKET_LEAF,
    TINY_DATA,
    abstraction,
    bow,
    build,
    check,
    check_or_refusal,
    start_kinds,
    start_of,
)

from crafting_system.abstraction import Goal
from crafting_system.actions import (
    ActionError,
    AnnulmentOrb,
    BenchCraft,
    ChaosOrb,
    ExaltedOrb,
    HarvestReforge,
    NotApplicableError,
    OutOfScopeError,
    ScouringOrb,
)
from crafting_system.items import Side

CHAOS, ANNUL, EXALT = ChaosOrb(), AnnulmentOrb(), ExaltedOrb()
FIRE_REFORGE, CASTER_REFORGE, ATTACK_REFORGE = HarvestReforge("fire"), HarvestReforge("caster"), HarvestReforge("attack")
REROLLS = {"chaos": CHAOS, "fire": FIRE_REFORGE, "caster": CASTER_REFORGE}
GOAL_SOCKET = Goal((SOCKET_LEAF,))


def cases():
    """(kind, meta, flag): every start with each metamod; an ordinary bow and one with the multimod run with the flag off and on."""
    for meta in [None, *METAMODS]:
        for kind in start_kinds(meta):
            for flag in (True,) if meta in BLOCKING else (False, True):
                yield pytest.param(kind, meta, flag, id=f"{meta or 'plain'}-{kind}-{'flag' if flag else 'noflag'}")


# --- layer 1: the rerolls ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("action", REROLLS.values(), ids=REROLLS.keys())
@pytest.mark.parametrize(("kind", "meta", "flag"), list(cases()))
def test_a_reroll_equals_the_brute_force(kind, meta, flag, action):
    ab = abstraction(metamods=flag)

    check_or_refusal(ab, start_of(kind, meta), action)


@pytest.mark.parametrize("action", REROLLS.values(), ids=REROLLS.keys())
@pytest.mark.parametrize(("kind", "meta", "flag"), list(cases()))
def test_a_reroll_keeps_a_fractured_mod_and_equals_the_brute_force(kind, meta, flag, action):
    ab = abstraction(metamods=flag)

    kernel = check_or_refusal(ab, start_of(kind, meta, fractured=[FIRE_RES]), action)

    assert all(len(after.fractured) >= 1 for after in kernel)


@pytest.mark.parametrize("action", REROLLS.values(), ids=REROLLS.keys())
@pytest.mark.parametrize("name", COMBOS)
def test_a_reroll_equals_the_brute_force_with_several_metamods(name, action):
    check_or_refusal(abstraction(metamods=True), bow(*COMBOS[name]), action)


@pytest.mark.parametrize("action", REROLLS.values(), ids=REROLLS.keys())
@pytest.mark.parametrize("meta", ["PL", "SL", "NA", "NC"])
def test_a_reroll_equals_the_brute_force_with_a_fractured_metamod(meta, action):
    # a fractured metamod stays through the reroll: a lock keeps its side, a tag metamod filters the draw
    ab = abstraction(metamods=True)

    check_or_refusal(ab, start_of("mixed", meta, fractured=[METAMODS[meta]]), action)


def test_a_chaos_orb_under_a_kept_attack_metamod_draws_no_attack_mod():
    ab = abstraction(metamods=True)
    start = bow(FIRE, SOCKET, AS_5, FIRE_RES, SL, NA)  # the suffix lock keeps all three suffixes, the Attack metamod among them

    kernel = check(ab, start, CHAOS)

    assert all(after.count(Side.SUFFIX) == 3 for after in kernel)  # kept: the attack speed, the resistance, the metamod
    assert len(kernel) == 3  # the prefixes drawn come from the socketed-gem and caster families only: either one, or both


def test_a_reforge_under_a_kept_attack_metamod_filters_its_first_mod_only():
    ab = abstraction(metamods=True)
    start = bow(FIRE, SOCKET, AS_5, FIRE_RES, SL, NA)

    check(ab, start, CASTER_REFORGE)  # the caster prefix first (no Attack tag), the rest from the whole pool
    with pytest.raises(NotApplicableError):
        ab.kernel(ab.compress(start), ATTACK_REFORGE)  # every Attack mod is blocked as the first mod


# --- a state that holds a lock gives a reroll that keeps the locked side ---------------------------------------------------


@pytest.mark.parametrize(("meta", "side"), [("PL", Side.PREFIX), ("SL", Side.SUFFIX)])
@pytest.mark.parametrize("action", REROLLS.values(), ids=REROLLS.keys())
def test_a_state_with_a_lock_gives_a_reroll_that_keeps_the_locked_side(meta, side, action):
    ab = abstraction(metamods=True)
    start = start_of("gem", meta)
    locked = Counter(slot for slot in ab.compress(start).slots if slot.side is side)

    kernel = check_or_refusal(ab, start, action)

    assert sum(locked.values()) == 2
    for after in kernel:
        assert locked <= Counter(after.slots)  # each kept mod of the locked side is still there
        assert not after.crafted  # the metamod sits on the other side and goes with the reroll
        assert 4 <= len(after.slots) + len(after.fractured) <= 6


@pytest.mark.parametrize("action", [CHAOS, ScouringOrb()], ids=["chaos", "scouring"])
def test_a_state_with_both_locks_is_not_changed_by_a_reroll_or_a_scouring(action):
    ab = abstraction(metamods=True)
    start = bow(FIRE, SOCKET, AS_5, FIRE_RES, PL, SL)

    kernel = check(ab, start, action)

    assert kernel == {ab.compress(start): 1}


def test_without_a_lock_a_reroll_takes_the_metamod_with_the_rest():
    ab = abstraction(metamods=True)

    kernel = check(ab, start_of("gem", "NA"), CHAOS)

    assert not any(after.crafted for after in kernel)


# --- the flag ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("meta", BLOCKING)
def test_an_item_with_a_blocking_metamod_is_out_of_scope_without_the_flag(meta):
    ab = abstraction(metamods=False)

    with pytest.raises(OutOfScopeError, match="metamods"):
        ab.compress(start_of("gem", meta))


def test_the_multimod_needs_no_flag_it_is_a_bench_limit_only():
    ab = abstraction(metamods=False)

    state = ab.compress(start_of("gem", "MM"))

    assert state.crafted
    check(ab, start_of("gem", "MM"), CHAOS)


@pytest.mark.parametrize("meta", BLOCKING)
def test_an_enabled_action_that_adds_a_blocking_metamod_turns_the_flag_on(meta):
    ab = abstraction(GOAL_SOCKET, (BenchCraft(METAMODS[meta]),), metamods=False)

    state = ab.compress(start_of("gem", meta))

    assert state.crafted
    check(ab, start_of("gem", meta), CHAOS)


def test_the_flag_changes_no_probability_for_a_bow_without_a_metamod():
    plain, flagged = abstraction(metamods=False), abstraction(metamods=True)
    start = start_of("gem", None)

    assert sorted(plain.kernel(plain.compress(start), CHAOS).values()) == sorted(flagged.kernel(flagged.compress(start), CHAOS).values())


# --- the reachable states of a route with a lock craft --------------------------------------------------------------


def test_the_closure_of_a_route_with_a_lock_craft_a_reroll_and_removals_equals_the_compressed_concrete_closure():
    actions = (BenchCraft(PL), ANNUL, EXALT)
    ab = abstraction(GOAL_SOCKET, actions, data=TINY_DATA)
    start = build(TINY_DATA, ab.base_id, (FIRE, SOCKET, AS_5, FIRE_RES))
    steps = [
        lambda item: crafted(TINY_DATA, item, PL),
        lambda item: rerolled(TINY_DATA, item),
        lambda item: annulled(TINY_DATA, item),
        lambda item: exalted(TINY_DATA, item),
    ]

    reached = ab.reachable([ab.compress(start)], (*actions, CHAOS))

    assert reached == {ab.compress(item) for item in closure(start, steps)}
    for state in reached:
        for action in (*actions, CHAOS):
            try:
                assert sum(ab.kernel(state, action).values()) == 1
            except ActionError:
                pass
