"""The reference fixtures of ADR-0059 (ticket #211): donor wants, lazy `Need` generation and the size of the product.

A tiny recombinator world (items of up to two prefixes from the classes A, B and an optional junk J, an Alteration, an
Exalted Orb, an Annulment and a recombination whose donor is a `Need`) is solved through `Acquisition` and compared with
three references that do not use the lazy loop: exact brute force over every stationary policy of the product, the
Bellman linear programme, and the product with every donor offered up front. The lazy loop of the ADR is written here as
the reference that the build ticket (#212 onward, "lazy donor generation in the solve") must reproduce: solve with the
donors offered so far, then offer every donor whose lower bound on the action does not exceed the value in hand, until
none does. The recombination kernel is the unpredictable recombinator of ADR-0033 on one side, computed twice, by
dynamic programming over the picked sets and by the ordered draws of the formula.
"""

import heapq
import itertools
import math
import random
from fractions import Fraction
from math import lcm

import pytest
from ssp_input_oracles import brute_force_inputs, lp_values_inputs

from crafting_system.solver import Acquisition, Action, Need, solve

# percent kept by pooled count (ADR-0033, the guide's table; renormalised per row)
COUNT_TABLE = {1: {0: 41, 1: 59}, 2: {1: 67, 2: 33}, 3: {1: 39, 2: 52, 3: 10}, 4: {1: 11, 2: 59, 3: 31}}


def scaled(dist):
    denominator = lcm(*(Fraction(p).denominator for p in dist.values()))
    return tuple((state, int(Fraction(p) * denominator)) for state, p in dist.items() if p)


class TinyWorld:
    """Items are sorted tuples of mod names (every mod its own family); `weights` maps a mod to its spawn weight."""

    def __init__(self, weights, costs, cap=2):
        self.weights, self.costs, self.cap = weights, costs, cap
        self.goal = tuple(sorted(name for name in weights if name in "AB"))

    def states(self):
        names = sorted(self.weights)
        return [c for n in range(self.cap + 1) for c in itertools.combinations(names, n)]

    def donors(self):
        return [s for s in self.states() if s]

    def is_goal(self, state):
        return state == self.goal

    # --- kernels ---
    def alt(self, state):
        total = sum(self.weights.values())
        return {(name,): Fraction(w, total) for name, w in self.weights.items()}

    def exalt(self, state):
        free = {n: w for n, w in self.weights.items() if n not in state}
        if len(state) >= self.cap or not free:
            return None
        total = sum(free.values())
        return {tuple(sorted(state + (n,))): Fraction(w, total) for n, w in free.items()}

    def annul(self, state):
        if not state:
            return None
        dist = {}
        for i in range(len(state)):
            rest = state[:i] + state[i + 1 :]
            dist[rest] = dist.get(rest, 0) + Fraction(1, len(state))
        return dist

    def recomb(self, a, b):
        """Dynamic programming over the picked sets: pooled entries (a mod on both inputs twice), a family closed once picked."""
        entries = list(a) + list(b)
        row = COUNT_TABLE[min(len(entries), 4)]
        total = sum(row.values())
        out = {}
        for kept, percent in row.items():
            dist = {(): Fraction(1)}
            for _ in range(min(kept, self.cap)):
                nxt = {}
                for picked, p in dist.items():
                    live = [(n, self.weights[n]) for n in entries if n not in picked]
                    weight = sum(w for _, w in live)
                    if not weight:
                        nxt[picked] = nxt.get(picked, 0) + p
                        continue
                    for n in {n for n, _ in live}:
                        share = Fraction(sum(w for m, w in live if m == n), weight)
                        key = tuple(sorted(picked + (n,)))
                        nxt[key] = nxt.get(key, 0) + p * share
                dist = nxt
            for picked, p in dist.items():
                out[picked] = out.get(picked, 0) + p * Fraction(percent, total)
        return out

    def recomb_by_orders(self, a, b):
        """The same kernel from the ordered draws of the formula, one entry at a time, closing its family."""
        entries = list(a) + list(b)
        row = COUNT_TABLE[min(len(entries), 4)]
        total = sum(row.values())
        out = {}

        def draw(remaining, picked, left, p, percent):
            if left == 0 or not remaining:
                key = tuple(sorted(picked))
                out[key] = out.get(key, 0) + p * Fraction(percent, total)
                return
            weight = sum(self.weights[n] for n in remaining)
            for i, n in enumerate(remaining):
                rest = [m for m in remaining if m != n]
                draw(rest, picked + [n], left - 1, p * Fraction(self.weights[n], weight), percent)

        for kept, percent in row.items():
            draw(entries, [], min(kept, self.cap), Fraction(1), percent)
        return out

    # --- the base model of the solver ---
    def model(self, offers):
        world = self
        cache = {}

        class Model:
            def is_goal(self, state):
                return world.is_goal(state)

            def actions(self, state):
                if state in cache:
                    return cache[state]
                found = []
                for label, kernel in (("alt", world.alt), ("exalt", world.exalt), ("annul", world.annul)):
                    if label in world.costs and (dist := kernel(state)):
                        found.append(Action(label, world.costs[label], scaled(dist)))
                for donor in offers(state):
                    found.append(
                        Action(("recomb", donor), world.costs["recomb"], scaled(world.recomb(state, donor)), (Need((), donor),))
                    )
                cache[state] = tuple(found)
                return cache[state]

        return Model()

    def solve(self, offers, **options):
        acquisition = Acquisition(self.model(offers))
        solution = solve(acquisition, [acquisition.start(())], **options)
        return solution, acquisition


def world_of(seed):
    rng = random.Random(seed)
    weights = {"A": rng.choice([1, 2, 5]), "B": rng.choice([1, 3, 9])}
    if rng.random() < 0.7:
        weights["J"] = rng.choice([2, 6, 20])
    costs = {"alt": 1, "recomb": rng.choice([1, 3, 10])}
    if rng.random() < 0.5:
        costs["exalt"] = rng.choice([2, 5])
    if rng.random() < 0.5:
        costs["annul"] = rng.choice([1, 3])
    return TinyWorld(weights, costs)


def product_spec(acquisition, start):
    """The reachable product as an oracle spec: goals and, per state, (label, cost, outcomes, inputs)."""
    seen, stack, table, goals = {start}, [start], {}, set()
    while stack:
        x = stack.pop()
        if acquisition.is_goal(x):
            goals.add(x)
            continue
        rows = []
        for a in acquisition.actions(x):
            rows.append((a.label, Fraction(a.cost), [(o.state, o.weight) for o in a.outcomes], list(a.extra_inputs)))
            for t in [o.state for o in a.outcomes] + list(a.extra_inputs):
                if t not in seen:
                    seen.add(t)
                    stack.append(t)
        table[x] = rows
    return goals, table


class Determinized:
    """The cheapest path to a state that reaches `want`: costs of the actions, any possible successor, inputs free. A lower bound on every value."""

    def __init__(self, world):
        self.world, self.reverse, self.memo = world, {}, {}
        for s in world.states():
            for kernel, label in ((world.alt, "alt"), (world.exalt, "exalt"), (world.annul, "annul")):
                if label in world.costs and (dist := kernel(s)):
                    for j in dist:
                        self.reverse.setdefault(j, []).append((world.costs[label], s))
            for d in world.donors():
                for j in world.recomb(s, d):
                    self.reverse.setdefault(j, []).append((world.costs["recomb"], s))

    def to(self, want):
        if want not in self.memo:
            best = {want: 0.0}
            heap = [(0.0, want)]
            while heap:
                d, s = heapq.heappop(heap)
                if d > best.get(s, math.inf):
                    continue
                for cost, prev in self.reverse.get(s, ()):
                    if d + cost < best.get(prev, math.inf):
                        best[prev] = d + cost
                        heapq.heappush(heap, (d + cost, prev))
            self.memo[want] = best
        return self.memo[want]


def lazy_solve(world, seed_donors, *, bound="expected", envelope=False):
    """The loop of ADR-0059: solve, prove every other donor unneeded or offer it, repeat. Returns (solution, acquisition, offers, rounds).

    The lower bound is the value in hand on the checked states and the determinized distance elsewhere. By default every built
    state with a finite value is checked. With `envelope` only the states the policy in hand reaches are, and a state joins them
    when an action offered at a checked state falls below the value there only because its successor was not checked (what an
    envelope search expands): the end test is the same, so the value is the same.
    """
    offers = {s: set(seed_donors(s)) for s in world.states()}
    det = Determinized(world)
    rounds = 0
    while True:
        rounds += 1
        solution, acquisition = world.solve(lambda s: sorted(offers[s]))
        values = solution.values
        start = acquisition.start(())
        if envelope:
            members, stack = {start}, [start]
            while stack:
                x = stack.pop()
                if x in solution.policy:
                    action = solution.policy[x]
                    for y in [o.state for o in action.outcomes] + list(action.extra_inputs):
                        if y not in members:
                            members.add(y)
                            stack.append(y)
        else:
            members = set(values)
        violations = set()
        grown = True
        while grown:
            grown = False
            for x in list(members):
                tag, want, s = x
                v = values[x]
                if v == 0.0:
                    continue
                if not math.isfinite(v):  # no value in hand here: nothing can be pruned
                    violations.update((s, d) for d in world.donors() if d not in offers[s])
                    for a in acquisition.actions(x):  # without a policy in hand the whole closure has to be looked at
                        for y in [o.state for o in a.outcomes] + list(a.extra_inputs):
                            if y in values and y not in members:
                                members.add(y)
                                grown = True
                    continue
                lower = det.to(world.goal) if str(want) == "MAIN" else det.to(want)

                def level(j, tag=tag, want=want, lower=lower):
                    y = (tag, want, j)
                    if y in members and math.isfinite(values.get(y, math.inf)):
                        return values[y]
                    return lower.get(j, math.inf)

                def acquisition_level(d):
                    y = ("in", d, ())
                    if y in members and math.isfinite(values.get(y, math.inf)):
                        return values[y]
                    return det.to(d).get((), math.inf)

                for d in world.donors():
                    dist = world.recomb(s, d)
                    q = world.costs["recomb"] + acquisition_level(d) + (
                        min(level(j) for j in dist) if bound == "support" else sum(float(p) * level(j) for j, p in dist.items())
                    )
                    if q >= v * (1 - 1e-9) - 1e-9:
                        continue
                    if d not in offers[s]:
                        violations.add((s, d))
                        continue
                    for y in [(tag, want, j) for j in dist] + [("in", d, ())]:  # offered: the successors were not checked, so check them
                        if y in values and y not in members:
                            members.add(y)
                            grown = True
                for label, kernel in (("alt", world.alt), ("exalt", world.exalt), ("annul", world.annul)):
                    dist = kernel(s) if label in world.costs else None
                    if dist and world.costs[label] + sum(float(p) * level(j) for j, p in dist.items()) < v * (1 - 1e-9) - 1e-9:
                        for j in dist:
                            y = (tag, want, j)
                            if y in values and y not in members:
                                members.add(y)
                                grown = True
        if not violations:
            return solution, acquisition, offers, rounds
        for s, d in violations:
            offers[s].add(d)


def branching_components(acquisition, start):
    """Sizes of the strongly connected components of the product that hold an input edge (outcome and input edges alike)."""
    order, edges = [start], {}
    seen = {start}
    for x in order:
        out = []
        if not acquisition.is_goal(x):
            for a in acquisition.actions(x):
                out += [(o.state, False) for o in a.outcomes] + [(y, True) for y in a.extra_inputs]
        edges[x] = out
        for y, _ in out:
            if y not in seen:
                seen.add(y)
                order.append(y)
    forward = {x: [y for y, _ in out] for x, out in edges.items()}
    backward = {x: [] for x in order}
    for x, ys in forward.items():
        for y in ys:
            backward[y].append(x)

    def closure(root, graph):
        found, stack = {root}, [root]
        while stack:
            for y in graph[stack.pop()]:
                if y not in found:
                    found.add(y)
                    stack.append(y)
        return found

    done, sizes = set(), []
    for x in order:
        if x in done:
            continue
        component = closure(x, forward) & closure(x, backward)
        done |= component
        if any(is_input and y in component for z in component for y, is_input in edges[z]):
            sizes.append(len(component))
    return sorted(sizes, reverse=True)


# --- the kernel of the fixture is the formula of ADR-0033 -------------------------------------------------


@pytest.mark.parametrize("pair", [(("A",), ("B",)), (("A", "B"), ("A",)), (("A", "J"), ("A", "J")), (("A", "B"), ("A", "B"))])
def test_the_recombination_kernel_equals_the_ordered_draws_of_the_formula(pair):
    world = TinyWorld({"A": 2, "B": 3, "J": 6}, {"recomb": 1})
    assert world.recomb(*pair) == world.recomb_by_orders(*pair)
    assert sum(world.recomb(*pair).values()) == 1


def test_a_mod_on_both_inputs_is_drawn_twice_as_often_and_its_family_is_closed():
    world = TinyWorld({"A": 1, "B": 1}, {"recomb": 1})
    out = world.recomb(("A",), ("A", "B"))  # pooled 3: A, A, B; kept 1 (39%), 2 (52%), 3 (10%) of 101
    # kept 1: A with chance 2/3; kept 2 and 3: both families are picked in some order, so A and B
    assert out[("A",)] == Fraction(39, 101) * Fraction(2, 3)
    assert out[("B",)] == Fraction(39, 101) * Fraction(1, 3)
    assert out[("A", "B")] == Fraction(62, 101)


# --- the tiny case equals brute force --------------------------------------------------------------------


def test_the_tiny_case_equals_brute_force_over_every_policy_of_the_product():
    world = TinyWorld({"A": 1, "B": 3}, {"alt": 1, "recomb": 2})
    donors = [("A",), ("B",)]
    solution, acquisition = world.solve(lambda s: donors)
    start = acquisition.start(())
    spec = product_spec(acquisition, start)
    assert len(spec[1]) == 9 and all(len(rows) == 3 for rows in spec[1].values())  # 3**9 = 19,683 policies
    best = brute_force_inputs(spec)
    for state, value in solution.values.items():
        if state in best and best[state] is not None:
            assert value == pytest.approx(float(best[state]), rel=1e-9), state
    assert solution.values[start] == pytest.approx(float(best[start]), rel=1e-9)
    assert float(best[start]) == pytest.approx(17.1616161616, rel=1e-9)  # pinned


# --- the lazy loop equals every donor offered up front ----------------------------------------------------


@pytest.mark.parametrize("seed", range(40))
def test_the_lazy_loop_equals_the_product_with_every_donor_offered_and_the_linear_programme(seed):
    world = world_of(seed)
    full, full_acquisition = world.solve(lambda s: world.donors())
    start = full_acquisition.start(())
    seeds = [lambda s: [], lambda s: [d for d in world.donors() if len(d) == 1]][seed % 2]
    lazy, lazy_acquisition, offers, rounds = lazy_solve(world, seeds, bound=["expected", "support"][seed // 2 % 2])
    assert lazy.values[lazy_acquisition.start(())] == pytest.approx(full.values[start], rel=1e-8)
    if all(math.isfinite(v) for v in full.values.values()):
        lp = lp_values_inputs(product_spec(full_acquisition, start))
        assert full.values[start] == pytest.approx(float(lp[start]), rel=1e-7)
    for state, value in lazy.values.items():  # every value the loop built is the value of the full model
        if math.isfinite(value) and state in full.values:
            assert value == pytest.approx(full.values[state], rel=1e-7, abs=1e-9)
    assert rounds <= 4


@pytest.mark.parametrize("seed", range(40))
def test_testing_only_the_states_the_policy_reaches_gives_the_same_value(seed):
    """What an envelope search (#312) would do: the lower bound is the value in hand inside the envelope and the determinized distance outside it."""
    world = world_of(seed)
    full, full_acquisition = world.solve(lambda s: world.donors())
    envelope, envelope_acquisition, offers, _ = lazy_solve(world, lambda s: [], envelope=True)
    assert envelope.values[envelope_acquisition.start(())] == pytest.approx(full.values[full_acquisition.start(())], rel=1e-8)


def test_the_loop_leaves_donors_out_that_it_proves_unneeded():
    world = world_of(0)
    _, _, offers, _ = lazy_solve(world, lambda s: [])
    possible = len(world.states()) * len(world.donors())
    assert sum(len(v) for v in offers.values()) < possible // 2


def test_the_lazy_product_is_smaller_and_its_branching_component_stays_within_the_direct_limit():
    world = TinyWorld({"A": 100, "B": 100, "J": 500, "K": 500}, {"alt": 1, "exalt": 50, "annul": 20, "recomb": 140})
    iso = lambda s: [d for d in world.donors() if set(d) <= {"A", "B"}]
    lazy, lazy_acquisition, offers, _ = lazy_solve(world, iso)
    full, full_acquisition = world.solve(lambda s: world.donors())
    start = full_acquisition.start(())
    assert lazy.values[lazy_acquisition.start(())] == pytest.approx(full.values[start], rel=1e-8)
    assert len(lazy.values) < len(full.values) // 2
    assert len({w for (_, w, _) in lazy.values}) < len({w for (_, w, _) in full.values})
    small = branching_components(lazy_acquisition, lazy_acquisition.start(()))
    assert small and small[0] <= 64  # the donors that feed each other still form a branching component, within the limit
    big = branching_components(full_acquisition, start)
    assert big and big[0] > 64 > small[0]  # all donors at once: one branching component beyond `direct_solve_limit`


# --- a donor class ends the acquisition at its first member ----------------------------------------------


def test_a_want_that_is_the_projection_a_consumer_reads_is_met_by_the_first_member_of_the_class():
    """The Awakener's Orb reads the influence and the influenced mod of a donor, not its junk: the want is that projection.

    The donor begins blank, `roll` gives the mod X with a junk mod or without one (1/2 each), and `scrub` removes the
    junk from X + junk. Asking for the exact item (X alone) pays for the scrub; asking for the projection (X) does not.
    """
    states = {"blank": [Action("roll", 1.0, (("X", 1), ("XJ", 1)))], "XJ": [Action("scrub", 4.0, (("X", 1),))], "X": []}
    from crafting_system.solver import TabularModel

    def cost_of(want, reaches):
        model = TabularModel({"X"}, states)
        acquisition = Acquisition(model, reaches=reaches)
        return solve(acquisition, [("in", want, "blank")]).values[("in", want, "blank")]

    exact = cost_of("X", lambda s, w: s == w)
    projected = cost_of("X", lambda s, w: s[0] == w)  # the projection of "XJ" is "X"
    assert exact == pytest.approx(1.0 + 0.5 * 4.0)
    assert projected == pytest.approx(1.0)


def tiny_awakener(projection):
    """A receiver that needs the Crusader mod ES, a Shaper donor that must carry AM, and the Awakener's Orb joining them.

    The receiver rolls ES by Chaos Orb; the donor rolls AM alone, AM with a junk mod, or nothing, or is bought with AM alone.
    The orb takes the receiver with ES and a donor with AM and gives the goal with chance 1/2, else the receiver is rerolled (R0).
    `projection` True asks for the donor as the projection the orb reads (AM, whatever else is on it), False for AM alone.
    """
    from crafting_system.solver import TabularModel

    table = {
        "R0": [Action("chaos", 1.0, (("R1", 1), ("R0", 3)))],
        "R1": [Action("awakener", 5.0, (("G", 1), ("R0", 1)), (Need("D0", "AM"),))],
        "D0": [Action("chaos-d", 1.0, (("AM", 1), ("AM+J", 1), ("D0", 2))), Action("buy", 12.0, (("AM", 1),))],
        "AM+J": [Action("annul", 3.0, (("AM", 1), ("J", 1)))],
        "J": [Action("scour", 1.0, (("D0", 1),))],
    }
    model = TabularModel({"G"}, table)
    reaches = (lambda s, want: s.startswith(want)) if projection else (lambda s, want: s == want)
    acquisition = Acquisition(model, reaches=reaches)
    return solve(acquisition, [acquisition.start("R0")]), acquisition


@pytest.mark.parametrize("projection", [True, False])
def test_the_tiny_awakener_case_equals_brute_force_with_the_donor_as_a_projection_or_whole(projection):
    solution, acquisition = tiny_awakener(projection)
    start = acquisition.start("R0")
    spec = product_spec(acquisition, start)
    best = brute_force_inputs(spec)
    for state, value in solution.values.items():
        if state in best and best[state] is not None:
            assert value == pytest.approx(float(best[state]), rel=1e-9), state
    # AM alone is a state "AM"; the projection also accepts "AM+J" (the orb never reads the junk), so it is never dearer
    if projection:
        assert solution.values[("in", "AM", "D0")] == pytest.approx(2.0, rel=1e-9)  # v = 1 + v / 2
    else:
        # by hand: v = 1 + w / 4 + v / 2 and w = 3 + (1 + v) / 2 (annul AM+J at 3: AM, or J then scour at 1), so v = 5
        assert solution.values[("in", "AM", "D0")] == pytest.approx(5.0, rel=1e-9)

