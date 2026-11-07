"""The packed walk of a plan (`cli/_packed.py`) on the committed fixture pool, checked against the abstraction and the risk module (ticket #413).

`test_packed_heavy.py` and `test_packed_plan_real.py` check this module on routes R04, R14 and S02, which CI does not run;
the measurement week (#399) found 29 of its 43 checked mutants alive, and 23 more never run because their test sets failed
clean or took too long. Here the same code runs on a graph of about a hundred states (a Mana Leech amulet, the Chaos Orb, the four
bench crafts, Remove Crafted Mods and a restart) in about a quarter of a second, and everything is compared with something this
module does not compute:

* the states and the kernels of the walk against a plain breadth-first search over `Abstraction.kernel`;
* the counts of the shared-kernel check against the count of a plain search (actions less distinct kernels), not the graph's own;
* the values against the object solver `solver.solve` on a table written out by a plain search over `Abstraction.kernel`;
* the mean of the lumped chain against `risk.evaluate`, which knows nothing of the walk.

The kernels themselves are always the abstraction's (`Abstraction.kernel`): the walk packs them, and what it must keep is exactly
them. This file has no second source for them. The second source is accepted to be the `test_abstraction_*` files, which check
`Abstraction.kernel` against brute force over concrete items, compressed one by one and added up in exact fractions:

* the Chaos Orb on the amulet pool of this world (`abstraction_pool.SMALL`):
  `test_abstraction_kernel.py::test_the_kernel_equals_the_enumeration_over_concrete_items` (with `abstraction_support.check_kernel`,
  which also checks the sum is exactly 1) and `test_abstraction_oracle.py` (which checks the brute force itself against `actions`);
* a bench craft and Remove Crafted Mods, on the belt fixture and not on this world:
  `test_abstraction_b1.py::test_a_craft_adds_a_crafted_slot_and_equals_the_deterministic_result` and
  `::test_remove_crafted_mods_drops_the_crafted_slots_and_equals_the_deterministic_result` (the one result of a craft, compared with
  `assert_same_distribution`); `test_abstraction_estimate.py` keeps the legality of this world's four crafts equal to `BenchCraft.outcomes`.

What is not covered is the kernel of this world's own four synthetic crafts and of Remove Crafted Mods by brute force (issue #460).

The conversion of a kernel to integer weights is not shared with the code under test: `cli/_packed.py` imports
`abstraction.integer_weights`, and every expectation here uses `weights_by_hand`, written in this file by another route (the product
of the denominators, not their least common multiple) and checked on kernels worked out on paper
(`test_the_weights_by_hand_are_the_ones_worked_out_on_paper`). A bug in `integer_weights` therefore shows as a difference between
the walk and the expectation; `test_integer_weights_is_the_weights_by_hand_on_the_kernels_of_the_world` also compares the two on every
kernel of the world.
"""

import math
from fractions import Fraction
from types import SimpleNamespace

import numpy as np
import pytest
from abstraction_pool import MANA_1
from coarse_support import CHAOS, CRAFTS, REMOVE, abstraction, item, roll

from crafting_system import risk
from crafting_system.abstraction import integer_weights
from crafting_system.actions import ActionError
from crafting_system.cli import Offer
from crafting_system.cli import _packed
from crafting_system.cli._offers import RESTART, BuyStartItem, PricedOffer
from crafting_system.solver import Action, Outcome, TabularModel, solve, solve_packed

START_ITEM = item(roll(MANA_1))
LABELS = ["Chaos Orb", *(f"Craft {c.mod_id}" for c in CRAFTS), "Remove Crafted Mods", RESTART]
PRICES = [1.0, 2.0, 2.0, 2.0, 2.0, 1.0, 3.0]


def weights_by_hand(kernel):
    """The kernel as integers with no common factor, written here and not taken from `abstraction.integer_weights`.

    Multiply every chance by the product of all the denominators (a whole number, though a larger one than the least common multiple),
    then divide by the greatest common divisor of the results.
    """
    if not kernel:
        return {}
    product = 1
    for chance in kernel.values():
        product *= Fraction(chance).denominator
    scaled = {state: Fraction(chance) * product for state, chance in kernel.items()}
    assert all(weight.denominator == 1 for weight in scaled.values())
    divisor = 0
    for weight in scaled.values():
        divisor = math.gcd(divisor, int(weight))
    return {state: int(weight) // divisor for state, weight in scaled.items()}


def make_offers(start_item=START_ITEM):
    actions = [CHAOS, *CRAFTS, REMOVE, BuyStartItem(start_item)]
    return [PricedOffer(Offer(label, action, {"Chaos Orb": 1}), price, ()) for label, action, price in zip(LABELS, actions, PRICES)]


def fresh_walk(**options):
    ab = abstraction()
    start = ab.compress(START_ITEM)
    lines = []
    walked = _packed.walk(ab, start, make_offers(), progress=lines.append, **options)
    return ab, start, walked, lines


@pytest.fixture(scope="module")
def world():
    ab, start, walked, lines = fresh_walk()
    return ab, start, walked, lines


def actions_of(graph, state):
    return range(int(graph.act_ptr[state]), int(graph.act_ptr[state + 1]))


def kernel_of(graph, action):
    kernel = int(graph.act_kernel[action])
    lo, hi = int(graph.k_ptr[kernel]), int(graph.k_ptr[kernel + 1])
    return dict(zip(graph.k_succ[lo:hi].tolist(), graph.kernel_weights(kernel)))


def reachable_by_search(ab, start, offers):
    """The states reachable from `start` by any offer that the game takes, by a plain search over `Abstraction.kernel`."""
    seen, queue = {start}, [start]
    while queue:
        state = queue.pop()
        if ab.is_goal(state):
            continue
        for priced in offers:
            action = priced.offer.action
            if isinstance(action, BuyStartItem):
                continue
            try:
                found = ab.kernel(state, action)
            except ActionError:
                continue
            for successor in found:
                if successor not in seen:
                    seen.add(successor)
                    queue.append(successor)
    return seen


# --- the conversion to integer weights, worked out on paper ---------------------------------------------------------------

WEIGHTS_ON_PAPER = [
    ({}, {}),
    ({"a": Fraction(1)}, {"a": 1}),
    ({"a": Fraction(1, 2), "b": Fraction(1, 2)}, {"a": 1, "b": 1}),
    ({"a": Fraction(3, 4), "b": Fraction(1, 4)}, {"a": 3, "b": 1}),
    # 1/6, 1/3, 1/2 over 6: 1, 2, 3 (the product of the denominators is 36: 6, 12, 18, and the common factor 6 goes)
    ({"a": Fraction(1, 6), "b": Fraction(1, 3), "c": Fraction(1, 2)}, {"a": 1, "b": 2, "c": 3}),
    # 1/6, 1/6, 2/3 = 1/6, 1/6, 4/6: 1, 1, 4
    ({"a": Fraction(1, 6), "b": Fraction(1, 6), "c": Fraction(2, 3)}, {"a": 1, "b": 1, "c": 4}),
    # 1/10, 3/10, 3/5 = 1/10, 3/10, 6/10: 1, 3, 6
    ({"a": Fraction(1, 10), "b": Fraction(3, 10), "c": Fraction(3, 5)}, {"a": 1, "b": 3, "c": 6}),
    # 2/3, 1/3 over 3: 2, 1 (the order of the keys is kept)
    ({"b": Fraction(2, 3), "a": Fraction(1, 3)}, {"b": 2, "a": 1}),
]


@pytest.mark.parametrize("kernel,expected", WEIGHTS_ON_PAPER, ids=lambda case: str(case))
def test_the_weights_by_hand_are_the_ones_worked_out_on_paper(kernel, expected):
    found = weights_by_hand(kernel)

    assert found == expected and list(found) == list(expected)


def test_integer_weights_is_the_weights_by_hand_on_the_kernels_of_the_world(world):
    ab, _, walked, _ = world
    checked = 0

    for state in walked.states:
        if ab.is_goal(state):
            continue
        for priced in make_offers():
            if isinstance(priced.offer.action, BuyStartItem):
                continue
            try:
                kernel = ab.kernel(state, priced.offer.action)
            except ActionError:
                continue
            assert integer_weights(kernel) == weights_by_hand(kernel)
            checked += 1

    graph, restart_tag = walked.graph, len(make_offers()) - 1
    assert checked == sum(1 for tag in graph.act_tag.tolist() if tag != restart_tag)  # exactly the actions the walk built, but the restarts


@pytest.mark.parametrize("kernel,expected", WEIGHTS_ON_PAPER, ids=lambda case: str(case))
def test_integer_weights_is_the_weights_worked_out_on_paper(kernel, expected):
    assert integer_weights(kernel) == expected


# --- the graph the walk builds --------------------------------------------------------------------------------------------


def test_the_walk_reaches_the_states_of_a_plain_search_and_numbers_them_from_the_start(world):
    ab, start, walked, _ = world

    assert set(walked.states) == reachable_by_search(ab, start, make_offers())
    assert walked.states[0] == start and walked.graph.n == len(walked.states) == len(walked.index)
    assert all(walked.index[state] == i for i, state in enumerate(walked.states))


def test_goal_states_are_marked_and_have_no_action(world):
    ab, _, walked, _ = world
    graph = walked.graph

    goals = [i for i, state in enumerate(walked.states) if ab.is_goal(state)]

    assert goals and graph.goal.tolist() == [ab.is_goal(state) for state in walked.states]
    assert all(len(actions_of(graph, i)) == 0 for i in goals)
    assert all(len(actions_of(graph, i)) > 0 for i in range(graph.n) if i not in goals)  # a restart at least


def test_every_action_has_the_cost_and_the_kernel_the_abstraction_gives_for_its_offer(world):
    ab, _, walked, _ = world
    graph = walked.graph
    restarts = 0

    for i, state in enumerate(walked.states):
        previous = -1
        for a in actions_of(graph, i):
            tag = int(graph.act_tag[a])
            priced = walked.offers[tag]
            assert tag > previous  # in the order of the offers
            previous = tag
            assert graph.act_cost[a] == priced.cost
            if isinstance(priced.offer.action, BuyStartItem):
                restarts += 1
                assert kernel_of(graph, a) == {0: 1}  # back to the start, for certain
            else:
                expected = {walked.index[s]: w for s, w in weights_by_hand(ab.kernel(state, priced.offer.action)).items()}
                assert kernel_of(graph, a) == expected
    assert restarts == sum(1 for i in range(1, graph.n) if not graph.goal[i])  # every state but the start (and the goals) can restart


def test_the_start_has_no_restart_and_the_other_states_share_one_restart_kernel(world):
    _, _, walked, _ = world
    graph = walked.graph
    restart_tag = len(make_offers()) - 1

    assert restart_tag not in [int(graph.act_tag[a]) for a in actions_of(graph, 0)]
    kernels = {int(graph.act_kernel[a]) for i in range(1, graph.n) for a in actions_of(graph, i) if int(graph.act_tag[a]) == restart_tag}
    assert len(kernels) == 1


def test_a_kernel_is_stored_once_for_all_the_actions_that_share_its_key(world):
    _, _, walked, _ = world
    graph = walked.graph

    assert graph.num_kernels < graph.num_actions // 2  # 326 actions, about a hundred kernels: states share them
    assert set(graph.act_kernel.tolist()) == set(range(graph.num_kernels))  # and every stored kernel is used


def test_the_walk_clears_the_per_state_cache_of_the_abstraction():
    ab, _, _, _ = fresh_walk()

    assert not ab._prepared_by


def test_the_walked_offers_are_the_offers_given_in_order(world):
    _, _, walked, _ = world

    assert [p.label for p in walked.offers] == LABELS and isinstance(walked.offers, tuple)


# --- the shared-kernel check ----------------------------------------------------------------------------------------------


def counts_of(ab, start, offers):
    """(shared-kernel hits, kernels computed) by a plain search of the abstraction, not from the graph the walk built.

    Each state the search reaches has one action for each distinct kernel among the offers it takes (equal kernels at one state are merged;
    the restart is not counted, it has a kernel of its own). A kernel is computed once, so the number computed is the number of distinct
    kernels in the whole world, and every other action is a hit on a kernel computed before: hits = actions - distinct kernels. This holds
    when `kernel_key` is exact, which is what the walk's own check of shared kernels is there to catch, so a key that said too little would
    show up as a count that is off (and as the ValueError of the tests below).
    """
    seen, queue = {start}, [start]
    actions, distinct = 0, set()
    while queue:
        state = queue.pop()
        if ab.is_goal(state):
            continue
        here = set()
        for priced in offers:
            action = priced.offer.action
            if isinstance(action, BuyStartItem):
                continue
            try:
                found = ab.kernel(state, action)
            except ActionError:
                continue
            here.add(frozenset(weights_by_hand(found).items()))
            for successor in found:
                if successor not in seen:
                    seen.add(successor)
                    queue.append(successor)
        actions += len(here)
        distinct |= here
    return actions - len(distinct), len(distinct)


def check_line(lines):
    line = next(text for text in lines if "shared kernels checked" in text)
    head = line.split(" shared kernels")[0]
    checked, hits = head.split(" of ")
    return int(checked), int(hits.replace(",", "")), line


@pytest.mark.parametrize("first,every", [(20, 4096), (3, 7), (0, 5), (0, 1000), (150, 1000)])
def test_the_check_of_shared_kernels_covers_the_first_few_and_then_one_in_so_many(monkeypatch, first, every):
    monkeypatch.setattr(_packed, "VERIFY_FIRST", first)
    monkeypatch.setattr(_packed, "VERIFY_EVERY", every)

    ab, start, walked, lines = fresh_walk()

    hits, computed = counts_of(ab, start, make_offers())
    checked, said_hits, line = check_line(lines)
    assert said_hits == hits and hits > 100
    assert walked.graph.num_kernels == computed + 1  # the kernels of the world, and the restart's
    assert checked == sum(1 for h in range(1, hits + 1) if h <= first or h % every == 0)
    assert line.endswith("checked against a fresh kernel: all equal")


def test_a_fresh_kernel_is_asked_of_the_abstraction_once_for_each_kernel_and_each_check(monkeypatch):
    ab = abstraction()
    asked = []
    real = ab.kernel
    monkeypatch.setattr(ab, "kernel", lambda state, action: asked.append(1) or real(state, action))
    start = ab.compress(START_ITEM)
    lines = []

    walked = _packed.walk(ab, start, make_offers(), progress=lines.append)

    checked, hits, _ = check_line(lines)
    assert len(asked) == (walked.graph.num_kernels - 1) + checked


def wrong_keys(real):
    """A `keyed_offers` that gives every offer other than restart the same kernel key: the walk would share kernels that differ."""

    def keyed(abstraction, offers, state, start, **options):
        return [(position, priced, None if isinstance(priced.offer.action, BuyStartItem) else "same") for position, priced, _ in real(abstraction, offers, state, start, **options)]

    return keyed


def test_a_kernel_key_that_says_too_little_is_caught_by_the_check(monkeypatch):
    monkeypatch.setattr(_packed, "keyed_offers", wrong_keys(_packed.keyed_offers))

    with pytest.raises(ValueError, match="share the kernel key of .* but not its kernel"):
        fresh_walk()


def test_the_check_after_the_first_few_looks_at_every_so_manyth_hit_only(monkeypatch):
    monkeypatch.setattr(_packed, "keyed_offers", wrong_keys(_packed.keyed_offers))
    monkeypatch.setattr(_packed, "VERIFY_FIRST", 0)
    monkeypatch.setattr(_packed, "VERIFY_EVERY", 10**9)
    ab, _, walked, lines = fresh_walk()  # nothing looked: the wrong sharing goes through
    assert check_line(lines)[0] == 0

    monkeypatch.setattr(_packed, "VERIFY_EVERY", 3)
    with pytest.raises(ValueError):
        fresh_walk()


# --- the clock and the progress lines -------------------------------------------------------------------------------------


class Clock:
    """A clock that starts at `origin` and moves `step` seconds each time it is read."""

    def __init__(self, step, origin=0.0):
        self.step, self.now = step, origin - step

    def perf_counter(self):
        self.now += self.step
        return self.now


def test_a_long_walk_says_where_it_is_every_so_many_seconds_and_how_long_it_took(monkeypatch):
    monkeypatch.setattr(_packed, "time", Clock(10.0, origin=1000.0))  # started at 1000; each finished state reads the clock: +10, +20, ...

    ab, _, walked, lines = fresh_walk()

    n = walked.graph.n
    reports = [text for text in lines if text.startswith("walk: ")]
    assert len(reports) == n // 3  # every third state: the clock is 30 s past the last report (equal to the interval counts)
    assert reports[0].endswith("(30 s)") and reports[1].endswith("(60 s)")
    assert reports[0].startswith("walk: ") and " done, " in reports[0] and "3 done" in reports[0]
    assert walked.seconds == 10.0 * (n + 1)  # the start, one read per state, and the end: not the sum of the first and the last
    assert lines[-1].endswith(f"({10 * (n + 1)} s)")


def test_a_walk_shorter_than_the_interval_stays_silent_until_it_ends(world):
    _, _, walked, lines = world

    assert not [text for text in lines if text.startswith("walk: ")]
    assert lines[-1].startswith(f"walk finished: {walked.graph.n:,} states, {walked.graph.num_actions:,} actions, {walked.graph.num_kernels:,} kernels, ")


def test_the_progress_of_the_module_is_used_when_no_callback_is_given_and_the_callback_wins(monkeypatch):
    seen, given = [], []
    monkeypatch.setattr(_packed, "PROGRESS", seen.append)

    ab = abstraction()
    _packed.walk(ab, ab.compress(START_ITEM), make_offers())
    assert any(text.startswith("walk finished") for text in seen)

    seen.clear()
    _packed.walk(ab, ab.compress(START_ITEM), make_offers(), progress=given.append)
    assert not seen and any(text.startswith("walk finished") for text in given)


def test_with_no_callback_at_all_the_walk_is_silent_and_works():
    ab = abstraction()

    walked = _packed.walk(ab, ab.compress(START_ITEM), make_offers())

    assert walked.graph.n > 100


# --- the policy of a packed solve ----------------------------------------------------------------------------------------


def first_actions(graph):
    """The policy that takes the first action of every state with one (the start's is action 0)."""
    return np.array([int(graph.act_ptr[i]) if graph.act_ptr[i + 1] > graph.act_ptr[i] else -1 for i in range(graph.n)], dtype=np.int64)


def followed(graph, action):
    """The non-goal states with an action that the policy reaches from state 0, by a plain search."""
    seen, queue = {0}, [0]
    while queue:
        s = queue.pop()
        if action[s] < 0:
            continue
        for successor in kernel_of(graph, int(action[s])):
            if successor not in seen:
                seen.add(successor)
                queue.append(successor)
    return {s for s in seen if action[s] >= 0}


def test_the_policy_holds_the_states_it_reaches_that_have_an_action(world):
    ab, start, walked, _ = world
    graph = walked.graph
    action = first_actions(graph)

    policy = _packed.PackedPolicy(ab, start, walked, action)

    expected = followed(graph, action)
    assert 0 in expected and len(policy) == len(expected) and {walked.index[s] for s in policy} == expected
    assert all(state in policy for state in policy)
    assert policy.walked is walked and policy.action_array is action


def test_a_state_the_policy_does_not_reach_is_not_in_it(world):
    ab, start, walked, _ = world
    graph = walked.graph
    action = first_actions(graph)
    action[0] = -1  # the policy takes nothing at the start: it reaches no state with an action beyond it
    other = next(state for state in walked.states if not ab.is_goal(state) and state != start)

    policy = _packed.PackedPolicy(ab, start, walked, action)

    assert len(policy) == 0 and start not in policy and other not in policy
    assert "not a state" not in policy  # nothing that was never walked is in it


def test_a_goal_and_a_state_never_walked_are_not_in_the_policy(world):
    ab, start, walked, _ = world
    policy = _packed.PackedPolicy(ab, start, walked, first_actions(walked.graph))
    goal = next(state for state in walked.states if ab.is_goal(state))
    never = ab.compress(item(roll(MANA_1, fractured=True)))

    assert never not in walked.index
    assert goal not in policy and never not in policy
    assert start in policy


def test_the_offer_of_a_state_is_the_offer_of_the_tag_of_its_action(world):
    ab, start, walked, _ = world
    graph = walked.graph
    action = first_actions(graph)
    policy = _packed.PackedPolicy(ab, start, walked, action)

    pairs = list(policy.offers())

    assert len(pairs) == len(policy)
    for state, priced in pairs:
        assert priced is walked.offers[int(graph.act_tag[action[walked.index[state]]])]
        assert policy.offer(state) is priced
    assert [state for state, _ in pairs] == list(policy)


def test_asking_for_the_offer_or_the_action_of_a_state_outside_the_policy_is_a_key_error(world):
    ab, start, walked, _ = world
    policy = _packed.PackedPolicy(ab, start, walked, first_actions(walked.graph))
    goal = next(state for state in walked.states if ab.is_goal(state))
    never = ab.compress(item(roll(MANA_1, fractured=True)))

    for state in (goal, never):
        with pytest.raises(KeyError):
            policy.offer(state)
        with pytest.raises(KeyError):
            policy[state]


def test_the_action_of_a_state_is_built_once_from_the_abstraction(world):
    ab, start, walked, _ = world
    graph = walked.graph
    action = first_actions(graph)
    policy = _packed.PackedPolicy(ab, start, walked, action)
    state = start

    built = policy[state]

    assert built is policy[state]
    priced = walked.offers[int(graph.act_tag[action[0]])]
    assert built.label == priced.label and built.cost == priced.cost
    assert {o.state: o.weight for o in built.outcomes} == dict(weights_by_hand(ab.kernel(state, priced.offer.action)))


# --- solving a walked graph ---------------------------------------------------------------------------------------------


def table_by_search(ab, start, offers):
    """The world written out as a model of the object solver by a plain search over `Abstraction.kernel`, without the walk's graph.

    A state has one action for each offer it takes, at the price of the offer; the restart goes back to the start from every state but the
    start. (The walk merges equal kernels to the cheapest and the table keeps them all: the optimal values are the same.)
    """
    table, goals, seen, queue = {}, [], {start}, [start]
    while queue:
        state = queue.pop()
        if ab.is_goal(state):
            goals.append(state)
            table[state] = []
            continue
        acts = []
        for priced in offers:
            action = priced.offer.action
            if isinstance(action, BuyStartItem):
                if state != start:
                    acts.append(Action(priced.label, priced.cost, (Outcome(start, 1),)))
                continue
            try:
                found = weights_by_hand(ab.kernel(state, action))
            except ActionError:
                continue
            acts.append(Action(priced.label, priced.cost, tuple(Outcome(s, w) for s, w in found.items())))
            for successor in found:
                if successor not in seen:
                    seen.add(successor)
                    queue.append(successor)
        table[state] = acts
    return TabularModel(goals, table)


@pytest.fixture(scope="module")
def solved(world):
    ab, start, walked, _ = world
    lines = []
    result = _packed.solve_walked(ab, start, walked, progress=lines.append)
    return result, lines


def test_the_values_of_the_walked_states_are_those_of_the_object_solver_on_a_table_made_by_a_plain_search(world, solved):
    # the table is not the graph of the walk (that would test the solver on what the walk built, and a wrong walk would give a wrong table
    # with right values): it is searched over `Abstraction.kernel` here. The kernels are the abstraction's own, which other tests check
    # against brute force over concrete items (`test_abstraction_*`); there is no second source for them at this size.
    ab, start, walked, _ = world
    result, _ = solved

    exact = solve(table_by_search(ab, start, make_offers()), [start])

    assert set(result.solution.values) == set(walked.states) == set(exact.values)
    for state in walked.states:
        assert result.solution.values[state] == pytest.approx(exact.values[state], rel=1e-9, abs=1e-12)
    assert result.solution.error_bound < 1e-9


def test_the_policy_of_the_solution_takes_for_each_state_an_action_as_good_as_the_best(world, solved):
    ab, start, walked, _ = world
    result, _ = solved
    graph = walked.graph
    values = {walked.index[s]: v for s, v in result.solution.values.items()}

    for state in result.solution.policy:
        i = walked.index[state]
        built = result.solution.policy[state]
        # the self loop is compiled out of a value, not of this sum: the action's value is the fixed point cost-to-go with it included
        total = sum(o.weight for o in built.outcomes)
        stay = sum(o.weight for o in built.outcomes if walked.index[o.state] == i)
        leave = (total - stay) / total
        other = sum(o.weight * values[walked.index[o.state]] for o in built.outcomes if walked.index[o.state] != i) / total
        assert (built.cost + other) / leave == pytest.approx(values[i], rel=1e-8)


def test_the_info_of_a_solve_has_the_walk_and_the_lump(world, solved):
    _, _, walked, _ = world
    result, lines = solved
    info = result.info

    assert info["states"] == walked.graph.n and info["transitions"] == sum(len(kernel_of(walked.graph, a)) for a in range(walked.graph.num_actions))
    assert info["walk_seconds"] == round(walked.seconds, 1)
    assert info["lumped_blocks"] >= 2 and info["lumped_transitions"] >= info["lumped_blocks"] - 1 and info["lump_rounds"] >= 1
    assert any(text.startswith(f"policy chain lumped: {info['lumped_blocks']:,} blocks, {info['lumped_transitions']:,} transitions (") for text in lines)


def test_the_lumped_chain_has_the_mean_of_the_solution(world, solved):
    ab, start, walked, _ = world
    result, _ = solved

    mean = risk.evaluate(result.risk_policy, result.risk_start, result.risk_is_goal).mean.value

    assert mean == pytest.approx(result.solution.values[start], rel=1e-9)
    assert not result.risk_is_goal(result.risk_start)
    assert all(not result.risk_is_goal(block) for block in result.risk_policy)


def test_the_lumped_chain_on_concrete_states_has_the_same_mean_and_a_state_per_block(world, solved):
    ab, start, walked, _ = world
    result, _ = solved

    assert result.view is not None and len(result.view) == len(result.risk_policy)
    shown_start = next(state for state in result.view if state == start) if start in result.view else None
    assert shown_start is not None  # the start is the first state of its block, so it shows its block
    mean = risk.evaluate(result.view, start, ab.is_goal).mean.value
    assert mean == pytest.approx(result.solution.values[start], rel=1e-9)
    for state, taken in result.view.items():
        assert not ab.is_goal(state) and taken.cost > 0 and taken.outcomes


def test_the_lumped_policy_gives_every_live_block_an_action_with_the_offers_label_and_the_summed_weights(world, solved):
    _, _, walked, _ = world
    result, _ = solved
    labels = set(LABELS)

    for block, taken in result.risk_policy.items():
        assert taken.label in labels and taken.cost > 0
        assert all(isinstance(o.state, int) and o.weight > 0 for o in taken.outcomes)
        assert len({o.state for o in taken.outcomes}) == len(taken.outcomes)  # one outcome per target block


def test_the_time_to_lump_is_the_clock_between_two_reads_in_tenths_of_a_second(world, monkeypatch):
    ab, start, walked, _ = world
    monkeypatch.setattr(_packed, "time", Clock(12.34, origin=1000.0))

    result = _packed.solve_walked(ab, start, walked)

    assert result.info["lump_seconds"] == 12.3  # one read apart: 12.34 to a tenth


class FakeLumped:
    """Three blocks: 0 takes action 1 to the goal block 1 or the dead block 2 (no action, not a goal); 1 is the goal."""

    count = 3
    action = np.array([1, -1, -1])
    goal = np.array([False, True, False])
    succ = [np.array([1, 2]), np.array([], dtype=np.int64), np.array([], dtype=np.int64)]
    weight = [np.array([3, 1]), np.array([], dtype=np.int64), np.array([], dtype=np.int64)]
    cost = np.array([2.5, 0.0, 0.0])
    rep = np.array([0, 1, 2])


def test_the_lumped_policy_leaves_out_the_goal_blocks_and_the_blocks_with_no_action():
    reduced = SimpleNamespace(act_tag=np.array([0, 1]))
    offers = [SimpleNamespace(label="first"), SimpleNamespace(label="second")]

    policy = _packed.lumped_policy(FakeLumped, reduced, offers)

    assert list(policy) == [0]
    assert policy[0].label == "second" and policy[0].cost == 2.5
    assert [(o.state, o.weight) for o in policy[0].outcomes] == [(1, 3), (2, 1)]


def test_the_lumped_view_leaves_out_the_goal_blocks_and_the_blocks_with_no_action_and_shows_each_block_by_its_first_state():
    reduced = SimpleNamespace(act_tag=np.array([0, 1]))
    walked = SimpleNamespace(states=["s0", "s1", "s2", "s3"], offers=[SimpleNamespace(label="first"), SimpleNamespace(label="second")])
    cls = np.array([2, 0, 1, 0])  # the classes of the four states; the blocks' representatives are classes 0, 1, 2

    view = _packed.lumped_view(FakeLumped, reduced, cls, walked)

    # class c is first met at state: 0 -> s1, 1 -> s2, 2 -> s0; block b is shown by the first state of class rep[b] = b
    assert list(view) == ["s1"]
    taken = view["s1"]
    assert taken.label == "second" and taken.cost == 2.5
    assert [(o.state, o.weight) for o in taken.outcomes] == [("s2", 3), ("s0", 1)]


def test_solve_walked_says_how_far_it_has_come(world, solved):
    _, lines = solved

    assert any(text.startswith("merged ") for text in lines) and any(text.startswith("certificate on the whole graph") for text in lines)


def test_solve_walked_uses_the_progress_of_the_module_when_it_is_given_none(world, monkeypatch):
    ab, start, walked, _ = world
    seen = []
    monkeypatch.setattr(_packed, "PROGRESS", seen.append)

    _packed.solve_walked(ab, start, walked)

    assert any(text.startswith("policy chain lumped") for text in seen)


# --- which solver --------------------------------------------------------------------------------------------------------


def edges_of(walked):
    graph = walked.graph
    return sum(len(kernel_of(graph, a)) for a in range(graph.num_actions))


def test_an_unknown_solver_name_is_refused_and_the_known_ones_are_not(world):
    ab, start, _, _ = world

    with pytest.raises(ValueError, match="solver must be one of auto, object, packed, envelope, got 'fast'"):
        _packed.packed_result(ab, start, make_offers(), solver="fast")


def test_the_object_solver_is_left_the_plan_without_a_walk(monkeypatch):
    monkeypatch.setattr(_packed, "walk", lambda *a, **k: pytest.fail("walked"))
    ab = abstraction()

    assert _packed.packed_result(ab, ab.compress(START_ITEM), make_offers(), solver="object") is None


def test_auto_leaves_a_graph_up_to_the_edge_limit_to_the_object_solver_and_takes_a_larger_one(world, monkeypatch):
    _, _, walked, _ = world
    edges = edges_of(walked)

    for limit, taken in ((edges, False), (edges - 1, True), (edges + 1, False)):
        monkeypatch.setattr(_packed, "OBJECT_SOLVER_EDGES", limit)
        ab = abstraction()
        result = _packed.packed_result(ab, ab.compress(START_ITEM), make_offers(), solver="auto")
        assert (result is not None) is taken, limit


def test_packed_solves_whatever_the_size_and_passes_its_tolerance_and_progress_on(monkeypatch):
    monkeypatch.setattr(_packed, "OBJECT_SOLVER_EDGES", 10**9)
    ab = abstraction()
    lines = []

    result = _packed.packed_result(ab, ab.compress(START_ITEM), make_offers(), solver="packed", progress=lines.append)

    assert result is not None and result.solution.error_bound < 1e-9
    assert any(text.startswith("walk finished") for text in lines)
    assert any(text.startswith("certificate on the whole graph") for text in lines)
    assert math.isfinite(result.solution.values[ab.compress(START_ITEM)])
