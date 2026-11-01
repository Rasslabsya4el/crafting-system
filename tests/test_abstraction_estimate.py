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

from crafting_system.abstraction import Abstraction, Coarsening, EstimateRefused, Goal, Wanted
from crafting_system.actions import BLOCKING, ActionError, Adds, BenchCraft, ChaosOrb, RegalOrb
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


def test_an_action_that_is_not_a_reroll_a_bench_craft_or_remove_crafted_mods_is_refused():
    ab = Abstraction(DATA, LIFE_GOAL, AMULET, 84, [RegalOrb()])
    from coarse_support import item, roll

    with pytest.raises(EstimateRefused, match="Regal"):
        ab.estimate([ab.compress(item(roll(MANA_1)))], [CHAOS, RegalOrb()])


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
