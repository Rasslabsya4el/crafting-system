"""Pruning offers by twins and by a lower bound on the cost, with a certificate (ticket #118, piece E).

`cli._bound_prune.solve_pruned` solves the plan on a small set of the offers and proves that the others
cannot improve any value (its module text has the argument). This file checks:

1. the pieces: which goal leaves are necessary, the set U, the kind of each offer, the best-first rho;
2. EXACTNESS on a small real world: the Sorcerer Boots pool cut to seven families, with the real fossil
   records and a few hundred fossil sets (every set of one or two fossils and some of three and four,
   Tangled, Fractured, Hollow and Glyphic among them), at made-up prices that are fixed by a hash of the
   name. The plan with the pruning has the mean, and at every state it solves the value, of the plan
   without it, and its policy picks at each state an action whose cost-to-go (by the values of the plan
   without pruning) is that value; start items with and without a fractured mod, four goals, and a world
   with bench crafts;
3. a deliberately wrong bound is caught by that comparison (the certificate trusts `reach_bound`: it
   proves the offers left out against the bounds, it does not check the bounds);
4. the routes R10, R11 and R05 on the real dump give the mean and the policy that the unmodified code gave
   (`tests/golden/plans_118.json`);
5. the plan still prices and evaluates an offer the pruning left out.

The real-data tests need the cached dump (`CRAFTING_CACHE_DIR`) and skip cleanly without it, as in CI. No
test asserts a run time (ADR-0014).
"""

import datetime
import hashlib
import json
import random
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from abstraction_support import real_game_data
from test_abstraction_b1_real import LEVEL, rolled, subset
from test_abstraction_fossil_real import BASE, FORCED, FRACTURED

from crafting_system.abstraction import Abstraction, AtLeast, Goal, Status, Wanted, keeps_shape
from crafting_system.actions import (
    BenchCraft,
    ChaosOrb,
    RemoveCraftedMods,
    ScouringOrb,
    fossil_actions,
)
from crafting_system.actions.fossil import CHAOTIC_RESONATOR_SOCKETS
from crafting_system.cli import RESTART, Offer, _bound_prune, _plan, evaluate_route, make_plan, parse_route
from crafting_system.cli._bound_prune import (
    CRAFT,
    REROLL,
    RESTART_KIND,
    TERMINAL,
    _Entry,
    _kind_of,
    best_first_rho,
    goal_set,
    necessary_leaves,
)
from crafting_system.cli._offers import BuyStartItem, PricedOffer, offer_of, price_offers
from crafting_system.cli._prune import solver_actions
from crafting_system.items import Item, Rarity
from crafting_system.prices import PriceEntry, PriceFile, load_price_file
from crafting_system.solver import Action as SolverAction
from crafting_system.targets import Requirement, Target, load_target

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden" / "plans_118.json"
ROUTE_PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
LIFE_CRAFT = "HelenaMasterIncreasedLife1"
RESTART_PRICE = 3.0


# --- 1. the pieces ---------------------------------------------------------------------------------------


def leaf(name: str) -> Wanted:
    return Wanted(frozenset({name}))


def test_necessary_leaves_are_those_under_the_requirements_or_under_all_of_n_nodes():
    a, b, c, d, e, f = (leaf(name) for name in "abcdef")
    goal = Goal((a, AtLeast(2, (b, c)), AtLeast(2, (d, AtLeast(1, (e, f))))))

    assert [leaf_.mod_ids for leaf_ in goal.leaves] == [frozenset(x) for x in "abcdef"]
    assert necessary_leaves(goal) == (0, 1, 2, 3)  # a, b, c, d; e and f sit under an AtLeast(1 of 2)


def test_an_at_least_with_k_below_n_makes_none_of_its_members_necessary():
    a, b, c = leaf("a"), leaf("b"), leaf("c")

    assert necessary_leaves(Goal((AtLeast(1, (a, b)),))) == ()
    assert necessary_leaves(Goal((c, AtLeast(2, (a, b, c))))) == (0,)
    assert necessary_leaves(Goal((AtLeast(1, (AtLeast(2, (a, b)), c)),))) == ()


def test_the_goal_set_leaves_out_a_leaf_that_passes_at_the_start():
    goal = Goal((leaf("a"), leaf("b"), leaf("c")))
    start = SimpleNamespace(status=(Status.PASSING, Status.BELOW, Status.ABSENT))

    assert goal_set(goal, start, frozenset()) == (1, 2)


def test_the_goal_set_leaves_out_a_leaf_a_bench_craft_can_finish_unless_nothing_would_remain():
    goal = Goal((leaf("a"), leaf("b")))
    start = SimpleNamespace(status=(Status.ABSENT, Status.ABSENT))

    assert goal_set(goal, start, frozenset({"a"})) == (1,)
    assert goal_set(goal, start, frozenset({"a", "b"})) == (0, 1)  # all would go: keep them all
    assert goal_set(goal, start, frozenset({"z"})) == (0, 1)


def _stub_entry(index: int, cost: float, kind=REROLL) -> _Entry:
    """An entry at level 0 (pbar 1, ratio = cost) whose offer has only a cost."""
    return _Entry(index, SimpleNamespace(cost=cost, label=f"x{index}"), kind)


def _ladder(table):
    """A `raise_level` that gives entry i the bound table[i][1] at level 1 and the exact chance table[i][2] at level 2."""
    asked: list[tuple[int, int]] = []

    def raise_level(entry, level):
        asked.append((entry.index, level))
        entry.level = level
        entry.pbar = table[entry.index][1] if level == 1 else table[entry.index][2]

    return asked, raise_level


def test_the_best_first_rho_stops_at_a_craft_that_is_smaller_than_every_bound():
    table = [(1.0, Fraction(1, 10), Fraction(1, 20)), (3.0, Fraction(1, 2), Fraction(1, 4)), (6.0, Fraction(1, 2), Fraction(1, 5))]
    entries = [_stub_entry(i, cost) for i, (cost, _, _) in enumerate(table)]
    entries.append(_stub_entry(3, 2.0, kind=CRAFT))  # a craft that can finish a leaf: pbar 1, ratio 2
    asked, raise_level = _ladder(table)

    rho = best_first_rho(entries, raise_level)

    assert rho == pytest.approx(2.0 * (1 - _bound_prune.SLACK))
    assert asked == [(0, 1)]  # only entry 0 (ratio 1) was below the craft; its loose bound (ratio 10) put it past 2


def test_the_best_first_rho_raises_the_levels_of_the_few_that_could_be_the_least():
    table = [
        (1.0, Fraction(1, 10), Fraction(1, 20)),  # ratios: level 0: 1, level 1: 10, level 2: 20
        (3.0, Fraction(1, 2), Fraction(1, 4)),  # 3, 6, 12
        (6.0, Fraction(1, 2), Fraction(1, 5)),  # 6, 12, 30
        (11.0, Fraction(1, 1), Fraction(1, 1)),  # 11, 11, 11
        (8.0, Fraction(1, 5), Fraction(1, 5)),  # 8, 40, 40
    ]
    entries = [_stub_entry(i, cost) for i, (cost, _, _) in enumerate(table)]
    asked, raise_level = _ladder(table)

    rho = best_first_rho(entries, raise_level)

    truth = min(cost / float(exact) for cost, _, exact in table)
    assert truth == 11.0
    assert rho == pytest.approx(truth * (1 - _bound_prune.SLACK))
    assert (0, 2) in asked and (1, 2) in asked  # the two whose exact ratio (20, 12) had to be seen to pass 11
    assert (4, 2) not in asked  # entry 4: the loose ratio 40 is past 11 already
    assert (3, 2) in asked  # entry 3 is the least in the end, so it was brought to the exact level to stop the loop


def test_a_restart_never_lowers_rho_and_is_an_infinite_ratio():
    entry = _Entry(0, SimpleNamespace(cost=5.0), "restart", 0, Fraction(0))

    assert entry.ratio == float("inf")
    assert best_first_rho([entry], lambda *_: None) == pytest.approx(_bound_prune.HUGE * (1 - _bound_prune.SLACK))


# --- the small real world ----------------------------------------------------------------------------------


def made_up_price(name: str, low: float, high: float) -> float:
    """The made-up prices of the timing runs: a hash of the name, so that they never move."""
    unit = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return round(low + (high - low) * unit, 2)


def made_up_prices(data, *extra: str) -> PriceFile:
    prices = {record.name: PriceEntry(made_up_price(record.name, 0.6, 12.0), "made-up") for record in data.fossils.values() if record.name}
    sockets = {1: 0.5, 2: 1.6, 3: 4.0, 4: 12.0}
    for name, count in CHAOTIC_RESONATOR_SOCKETS.value.items():
        prices[f"{name} Chaotic Resonator"] = PriceEntry(sockets[count], "made-up")
    for name in extra:
        prices[name] = PriceEntry(0.5, "made-up")
    return PriceFile("Test", datetime.datetime(2026, 10, 31, tzinfo=datetime.UTC), 300.0, prices)


def world_data(real, families: set[str]):
    """The boots pool cut to `families`, with the mods the fossils add or force, the corrupted-essence mods and the life craft."""
    item_class = real.base_items[BASE].item_class
    corruption = {e.mod_for(item_class) for e in real.essences.values() if e.is_corruption_only} - {None}
    fossil_mods = {mod for record in real.fossils.values() for mod in (*record.added_mods, *record.forced_mods)}
    return subset(real, BASE, families, {FORCED, FRACTURED, LIFE_CRAFT} | corruption | fossil_mods)


FAMILIES = {"IncreasedLife", "MovementVelocity", "IncreasedMana", "Intelligence", "FireResistance", "StunRecovery", "ColdResistance"}


@pytest.fixture(scope="module")
def real():
    return real_game_data()


@pytest.fixture(scope="module")
def world(real):
    data = world_data(real, FAMILIES)
    return SimpleNamespace(
        data=data,
        plain=Item.build(data, base_id=BASE, item_level=LEVEL, rarity=Rarity.RARE),
        fractured=Item.build(data, base_id=BASE, item_level=LEVEL, rarity=Rarity.RARE, mods=(rolled(data, FRACTURED, fractured=True),)),
        prices=made_up_prices(data, "Orb of Alteration", "Orb of Scouring"),
    )


def requirement(data, family: str, **limits) -> Requirement:
    ids = frozenset(mod.id for mod in data.mods.values() if mod.families == (family,))
    return Requirement(family, None, ids, **limits)


def goals(data):
    life, speed = requirement(data, "IncreasedLife"), requirement(data, "MovementVelocity")
    life1, speed1 = requirement(data, "IncreasedLife", min_tier=1), requirement(data, "MovementVelocity", min_tier=1)
    fire1, cold = requirement(data, "FireResistance", min_tier=1), requirement(data, "ColdResistance")
    from crafting_system.targets import KOfN

    return {
        "two": (life, speed),
        "two-top-tier": (life1, speed1),
        "three-top-tier": (life1, speed1, fire1),
        "with-an-either-or": (life1, speed1, KOfN(1, (fire1, cold))),
    }


def fossil_sets(data, item, *, fractured: bool = True):
    """Every set of one or two fossils, and 8 each of Tangled, Fractured, Hollow and Glyphic sets of three or four."""
    everything = fossil_actions(data, item)
    chosen = [action for action in everything if len(action.fossils) <= 2]
    rng = random.Random(118)
    for special in ("Tangled", "Fractured", "Hollow", "Glyphic"):
        if special == "Fractured" and not fractured:
            continue
        bigger = [a for a in everything if len(a.fossils) > 2 and f"{special} Fossil" in a.fossils]
        chosen += rng.sample(bigger, min(8, len(bigger)))
    if not fractured:
        chosen = [a for a in chosen if "Fractured Fossil" not in a.fossils]
    return list(dict.fromkeys(chosen))


def offers_of(data, item, actions):
    return [offer_of(action, action.label(data), data, item) for action in [ChaosOrb(), *actions]]


class Planned:
    """A plan with the pruning and the same plan without it."""

    def __init__(self, data, target, prices, offers, start_price=None):
        self.data = data
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(_plan, "PRUNE_BOUND", True)
            self.pruned = make_plan(data, target, prices, offers=offers, start_price=start_price)
            patch.setattr(_plan, "PRUNE_BOUND", False)
            self.whole = make_plan(data, target, prices, offers=offers, start_price=start_price)

    def cost_to_go(self, state, action) -> float:
        """The cost of `action` at `state` plus the expected value after it, by the values of the plan WITHOUT pruning."""
        plan = self.whole
        built = _plan.offer_action(plan.abstraction, plan.offer_of(action), state, plan.start)
        total = sum(weight for _, weight in built.outcomes)
        return built.cost + sum(weight * plan.solution.values[successor] for successor, weight in built.outcomes) / total


def assert_exact(planned: Planned) -> None:
    """Same mean, same value at every state the pruned plan solved, and a policy that is optimal by the unpruned values."""
    pruned, whole = planned.pruned, planned.whole
    assert pruned.mean_remaining == pytest.approx(whole.mean_remaining, rel=1e-9)
    assert pruned.solution.values.keys() <= whole.solution.values.keys()
    for state, value in pruned.solution.values.items():
        assert value == pytest.approx(whole.solution.values[state], rel=1e-9), state
    assert pruned.policy, "the plan has no policy"
    for state, action in pruned.policy.items():
        assert planned.cost_to_go(state, action) == pytest.approx(whole.solution.values[state], rel=1e-9), (state, action.label)


CASES = [(start, goal) for start in ("plain", "fractured") for goal in ("two", "two-top-tier", "three-top-tier", "with-an-either-or")]


@pytest.fixture(scope="module")
def planned(world):
    cache: dict = {}

    def get(start: str, goal: str, *, with_fractured_sets: bool = True, start_price: float | None = None) -> Planned:
        key = (start, goal, with_fractured_sets, start_price)
        if key not in cache:
            item = getattr(world, start)
            target = Target(BASE, LEVEL, frozenset(), goals(world.data)[goal], item)
            actions = fossil_sets(world.data, item, fractured=with_fractured_sets)
            cache[key] = Planned(world.data, target, world.prices, offers_of(world.data, item, actions), start_price)
        return cache[key]

    return get


# --- 2. exactness ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(("start", "goal"), [case for case in CASES if case[0] == "fractured"])
def test_with_a_fractured_mod_on_the_start_the_pruned_plan_is_the_plan_without_pruning(planned, start, goal):
    result = planned(start, goal)
    pruned = result.pruned.pruned

    assert_exact(result)
    assert pruned is not None and not pruned.fell_back, pruned.why
    assert len(pruned.twins) + len(pruned.bounded) + len(pruned.inapplicable) > len(result.pruned.offers) / 2
    assert len(pruned.used) < len(result.pruned.offers) / 5


@pytest.mark.parametrize(("start", "goal"), [case for case in CASES if case[0] == "plain"])
def test_without_a_fractured_mod_and_without_fractured_sets_the_pruned_plan_is_the_plan_without_pruning(planned, start, goal):
    result = planned(start, goal, with_fractured_sets=False)
    pruned = result.pruned.pruned

    assert_exact(result)
    assert pruned is not None and not pruned.fell_back, pruned.why
    assert len(pruned.twins) + len(pruned.bounded) + len(pruned.inapplicable) > len(result.pruned.offers) / 2


def test_a_fractured_fossil_set_in_the_model_moves_the_item_to_another_shape_and_the_pruning_steps_back(world):
    """A Fractured set cheaper than the plan cannot be proved dear, so it enters the model; then the item can
    change shape and the bound (read on the start's shape) no longer holds: the pruning keeps only the twins."""
    item = world.plain
    prices = PriceFile(
        "Test", world.prices.fetched_at, 300.0, {**world.prices.prices, "Fractured Fossil": PriceEntry(0.01, "made-up")}
    )
    target = Target(BASE, LEVEL, frozenset(), goals(world.data)["two-top-tier"], item)
    actions = [a for a in fossil_actions(world.data, item) if len(a.fossils) <= 2][:40]
    actions.append(next(a for a in actions if a.fossils == ("Fractured Fossil",)))
    offers = offers_of(world.data, item, list(dict.fromkeys(actions)))
    abstraction = Abstraction(world.data, Goal.from_target(target), BASE, LEVEL)
    start = abstraction.compress(item)
    priced, _ = price_offers(offers, prices)

    found = _bound_prune.solve_pruned(abstraction, start, priced, item, min_offers=0)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(_plan, "PRUNE_BOUND", False)
        whole = make_plan(world.data, target, prices, offers=offers)

    assert found.fell_back and "shape" in found.why
    assert found.solution.values[start] == pytest.approx(whole.mean_remaining, rel=1e-9)
    assert len(found.used) == len(priced) - len(found.twins)


def test_the_pruning_has_tangled_and_fractured_sets_among_the_offers(planned):
    result = planned("plain", "two")  # Fractured sets are listed only for an item without a fractured mod
    fossils = [priced.offer.action.fossils for priced in result.pruned.offers if priced.label != "Chaos Orb"]

    assert_exact(result)
    assert sum("Tangled Fossil" in names for names in fossils) >= 5
    assert sum("Fractured Fossil" in names for names in fossils) >= 5
    assert sum("Hollow Fossil" in names for names in fossils) >= 5 and sum("Glyphic Fossil" in names for names in fossils) >= 5
    assert len(result.pruned.pruned.twins) + len(result.pruned.pruned.bounded) > len(result.pruned.offers) / 2
    # an item with a fractured mod is offered no Fractured set at all
    assert not any("Fractured Fossil" in names for names in (priced.offer.action.fossils for priced in planned("fractured", "two").pruned.offers if priced.label != "Chaos Orb"))


def test_a_restart_is_kept_and_the_plan_stays_exact(planned):
    result = planned("fractured", "three-top-tier", start_price=RESTART_PRICE)

    assert_exact(result)
    assert RESTART in {priced.label for priced in result.pruned.offers}
    assert RESTART in {priced.label for priced in result.pruned.pruned.used}


def test_the_plan_keeps_every_priced_offer_and_says_what_it_left_out(planned):
    result = planned("fractured", "two-top-tier")
    plan = result.pruned
    reasons = {left.reason: left.labels for left in plan.left_out}
    labels = {priced.label for priced in plan.offers}

    assert len(plan.offers) == len(result.whole.offers)
    assert reasons["same outcome as a cheaper offer"] == tuple(dropped for dropped, _ in plan.pruned.twins)
    assert reasons["proved never better: even its best case costs more than the plan"] == plan.pruned.bounded
    assert set(reasons["same outcome as a cheaper offer"]) | set(plan.pruned.bounded) <= labels
    assert not {priced.label for priced in plan.pruned.used} & set(plan.pruned.bounded)
    assert plan.pruned.rho > 0 and plan.pruned.j_max >= plan.pruned.rho * (1 - 1e-9)
    assert result.whole.pruned is None and not result.whole.left_out


def test_a_route_may_name_an_offer_the_pruning_left_out_and_it_is_priced_and_evaluated(planned, world):
    plan = planned("fractured", "two").pruned
    dropped, kept = plan.pruned.twins[0]
    route = parse_route(f"name: names a twin\nrules:\n  - do: {dropped}\n", plan, world.data)

    result = evaluate_route(plan, route, world.data)

    assert dropped not in {priced.label for priced in plan.pruned.used}
    assert not result.gaps
    assert {action.label for action in result.policy.values()} == {dropped}
    assert plan.offer_of(result.policy[plan.start]).cost == next(p for p in plan.offers if p.label == dropped).cost


def test_the_rounds_grow_the_set_when_the_first_guess_is_too_small(world, monkeypatch):
    """With one offer in the first round and two more per round the certificate still closes on the same plan."""
    monkeypatch.setattr(_bound_prune, "SMALL_START", 1)
    monkeypatch.setattr(_bound_prune, "PER_ROUND", 2)
    item = world.fractured
    target = Target(BASE, LEVEL, frozenset(), goals(world.data)["with-an-either-or"], item)
    offers = offers_of(world.data, item, fossil_sets(world.data, item)[:120])

    result = Planned(world.data, target, world.prices, offers)

    assert_exact(result)
    assert not result.pruned.pruned.fell_back, result.pruned.pruned.why


def test_the_last_round_takes_every_offer_that_fails_and_still_closes(world, monkeypatch):
    monkeypatch.setattr(_bound_prune, "SMALL_START", 1)
    monkeypatch.setattr(_bound_prune, "PER_ROUND", 1)
    item = world.fractured
    target = Target(BASE, LEVEL, frozenset(), goals(world.data)["three-top-tier"], item)
    offers = offers_of(world.data, item, fossil_sets(world.data, item)[:120])

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(_plan, "PRUNE_BOUND", True)
        plan = make_plan(world.data, target, world.prices, offers=offers)
    whole = Planned(world.data, target, world.prices, offers).whole

    assert plan.mean_remaining == pytest.approx(whole.mean_remaining, rel=1e-9)


def test_a_model_with_no_proper_policy_in_the_first_round_gets_more_offers_not_a_wrong_answer(world, monkeypatch):
    """Only the cheapest offers at first: when they cannot reach the goal, the next round adds more."""
    monkeypatch.setattr(_bound_prune, "SMALL_START", 0)
    item = world.fractured
    target = Target(BASE, LEVEL, frozenset(), goals(world.data)["two-top-tier"], item)
    offers = offers_of(world.data, item, fossil_sets(world.data, item)[:120])

    result = Planned(world.data, target, world.prices, offers)

    assert_exact(result)


def test_too_few_rounds_step_back_to_the_whole_model(world, monkeypatch):
    monkeypatch.setattr(_bound_prune, "SMALL_START", 0)
    monkeypatch.setattr(_bound_prune, "PER_ROUND", 1)
    item = world.fractured
    target = Target(BASE, LEVEL, frozenset(), goals(world.data)["three-top-tier"], item)
    offers = offers_of(world.data, item, fossil_sets(world.data, item)[:120])
    abstraction = Abstraction(world.data, Goal.from_target(target), BASE, LEVEL)
    start = abstraction.compress(item)
    priced, _ = price_offers(offers, world.prices)

    found = _bound_prune.solve_pruned(abstraction, start, priced, item, rounds=1)

    assert found.fell_back and "rounds" in found.why
    assert len(found.used) == len(priced) - len(found.twins)


def test_fewer_than_min_offers_are_solved_whole(world):
    item = world.fractured
    target = Target(BASE, LEVEL, frozenset(), goals(world.data)["two"], item)
    offers = offers_of(world.data, item, fossil_sets(world.data, item)[:10])

    plan = make_plan(world.data, target, world.prices, offers=offers)

    assert plan.pruned is None and not plan.left_out


# --- the bench: a goal leaf a craft can finish ---------------------------------------------------------------


@pytest.fixture(scope="module")
def bench(real):
    """A smaller pool (the states multiply with the junk the bench actions read), the life craft and Remove Crafted Mods."""
    data = world_data(real, {"IncreasedLife", "MovementVelocity", "IncreasedMana", "FireResistance"})
    item = Item.build(data, base_id=BASE, item_level=LEVEL, rarity=Rarity.RARE, mods=(rolled(data, FRACTURED, fractured=True),))
    actions = [BenchCraft(LIFE_CRAFT), RemoveCraftedMods(), *fossil_sets(data, item)[:90]]
    prices = made_up_prices(data, "Orb of Alteration", "Orb of Scouring")
    life, speed1 = requirement(data, "IncreasedLife"), requirement(data, "MovementVelocity", min_tier=1)
    target = Target(BASE, LEVEL, frozenset(), (life, speed1), item)
    offers = [offer_of(ChaosOrb(), "Chaos Orb", data, item)] + [offer_of(a, a.label(data), data, item) for a in actions]
    return SimpleNamespace(data=data, item=item, target=target, offers=offers, prices=prices)


def test_with_bench_crafts_offered_the_pruned_plan_is_the_plan_without_pruning(bench):
    result = Planned(bench.data, bench.target, bench.prices, bench.offers)
    pruned = result.pruned.pruned

    assert_exact(result)
    assert not pruned.fell_back, pruned.why
    assert {"Bench craft +# to maximum Life", "Remove Crafted Mods"} <= {priced.label for priced in pruned.used}
    assert len(pruned.twins) + len(pruned.bounded) + len(pruned.inapplicable) > len(result.pruned.offers) / 2


def test_the_leaf_a_craft_can_finish_is_dropped_from_the_set_the_bound_is_read_on(bench):
    abstraction = Abstraction(bench.data, Goal.from_target(bench.target), BASE, LEVEL, [BenchCraft(LIFE_CRAFT), RemoveCraftedMods()])
    start = abstraction.compress(bench.item)
    crafted = frozenset(BenchCraft(LIFE_CRAFT).adds(bench.data, bench.item).named)

    assert goal_set(abstraction.goal, start, crafted) == (1,)  # life is leaf 0: the craft finishes it
    assert goal_set(abstraction.goal, start, frozenset()) == (0, 1)


def test_with_bench_crafts_and_small_rounds_the_certificate_still_closes_on_the_same_plan(bench, monkeypatch):
    monkeypatch.setattr(_bound_prune, "SMALL_START", 1)
    monkeypatch.setattr(_bound_prune, "PER_ROUND", 3)

    result = Planned(bench.data, bench.target, bench.prices, bench.offers)

    assert_exact(result)


# --- the kind of an offer -----------------------------------------------------------------------------------


def priced_of(world, action, label=None):
    data = world.data
    offer = offer_of(action, label or action.label(data), data, world.fractured)
    (priced,), _ = price_offers([offer], world.prices)
    return priced


def test_the_kind_of_an_offer_follows_what_the_action_declares(world):
    data, item = world.data, world.fractured
    fossil = next(a for a in fossil_actions(data, item) if len(a.fossils) == 1)
    restart = PricedOffer(Offer(RESTART, BuyStartItem(item), {}, shares=False), 5.0, ())
    craft = priced_of(world, BenchCraft(LIFE_CRAFT))

    assert _kind_of(data, item, restart) == (RESTART_KIND, frozenset())
    assert _kind_of(data, item, priced_of(world, ChaosOrb())) == (REROLL, frozenset())
    assert _kind_of(data, item, priced_of(world, fossil)) == (REROLL, frozenset())
    assert _kind_of(data, item, craft) == (CRAFT, frozenset({LIFE_CRAFT}))
    assert _kind_of(data, item, priced_of(world, RemoveCraftedMods())) == (CRAFT, frozenset())


def test_keeps_shape_tells_a_reroll_from_an_action_that_fractures_or_changes_the_rarity(world):
    data = world.data
    ab = Abstraction(data, Goal((Wanted(frozenset({"x"})),)), BASE, LEVEL)
    bare = ab.compress(world.plain)
    fractures = next(a for a in fossil_actions(data, world.plain) if a.fossils == ("Fractured Fossil",))
    other = next(a for a in fossil_actions(data, world.plain) if len(a.fossils) == 1 and a.fossils != ("Fractured Fossil",))

    assert keeps_shape(ab, bare, ChaosOrb())
    assert keeps_shape(ab, bare, other)
    assert not keeps_shape(ab, bare, fractures)
    assert not keeps_shape(ab, bare, ScouringOrb())  # a rare item with no mod scours to a normal one


def test_the_kind_of_a_scouring_orb_is_a_reroll_until_its_shape_is_read(world):
    """A Scouring Orb reads no junk, so it starts as a reroll; `raise_level` makes it terminal (it moves the rarity)."""
    data, item = world.data, world.plain
    abstraction = Abstraction(data, Goal.from_target(Target(BASE, LEVEL, frozenset(), (requirement(data, "IncreasedLife"),), item)), BASE, LEVEL)
    start = abstraction.compress(item)
    priced = [priced_of(world, ScouringOrb()), *(priced_of(world, a) for a in fossil_actions(data, item)[:45])]

    found = _bound_prune.solve_pruned(abstraction, start, priced, item)

    assert "Orb of Scouring" not in {p.label for p in found.used} or found.fell_back
    assert found.solution.values[start] > 0


# --- 3. a wrong bound is caught -----------------------------------------------------------------------------


def test_a_wrong_bound_gives_a_wrong_plan_and_the_comparison_with_the_unpruned_plan_catches_it(world, monkeypatch):
    """The certificate proves the offers left out against the bounds it is given; it does not check them.

    So the safeguard is the bound's own tests (tests/test_abstraction_bound.py: never below the exact chance)
    and this comparison. Here `reach_bound` is made to say 0 for the best offer ("it can never reach the
    goal"): the best offer is then dropped as proved dear, and the plan is dearer than the true optimum.
    """
    item = world.fractured
    target = Target(BASE, LEVEL, frozenset(), goals(world.data)["two-top-tier"], item)
    offers = offers_of(world.data, item, fossil_sets(world.data, item)[:120])
    honest = Planned(world.data, target, world.prices, offers)
    best = honest.whole.policy[honest.whole.start].label
    best_action = honest.whole.offer_of(honest.whole.policy[honest.whole.start]).offer.action
    real_bound = _bound_prune.reach_bound

    def lying(abstraction, state, action, leaves, **kwargs):
        return Fraction(0) if action == best_action else real_bound(abstraction, state, action, leaves, **kwargs)

    monkeypatch.setattr(_bound_prune, "reach_bound", lying)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(_plan, "PRUNE_BOUND", True)
        wrong = make_plan(world.data, target, world.prices, offers=offers)

    assert wrong.mean_remaining > honest.whole.mean_remaining * (1 + 1e-6), best
    assert best not in {priced.label for priced in wrong.pruned.used}
    assert honest.pruned.mean_remaining == pytest.approx(honest.whole.mean_remaining, rel=1e-9)


# --- the cache of built actions -----------------------------------------------------------------------------


def test_the_cache_of_built_actions_builds_each_state_and_offer_once(world, monkeypatch):
    item = world.fractured
    abstraction = Abstraction(world.data, Goal.from_target(Target(BASE, LEVEL, frozenset(), goals(world.data)["two"], item)), BASE, LEVEL)
    start = abstraction.compress(item)
    priced, _ = price_offers(offers_of(world.data, item, fossil_sets(world.data, item)[:6]), world.prices)
    built = []
    real_build = _plan.offer_action
    monkeypatch.setattr(_plan, "offer_action", lambda *args, **kwargs: built.append(args[1].label) or real_build(*args, **kwargs))
    cache: dict = {}

    first = solver_actions(abstraction, priced, start, start, cache=cache)
    count = len(built)
    second = solver_actions(abstraction, priced, start, start, cache=cache)
    more = solver_actions(abstraction, priced[:3], start, start, cache=cache)

    assert count > 0 and len(built) == count
    assert [a.label for a in second] == [a.label for a in first]
    assert {a.label for a in more} <= {a.label for a in first}
    assert all(isinstance(a, SolverAction) for a in second)
    assert len(solver_actions(abstraction, priced, start, start)) == len(first)  # no cache: same actions
    assert len(built) > count


# --- 4. the routes on the real dump ---------------------------------------------------------------------------

ROUTES = ["r11-reservation-helmet", "r10-fractured-boots", "r05-strength-ring"]


@pytest.fixture(scope="module")
def golden():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module", params=ROUTES)
def route_plan(request, real):
    target = load_target(ROOT / "examples" / "targets" / f"{request.param}.yaml", real)
    return request.param, make_plan(real, target, load_price_file(ROUTE_PRICES))


def test_the_routes_give_the_mean_and_the_policy_the_code_before_the_pruning_gave(route_plan, golden):
    """Mean to 1e-9 and the same action at every state. The golden file was written from the unmodified main branch."""
    stem, plan = route_plan
    expected = golden[stem]

    assert repr(plan.start) == expected["start"]
    assert plan.mean_remaining == pytest.approx(expected["mean_remaining"], rel=1e-9)
    # The pruned model leaves out offers that are never better, so it may reach FEWER states than the golden
    # plan (R05: 262 of 597); every state it does solve has the action the golden plan has there.
    assert len(plan.solution.values) <= expected["states"]
    policy = {repr(state): action.label for state, action in plan.policy.items()}
    assert policy.keys() <= expected["policy"].keys()
    assert {state: label for state, label in policy.items() if label != expected["policy"][state]} == {}
    if plan.pruned is None or not plan.pruned.fell_back and not plan.pruned.bounded:
        assert len(plan.solution.values) == expected["states"]


def test_the_route_with_more_than_the_minimum_of_offers_ran_the_pruning(route_plan):
    stem, plan = route_plan
    if len(plan.offers) < _plan.MIN_OFFERS_TO_PRUNE:
        assert plan.pruned is None
    else:
        assert plan.pruned is not None, stem
        print(f"\n{stem}: {len(plan.offers)} offers, twins {len(plan.pruned.twins)}, bounded {len(plan.pruned.bounded)}, "
              f"used {len(plan.pruned.used)}, rounds {plan.pruned.rounds}, fell back {plan.pruned.fell_back}")


# --- 5. R12 through the fixture is unchanged: tests/test_cli_plan.py and tests/test_prune_equal.py hold it ------
