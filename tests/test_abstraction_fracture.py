"""Layer 1 (ADR-0019) for the Fracturing Orb and for a fracture made in the middle of a route, on the fixture Thicket Bow (ticket #69).

The Fracturing Orb fractures one of all the mods of a rare item of 4 or more mods that is not influenced and holds no
fractured mod, uniformly: a junk mod, a wanted one, an ordinary crafted mod or a metamod (the fractured copy stays like any
fractured mod). Its kernel equals the brute force of `abstraction_metamod_oracle.py` from every start of the other tests
(with and without each metamod). Then each of the items it can leave is the start of a second action (Annulment, Exalted,
Chaos, a reforge, Scouring, a second fracture that the game refuses), and that kernel equals the brute force on that
concrete item too; a fractured metamod keeps its lock or its tag filter through the reroll. Two junk mods of one family type
that are fractured give one state, and the kernels of two steps composed equal the brute force of the two steps.
"""

from fractions import Fraction

import pytest
from abstraction_metamod_oracle import compose, fracture_one, rerolled, scoured, then
from abstraction_oracle import assert_same_distribution, compressed_distribution
from abstraction_removals_support import (
    AS_5,
    BLOCKING,
    COLD,
    COMBOS,
    FIRE,
    FIRE_RES,
    FRACTURING,
    HUNTER,
    METAMODS,
    SOCKET,
    abstraction,
    bow,
    check,
    check_or_refusal,
    passing,
    start_kinds,
    start_of,
)

from crafting_system.abstraction import Status
from crafting_system.actions import (
    AnnulmentOrb,
    ChaosOrb,
    ExaltedOrb,
    FracturingOrb,
    HarvestReforge,
    NotApplicableError,
    OutOfScopeError,
    ScouringOrb,
)

FRACTURE = FracturingOrb()
FOLLOW_UPS = {
    "annul": AnnulmentOrb(),
    "exalted": ExaltedOrb(),
    "chaos": ChaosOrb(),
    "fire": HarvestReforge("fire"),
    "scour": ScouringOrb(),
    "fracture": FRACTURE,  # the item has a fractured mod now: the game refuses
}


def cases():
    """(kind, meta, flag): every start with each metamod; an ordinary bow and one with the multimod run with the flag off and on."""
    for meta in [None, *METAMODS]:
        for kind in start_kinds(meta):
            for flag in (True,) if meta in BLOCKING else (False, True):
                yield pytest.param(kind, meta, flag, id=f"{meta or 'plain'}-{kind}-{'flag' if flag else 'noflag'}")


def route_cases():
    """The starts whose every fracture is followed by a second action: one kind per metamod, flag on."""
    for meta in [None, *METAMODS]:
        for kind in ("mixed", *(["crafted"] if meta in (None, "MM") else [])):
            yield pytest.param(kind, meta, id=f"{meta or 'plain'}-{kind}")


def fracturing(*, metamods: bool = True, **fields):
    return abstraction(actions=FRACTURING, metamods=metamods, **fields)


# --- layer 1: the Fracturing Orb -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("kind", "meta", "flag"), list(cases()))
def test_fracturing_equals_the_brute_force(kind, meta, flag):
    ab = fracturing(metamods=flag)

    kernel = check(ab, start_of(kind, meta), FRACTURE)

    assert all(len(after.fractured) == 1 for after in kernel)


@pytest.mark.parametrize("name", COMBOS)
def test_fracturing_equals_the_brute_force_with_several_metamods(name):
    check(fracturing(), bow(*COMBOS[name]), FRACTURE)


@pytest.mark.parametrize("flag", [False, True])
def test_a_wanted_mod_that_is_fractured_keeps_what_it_gives_the_goal(flag):
    ab = fracturing(metamods=flag)
    start = start_of("gem", None)  # the socketed-gem prefix and the tier 1 attack speed are wanted

    kernel = check(ab, start, FRACTURE)

    assert all(passing(after, 0) and passing(after, 3) for after in kernel)  # fractured or not, the item holds both
    wanted_fractured = [after for after in kernel if any(entry.contribution != (Status.ABSENT,) * 4 for entry in after.fractured)]
    assert sum(kernel[after] for after in wanted_fractured) == Fraction(2, 4)


def test_a_fractured_ordinary_crafted_mod_is_a_fractured_mod_of_the_state():
    ab = fracturing()

    kernel = check(ab, start_of("crafted", None), FRACTURE)

    no_crafted_slot = [after for after in kernel if not after.crafted]  # the craft is the fractured mod, so it is no slot
    assert len(no_crafted_slot) == 1 and kernel[no_crafted_slot[0]] == Fraction(1, 4)


@pytest.mark.parametrize("meta", ["PL", "SL", "NA", "NC", "MM"])
def test_a_fractured_metamod_is_a_fractured_mod_of_the_state(meta):
    ab = fracturing()

    kernel = check(ab, start_of("gem", meta), FRACTURE)

    no_crafted_slot = [after for after in kernel if not after.crafted]  # the metamod is the fractured mod, so it is no slot
    assert len(no_crafted_slot) == 1 and kernel[no_crafted_slot[0]] == Fraction(1, 5)


def test_two_junk_mods_of_one_family_type_that_are_fractured_make_one_state():
    ab = fracturing()
    start = bow(FIRE, COLD, SOCKET, AS_5)  # fire and cold damage: two Attack prefixes of one weight

    kernel = check(ab, start, FRACTURE)
    fire = ab.compress(bow(FIRE, COLD, SOCKET, AS_5, fractured=[FIRE]))
    cold = ab.compress(bow(FIRE, COLD, SOCKET, AS_5, fractured=[COLD]))

    assert fire == cold  # one state: a plain draw, Annulment or Scouring cannot tell them apart (a tagged reforge can: it is refused below)
    assert len(kernel) == 3 and kernel[fire] == Fraction(1, 2)


@pytest.mark.parametrize("flag", [False, True])
@pytest.mark.parametrize("tag", ["fire", "cold"])
def test_a_tagged_reforge_is_refused_when_the_fractured_mod_stands_for_a_family_type(flag, tag):
    ab = fracturing(metamods=flag)
    fire = bow(FIRE, COLD, SOCKET, AS_5, fractured=[FIRE])
    cold = bow(FIRE, COLD, SOCKET, AS_5, fractured=[COLD])
    reforge = HarvestReforge(tag)

    assert ab.compress(fire) == ab.compress(cold)  # one state for two items ...
    assert reforge.outcomes(ab.data, fire).chance_all([FIRE]) != reforge.outcomes(ab.data, cold).chance_all([FIRE])  # ... that the reforge tells apart
    with pytest.raises(OutOfScopeError):
        ab.kernel(ab.compress(fire), reforge)  # so the kernel, which cannot say which, refuses


@pytest.mark.parametrize("flag", [False, True])
def test_an_untagged_draw_after_the_same_fracture_is_exact(flag):
    ab = fracturing(metamods=flag)
    for fractured in (FIRE, COLD):
        for action in (ChaosOrb(), ExaltedOrb(), AnnulmentOrb(), ScouringOrb()):
            check_or_refusal(ab, bow(FIRE, COLD, SOCKET, AS_5, fractured=[fractured]), action)


def test_the_fracturing_orb_refuses_what_the_game_refuses():
    ab, influenced = fracturing(), fracturing(level=78)
    refused = [
        (ab, bow(FIRE, SOCKET, AS_5)),  # three mods
        (ab, bow(FIRE, SOCKET, AS_5, FIRE_RES, fractured=[FIRE_RES])),  # a fractured mod already
        (influenced, bow(FIRE, SOCKET, AS_5, FIRE_RES, influences=HUNTER, level=78)),  # an influence
    ]

    for one, start in refused:
        with pytest.raises(NotApplicableError):
            one.kernel(one.compress(start), FRACTURE)
        with pytest.raises(ValueError):
            fracture_one(one.data, start)


# --- a fracture in the middle of a route ------------------------------------------------------------------------------------


@pytest.mark.parametrize("action", FOLLOW_UPS.values(), ids=FOLLOW_UPS.keys())
@pytest.mark.parametrize(("kind", "meta"), list(route_cases()))
def test_every_item_a_fracture_can_leave_gives_the_kernel_of_the_brute_force_for_the_next_action(kind, meta, action):
    ab = fracturing()

    for after, _ in fracture_one(ab.data, start_of(kind, meta)):
        state = ab.compress(after)
        try:
            ab.kernel(state, action)
        except OutOfScopeError:  # a tagged reforge refuses a fractured mod that stands for a family type of several families
            assert isinstance(action, HarvestReforge) and any(entry.mod_id.startswith("~") for entry in state.fractured)
            continue
        except Exception:  # noqa: BLE001  (the game's own refusals are checked below)
            pass
        check_or_refusal(ab, after, action)


@pytest.mark.parametrize("meta", ["PL", "SL", "NA", "NC"])
@pytest.mark.parametrize("action", [ChaosOrb(), ScouringOrb(), AnnulmentOrb()], ids=["chaos", "scour", "annul"])
def test_a_metamod_fractured_by_the_orb_keeps_its_lock_or_filter_through_the_next_action(meta, action):
    ab = fracturing()
    start = start_of("mixed", meta)
    (fractured_meta,) = [
        after for after, _ in fracture_one(ab.data, start) if any(e.mod_id == METAMODS[meta] and e.fractured for e in after.mods)
    ]

    kernel = check_or_refusal(ab, fractured_meta, action)

    state = ab.compress(fractured_meta)
    assert len(state.fractured) == 1 and not state.crafted  # a fractured crafted mod is a fractured mod, not a crafted slot
    assert kernel or isinstance(action, AnnulmentOrb)
    if not isinstance(action, AnnulmentOrb):
        assert all(len(after.fractured) == 1 for after in kernel)  # the reroll and the scouring keep it


@pytest.mark.parametrize("second", [ChaosOrb(), ScouringOrb()], ids=["chaos", "scour"])
@pytest.mark.parametrize(("kind", "meta"), [("mixed", None), ("gem", "PL"), ("gem", "SL"), ("mixed", "NC"), ("crafted", "MM")])
def test_the_kernels_of_two_steps_composed_equal_the_brute_force_of_the_two_steps(kind, meta, second):
    ab = fracturing()
    start = start_of(kind, meta)
    step = (lambda item: rerolled(ab.data, item)) if isinstance(second, ChaosOrb) else (lambda item: scoured(ab.data, item))

    composed = compose(ab.kernel(ab.compress(start), FRACTURE), lambda state: ab.kernel(state, second))

    assert_same_distribution(composed, compressed_distribution(then(fracture_one(ab.data, start), step), ab.compress))
