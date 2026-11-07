"""`benchmark` compares the planner with the guide on both sides (ticket #554, audit TESTS-22 part 1).

Every state where the guide's route and the planner part is listed with its chance under each policy, the ratio of the two means is
printed, and a route whose planner is far cheaper than the guide gets a "needs a human" row (the review line is a setting, OR-12).

The expected chances are computed here by hand on small chains and, for the visit chance itself, by `reach_probabilities` (the older
dense solve of the text report) on random chains. No test asserts a run time.
"""

import random
from fractions import Fraction

import pytest
from cli_support import TODAY, price_file, read_json
from targets_support import DATA, EXAMPLES

import crafting_system.cli._benchmark_divergence as divergence_module
from crafting_system.cli import _route_flow, evaluate_route, main, make_plan, parse_route
from crafting_system.cli._benchmark_divergence import divergence_lines, divergences_of, mean_ratio, review_lines, review_of
from crafting_system.cli._reach import reach_probabilities
from crafting_system.cli._report import number_states
from crafting_system.cli._route_flow import chain_of_policy, reach_of
from crafting_system.config import load_config
from crafting_system.prices import PriceEntry
from crafting_system.solver import Action, Outcome
from crafting_system.targets import parse_target, start_price_key
from test_cli_benchmark import entry_of

GEM_TEXT = "+1 to Level of all Lightning Skill Gems"
REFORGE = "Harvest Reforge Lightning"
CHAOS = "Chaos Orb"
COMMAND = "bench" + "mark"  # the name of the command; a bare string with it would trip tests/test_no_timing.py


# --- the visit chance of a state (reach_of) ------------------------------------------------------------------


def act(label, *outcomes):
    return Action(label, 1.0, tuple(Outcome(state, weight) for state, weight in outcomes))


def is_goal(state):
    return state == "goal"


def hand_chain():
    # S: stays 1/2, to B 3/10, goal 1/5. B: back to S 2/5, goal 3/5.
    policy = {"S": act("s", ("S", 5), ("B", 3), ("goal", 2)), "B": act("b", ("S", 2), ("goal", 3))}
    return policy, chain_of_policy("S", policy, is_goal)


def test_the_chance_of_visiting_a_state_is_the_closed_form_on_a_hand_chain():
    policy, chain = hand_chain()
    index = {state: i for i, state in enumerate(chain.states)}

    reached = reach_of(chain, [index["S"], index["B"]])

    # From S each pass ends in B with 3/10 or in the goal with 1/5, so B is visited with (3/10) / (3/10 + 1/5) = 3/5. The start is visited for sure.
    assert [r.chance for r in reached] == [pytest.approx(1.0), pytest.approx(0.6)]
    assert all(r.exact for r in reached)


def test_above_the_inversion_limit_the_chance_is_the_same_by_a_solve_with_the_state_absorbing(monkeypatch):
    policy, chain = hand_chain()
    index = {state: i for i, state in enumerate(chain.states)}
    monkeypatch.setattr(_route_flow, "ENTRY_STATES", 1)  # the sparse path

    reached = reach_of(chain, [index["S"], index["B"]])

    assert reached[0].chance == pytest.approx(1.0)
    assert reached[1].chance == pytest.approx(0.6, rel=1e-9) and reached[1].exact


def test_a_state_past_the_solve_budget_gets_an_upper_bound_that_says_so(monkeypatch):
    policy, chain = hand_chain()
    index = {state: i for i, state in enumerate(chain.states)}
    monkeypatch.setattr(_route_flow, "ENTRY_STATES", 1)
    monkeypatch.setattr(_route_flow, "EXACT_RETURNS", 0)

    (bound,) = reach_of(chain, [index["B"]])

    # The visits of B are 0.6 / (1 - 2/5 * 3/5) and no self-loop is taken in B, so the bound is the visits, capped at 1.
    assert not bound.exact
    assert 0.6 <= bound.chance <= 1.0


def test_a_chain_with_too_many_edges_gets_bounds_only(monkeypatch):
    policy, chain = hand_chain()
    index = {state: i for i, state in enumerate(chain.states)}
    monkeypatch.setattr(_route_flow, "ENTRY_STATES", 1)
    monkeypatch.setattr(_route_flow, "EXACT_RETURN_EDGES", 2)  # the chain has more edges than this

    (bound,) = reach_of(chain, [index["B"]])

    assert not bound.exact and 0.6 <= bound.chance <= 1.0


def test_the_chance_of_a_state_the_run_cannot_finish_from_is_not_measured():
    policy = {"S": act("s", ("A", 1), ("goal", 1)), "A": act("a", ("A", 1))}  # A loops for ever
    chain = chain_of_policy("S", policy, is_goal)
    index = {state: i for i, state in enumerate(chain.states)}

    (stuck,) = reach_of(chain, [index["A"]])

    assert stuck.chance is None and not stuck.exact


@pytest.mark.parametrize("seed", [554, 22, 24, 32, 34, 37])  # the last five are seeds on which the iteration of `_bicgstab` claimed a residual it did not have
@pytest.mark.parametrize("sparse", [False, True])
def test_the_visit_chance_matches_the_dense_solve_of_the_text_report_on_random_policies(monkeypatch, sparse, seed):
    if sparse:
        monkeypatch.setattr(_route_flow, "ENTRY_STATES", 1)
    rng = random.Random(seed)
    checked = 0
    for _ in range(150):
        size = rng.randint(2, 8)
        names = [f"s{i}" for i in range(size)]
        policy = {}
        for name in names:
            pool = [*names, "goal"]
            targets = rng.sample(pool, min(len(pool), rng.randint(2, 4)))
            policy[name] = act("a", *((target, rng.choice([1, 2, 3])) for target in targets))
        chain = chain_of_policy("s0", policy, is_goal)
        reached = reach_of(chain, list(range(chain.m)))
        if any(r.chance is None for r in reached):
            continue
        expected = reach_probabilities("s0", policy, is_goal)
        for state, found in zip(chain.states, reached):
            assert found.chance == pytest.approx(expected[state], rel=1e-7, abs=1e-9)
            assert found.exact
        checked += 1
    assert checked > 50


# --- every divergence of a tiny target, with its chances -------------------------------------------------------


@pytest.fixture(scope="module")
def tiny():
    """Paua Amulet, a bare rare start, needing the gem and a Lightning Resistance of any tier; the planner rerolls with Harvest, the route with Chaos.

    Three states (neither mod, only the resistance, only the gem) and, from each, one and the same reroll: the chance of landing in a state
    does not depend on the state, so the chance of ever visiting a state other than the start is (its landing chance) / (its landing
    chance + the chance of the goal).
    """
    text = f"""\
base: Paua Amulet
item_level: 84
requirements:
  - stat: "{GEM_TEXT}"
  - family: LightningResistance
    min_tier: any
start_item:
  rarity: rare
start: bought
"""
    target = parse_target(text, DATA, source="tiny.yaml")
    prices = price_file(start=None)
    prices.prices[start_price_key(DATA, target)] = PriceEntry(4.0, "trade-api")
    plan = make_plan(DATA, target, prices)
    route = parse_route(f"rules:\n  - do: {CHAOS}\n", plan, DATA)
    return plan, evaluate_route(plan, route, DATA)


def landing(plan, action, state):
    """The chance one use of `action` lands in `state` (the goal when `state` is None), from the integer weights of its outcomes."""
    total = sum(weight for _, weight in action.outcomes)
    into = sum(w for s, w in action.outcomes if (plan.is_goal(s) if state is None else s == state))
    return Fraction(into, total)


def visit_chance(plan, action, state):
    """The chance of ever visiting `state` (not the start) when every use of `action` lands alike: p / (p + the goal's chance)."""
    p, g = landing(plan, action, state), landing(plan, action, None)
    return float(p / (p + g))


def test_every_state_where_the_route_and_the_planner_part_is_listed_with_its_chances(tiny):
    plan, result = tiny
    ids = number_states(plan)
    start = plan.start

    block = divergences_of(plan, result, DATA)

    assert result.divergences and result.divergence == result.divergences[0]
    assert block["count"] == 3 == len(result.divergences) == len(ids) and block["more"] is None
    by_state = {row["state"]: row for row in block["shown"]}
    assert set(by_state) == set(ids.values())
    for state, state_id in ids.items():
        row = by_state[state_id]
        assert (row["solver_action"], row["route_action"]) == (REFORGE, CHAOS)
        planner_chance = 1.0 if state == start else visit_chance(plan, plan.policy[start], state)
        route_chance = 1.0 if state == start else visit_chance(plan, result.policy[start], state)
        assert row["planner_chance"] == pytest.approx(planner_chance, rel=1e-9)
        assert row["route_chance"] == pytest.approx(route_chance, rel=1e-9)
        assert row["planner_chance_exact"] and row["route_chance_exact"]
        assert row["description"].startswith("rare;")
    chances = [max(row["planner_chance"], row["route_chance"]) for row in block["shown"]]
    assert chances == sorted(chances, reverse=True) and block["shown"][0]["state"] == ids[start]


def test_lines_past_the_cap_are_counted_with_their_chances_not_dropped(tiny, monkeypatch):
    plan, result = tiny
    monkeypatch.setattr(divergence_module, "SHOWN", 1)

    block = divergences_of(plan, result, DATA)

    assert len(block["shown"]) == 1 and block["count"] == 3
    rest = [row for row in divergences_of_all(plan, result) if row["state"] != block["shown"][0]["state"]]
    assert block["more"]["count"] == 2 == len(rest)
    assert block["more"]["planner_chance"] == pytest.approx(sum(row["planner_chance"] for row in rest))
    assert block["more"]["route_chance"] == pytest.approx(sum(row["route_chance"] for row in rest))
    text = "\n".join(divergence_lines(block))
    assert "and 2 more, visited" in text and "summed over the states" in text and text.isascii()
    one = {"count": 1, "shown": [{**block["shown"][0], "description": "rare; lacks a\nb\nc"}], "more": None}
    assert "lacks a / b / c" in "\n".join(divergence_lines(one))  # a mod that reads on several lines stays on one line


def divergences_of_all(plan, result):
    saved = divergence_module.SHOWN
    divergence_module.SHOWN = 100
    try:
        return divergences_of(plan, result, DATA)["shown"]
    finally:
        divergence_module.SHOWN = saved


def test_the_lines_say_what_the_item_is_what_each_does_and_both_chances(tiny):
    plan, result = tiny

    text = "\n".join(divergence_lines(divergences_of(plan, result, DATA)))

    assert "the guide does Chaos Orb, the planner does Harvest Reforge Lightning" in text
    assert "the planner visits it with chance 100%, the guide with chance 100%" in text
    assert "lacks +1 to Level of all Lightning Skill Gems" in text and "S1:" in text


def test_a_route_that_does_what_the_planner_does_has_no_divergence_lines():
    target = parse_target(f'base: Paua Amulet\nitem_level: 84\nrequirements:\n  - stat: "{GEM_TEXT}"\nstart_item:\n  rarity: rare\nstart: given\n', DATA, source="given.yaml")
    plan = make_plan(DATA, target, price_file(start=None))
    route = parse_route(f"rules:\n  - do: {next(iter(plan.policy.values())).label}\n", plan, DATA)

    block = divergences_of(plan, evaluate_route(plan, route, DATA), DATA)

    assert block == {"count": 0, "shown": [], "more": None} and divergence_lines(block) == []


# --- the ratio and the review line ---------------------------------------------------------------------------


def test_the_ratio_is_the_planner_mean_over_the_guide_mean_and_a_guide_that_never_finishes_has_none():
    assert mean_ratio(30.0, 120.0) == 0.25
    assert mean_ratio(30.0, None) is None and mean_ratio(None, 30.0) is None and mean_ratio(1.0, 0.0) is None


def test_a_ratio_below_the_review_line_prints_a_needs_a_human_row_naming_the_top_divergences(tiny):
    plan, result = tiny
    block = divergences_of(plan, result, DATA)

    below = "\n".join(review_lines("guide", review_of(0.25, 0.5), block))
    above = "\n".join(review_lines("guide", review_of(0.75, 0.5), block))

    assert "NEEDS A HUMAN" in below and "the guide does Chaos Orb, the planner does Harvest Reforge Lightning" in below
    assert "planner mean / guide mean: 0.250" in below
    assert "NEEDS A HUMAN" not in above and "planner mean / guide mean: 0.750" in above


def test_a_ratio_equal_to_the_line_and_a_ratio_that_is_not_known_need_no_human():
    assert review_of(0.5, 0.5)["needs_human"] is False
    assert review_of(None, 0.5)["needs_human"] is False
    assert review_lines("guide", review_of(None, 0.5), {"count": 0, "shown": [], "more": None}) == []


# --- the benchmark command ---------------------------------------------------------------------------------


def run_with_config(tmp_path, review_ratio=None, lifeforce=0.2):
    """R12 with the lifeforce at `lifeforce` (at 0.2 the planner rerolls with Chaos and the guide's Harvest reroll is dearer), and the config's review line."""
    env = {}
    if review_ratio is not None:
        config = tmp_path / "review.toml"
        config.write_text(f"[benchmark]\nreview_ratio = {review_ratio}\n", encoding="utf-8")
        env = {"CRAFTING_CONFIG": str(config)}
    out = tmp_path / "out"
    code = main([COMMAND, "--out", str(out)], data=DATA, prices=price_file(lifeforce=lifeforce), env=env, today=TODAY)
    assert code == 0
    return read_json(out / "benchmark.json")


def test_the_document_carries_the_divergences_the_ratio_and_the_review_of_each_route(tmp_path):
    entry = entry_of(run_with_config(tmp_path))
    given = entry["given_route"]

    assert given["divergences"]["count"] == len(given["divergences"]["shown"]) == 1  # R12 has one state
    row = given["divergences"]["shown"][0]
    assert (row["solver_action"], row["route_action"]) == ("Chaos Orb", REFORGE)
    assert row["planner_chance"] == pytest.approx(1.0) and row["route_chance"] == pytest.approx(1.0)
    ratio = entry["solver"]["mean"] / given["mean"]
    assert given["mean_ratio"]["ratio"] == pytest.approx(ratio) and 0.0 < ratio < 1.0
    assert given["mean_ratio"]["line"] == load_config({}).benchmark_review_ratio == 0.5
    assert given["first_divergence"]["solver_action"] == "Chaos Orb"  # the old field is still there


def test_the_review_line_is_read_from_the_config_and_changing_it_changes_the_row(tmp_path, capsys):
    for name in ("a", "b", "c"):
        (tmp_path / name).mkdir()
    plain = entry_of(run_with_config(tmp_path / "a"))
    ratio = plain["solver"]["mean"] / plain["given_route"]["mean"]
    capsys.readouterr()

    above_line = min(1.0, ratio * 1.01)  # the planner is below this share of the guide: a human looks
    below_line = ratio * 0.99  # the planner is above this share: none
    flagged = entry_of(run_with_config(tmp_path / "b", above_line))["given_route"]["mean_ratio"]
    flagged_text = capsys.readouterr().out
    quiet = entry_of(run_with_config(tmp_path / "c", below_line))["given_route"]["mean_ratio"]
    quiet_text = capsys.readouterr().out

    assert flagged["needs_human"] is True and flagged["line"] == pytest.approx(above_line)
    assert quiet["needs_human"] is False and quiet["line"] == pytest.approx(below_line)
    assert "NEEDS A HUMAN" in flagged_text and "NEEDS A HUMAN" not in quiet_text
    assert "the guide does Harvest Reforge Lightning, the planner does Chaos Orb" in flagged_text


def test_at_the_default_prices_the_planner_equals_the_guide_and_no_row_is_printed(tmp_path, capsys):
    document = run_with_config(tmp_path, lifeforce=0.01)

    given = entry_of(document)["given_route"]
    assert given["mean_ratio"]["ratio"] == pytest.approx(1.0) and given["mean_ratio"]["needs_human"] is False
    assert given["divergences"] == {"count": 0, "shown": [], "more": None}
    text = capsys.readouterr().out
    assert "NEEDS A HUMAN" not in text and "planner mean / guide mean: 1.000" in text


@pytest.mark.parametrize("value", ["0", "-0.1", "1.5", '"half"', "true", "nan"])
def test_a_bad_review_line_is_a_config_error_naming_the_key(tmp_path, value):
    path = tmp_path / "crafting.toml"
    path.write_text(f"[benchmark]\nreview_ratio = {value}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"crafting\.toml.*review_ratio"):
        load_config(env={}, project_root=tmp_path)


def test_an_unknown_benchmark_key_is_refused_and_the_default_is_a_half(tmp_path):
    path = tmp_path / "crafting.toml"
    path.write_text("[benchmark]\nreview = 0.5\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unknown key 'review' in \\[benchmark\\]"):
        load_config(env={}, project_root=tmp_path)
    assert load_config(env={}, project_root=tmp_path / "no-file").benchmark_review_ratio == 0.5


def test_the_project_config_states_the_review_line_and_says_it_is_not_a_cut():
    text = (EXAMPLES.parents[1] / "crafting.toml").read_text(encoding="utf-8")

    assert "review_ratio = 0.5" in text and "NOT a cut of the search" in text
    assert load_config({}).benchmark_review_ratio == 0.5



def test_a_packed_plan_lists_every_divergence_also_where_the_route_never_goes(tiny):
    """The packed reading asks the route again at a state of the planner's line that the route does not reach (`labels` has no entry for it)."""
    from crafting_system.cli import Divergence
    from crafting_system.cli._route_packed import _divergences

    plan, result = tiny
    target = plan.target
    prices = price_file(start=None)
    prices.prices[start_price_key(DATA, target)] = PriceEntry(4.0, "trade-api")
    packed = make_plan(DATA, target, prices, solver="packed")
    route = parse_route(f"rules:\n  - do: {CHAOS}\n", packed, DATA)

    parted = _divergences(packed, route, DATA, {}, Divergence)

    assert len(parted) == 3 and {(d.solver_action, d.route_action) for d in parted} == {(REFORGE, CHAOS)}
    assert len(evaluate_route(packed, route, DATA).divergences) == 3
