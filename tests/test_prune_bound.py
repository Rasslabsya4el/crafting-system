"""The fossil sets through the one envelope search, each offer carried by its own floor (tickets #118, #829).

Since #829 the bound pruning (`solve_pruned`, which solved a few offers and certified the rest) is gone: with `MIN_OFFERS` offers
or more the envelope search builds its bound on the offers that can matter and carries the others by their floors
(`_offer_kinds`, `_offer_floor`). This file checks:

1. the pieces the floors are made of: which goal leaves are necessary, the set U, the kind of each offer, the best-first rho;
2. EXACTNESS on a small real world: the Sorcerer Boots pool cut to seven families, with the real fossil records and a few
   hundred fossil sets (every set of one or two fossils and some of three and four, Tangled, Fractured, Hollow and Glyphic
   among them), at made-up prices fixed by a hash of the name. The plan of the search has the mean of the plan of the
   whole walk (the object solver with nothing left out), and at every state its policy visits the walk's value and an
   action whose cost-to-go by the walk's values is that value; start items with and without a fractured mod, four goals,
   a restart, and a world with bench crafts. The search's values off its policy are bounds, not V*, so only its policy is
   compared;
3. the routes R10, R11 and R05 on the real dump give the mean and the policy that the whole walk gave
   (`tests/golden/plans_118.json`, the three targets planned with the twins and the floors turned off, at the route prices;
   when a target file or a price changes, `UPDATE_GOLDEN=1` rewrites it on a runner).

The real-data tests need the cached dump (`CRAFTING_CACHE_DIR`) and skip cleanly without it, as in CI. No test asserts a
run time (ADR-0014).

Every test here plans with the CLASSIC offers (`cli_support.CLASSIC_KINDS`, `CLASSIC_OFFERS` below): what a target with no
`actions:` was offered before #886 turned every beta method on, so its records of before hold. It is not a test of the default plan:
with every method on, a real route gives no plan within CI's time and memory, and the heavy benchmark records those plans.
"""

import datetime
import hashlib
import json
import os
import random
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import golden_diff
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
from crafting_system.cli import RESTART, Offer, evaluate_route, make_plan, parse_route
from crafting_system.planner import _offer_kinds, _plan
from crafting_system.planner._offer_kinds import (
    CRAFT,
    REROLL,
    RESTART_KIND,
    _Entry,
    _kind_of,
    best_first_rho,
    goal_set,
    necessary_leaves,
)
from crafting_system.planner._offers import BuyStartItem, PricedOffer, offer_of, price_offers
from crafting_system.planner._pattern_bound import MIN_OFFERS
from crafting_system.planner._prune import solver_actions
from crafting_system.items import Item, Rarity
from crafting_system.prices import PriceEntry, PriceFile, load_price_file
from crafting_system.solver import Action as SolverAction
from crafting_system.targets import Requirement, StartKind, Target, load_target

CLASSIC_OFFERS = True  # tests/conftest.py: this module plans with `cli_support.CLASSIC_KINDS` (#886)

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden" / "plans_118.json"
ROUTE_PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json"
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

    assert rho == pytest.approx(2.0 * (1 - _offer_kinds.SLACK))
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
    assert rho == pytest.approx(truth * (1 - _offer_kinds.SLACK))
    assert (0, 2) in asked and (1, 2) in asked  # the two whose exact ratio (20, 12) had to be seen to pass 11
    assert (4, 2) not in asked  # entry 4: the loose ratio 40 is past 11 already
    assert (3, 2) in asked  # entry 3 is the least in the end, so it was brought to the exact level to stop the loop


def test_a_restart_never_lowers_rho_and_is_an_infinite_ratio():
    entry = _Entry(0, SimpleNamespace(cost=5.0), "restart", 0, Fraction(0))

    assert entry.ratio == float("inf")
    assert best_first_rho([entry], lambda *_: None) == pytest.approx(_offer_kinds.HUGE * (1 - _offer_kinds.SLACK))


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
    """The plan of the envelope search, with the floors on, and the plan of the whole walk with nothing left out."""

    def __init__(self, data, target, prices, offers, start_price=None):
        self.data = data
        self.searched = make_plan(data, target, prices, offers=offers, start_price=start_price, solver="envelope")
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(_plan, "PRUNE_BOUND", False)  # no twin left out, no floor: every offer at every state
            self.whole = make_plan(data, target, prices, offers=offers, start_price=start_price, solver="object")

    def cost_to_go(self, state, action) -> float:
        """The cost of `action` at `state` plus the expected value after it, by the values of the whole walk."""
        plan = self.whole
        built = _plan.offer_action(plan.abstraction, plan.offer_of(action), state, plan.start)
        total = sum(weight for _, weight in built.outcomes)
        return built.cost + sum(weight * plan.solution.values[successor] for successor, weight in built.outcomes) / total


def assert_exact(planned: Planned) -> None:
    """Same mean, and at every state of the search's policy the walk's value and an action that is optimal by the walk's values."""
    searched, whole = planned.searched, planned.whole
    assert len(searched.offers) >= MIN_OFFERS, "fewer offers than turn the floors on"
    assert searched.mean_remaining == pytest.approx(whole.mean_remaining, rel=1e-9)
    assert searched.policy, "the plan has no policy"
    for state, action in searched.policy.items():
        assert searched.solution.values[state] == pytest.approx(whole.solution.values[state], rel=1e-9), state
        assert planned.cost_to_go(state, action) == pytest.approx(whole.solution.values[state], rel=1e-9), (state, action.label)


CASES = [(start, goal) for start in ("plain", "fractured") for goal in ("two", "two-top-tier", "three-top-tier", "with-an-either-or")]


@pytest.fixture(scope="module")
def planned(world):
    cache: dict = {}

    def get(start: str, goal: str, *, with_fractured_sets: bool = True, start_price: float | None = None) -> Planned:
        key = (start, goal, with_fractured_sets, start_price)
        if key not in cache:
            item = getattr(world, start)
            start = StartKind.GIVEN if start_price is None else StartKind.BOUGHT  # a restart is the buying of a bought start item (OR-6)
            target = Target(BASE, LEVEL, frozenset(), goals(world.data)[goal], item, start=start)
            actions = fossil_sets(world.data, item, fractured=with_fractured_sets)
            cache[key] = Planned(world.data, target, world.prices, offers_of(world.data, item, actions), start_price)
        return cache[key]

    return get


# --- 2. exactness ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(("start", "goal"), [case for case in CASES if case[0] == "fractured"])
def test_with_a_fractured_mod_on_the_start_the_search_gives_the_plan_of_the_whole_walk(planned, start, goal):
    assert_exact(planned(start, goal))


@pytest.mark.parametrize(("start", "goal"), [case for case in CASES if case[0] == "plain"])
def test_without_a_fractured_mod_and_without_fractured_sets_the_search_gives_the_plan_of_the_whole_walk(planned, start, goal):
    assert_exact(planned(start, goal, with_fractured_sets=False))


def test_the_search_has_tangled_and_fractured_sets_among_the_offers(planned):
    result = planned("plain", "two")  # Fractured sets are listed only for an item without a fractured mod
    fossils = [priced.offer.action.fossils for priced in result.searched.offers if priced.label != "Chaos Orb"]

    assert_exact(result)
    assert sum("Tangled Fossil" in names for names in fossils) >= 5
    assert sum("Fractured Fossil" in names for names in fossils) >= 5
    assert sum("Hollow Fossil" in names for names in fossils) >= 5 and sum("Glyphic Fossil" in names for names in fossils) >= 5
    # an item with a fractured mod is offered no Fractured set at all
    assert not any("Fractured Fossil" in names for names in (priced.offer.action.fossils for priced in planned("fractured", "two").searched.offers if priced.label != "Chaos Orb"))


def test_a_restart_is_kept_and_the_plan_stays_exact(planned):
    result = planned("fractured", "three-top-tier", start_price=RESTART_PRICE)

    assert_exact(result)
    assert RESTART in {priced.label for priced in result.searched.offers}


def test_a_route_may_name_a_twin_the_search_left_out_and_it_is_priced_and_evaluated(planned, world):
    """A judged route is walked on its own reach (#829): an offer the search never built, a dearer twin among them, is priced and evaluated."""
    plan = planned("fractured", "two").searched
    (twins,) = [limit for limit in plan.limits if limit.why == "same outcome as a cheaper action"]
    dropped = twins.labels[0]
    route = parse_route(f"name: names a twin\nrules:\n  - do: {dropped}\n", plan, world.data)

    result = evaluate_route(plan, route, world.data)

    assert dropped not in {action.label for action in plan.policy.values()}
    assert not result.gaps
    assert {action.label for action in result.policy.values()} == {dropped}
    assert plan.offer_of(result.policy[plan.start]).cost == next(p for p in plan.offers if p.label == dropped).cost
    assert result.risk.mean.value >= plan.mean_remaining * (1 - 1e-9)  # the plan is exact here: no route is cheaper


# --- the bench: a goal leaf a craft can finish ---------------------------------------------------------------


@pytest.fixture(scope="module")
def bench(real):
    """A smaller pool (the states multiply with the junk the bench actions read), the life craft and Remove Crafted Mods."""
    data = world_data(real, {"IncreasedLife", "MovementVelocity", "IncreasedMana", "FireResistance"})
    item = Item.build(data, base_id=BASE, item_level=LEVEL, rarity=Rarity.RARE, mods=(rolled(data, FRACTURED, fractured=True),))
    actions = [BenchCraft(LIFE_CRAFT), RemoveCraftedMods(), *fossil_sets(data, item)[:90]]
    prices = made_up_prices(data, "Orb of Alteration", "Orb of Scouring")
    life, speed1 = requirement(data, "IncreasedLife"), requirement(data, "MovementVelocity", min_tier=1)
    target = Target(BASE, LEVEL, frozenset(), (life, speed1), item, start=StartKind.GIVEN)
    offers = [offer_of(ChaosOrb(), "Chaos Orb", data, item)] + [offer_of(a, a.label(data), data, item) for a in actions]
    return SimpleNamespace(data=data, item=item, target=target, offers=offers, prices=prices)


def test_with_bench_crafts_offered_the_search_gives_the_plan_of_the_whole_walk(bench):
    assert_exact(Planned(bench.data, bench.target, bench.prices, bench.offers))


def test_the_leaf_a_craft_can_finish_is_dropped_from_the_set_the_bound_is_read_on(bench):
    abstraction = Abstraction(bench.data, Goal.from_target(bench.target), BASE, LEVEL, [BenchCraft(LIFE_CRAFT), RemoveCraftedMods()])
    start = abstraction.compress(bench.item)
    crafted = frozenset(BenchCraft(LIFE_CRAFT).adds(bench.data, bench.item).named)

    assert goal_set(abstraction.goal, start, crafted) == (1,)  # life is leaf 0: the craft finishes it
    assert goal_set(abstraction.goal, start, frozenset()) == (0, 1)


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


# --- the cache of built actions -----------------------------------------------------------------------------


def test_the_cache_of_built_actions_builds_each_state_and_offer_once(world, monkeypatch):
    item = world.fractured
    abstraction = Abstraction(world.data, Goal.from_target(Target(BASE, LEVEL, frozenset(), goals(world.data)["two"], item, start=StartKind.GIVEN)), BASE, LEVEL)
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


# --- 3. the routes on the real dump ---------------------------------------------------------------------------

ROUTES = ["r11-reservation-helmet", "r10-fractured-boots", "r05-strength-ring"]


@pytest.fixture(scope="module")
def golden():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module", params=ROUTES)
def route_plan(request, real):
    target = load_target(ROOT / "examples" / "targets" / f"{request.param}.yaml", real)
    return request.param, make_plan(real, target, load_price_file(ROUTE_PRICES))  # `auto`: the envelope search (#829)


def test_the_routes_give_the_mean_and_the_policy_of_the_whole_walk(route_plan, golden, real, monkeypatch):
    """Mean to 1e-9 and the same action at every state, against the plan of the whole walk (the golden file).

    `UPDATE_GOLDEN=1` rewrites this route's entry from the walk with the twins and the floors turned off (`_plan.PRUNE_BOUND`), the
    reference the plan is held to, at the current prices (#838), then compares as usual."""
    stem, plan = route_plan
    if os.environ.get("UPDATE_GOLDEN"):
        monkeypatch.setattr(_plan, "PRUNE_BOUND", False)
        target = load_target(ROOT / "examples" / "targets" / f"{stem}.yaml", real)
        whole = make_plan(real, target, load_price_file(ROUTE_PRICES), solver="object")
        found = json.loads(GOLDEN.read_text(encoding="utf-8"))
        found[stem] = {
            "mean_remaining": whole.mean_remaining,
            "policy": {repr(state): action.label for state, action in whole.policy.items()},
            "start": repr(whole.start),
            "states": len(whole.solution.values),
        }
        GOLDEN.write_text(json.dumps(found, indent=0, sort_keys=True), encoding="utf-8", newline="\n")
        golden[stem] = found[stem]
    expected = golden[stem]

    golden_diff.check_objects(expected["start"], repr(plan.start), f"{stem}: the start state differs from tests/golden/plans_118.json")
    golden_diff.check_objects(
        expected["mean_remaining"], plan.mean_remaining, f"{stem}: the mean differs from tests/golden/plans_118.json", rel=1e-9
    )
    # The twins left out may leave FEWER states reached than the golden plan has; every state the plan solves has the
    # action the golden plan has there.
    assert len(plan.solution.values) <= expected["states"]
    policy = {repr(state): action.label for state, action in plan.policy.items()}
    title = f"{stem}: the policy differs from tests/golden/plans_118.json"
    golden_diff.check_objects([], sorted(policy.keys() - expected["policy"].keys()), f"{title} (states the golden plan does not have)")
    golden_diff.check_objects(
        {state: expected["policy"][state] for state in policy}, policy, f"{title} (the action at a state both reach)"
    )
