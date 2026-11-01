"""The two shapes of the imprint state against brute force and the exact LP (ADR-0059, ticket #218).

The truth is a literal game written out here and not taken from `imprint_prototype`: a state is the item's base state
and the imprints it holds as a multiset (a duplicate is allowed, a throw-away costs a nominal amount), every rule of
ADR-0034 is one action, and the optimum is found by brute force over every stationary policy (`brute_force_inputs`, exact
fractions) where the game is small enough and by the Bellman LP (`lp_values_inputs`, HiGHS) where it is not. Shape A
(`WithImprints`) and shape B (`ImprintAndTry`) are then solved by `solver.solve` and compared with it.

Parts: the toy loop of the ticket (one risky action, imprint priced at 1) against brute force and closed forms; R15's and
R17's loops at toy scale; a seeded fuzz of random graphs (A equals the multiset truth, B is never cheaper than A);
the charge the first reading of ADR-0013 would make on every restore; the refusals; the composition with `Acquisition`
(a donor made with imprints); and the state counts per extra imprint.
"""

import random
from fractions import Fraction

import pytest
from imprint_prototype import RESTORE_COST, ImprintAndTry, WithImprints, all_bodies, count_states, spec_of
from ssp_input_oracles import brute_force_inputs, lp_values_inputs, to_model

from crafting_system.solver import Acquisition, Action, Need, Outcome, TabularModel, solve

EPS = Fraction(RESTORE_COST)
CLOSE = 1e-4  # the nominal restore and throw-away costs move a value by a few millionths


def act(label, cost, *outcomes, inputs=()):
    return Action(label, cost, tuple(outcomes), tuple(inputs))


def value_of(model, start):
    solution = solve(model, [start])
    return solution.values[start]


def truth_spec(base, start, *, price, limit, imprintable, restorable=lambda s: True):
    """The game of ADR-0034 as an explicit `(goals, table)`: the item's state and a multiset of imprints, nothing shared with the layers."""
    goals, table = base
    out_goals, out = set(), {}
    stack, seen = [(start, ())], set()
    while stack:
        state = stack.pop()
        if state in seen:
            continue
        seen.add(state)
        s, held = state
        if s in goals:
            out_goals.add(state)
            continue
        rows = []
        for label, cost, outcomes, _ in table.get(s, []):
            rows.append((label, cost, [((t, held if restorable(t) else ()), w) for t, w in outcomes], []))
        if imprintable(s) and len(held) < limit:
            rows.append((("imprint",), Fraction(price), [((s, tuple(sorted(held + (s,), key=repr))), 1)], []))
        for h in sorted(set(held), key=repr):
            rest = list(held)
            rest.remove(h)
            rest = tuple(rest)
            rows.append((("throw", h), EPS, [((s, rest), 1)], []))
            if restorable(s):
                rows.append((("restore", h), EPS, [((h, rest), 1)], []))
        out[state] = rows
        for row in rows:
            stack.extend(t for t, _ in row[2])
    return out_goals | {state for state in seen if state[0] in goals}, out


# --- 1. The toy loop: one risky action, the imprint priced at 1 -----------------------------------------------------------------

LOOP = ({"goal"}, {
    "base": [("try", Fraction(2), [("goal", 1), ("bad", 3)], [])],  # succeeds one time in four
    "bad": [("rebuild", Fraction(20), [("base", 1)], [])],  # the failure is undone by building the item again
})
LOOP_PRICE = 1


def loop_model():
    return to_model(LOOP)


def loop_values():
    """The closed forms: without an imprint (2 + 3/4 * 20) / (1/4); with one (1 + 2 + 3/4 * epsilon) / (1/4)."""
    return Fraction(68), (3 + Fraction(3, 4) * EPS) * 4


@pytest.mark.parametrize("limit", [1, 2])
def test_the_truth_of_the_loop_by_brute_force(limit):
    spec = truth_spec(LOOP, "base", price=LOOP_PRICE, limit=limit, imprintable=lambda s: s == "base")
    best = brute_force_inputs(spec)

    assert float(best[("base", ())]) == pytest.approx(float(loop_values()[1]), abs=CLOSE)


def test_the_closed_forms_of_the_loop():
    without, with_imprint = loop_values()
    plain = brute_force_inputs(LOOP)

    assert plain["base"] == without
    assert float(with_imprint) == pytest.approx(12.0, abs=CLOSE)


@pytest.mark.parametrize("limit", [1, 2])
def test_shape_a_agrees_with_brute_force_on_the_loop(limit):
    layer = WithImprints(loop_model(), price=LOOP_PRICE, limit=limit, imprintable=lambda s: s == "base")
    start = layer.start("base")
    truth = brute_force_inputs(truth_spec(LOOP, "base", price=LOOP_PRICE, limit=limit, imprintable=lambda s: s == "base"))
    own = brute_force_inputs(spec_of(layer, [start]))

    assert value_of(layer, start) == pytest.approx(float(truth[("base", ())]), abs=CLOSE)
    assert float(own[start]) == pytest.approx(float(truth[("base", ())]), abs=CLOSE)  # the layer's own graph is the truth's, by brute force too


def test_shape_b_agrees_with_brute_force_on_the_loop():
    layer = ImprintAndTry(
        loop_model(), price=LOOP_PRICE, imprintable=lambda s: s == "base", bodies=lambda s: [("try",)], accept=lambda s, t: t != "bad"
    )
    truth = brute_force_inputs(truth_spec(LOOP, "base", price=LOOP_PRICE, limit=1, imprintable=lambda s: s == "base"))
    own = brute_force_inputs(spec_of(layer, ["base"]))

    assert value_of(layer, "base") == pytest.approx(float(truth[("base", ())]), abs=CLOSE)
    assert float(own["base"]) == pytest.approx(12.0, abs=1e-12)  # no restore action, so no nominal cost at all


def test_the_imprint_pays_exactly_while_its_price_is_below_the_expected_rebuild_cost():
    """An imprint replaces a rebuild that happens in 3 of 4 tries and costs 20: it pays while its price is below 15."""
    values = {}
    for price in (14, 16):
        layer = WithImprints(loop_model(), price=price, limit=1, imprintable=lambda s: s == "base")
        values[price] = value_of(layer, layer.start("base"))

    assert values[14] == pytest.approx((14 + 2) * 4, abs=CLOSE)  # 64 < 68
    assert values[16] == pytest.approx(68.0, abs=CLOSE)  # the policy builds again and never imprints


def test_the_policy_of_shape_a_is_imprint_try_restore():
    layer = WithImprints(loop_model(), price=1, limit=1, imprintable=lambda s: s == "base")
    policy = solve(layer, [layer.start("base")]).policy

    assert policy[("base", frozenset())].label == ("imprint",)
    assert policy[("base", frozenset({"base"}))].label == "try"
    assert policy[("bad", frozenset({"base"}))].label == ("restore", "base")


def test_the_restore_epsilon_is_certified_to_better_than_a_millionth():
    layer = WithImprints(loop_model(), price=1, limit=1, imprintable=lambda s: s == "base")

    assert solve(layer, [layer.start("base")]).error_bound < 1e-6


# --- 2. R15 and R17 at toy scale ------------------------------------------------------------------------------------------------

#: R15: a magic bow holding the wanted mod `m` (alteration spam, one in twenty); Regal adds a mod and Annulment removes one of the
#: two at random; half the time the wanted mod is lost. A rare non-Talisman cannot be imprinted, so the imprint made at `m` has to
#: carry the item through the Regal, the Annulment and the Exalted slam after it.
R15 = TabularModel({"goal"}, {
    "start": [act("alt", 1, ("m", 1), ("start", 19))],
    "m": [act("regal", 1, ("r2", 1))],
    "r2": [act("annul", 1, ("iso", 1), ("lost", 1))],
    "iso": [act("slam", 1, ("goal", 3), ("jk", 1))],
    "lost": [act("scrap", 2, ("start", 1))],
    "jk": [act("scrap", 2, ("start", 1))],
})
R15_LABELS = ["alt", "regal", "annul", "slam", "scrap"]


def r15_layer(limit):
    return WithImprints(R15, price=1, limit=limit, imprintable=lambda s: s == "m")


def test_r15_costs_29_and_a_third_with_the_imprint_and_63_and_a_third_without():
    without = value_of(R15, "start")
    layer = r15_layer(1)
    with_imprint = value_of(layer, layer.start("start"))

    assert without == pytest.approx(190 / 3)
    assert with_imprint == pytest.approx(20 + 28 / 3 + 5e-6 / 3, abs=1e-9)  # 20 alterations, then (3.5 + 5 eps / 8) / (3/8)


def test_r15_by_the_lp_agrees_with_shape_a_for_one_to_three_imprints():
    base = spec_of(R15, ["start"])
    for limit in (1, 2, 3):
        layer = r15_layer(limit)
        truth = lp_values_inputs(truth_spec(base, "start", price=1, limit=limit, imprintable=lambda s: s == "m"))
        assert value_of(layer, layer.start("start")) == pytest.approx(truth[("start", ())], abs=CLOSE)


def test_r15_the_imprint_made_at_the_magic_state_is_held_through_the_rare_steps_and_the_slam():
    layer = r15_layer(1)
    policy = solve(layer, [layer.start("start")]).policy

    assert policy[("iso", frozenset({"m"}))].label == "slam"  # no new imprint is possible on the rare bow
    assert policy[("jk", frozenset({"m"}))].label == ("restore", "m")  # a failed slam is undone by the imprint of the magic bow
    assert policy[("lost", frozenset({"m"}))].label == ("restore", "m")


@pytest.mark.parametrize("longest, expected", [(1, 190 / 3), (2, 110 / 3), (3, 88 / 3), (4, 88 / 3)])
def test_r15_shape_b_needs_a_body_as_long_as_the_run_of_rare_steps(longest, expected):
    """Shape B is exact only when a macro-action covers the whole run from the imprint to the last risky step."""
    layer = ImprintAndTry(
        R15, price=1, imprintable=lambda s: s == "m", bodies=lambda s: all_bodies(R15_LABELS, longest), accept=lambda s, t: t in ("iso", "goal")
    )

    assert value_of(layer, "start") == pytest.approx(expected)


def test_r15_the_catalogue_of_shape_b_grows_with_the_body_while_shape_a_adds_nothing():
    layer = ImprintAndTry(R15, price=1, imprintable=lambda s: s == "m", bodies=lambda s: all_bodies(R15_LABELS, 3), accept=lambda s, t: True)
    macros = [a for a in layer.actions("m") if a.label[0] == "imprint"]

    assert len(macros) == 71  # five labels, bodies of up to three, those that do something at `m`
    assert [a.label for a in r15_layer(1).actions(("m", frozenset()))] == ["regal", ("imprint",)]


def chain(stages):
    """R17: a rare Talisman at a +2 checkpoint; each Exalted slam keeps the item at the next checkpoint one time in three, else it is junk."""
    table = {}
    for i in range(stages):
        table[f"c{i}"] = [act("exalt", 1, (f"c{i + 1}" if i + 1 < stages else "goal", 1), (f"j{i}", 2))]
        table[f"j{i}"] = [act("rebuild", 50, ("c0", 1))]
    return TabularModel({"goal"}, table)


def chain_layer(stages, limit):
    return WithImprints(chain(stages), price=1, limit=limit, imprintable=lambda s: s.startswith("c"))  # a rare Talisman: every checkpoint


@pytest.mark.parametrize("stages", [2, 3, 5])
def test_r17_costs_six_per_checkpoint_with_the_imprint_renewed_before_every_slam(stages):
    layer = chain_layer(stages, 1)

    assert value_of(layer, layer.start("c0")) == pytest.approx(6 * stages + 2e-6 * stages, abs=1e-9)  # (1 + 1) / (1/3) each, plus 2 epsilon


def test_r17_without_the_imprint_the_slams_cost_hundreds():
    base = chain(3)
    layer = chain_layer(3, 0)

    assert value_of(base, "c0") == pytest.approx(1339.0)
    assert value_of(layer, layer.start("c0")) == pytest.approx(1339.0)


@pytest.mark.parametrize("stages", [2, 3, 4])
def test_r17_shape_b_agrees_with_shape_a(stages):
    layer = ImprintAndTry(
        chain(stages), price=1, imprintable=lambda s: s.startswith("c"), bodies=lambda s: [("exalt",)], accept=lambda s, t: not t.startswith("j")
    )
    a = chain_layer(stages, 1)

    assert value_of(layer, "c0") == pytest.approx(6 * stages)
    assert value_of(a, a.start("c0")) == pytest.approx(6 * stages, abs=CLOSE)


def test_r17_by_the_lp_agrees_with_shape_a_for_one_and_two_imprints():
    base = spec_of(chain(3), ["c0"])
    for limit in (1, 2):
        layer = chain_layer(3, limit)
        truth = lp_values_inputs(truth_spec(base, "c0", price=1, limit=limit, imprintable=lambda s: s.startswith("c")))
        assert value_of(layer, layer.start("c0")) == pytest.approx(truth[("c0", ())], abs=CLOSE)


# --- 3. Random graphs ------------------------------------------------------------------------------------------------------------


def random_graph(seed, size=(3, 5)):
    """A random base game of `n` states (the goal is `n`) with a buy action everywhere so that every value is finite; a random set of imprintable states and a price."""
    rng = random.Random(seed)
    n = rng.randint(*size)
    table = {}
    for s in range(n):
        actions = []
        for index in range(rng.randint(1, 3)):
            outcomes = [(rng.randint(0, n), rng.randint(1, 5)) for _ in range(rng.randint(1, 3))]
            actions.append((f"{s}.{index}", Fraction(rng.randint(1, 8), 2), outcomes, []))
        actions.append((f"{s}.buy", Fraction(rng.choice([30, 200])), [(n, 1)], []))
        table[s] = actions
    imprintable = {s for s in range(n) if rng.random() < 0.5} or {0}
    return ({n}, table), imprintable, Fraction(rng.choice([1, 5, 10, 20]), 20)


@pytest.mark.parametrize("seed", range(24))
def test_shape_a_with_sets_equals_the_multiset_truth_by_the_lp(seed):
    base, imprintable, price = random_graph(seed)
    for limit in (1, 2):
        layer = WithImprints(to_model(base), price=float(price), limit=limit, imprintable=lambda s: s in imprintable)
        truth = lp_values_inputs(truth_spec(base, 0, price=price, limit=limit, imprintable=lambda s: s in imprintable))

        assert value_of(layer, layer.start(0)) == pytest.approx(truth[(0, ())], abs=CLOSE)


@pytest.mark.parametrize("seed", range(12))
def test_shape_b_is_never_cheaper_than_shape_a(seed):
    """A macro-action is one policy of the game, so no catalogue of bodies and no way of accepting can beat the optimum."""
    base, imprintable, price = random_graph(seed)
    model = to_model(base)
    labels = sorted({label for actions in base[1].values() for label, *_ in actions}, key=str)[:6]
    rng = random.Random(seed)
    good = {s for s in range(len(base[1]) + 1) if rng.random() < 0.5}
    layer = ImprintAndTry(
        model, price=float(price), imprintable=lambda s: s in imprintable, bodies=lambda s: all_bodies(labels, 2), accept=lambda s, t: t in good
    )
    a = WithImprints(model, price=float(price), limit=1, imprintable=lambda s: s in imprintable)

    assert value_of(layer, 0) >= value_of(a, a.start(0)) - CLOSE


def test_a_second_imprint_can_pay_though_rarely():
    """Found by search over 1,500 random graphs: two held imprints beat one by 0.019 (0.08%); a third never helps."""
    rng = random.Random(256)
    n = rng.randint(4, 8)
    table = {}
    for s in range(n):
        actions = []
        for index in range(rng.randint(1, 3)):
            outcomes = [(rng.randint(0, n), rng.randint(1, 5)) for _ in range(rng.randint(1, 3))]
            actions.append((f"{s}.{index}", Fraction(rng.randint(1, 8), 2), outcomes, []))
        actions.append((f"{s}.buy", Fraction(rng.choice([30, 200])), [(n, 1)], []))
        table[s] = actions
    imprintable = {s for s in range(n) if rng.random() < 0.5} or {0}
    price = Fraction(rng.choice([1, 5, 10, 20]), 20)
    model = to_model(({n}, table))
    values = {}
    for limit in (1, 2, 3):
        layer = WithImprints(model, price=float(price), limit=limit, imprintable=lambda s: s in imprintable)
        values[limit] = value_of(layer, layer.start(0))

    assert (n, sorted(imprintable), price) == (7, [0, 1, 2, 3, 4, 6], 1)
    assert values[1] - values[2] == pytest.approx(0.01875, abs=1e-4)
    assert values[2] == pytest.approx(values[3], abs=1e-9)


class Fallback:
    """The base game without a held set: the state is `(s, w)` and one extra option, to restore, ends the game at `w`.

    `w` is the value of an item that is back in the snapshot state with nothing held (`None`: no imprint held). An imprint
    made at `s` leaves with `w` set to the value of `s` with nothing held. This is the game of one imprint with the snapshot
    replaced by a number.
    """

    def __init__(self, base, goal, imprintable, price, empty):
        self.base, self.goal, self.imprintable, self.price, self.empty = base, goal, imprintable, price, empty

    def is_goal(self, state):
        return state[0] in (self.goal, "stop")

    def actions(self, state):
        s, w = state
        result = [
            Action(a.label, a.cost, tuple(Outcome((t, w), weight) for t, weight in a.outcomes)) for a in self.base.actions(s)
        ]
        if w is not None:
            result.append(Action("restore", RESTORE_COST + w, ((("stop", None), 1),)))
        if self.imprintable(s) and s in self.empty:
            result.append(Action("imprint", self.price, (((s, self.empty[s]), 1),)))
        return result


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 13])  # seeds 7 and 12 never reach an imprintable state
def test_one_held_imprint_enters_the_value_only_as_the_value_of_its_state(seed):
    """With one imprint the held state can be replaced by the number V(h, nothing held): a solver that walks values may carry that."""
    base, imprintable, price = random_graph(seed)
    layer = WithImprints(to_model(base), price=float(price), limit=1, imprintable=lambda s: s in imprintable)
    values = solve(layer, [layer.start(0)]).values
    empty = {s: v for (s, held), v in values.items() if not held}
    checked = 0
    for (s, held), value in values.items():
        if len(held) != 1 or s not in range(max(base[0])) or next(iter(held)) not in empty:
            continue
        number = empty[next(iter(held))]
        game = Fallback(layer._base, max(base[0]), lambda t: t in imprintable, float(price), empty)

        assert solve(game, [(s, number)]).values[(s, number)] == pytest.approx(value, abs=1e-9)
        checked += 1
    assert checked


# --- 4. What the first reading of ADR-0013 would charge --------------------------------------------------------------------------


def test_a_restore_that_acquires_a_copy_pays_for_building_the_snapshot_state_again():
    """ADR-0013's "imprint as acquiring a copy": the restore needs a second item in the snapshot state, paid by a `Need` on every restore."""
    table = {
        "start": [act("build", 20, ("base", 1))],
        "base": [act("try", 2, ("goal", 1), ("bad", 3))],
        "bad": [act("restore", RESTORE_COST, ("base", 1), inputs=[Need("start", "base")])],
    }
    product = Acquisition(TabularModel({"goal"}, table))
    copy_reading = solve(product, [product.start("base")]).values[product.start("base")]
    right = WithImprints(loop_model(), price=1, limit=1, imprintable=lambda s: s == "base")

    assert copy_reading == pytest.approx(68.0, abs=CLOSE)  # every restore costs the 20 of building the item: the imprint has bought nothing
    assert value_of(right, right.start("base")) == pytest.approx(12.0, abs=CLOSE)  # the beast, once, when the imprint is made


# --- 5. Refusals and clearing ----------------------------------------------------------------------------------------------------


def refusal_layer(**options):
    table = {
        "magic": [act("regal", 1, ("rare", 1)), act("fracture", 1, ("frac", 1)), act("combine", 1, ("fresh", 1))],
        "rare": [act("go", 1, ("goal", 1))],
        "frac": [act("go", 1, ("goal", 1))],
        "fresh": [act("go", 1, ("goal", 1))],
    }
    return WithImprints(
        TabularModel({"goal"}, table), price=1, limit=2, imprintable=lambda s: s in ("magic", "fresh"),
        restorable=lambda s: s != "frac", clears=lambda label: label == "combine", **options,
    )


def labels(layer, state):
    return [a.label for a in layer.actions(state)]


def test_an_imprint_is_offered_only_where_the_beasts_can_make_one():
    layer = refusal_layer()

    assert ("imprint",) in labels(layer, ("magic", frozenset()))
    assert ("imprint",) not in labels(layer, ("rare", frozenset()))  # a rare item that is not a Talisman
    assert ("imprint",) not in labels(layer, ("magic", frozenset({"magic"})))  # a second imprint of the same state never helps


def test_a_restore_is_refused_on_a_fractured_item_and_the_imprints_are_gone_after_the_fracture():
    layer = refusal_layer()
    held = frozenset({"magic"})
    fracture = next(a for a in layer.actions(("magic", held)) if a.label == "fracture")

    assert [o.state for o in fracture.outcomes] == [("frac", frozenset())]  # the item is lost for restoring: the state forgets its imprints
    assert ("restore", "magic") not in labels(layer, ("frac", held))
    assert ("restore", "magic") in labels(layer, ("rare", held))


def test_a_new_item_does_not_keep_the_imprints_of_the_old_one():
    layer = refusal_layer()
    combine = next(a for a in layer.actions(("magic", frozenset({"magic"}))) if a.label == "combine")

    assert [o.state for o in combine.outcomes] == [("fresh", frozenset())]


def test_at_the_limit_a_new_imprint_replaces_one():
    layer = WithImprints(chain(3), price=1, limit=1, imprintable=lambda s: s.startswith("c"))
    found = [a for a in layer.actions(("c1", frozenset({"c0"})))]

    assert [a.label for a in found] == ["exalt", ("imprint", "c0"), ("restore", "c0")]
    assert found[1].outcomes[0].state == ("c1", frozenset({"c1"}))


# --- 6. The layer sits below `Acquisition`: a donor made with imprints ----------------------------------------------------------


def test_a_donor_built_with_imprints_costs_what_the_loop_costs_and_keeps_none_when_consumed():
    table = {
        "main": [act("combine", 1, ("goal", 1), inputs=[Need("d0", "d1")])],
        "d0": [act("try", 2, ("d1", 1), ("bad", 3))],
        "bad": [act("rebuild", 20, ("d0", 1))],
    }
    base = TabularModel({"goal", "d1"}, table)
    for limit, expected in ((0, 1 + 68.0), (1, 1 + 12.0)):
        layer = WithImprints(base, price=1, limit=limit, imprintable=lambda s: s == "d0")
        product = Acquisition(layer, reaches=lambda state, want: state[0] == want[0])
        start = product.start(layer.start("main"))
        solution = solve(product, [start])

        assert solution.values[start] == pytest.approx(expected, abs=CLOSE)
        (combine,) = [a for a in product.actions(start) if a.label == "combine"]
        assert combine.extra_inputs == (("in", ("d1", frozenset()), ("d0", frozenset())),)  # the donor starts and ends with no imprint


# --- 7. State growth per extra imprint -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("stages", [2, 3, 4, 5])
def test_one_imprint_multiplies_the_states_of_the_chain_by_the_number_of_checkpoints_plus_one(stages):
    sizes = [count_states(chain_layer(stages, k), [chain_layer(stages, k).start("c0")]) for k in (0, 1)]

    assert sizes == [2 * stages, 2 * stages * (stages + 1)]


def test_the_counts_for_up_to_three_imprints_on_chains_of_three_and_five_checkpoints():
    counts = {
        stages: [count_states(chain_layer(stages, k), [chain_layer(stages, k).start("c0")]) for k in (0, 1, 2, 3)] for stages in (3, 5)
    }

    assert counts == {3: [6, 24, 42, 48], 5: [10, 60, 160, 260]}
