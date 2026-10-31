"""Equal kernels at a state: only the cheapest offer stays, and the plan does not change (ticket #118, piece B).

`Abstraction.kernel_key(state, a) == kernel_key(state, b)` must imply `kernel(state, a) == kernel(state, b)`
exactly; the converse is not required. `cli._prune.solver_actions` keeps, of the offers with one key at a
state, the cheapest (the earliest on a tie). Exact means the optimal values and the policy are those of the
plan without the merge: the fixture R12 plan has numbers written from the run before the change, and R10 on
the real dump (it skips without the cache) is planned twice, with and without the merge, and compared.
"""

import dataclasses
from collections import Counter, defaultdict
from pathlib import Path

import pytest
import test_abstraction_b1 as belt_world
import test_abstraction_fossil as fossil_world
from abstraction_support import real_game_data
from cli_support import LIFEFORCE, R12, price_file
from targets_support import DATA

from crafting_system.abstraction import Abstraction, Goal
from crafting_system.abstraction import _kernel as kernel_module
from crafting_system.actions import (
    ActionError,
    ApplyFossils,
    ChaosOrb,
    HarvestReforge,
    NotApplicableError,
    RemoveCraftedMods,
    catalog,
)
from crafting_system.cli import Offer, _plan, default_offers, make_plan
from crafting_system.cli._offers import price_offers
from crafting_system.cli._prune import solver_actions
from crafting_system.prices import PriceEntry, load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
R10 = ROOT / "examples" / "targets" / "r10-fractured-boots.yaml"

# --- the property, on two fixture worlds -------------------------------------------------------------
#
# The fossil boots: a Chaos Orb and every kind of resonator (mixtures, the Fractured Fossil), with
# fractured mods on the item. The fixture belt: bench crafts, a crafted slot, essences, fractured mods.


def _fossil_world(tracked: bool):
    sets = [*fossil_world.SETS, *fossil_world.FRACTURING, ("Gloveless",), ("Dull",)]
    if tracked:  # the states multiply with the junk kept: a few sets of each shape
        sets = [("Gloveless",), ("Dull",), ("Scorched",), ("Tangled",), ("Hollow",), ("Fractured", "Hollow"), ("Fractured", "Glyphic")]
    actions = [ChaosOrb(), *(fossil_world.fossils(*names) for names in sets)]
    enabled = []
    if tracked:  # an enabled action that reads the junk makes the state keep the ordinary mods
        enabled = [RemoveCraftedMods()]
        actions.append(RemoveCraftedMods())
    boots, roll = fossil_world.boots, fossil_world.roll
    starts = [
        boots(),
        boots(roll("CasterA", fractured=True), roll("LifeA")),
        boots(roll("CasterA", fractured=True), roll("FireB", fractured=True), roll("BareA")),
        boots(roll("CasterA"), roll("LifeA"), roll("FireResA")),
    ]
    ab = Abstraction(fossil_world.DATA, fossil_world.GOAL, fossil_world.BOOTS, fossil_world.LEVEL, enabled)
    return ab, actions, [ab.compress(item) for item in starts]


def _belt_world():
    belt, roll, data = belt_world.belt, belt_world.roll, belt_world.DATA
    starts = [
        belt(),
        belt(roll(belt_world.FIRE, fractured=True), roll(belt_world.LIFE), roll(belt_world.REGEN)),
        belt_world.crafted_damage(belt(roll(belt_world.LIFE))),
        belt(roll(belt_world.LIGHTNING, fractured=True), roll(belt_world.LIFE_3), roll(belt_world.COLD)),
    ]
    found = {}
    for start in starts:
        for action in catalog(data, start):
            if action in belt_world.CRAFTS or not action.reads(data).junk:  # the others are not enabled here
                found.setdefault(action)
    actions = list(dict.fromkeys([*found, *belt_world.CRAFTS]))
    ab = belt_world.abstraction(belt_world.LIFE_LEAF, belt_world.COLD_LEAF)
    return ab, actions, [ab.compress(item) for item in starts]


WORLDS = {
    "fossil-junk-erased": lambda: _fossil_world(False),
    "fossil-junk-kept": lambda: _fossil_world(True),
    "belt": _belt_world,
}


def _outcome_of(call):
    try:
        return "ok", call()
    except ActionError as problem:
        return type(problem), None


def _spread(ab, actions, starts, limit=40):
    """The starts and, breadth first, the states one action takes from them, up to `limit` states."""
    states = list(dict.fromkeys(starts))
    seen = set(states)
    for state in states:
        for action in actions:
            if len(states) >= limit:
                return states
            if _outcome_of(lambda: ab.kernel(state, action))[0] != "ok":
                continue
            for successor in sorted(ab.kernel(state, action), key=repr):
                if successor not in seen and len(states) < limit:
                    seen.add(successor)
                    states.append(successor)
    return states


@pytest.fixture(scope="module", params=list(WORLDS))
def world(request):
    """(world name, abstraction, a spread of reachable states, (state, action, key, kernel) of every action that applies there)."""
    ab, actions, starts = WORLDS[request.param]()
    states = _spread(ab, actions, starts)
    found = []
    for state in states:
        for action in actions:
            keyed = _outcome_of(lambda: ab.kernel_key(state, action))
            kernel = _outcome_of(lambda: dict(ab.kernel(state, action)))
            assert keyed[0] == kernel[0], f"kernel_key and kernel disagree on {action!r} at {state!r}"
            if keyed[0] == "ok":
                found.append((state, action, keyed[1], kernel[1]))
    return request.param, ab, states, found


def test_equal_keys_mean_equal_kernels_at_every_state(world):
    name, _, _, found = world
    groups = defaultdict(list)
    for state, action, key, kernel in found:
        groups[(state, key)].append((action, kernel))

    merged = 0
    for members in groups.values():
        first_action, first_kernel = members[0]
        for action, kernel in members[1:]:
            assert kernel == first_kernel, f"{action!r} and {first_action!r} share a key and differ in kernel"
            merged += 1
    print(f"\n{name}: {len(found)} (state, action) pairs, {len(groups)} distinct keys, {merged} merged")
    if name.startswith("fossil"):
        assert merged > 0, "no two actions share a key: the property was not exercised"


def test_the_worlds_hold_fractured_mods_and_crafted_slots(world):
    name, _, states, found = world
    assert any(state.fractured for state in states)
    assert len(found) > 50
    if name == "belt":
        assert any(any(slot.crafted for slot in state.slots) for state in states)


def test_the_fossil_world_exercises_the_fractured_fossil_and_the_mixtures(world):
    name, _, _, found = world
    if not name.startswith("fossil"):
        pytest.skip("fossils are in the fossil world")
    used = {name for _, action, _, _ in found if isinstance(action, ApplyFossils) for name in action.fossils}
    assert {"Fractured Fossil", "Tangled Fossil", "Glyphic Fossil", "Hollow Fossil"} <= used


def test_sets_of_one_pool_share_a_key_with_the_chaos_orb():
    ab, _, _ = _fossil_world(False)
    state = ab.compress(fossil_world.boots())
    same = [ChaosOrb(), fossil_world.fossils("Gloveless"), fossil_world.fossils("Dull")]

    assert len({ab.kernel_key(state, action) for action in same}) == 1
    assert ab.kernel_key(state, fossil_world.fossils("Scorched")) != ab.kernel_key(state, ChaosOrb())


def test_kernel_key_builds_no_state_and_no_weights(monkeypatch):
    ab, actions, starts = _fossil_world(False)
    expected = {(start, action): _outcome_of(lambda: ab.kernel_key(start, action)) for start in starts for action in actions}
    fresh, actions, starts = _fossil_world(False)

    def refuse(*args, **kwargs):
        raise AssertionError("kernel_key built the states of a kernel")

    for name in ("_add_drawn", "_add_fractured", "_add_fixed"):
        monkeypatch.setattr(kernel_module.Abstraction, name, refuse)
    monkeypatch.setattr(kernel_module, "integer_weights", refuse)

    for start in starts:
        for action in actions:
            assert _outcome_of(lambda: fresh.kernel_key(start, action)) == expected[(start, action)]


def test_kernel_key_refuses_what_the_kernel_refuses():
    ab, _, _ = _fossil_world(False)
    fractured = ab.compress(fossil_world.boots(fossil_world.roll("CasterA", fractured=True)))

    with pytest.raises(NotApplicableError):
        ab.kernel_key(fractured, fossil_world.fossils("Fractured"))
    with pytest.raises(ValueError, match="not among the enabled"):
        ab.kernel_key(ab.compress(fossil_world.boots()), RemoveCraftedMods())
    other = Abstraction(fossil_world.DATA, Goal(fossil_world.GOAL.leaves[:1]), fossil_world.BOOTS, fossil_world.LEVEL)
    with pytest.raises(ValueError, match="another abstraction"):
        other.kernel_key(fractured, ChaosOrb())


# --- offers that differ only in price ----------------------------------------------------------------

GEM = "GlobalLightningGemLevel1"


@pytest.fixture(scope="module")
def target():
    return load_target(R12, DATA)


def _prices(**extra):
    base = price_file()
    return dataclasses.replace(base, prices={**base.prices, **{name: PriceEntry(chaos, "test") for name, chaos in extra.items()}})


def _reforge(label, lifeforce):
    """A Harvest reforge of Lightning under another label that takes `lifeforce` units (the real one takes 50)."""
    return Offer(label, HarvestReforge("lightning"), {LIFEFORCE: lifeforce}, tag="lightning")


def _labels(plan):
    return {action.label for action in plan.policy.values()}


def test_a_dearer_copy_of_an_offer_changes_nothing(target):
    plain = make_plan(DATA, target, price_file())
    dearer = make_plan(DATA, target, price_file(), offers=[*default_offers(), _reforge("Dear Reforge", 400)])

    assert dearer.mean_remaining == pytest.approx(plain.mean_remaining, rel=1e-12)
    assert _labels(dearer) == _labels(plain) == {"Harvest Reforge Lightning"}
    assert "Dear Reforge" in {priced.label for priced in dearer.offers}  # it was offered, and priced


def test_the_dearer_copy_is_not_even_given_to_the_solver(target):
    priced, _ = price_offers([*default_offers(), _reforge("Dear Reforge", 400)], price_file())
    ab = Abstraction(DATA, Goal.from_target(target), target.base_id, target.item_level)
    start = ab.compress(target.start_item)

    merged = {action.label for action in solver_actions(ab, priced, start, start)}
    unmerged = {action.label for action in solver_actions(ab, priced, start, start, merge_equal=False)}

    assert "Dear Reforge" in unmerged and "Dear Reforge" not in merged
    assert merged == unmerged - {"Dear Reforge"}


def test_a_cheaper_copy_takes_the_place_of_the_original(target):
    q = float(HarvestReforge("lightning").outcomes(DATA, target.start_item).chance_all([GEM]))
    cheaper = make_plan(DATA, target, price_file(), offers=[*default_offers(), _reforge("Cheap Reforge", 10)])

    assert _labels(cheaper) == {"Cheap Reforge"}
    assert cheaper.mean_remaining == pytest.approx(10 * 0.01 / q, rel=1e-9)
    assert cheaper.mean_remaining < make_plan(DATA, target, price_file()).mean_remaining


def test_on_a_tie_of_cost_the_earliest_offer_stays(target):
    twin = _reforge("Twin Reforge", 50)
    first = make_plan(DATA, target, price_file(), offers=[*default_offers(), twin])
    last = make_plan(DATA, target, price_file(), offers=[twin, *default_offers()])

    assert _labels(first) == {"Harvest Reforge Lightning"}
    assert _labels(last) == {"Twin Reforge"}


def test_restart_is_never_merged_and_stays_off_the_start_state(target):
    priced, _ = price_offers(default_offers(), price_file())
    ab = Abstraction(DATA, Goal.from_target(target), target.base_id, target.item_level)
    start = ab.compress(target.start_item)
    plan = make_plan(DATA, target, price_file())
    (restart,) = [offer for offer in plan.offers if offer.label == "restart"]
    elsewhere = ab.kernel(start, ChaosOrb())
    other = next(state for state in elsewhere if state != start)

    assert "restart" not in {a.label for a in solver_actions(ab, (*priced, restart), start, start)}
    assert "restart" in {a.label for a in solver_actions(ab, (*priced, restart), other, start)}


# --- the fixture target, numbers from the run before the change --------------------------------------


def test_r12_gives_the_mean_and_the_policy_it_gave_before_the_merge(target):
    plan = make_plan(DATA, target, price_file())

    assert plan.mean_remaining == pytest.approx(8.982640767063662, rel=1e-9)
    assert [priced.label for priced in plan.offers] == ["Chaos Orb", "Harvest Reforge Lightning", "restart"]
    assert _labels(plan) == {"Harvest Reforge Lightning"} and len(plan.policy) == 1


# --- R10 on the real dump, with and without the merge --------------------------------------------------


@pytest.fixture(scope="module")
def r10():
    """The R10 plan with the merge and without it (planned once each), with the seconds each took."""
    real = real_game_data()
    target = load_target(R10, real)
    prices = load_price_file(PRICES)
    merged = make_plan(real, target, prices)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(_plan, "MERGE_EQUAL", False)
        reference = make_plan(real, target, prices)
    print(f"\nR10 solve seconds: with the merge {merged.solve_seconds:.1f} s, without {reference.solve_seconds:.1f} s")
    return merged, reference


def test_r10_has_the_same_mean_and_policy_without_the_merge(r10):
    merged, reference = r10

    assert merged.mean_remaining == pytest.approx(reference.mean_remaining, rel=1e-9)
    assert merged.solution.values.keys() == reference.solution.values.keys()
    for state, value in reference.solution.values.items():
        assert merged.solution.values[state] == pytest.approx(value, rel=1e-9)
    assert merged.policy.keys() == reference.policy.keys()
    for state, action in reference.policy.items():
        assert merged.policy[state].label == action.label


def test_r10_offers_collapse_to_fewer_kernels_than_pairs(r10):
    _, reference = r10
    ab = reference.abstraction
    states = sorted(reference.solution.values, key=repr)
    states = states[:: max(1, len(states) // 40)]

    pairs = distinct = 0
    for state in states:
        keys = Counter()
        for priced in reference.offers:
            if priced.label == "restart":
                continue
            try:
                keys[ab.kernel_key(state, priced.offer.action)] += 1
            except ActionError:
                continue
        pairs += sum(keys.values())
        distinct += len(keys)

    print(f"\nR10: {pairs} (state, offer) pairs, {distinct} distinct kernel keys at {len(states)} states")
    assert 0 < distinct < pairs
