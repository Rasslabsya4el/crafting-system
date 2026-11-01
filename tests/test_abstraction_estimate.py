"""The pilot count (ticket #127, ADR-0023): `Abstraction.estimate` against the real expansion on the committed fixture.

The real expansion is written here from `Abstraction.kernel` alone: a breadth-first walk that does not expand a
goal, as the solver's graph does. The pilot decides the legality of bench crafts and Remove Crafted Mods by its own
sets of families and free slots, so these checks are what keeps that logic equal to `BenchCraft.outcomes`: random
subsets of crafts (a metamod craft included, which makes a reroll refuse), random starts (rare, magic, corrupted,
with a fractured mod, with a crafted mod), two goals. Rates are not asserted (ADR-0014); the clock is a counter.
"""

import dataclasses
import itertools
import random
from collections import deque
from fractions import Fraction

import pytest
from abstraction_pool import COLD_RESIST, CRAFTED, DAMAGE_1, FIRE_RESIST, GEM, LIFE_1, MANA_1, RESIST_2
from coarse_support import CHAOS, DAMAGE_CRAFT, DATA as BASE_DATA, HYBRID_CRAFT, HYBRID_JUNK, LIGHTNING_CRAFT, MANA_CRAFT, REMOVE, concrete_items
from items_support import AMULET

from crafting_system.abstraction import ADDING_LIMIT, DEFAULT_LIMIT, Abstraction, Coarsening, EstimateRefused, Goal, Wanted, needs_walk
from crafting_system.actions import (
    BLOCKING,
    ActionError,
    Adds,
    AlchemyOrb,
    AlterationOrb,
    AnnulmentOrb,
    AugmentationOrb,
    BenchCraft,
    ChaosOrb,
    ExaltedOrb,
    RegalOrb,
    ScouringOrb,
    TransmutationOrb,
)
from crafting_system.items import Metamod, Rarity

LIFE_GOAL = Goal((Wanted(frozenset({LIFE_1})),))
CRAFT_GOAL = Goal((Wanted(frozenset({HYBRID_CRAFT})), Wanted(frozenset({LIFE_1}))))

_template = next(o for o in BASE_DATA.bench_options if o.actions.add_explicit_mod == DAMAGE_CRAFT)
DATA = dataclasses.replace(
    BASE_DATA,
    bench_options=(*BASE_DATA.bench_options, dataclasses.replace(_template, actions=dataclasses.replace(_template.actions, add_explicit_mod=CRAFTED))),
)
MULTIMOD = "TestMultimod"
DATA = dataclasses.replace(
    DATA,
    mods={**DATA.mods, MULTIMOD: dataclasses.replace(DATA.mods[CRAFTED], id=MULTIMOD, type=MULTIMOD, families=(Metamod.MULTIPLE_CRAFTED_MODS.value,))},
    bench_options=(*DATA.bench_options, dataclasses.replace(_template, actions=dataclasses.replace(_template.actions, add_explicit_mod=MULTIMOD))),
)
META_CRAFT = BenchCraft(CRAFTED)
CRAFTS = (BenchCraft(HYBRID_CRAFT), BenchCraft(MANA_CRAFT), BenchCraft(LIGHTNING_CRAFT), BenchCraft(DAMAGE_CRAFT), META_CRAFT, BenchCraft(MULTIMOD))


@dataclasses.dataclass(frozen=True)
class KeepsCrafted(ChaosOrb):
    """A Chaos Orb that declares it keeps crafted mods: its kernel is then keyed by the crafted slots, not only the metamods."""

    def adds(self, data=None, item=None) -> Adds:
        return Adds(named=frozenset(), single_draw=True)


POOL = [MANA_1, COLD_RESIST, FIRE_RESIST, HYBRID_JUNK, DAMAGE_1, RESIST_2, LIFE_1, GEM]
START_MODS = list(
    concrete_items(DATA, POOL, crafted=[MANA_CRAFT, LIGHTNING_CRAFT, DAMAGE_CRAFT, CRAFTED, MULTIMOD], largest=3, rarities=(Rarity.RARE, Rarity.MAGIC))
)


def real_graph(ab, starts, actions):
    """(states, transitions) of the graph the solver would build: every kernel entry of every action on a state that is not a goal."""
    seen = set(starts)
    queue = deque(seen)
    transitions = 0
    while queue:
        state = queue.popleft()
        if ab.is_goal(state):
            continue
        for action in actions:
            try:
                kernel = ab.kernel(state, action)
            except ActionError:
                continue
            transitions += len(kernel)
            for successor in kernel:
                if successor not in seen:
                    seen.add(successor)
                    queue.append(successor)
    return len(seen), transitions


def counter():
    ticks = itertools.count()
    return lambda: float(next(ticks))


def random_case(seed):
    rng = random.Random(seed)
    crafts = [craft for craft in CRAFTS if rng.random() < 0.6]
    removal = [REMOVE] if rng.random() < 0.7 else []
    rerolls = [CHAOS] if rng.random() < 0.7 or not (crafts or removal) else []
    if rerolls and rng.random() < 0.3:
        rerolls.append(KeepsCrafted())
    goal = rng.choice([LIFE_GOAL, CRAFT_GOAL])
    item = rng.choice(START_MODS)
    if rng.random() < 0.1:
        item = dataclasses.replace(item, corrupted=True)
    junk_readers = [*crafts, *removal]
    holds_lock = bool(item.metamods(DATA) & BLOCKING)  # the state has to be built to hold a lock or an Attack/Caster metamod (#69)
    ab = Abstraction(DATA, goal, AMULET, item.item_level, junk_readers, metamods=holds_lock)
    return ab, [ab.compress(item)], [*rerolls, *junk_readers]


@pytest.mark.parametrize("seed", range(120))
def test_the_pilot_counts_the_states_and_transitions_of_the_real_expansion(seed):
    ab, starts, actions = random_case(seed)

    try:
        real = real_graph(ab, starts, actions)
    except ValueError as error:  # the kernel itself cannot place two hybrid junk slots on one item; the pilot has nothing to match
        pytest.skip(str(error))
    found = ab.estimate(starts, actions, clock=counter())

    assert (found.states, found.transitions) == real
    assert found.complete


def test_the_random_cases_reach_crafts_rerolls_refusals_and_graphs_of_several_sizes():
    sizes = set()
    refused = crafted = 0
    for seed in range(120):
        ab, starts, actions = random_case(seed)
        found = ab.estimate(starts, actions, clock=counter())
        sizes.add(found.states)
        crafted += any(isinstance(action, BenchCraft) for action in actions) and found.states > 1
        if seed < 25:
            for state in found._pilot.reached:
                for action in actions:
                    try:
                        ab.kernel(state, action)
                    except ActionError:
                        refused += 1
    assert len(sizes) > 20
    assert crafted > 30
    assert refused > 100


def test_a_start_that_is_a_goal_is_not_expanded():
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [REMOVE])
    from coarse_support import item, roll

    start = ab.compress(item(roll(LIFE_1)))

    found = ab.estimate([start], [CHAOS, REMOVE], clock=counter())

    assert (found.states, found.transitions) == (1, 0)


def test_the_kernel_rate_is_the_measured_time_per_outcome_of_a_repeated_call():
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [REMOVE])
    from coarse_support import item, roll

    found = ab.estimate([ab.compress(item(roll(MANA_1)))], [CHAOS], clock=counter())

    outcomes = len(ab.kernel(ab.compress(item(roll(MANA_1))), CHAOS))
    assert found.kernel_rate == pytest.approx(1.0 / outcomes)  # the counter ticks once between the two reads


def test_without_a_reroll_there_is_no_kernel_rate():
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [REMOVE, *CRAFTS[:1]])
    from coarse_support import item, roll

    found = ab.estimate([ab.compress(item(roll(MANA_1)))], [CRAFTS[0], REMOVE], clock=counter())

    assert found.kernel_rate == 0.0


@dataclasses.dataclass(frozen=True)
class BrokenRegal(RegalOrb):
    """A Regal Orb whose outcomes cannot be computed on any item, not even as a refusal (a `ValueError` that is no `ActionError`)."""

    def outcomes(self, data, item):
        raise ValueError("this action has no outcomes")


def test_a_walked_action_whose_kernel_cannot_be_computed_is_refused():
    broken = BrokenRegal()
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [broken])
    from coarse_support import item, roll

    with pytest.raises(EstimateRefused, match="Regal"):
        ab.estimate([ab.compress(item(roll(MANA_1), rarity=Rarity.MAGIC))], [CHAOS, broken])


def test_an_action_the_abstraction_was_not_built_with_is_a_callers_error():
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [])
    from coarse_support import item, roll

    with pytest.raises(ValueError, match="not among the enabled"):
        ab.estimate([ab.compress(item(roll(MANA_1)))], [CRAFTS[0]])


def test_the_walk_stops_at_its_limit_and_says_the_counts_are_lower_bounds():
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [REMOVE, *CRAFTS])
    from coarse_support import item, roll

    start = ab.compress(item(roll(MANA_1)))
    full = ab.estimate([start], [CHAOS, REMOVE, *CRAFTS], clock=counter())

    cut = ab.estimate([start], [CHAOS, REMOVE, *CRAFTS], limit=10, clock=counter())

    assert full.complete and not cut.complete
    assert cut.states < full.states and cut.transitions < full.transitions
    assert cut.coarsened(Coarsening(ab)) is None


def test_the_seconds_of_an_estimate_are_outcomes_at_the_kernel_rate_plus_the_solved_edges_at_the_solve_rate():
    ab, starts, actions = random_case(3)
    found = ab.estimate(starts, actions, clock=counter())

    assert found.seconds(2.0, 3.0) == found.outcomes * 2.0 + found.transitions * 3.0
    assert dataclasses.replace(found, solves=2).seconds(0.0, 1.0) == 2 * found.transitions


# --- a coarse level forecast ---------------------------------------------------------------------------


def test_the_forecast_of_a_coarse_level_has_the_blocks_that_the_reachable_states_map_to():
    ab = Abstraction(DATA, CRAFT_GOAL, AMULET, 84, [REMOVE, *CRAFTS[:4]])
    from coarse_support import item, roll

    actions = [CHAOS, REMOVE, *CRAFTS[:4]]
    start = ab.compress(item(roll(COLD_RESIST, fractured=True)))
    exact = ab.estimate([start], actions, clock=counter())
    pooling = Coarsening.pooling_irrelevant(ab, None, start)

    level = exact.coarsened(pooling)

    reached = pooling.reachable([pooling.coarsen(start)], actions, "lower", stop_at_goal=True)
    assert level is not None and level.solves == 2
    assert {pooling.coarsen(state) for state in exact._pilot.reached} <= reached
    assert level.states == len({pooling.coarsen(state) for state in exact._pilot.reached})
    assert level.states < exact.states
    assert level.transitions < exact.transitions


# --- the closed prefix ------------------------------------------------------------------------------------


def test_the_first_layers_are_closed_and_carry_the_integer_weights_of_the_kernels():
    ab, starts, actions = random_case(7)
    found = ab.estimate(starts, actions, clock=counter())

    layers = found.first_layers(10**9)

    reached = set(found._pilot.reached)
    assert set(layers) <= reached
    for state, offered in layers.items():
        for action, outcomes in offered:
            assert all(successor in reached for successor, _ in outcomes)
            kernel = ab.kernel(state, action)
            assert {s for s, _ in outcomes} == set(kernel)
            ratios = {Fraction(weight, sum(w for _, w in outcomes)) for _, weight in outcomes}
            assert ratios == set(kernel.values())


def test_a_small_prefix_drops_the_outcomes_that_leave_it():
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [REMOVE, *CRAFTS])
    from coarse_support import item, roll

    found = ab.estimate([ab.compress(item(roll(MANA_1)))], [CHAOS, REMOVE, *CRAFTS], clock=counter())

    layers = found.first_layers(5)

    members = set(layers) | {state for state in found._pilot.reached if ab.is_goal(state)}
    assert 0 < len(layers) < found.states
    assert all(successor in members for offered in layers.values() for _, outcomes in offered for successor, _ in outcomes)


# --- walked actions: additions and Annulment ----------------------------------------------------------------

ADDERS = (RegalOrb(), ExaltedOrb(), AugmentationOrb(), AnnulmentOrb())


class Unslotted:
    """A stand-in for a `Coarsening` that the variants level has not built yet: a block is the state without its slots."""

    def coarsen(self, state):
        return dataclasses.replace(state, slots=())


MAGIC_STARTS = [start for start in START_MODS if start.rarity is Rarity.MAGIC]


def walked_case(seed):
    rng = random.Random(seed)
    walked = [action for action in ADDERS if rng.random() < 0.5] or [rng.choice(ADDERS)]
    crafts = [craft for craft in CRAFTS[:4] if rng.random() < 0.3]
    removal = [REMOVE] if rng.random() < 0.3 else []
    rerolls = [CHAOS] if rng.random() < 0.4 else []
    goal = rng.choice([LIFE_GOAL, CRAFT_GOAL])
    item = rng.choice(START_MODS if rng.random() < 0.5 else MAGIC_STARTS)  # Augmentation and Regal need a magic item
    junk_readers = [*walked, *crafts, *removal]
    ab = Abstraction(DATA, goal, AMULET, item.item_level, junk_readers)
    return ab, [ab.compress(item)], [*rerolls, *junk_readers]


@pytest.mark.parametrize("seed", range(40))
def test_the_walked_count_equals_the_real_expansion(seed):
    ab, starts, actions = walked_case(seed)

    try:
        real = real_graph(ab, starts, actions)
    except ValueError as error:  # the kernel itself cannot place two hybrid junk slots on one item; the pilot has nothing to match
        pytest.skip(str(error))
    found = ab.estimate(starts, actions, clock=counter(), limit=10**9)

    assert (found.states, found.transitions, found.outcomes) == (*real, real[1])
    assert found.complete and found.walked


def test_the_walked_cases_reach_every_walked_action_and_graphs_of_several_sizes():
    sizes = set()
    used = set()
    for seed in range(40):
        ab, starts, actions = walked_case(seed)
        try:
            found = ab.estimate(starts, actions, clock=counter(), limit=10**9)
        except ValueError:
            continue
        sizes.add(found.states)
        for state in found._pilot.reached:
            for action in actions:
                if action in ADDERS and _legal(ab, state, action):
                    used.add(action)
    assert len(sizes) > 10
    assert used == set(ADDERS)


def _legal(ab, state, action):
    try:
        ab.kernel(state, action)
    except ActionError:
        return False
    return True


def test_a_query_with_no_walked_action_is_not_marked_walked():
    ab, starts, actions = random_case(3)

    assert not ab.estimate(starts, actions, clock=counter()).walked


def test_the_walked_kernel_rate_is_measured_on_the_first_kernel_when_no_reroll_did():
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [RegalOrb()])
    from coarse_support import item, roll

    start = ab.compress(item(roll(MANA_1), rarity=Rarity.MAGIC))

    found = ab.estimate([start], [RegalOrb()], clock=counter())

    assert found.kernel_rate == pytest.approx(1.0 / len(ab.kernel(start, RegalOrb())))


def test_a_reroll_that_measured_the_rate_keeps_it_when_a_walked_action_comes_later():
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [ExaltedOrb()])
    from coarse_support import item, roll

    start = ab.compress(item(roll(MANA_1)))

    found = ab.estimate([start], [ExaltedOrb(), CHAOS], clock=counter())

    assert found.kernel_rate == pytest.approx(1.0 / len(ab.kernel(start, CHAOS)))


def test_the_walk_of_additions_stops_at_its_limit_and_says_the_counts_are_lower_bounds():
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [RegalOrb(), ExaltedOrb(), AnnulmentOrb(), AugmentationOrb()])
    from coarse_support import item, roll

    start = ab.compress(item(roll(MANA_1), rarity=Rarity.MAGIC))
    actions = [*ADDERS, CHAOS]
    full = ab.estimate([start], actions, clock=counter())

    cut = ab.estimate([start], actions, limit=5, clock=counter())

    assert full.complete and not cut.complete
    assert 5 < cut.states < full.states and cut.transitions < full.transitions
    assert cut.coarsened(Unslotted()) is None
    assert cut.walked


def test_the_limit_for_additions_is_smaller_than_the_default():
    assert 0 < ADDING_LIMIT < DEFAULT_LIMIT


def test_needs_walk_is_true_exactly_for_an_action_that_is_no_reroll_no_bench_craft_and_not_remove_crafted_mods():
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [])
    rerolls = [CHAOS, KeepsCrafted(), TransmutationOrb(), AlterationOrb(), AlchemyOrb(), ScouringOrb()]

    for action in (*rerolls, *CRAFTS, REMOVE):
        assert not needs_walk(ab, [action]), action
    for action in ADDERS:
        assert needs_walk(ab, [action]), action
    assert needs_walk(ab, [CHAOS, *CRAFTS, ExaltedOrb(), REMOVE])
    assert not needs_walk(ab, [])


def test_the_forecast_of_a_coarse_level_of_a_walked_query_counts_the_blocks_and_the_transitions():
    walked = [AnnulmentOrb(), *CRAFTS[:4], REMOVE]
    actions = [*walked, CHAOS]
    ab = Abstraction(DATA, CRAFT_GOAL, AMULET, 84, walked)
    from coarse_support import item, roll

    start = ab.compress(item(roll(COLD_RESIST, fractured=True)))
    exact = ab.estimate([start], actions, clock=counter())
    pooling = Coarsening.pooling_irrelevant(ab, None, start)

    level = exact.complete and exact.coarsened(pooling)

    assert exact.walked
    assert level and level.walked and level.solves == 2
    assert level.states == len({pooling.coarsen(state) for state in exact._pilot.reached})
    assert level.states < exact.states
    assert level.transitions > 0 and level.outcomes > 0
    assert level.seconds(1.0, 1.0) > 0
    assert exact.seconds(1.0, 1.0) > 0


def test_a_coarse_forecast_counts_two_kernels_for_an_action_that_declares_variants_and_one_for_any_other():
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [ExaltedOrb(), AnnulmentOrb()])
    from coarse_support import item, roll

    start = ab.compress(item(roll(MANA_1), roll(COLD_RESIST)))
    unslotted = Unslotted()
    annul = ab.estimate([start], [AnnulmentOrb()], clock=counter())
    exalt = ab.estimate([start], [ExaltedOrb()], clock=counter())

    assert annul._pilot.walked == {AnnulmentOrb(): 1}
    assert exalt._pilot.walked == {ExaltedOrb(): 2}
    for found, action, factor in ((annul, AnnulmentOrb(), 1), (exalt, ExaltedOrb(), 2)):
        first = {}
        for state in found._pilot.reached:
            first.setdefault(unslotted.coarsen(state), state)
        legal = [(block, state) for block, state in first.items() if not ab.is_goal(block) and _legal(ab, state, action)]
        level = found.coarsened(unslotted)
        assert level.outcomes == factor * sum(len(ab.kernel(state, action)) for _, state in legal)
        assert level.transitions == factor * sum(len({unslotted.coarsen(s) for s in ab.kernel(state, action)}) for _, state in legal)


def test_the_first_layers_of_a_walked_query_carry_the_real_kernel():
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [ExaltedOrb(), AnnulmentOrb()])
    from coarse_support import item, roll

    found = ab.estimate([ab.compress(item(roll(MANA_1), roll(COLD_RESIST)))], [ExaltedOrb(), AnnulmentOrb(), CHAOS], clock=counter())

    layers = found.first_layers(10**9)

    assert {action for offered in layers.values() for action, _ in offered} >= {ExaltedOrb(), AnnulmentOrb()}
    for state, offered in layers.items():
        for action, outcomes in offered:
            kernel = ab.kernel(state, action)
            assert {s for s, _ in outcomes} == set(kernel)
            ratios = {Fraction(weight, sum(w for _, w in outcomes)) for _, weight in outcomes}
            assert ratios == set(kernel.values())


def test_the_walk_stops_when_its_seconds_are_spent_and_says_the_counts_are_lower_bounds():
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [RegalOrb(), ExaltedOrb(), AnnulmentOrb(), AugmentationOrb()])
    from coarse_support import item, roll

    start = ab.compress(item(roll(MANA_1), rarity=Rarity.MAGIC))
    actions = [*ADDERS, CHAOS]
    full = ab.estimate([start], actions, clock=counter())

    cut = ab.estimate([start], actions, seconds=3.0, clock=counter())  # the counting clock moves one unit per reading

    assert full.complete and not cut.complete
    assert cut.states < full.states and cut.walked
