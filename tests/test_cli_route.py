"""Given routes (ticket #57): a route written as rules, evaluated as a fixed policy at the solver's prices.

The expected numbers come from the definition, not from the code under test. The example route of
R12 (Harvest Reforge Lightning until the mod) is the solver's own policy, so its mean is the solver's
mean. A route that rerolls with a Chaos Orb until the mod is a geometric run: mean = start price +
1 Chaos / q, q being the exact chance one Chaos Orb leaves the mod (`Outcomes.chance_all`). A route
that restarts is solved by hand on a two-leaf target. No test asserts a run time.
"""

import math
import textwrap
from pathlib import Path

import pytest
from cli_support import R12, geometric_p90_clicks, price_file, read_json
from cli_support import run as run_command
from targets_support import DATA

from crafting_system.actions import ChaosOrb
from crafting_system.cli import RouteError, RouteResult, evaluate_route, load_route, make_plan, parse_route
from crafting_system.targets import load_target, parse_target

ROUTE = R12.parents[1] / "routes" / "r12-lightning-amulet.yaml"
GEM = "GlobalLightningGemLevel1"
GEM_TEXT = "+1 to Level of all Lightning Skill Gems"
START_PRICE = 4.0
CHAOS = "Chaos Orb"
REFORGE = "Harvest Reforge Lightning"


def run(tmp_path, *arguments, prices="default", **fields):
    return run_command(tmp_path, *arguments, prices=price_file() if prices == "default" else prices, **fields)


def route_file(tmp_path: Path, text: str, name: str = "route.yaml") -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def target():
    return load_target(R12, DATA)


@pytest.fixture(scope="module")
def plan(target):
    return make_plan(DATA, target, price_file())


def read(text: str, plan, source: str = "route.yaml"):
    return parse_route(textwrap.dedent(text).lstrip("\n"), plan, DATA, source)


def error_of(text: str, plan, **kwargs) -> str:
    with pytest.raises(RouteError) as caught:
        read(text, plan, **kwargs)
    return str(caught.value)


# --- the ticket's Done-when --------------------------------------------------------------------------


def test_the_given_route_of_r12_costs_what_the_solver_costs(tmp_path, capsys):
    code, out = run(tmp_path, "--route", str(ROUTE))

    assert code == 0
    document = read_json(out)
    totals, given = document["totals"], document["given_route"]
    assert given["name"] == "R12, PoE Vault guide"
    assert given["file"] == "r12-lightning-amulet.yaml"
    assert given["success_probability"]["value"] == 1.0 == totals["success_probability"]["value"]
    assert given["mean_cost"]["value"] == pytest.approx(totals["mean_cost"]["value"], rel=1e-9)
    assert given["p50"]["value"] == pytest.approx(totals["p50"]["value"], rel=1e-9)
    assert given["p90"]["value"] == pytest.approx(totals["p90"]["value"], rel=1e-9)
    assert given["first_divergence"] is None
    assert given["gaps"] == []
    assert given["timings_seconds"]["route_evaluate"] >= 0.0
    text = capsys.readouterr().out
    assert "Given route" in text and "no divergence" in text.lower()
    assert text.isascii()


def test_a_chaos_orb_route_costs_its_geometric_run_and_names_where_it_leaves_the_policy(tmp_path, target, capsys):
    q = float(ChaosOrb().outcomes(DATA, target.start_item).chance_all([GEM]))
    worse = route_file(
        tmp_path,
        f"""
        name: Chaos until the mod
        rules:
          - do: {CHAOS}
        """,
    )

    code, out = run(tmp_path, "--route", str(worse))

    assert code == 0
    document = read_json(out)
    given = document["given_route"]
    assert given["success_probability"]["value"] == 1.0
    assert given["mean_cost"]["value"] == pytest.approx(START_PRICE + 1.0 / q, rel=1e-9)
    assert given["p90"]["value"] == pytest.approx(START_PRICE + geometric_p90_clicks(q), rel=1e-9)
    assert given["mean_cost"]["value"] > document["totals"]["mean_cost"]["value"]
    divergence = given["first_divergence"]
    assert divergence["state"] == "S1"
    assert divergence["policy_action"] == REFORGE
    assert divergence["route_action"] == CHAOS
    assert divergence["description"] == document["states"][0]["description"]
    text = capsys.readouterr().out
    section = text[text.index("Given route") :]
    assert "First divergence" in section and "S1" in section
    assert f"policy does {REFORGE}" in section and f"route does {CHAOS}" in section
    assert text.isascii()


# --- evaluating a route ------------------------------------------------------------------------------


def test_a_state_no_rule_covers_is_a_gap_and_the_route_never_finishes(plan):
    route = read(
        f"""
        rules:
          - when:
              rarity: magic
            do: {REFORGE}
        """,
        plan,
    )

    result = evaluate_route(plan, route, DATA)

    assert isinstance(result, RouteResult)
    assert [gap.state for gap in result.gaps] == [plan.start]
    assert "no rule" in result.gaps[0].reason
    assert result.policy == {}
    assert result.risk.success_probability.value < 1.0
    assert math.isinf(result.risk.mean.value)
    assert result.divergence is None  # a gap is not a divergence
    assert result.seconds >= 0.0


def test_the_cli_reports_a_gap_with_its_state_and_a_mean_that_never_comes(tmp_path, capsys):
    gappy = route_file(
        tmp_path,
        f"""
        rules:
          - when:
              rarity: magic
            do: {REFORGE}
        """,
    )

    code, out = run(tmp_path, "--route", str(gappy))

    assert code == 0
    given = read_json(out)["given_route"]
    assert given["mean_cost"]["value"] is None and given["success_probability"]["value"] == 0.0
    (gap,) = given["gaps"]
    assert gap["state"] == "S1" and "no rule" in gap["reason"] and gap["description"].startswith("rare;")
    text = capsys.readouterr().out
    section = text[text.index("Given route") :]
    assert "never" in section and "Gaps" in section and "S1" in section and "no rule" in section


def test_the_first_matching_rule_wins(plan):
    route = read(
        f"""
        rules:
          - when:
              rarity: rare
            do: {REFORGE}
          - do: {CHAOS}
        """,
        plan,
    )

    result = evaluate_route(plan, route, DATA)

    assert result.policy[plan.start].label == REFORGE
    assert result.gaps == () and result.divergence is None


def test_a_goal_state_is_never_acted_on(plan):
    route = read(f"rules:\n  - do: {REFORGE}\n", plan)

    result = evaluate_route(plan, route, DATA)

    assert set(result.policy) == {plan.start}  # the goal reached by the reforge has no entry


def test_fractured_conditions_read_the_fractured_mods_of_the_state(plan):
    lines = f"""
        rules:
          - when:
              fractured: {{FRACTURED}}
            do: {REFORGE}
        """

    held = evaluate_route(plan, read(lines.replace("{FRACTURED}", "[{family: LightningResistance}]"), plan), DATA)
    none = evaluate_route(plan, read(lines.replace("{FRACTURED}", "none"), plan), DATA)

    assert set(held.policy) == {plan.start} and held.gaps == ()
    assert none.policy == {} and len(none.gaps) == 1


@pytest.mark.parametrize(
    ("when", "matches"),
    [
        ("corrupted: false", True),
        ("corrupted: true", False),
        ("crafted_mods: false", True),
        ("crafted_mods: true", False),
        ("rarity: [magic, rare]", True),
        ("rarity: normal", False),
    ],
)
def test_flag_conditions(plan, when, matches):
    route = read(f"rules:\n  - when:\n      {when}\n    do: {REFORGE}\n", plan)

    result = evaluate_route(plan, route, DATA)

    assert (plan.start in result.policy) is matches


@pytest.mark.parametrize(
    ("selector", "status", "matches"),
    [
        (f'stat: "{GEM_TEXT}"', "absent", True),
        (f'stat: "{GEM_TEXT}"', "[below, passing]", False),
        ("family: LightningResistance", "passing", True),
        ("family: LightningResistance", "absent", False),
    ],
)
def test_requirement_conditions_read_the_status_of_a_leaf(plan, selector, status, matches):
    route = read(
        f"""
        rules:
          - when:
              requirements:
                - {selector}
                  status: {status}
            do: {REFORGE}
        """,
        plan,
    )

    assert (plan.start in evaluate_route(plan, route, DATA).policy) is matches


def test_a_restart_buys_the_start_item_again_at_the_start_price(plan):
    route = read("rules:\n  - do: restart\n", plan)

    result = evaluate_route(plan, route, DATA)

    action = result.policy[plan.start]
    assert action.label == "restart" and action.cost == START_PRICE
    assert [(state, weight) for state, weight in action.outcomes] == [(plan.start, 1)]
    assert result.risk.success_probability.value == 0.0 and math.isinf(result.risk.mean.value)
    assert result.divergence.route_action == "restart"


def test_a_restart_costs_the_closed_form_on_a_two_leaf_target():
    """Start on a bare rare amulet that needs the gem AND Lightning Resistance; Chaos rerolls everything.

    From any non-goal state a Chaos Orb ends in the goal with chance g (both mods). A state with the gem
    but no resistance restarts for the start price; every other state rerolls. All states reroll alike,
    so E = (1 + 4 b) / g, b = the chance of the gem without the resistance.
    """
    text = f"""\
base: Paua Amulet
item_level: 84
requirements:
  - stat: "{GEM_TEXT}"
  - family: LightningResistance
start_item:
  rarity: rare
start_price: R12 start amulet
"""
    two = parse_target(text, DATA, source="two.yaml")
    plan = make_plan(DATA, two, price_file())
    outcomes = ChaosOrb().outcomes(DATA, two.start_item)
    resists = [mod_id for mod_id, mod in DATA.mods.items() if "LightningResistance" in mod.families]
    gem_chance = float(outcomes.chance_all([GEM]))
    goal_chance = sum(float(outcomes.chance_all([GEM, mod_id])) for mod_id in resists)
    gem_only = gem_chance - goal_chance
    route = read(
        f"""
        rules:
          - when:
              requirements:
                - stat: "{GEM_TEXT}"
                  status: passing
                - family: LightningResistance
                  status: absent
            do: restart
          - do: {CHAOS}
        """,
        plan,
    )

    result = evaluate_route(plan, route, DATA)

    assert result.gaps == ()
    assert result.risk.success_probability.value == 1.0
    assert result.risk.mean.value == pytest.approx((1.0 + START_PRICE * gem_only) / goal_chance, rel=1e-9)
    assert {action.label for action in result.policy.values()} == {"restart", CHAOS}


# --- the reader's errors -----------------------------------------------------------------------------


def test_the_example_route_is_read(plan):
    route = load_route(ROUTE, plan, DATA)

    assert route.name == "R12, PoE Vault guide" and len(route.rules) == 1


def test_a_missing_route_file_is_named(plan, tmp_path):
    with pytest.raises(RouteError, match="no-such-route.yaml: the route file does not exist"):
        load_route(tmp_path / "no-such-route.yaml", plan, DATA)


def test_an_unknown_top_key_has_a_hint(plan):
    message = error_of("name: x\nrulez:\n  - do: Chaos Orb\n", plan)

    assert message == "route.yaml:2: rulez: unknown key `rulez`; did you mean `rules`?"


def test_a_route_without_rules_is_refused(plan):
    assert error_of("name: x\n", plan) == "route.yaml:1: rules: this key is required but missing"
    assert error_of("rules: []\n", plan) == "route.yaml:1: rules: must hold at least one rule"


def test_a_rule_without_do_is_refused(plan):
    message = error_of("rules:\n  - when:\n      rarity: rare\n", plan)

    assert message == "route.yaml:2: rules[0].do: this key is required but missing"


def test_an_unknown_when_key_has_a_hint(plan):
    message = error_of("rules:\n  - when:\n      rarty: rare\n    do: Chaos Orb\n", plan)

    assert message == "route.yaml:3: rules[0].when.rarty: unknown key `rarty`; did you mean `rarity`?"


@pytest.mark.parametrize(
    "key", ["prefixes", "suffixes", "free_prefixes", "free_suffixes", "free_slots", "metamods", "mods_per_side"]
)
def test_a_condition_the_state_cannot_answer_is_refused(plan, key):
    message = error_of(f"rules:\n  - when:\n      {key}: 1\n    do: Chaos Orb\n", plan)

    assert message.startswith(f"route.yaml:3: rules[0].when.{key}: ")
    assert "compressed state does not hold" in message and "later ticket" in message


def test_a_bad_status_names_file_line_and_key(plan):
    text = f"""
        rules:
          - do: {CHAOS}
          - when:
              requirements:
                - stat: "{GEM_TEXT}"
                  status: gone
            do: {CHAOS}
        """

    message = error_of(text, plan)

    assert message.startswith("route.yaml:6: rules[1].when.requirements[0].status: ")
    assert "`absent`, `below`, `passing`" in message and '"gone"' in message


def test_a_bad_rarity_a_bad_flag_and_a_requirement_without_status(plan):
    assert "rules[0].when.rarity: must be one of `normal`, `magic`, `rare`" in error_of(
        "rules:\n  - when:\n      rarity: unique\n    do: Chaos Orb\n", plan
    )
    assert "rules[0].when.corrupted: must be true or false" in error_of(
        "rules:\n  - when:\n      corrupted: maybe\n    do: Chaos Orb\n", plan
    )
    assert "rules[0].when.requirements[0].status: this key is required but missing" in error_of(
        f'rules:\n  - when:\n      requirements:\n        - stat: "{GEM_TEXT}"\n    do: Chaos Orb\n', plan
    )


def test_an_unknown_action_lists_the_known_ones_with_a_close_match(plan):
    message = error_of("rules:\n  - do: Chaos Orbs\n", plan)

    assert message.startswith('route.yaml:2: rules[0].do: unknown action "Chaos Orbs"')
    assert f"`{CHAOS}`" in message and f"`{REFORGE}`" in message and "`restart`" in message
    assert f"did you mean `{CHAOS}`?" in message


def test_an_action_dropped_for_lack_of_a_price_names_the_missing_price(target):
    unpriced = make_plan(DATA, target, price_file(lifeforce=None))

    message = error_of(f"rules:\n  - do: {REFORGE}\n", unpriced)

    assert message.startswith(f'route.yaml:2: rules[0].do: "{REFORGE}" has no price')
    assert "Primal Crystallised Lifeforce" in message


def test_a_restart_needs_a_start_price_above_zero(target):
    free = make_plan(DATA, target, price_file(), start_price=0.0)

    message = error_of("rules:\n  - do: restart\n", free)

    assert message.startswith("route.yaml:2: rules[0].do: ") and "start price" in message


def test_an_unknown_requirement_selector_lists_the_selectors_of_the_target(plan):
    message = error_of(
        "rules:\n  - when:\n      requirements:\n        - stat: Nonsense\n          status: absent\n    do: Chaos Orb\n",
        plan,
    )

    assert message.startswith("route.yaml:4: rules[0].when.requirements[0].stat: ")
    assert f'stat "{GEM_TEXT}"' in message and "family LightningResistance" in message


def test_a_selector_that_names_two_leaves_is_ambiguous():
    twice = parse_target(
        f"base: Paua Amulet\nitem_level: 84\nrequirements:\n  - stat: \"{GEM_TEXT}\"\n  - stat: \"{GEM_TEXT}\"\n"
        "start_item:\n  rarity: rare\nstart_price: R12 start amulet\n",
        DATA,
        source="twice.yaml",
    )
    plan = make_plan(DATA, twice, price_file())

    message = error_of(
        f'rules:\n  - when:\n      requirements:\n        - stat: "{GEM_TEXT}"\n          status: absent\n    do: Chaos Orb\n',
        plan,
    )

    assert message.startswith("route.yaml:4: rules[0].when.requirements[0].stat: ") and "ambiguous" in message


def test_an_unknown_fractured_family_is_an_error(plan):
    message = error_of(
        "rules:\n  - when:\n      fractured:\n        - family: LightningResistanc\n    do: Chaos Orb\n", plan
    )

    assert message.startswith("route.yaml:4: rules[0].when.fractured[0].family: ")
    assert "LightningResistance" in message


def test_a_bad_yaml_file_names_the_line(plan):
    assert error_of("rules: [\n", plan).startswith("route.yaml:")
    assert error_of("- just\n- a list\n", plan).startswith("route.yaml:1: ")


def test_a_route_error_stops_the_command_with_exit_1(tmp_path, capsys):
    bad = route_file(tmp_path, "rules:\n  - do: Chaos Orbs\n")

    code, _ = run(tmp_path, "--route", str(bad))

    assert code == 1
    assert "Error: " in capsys.readouterr().err


def test_the_route_composes_with_verify(tmp_path, capsys):
    code, out = run(tmp_path, "--route", str(ROUTE), "--verify", "--runs", "200")

    document = read_json(out)
    assert code == 0 and "verification" in document and "given_route" in document
    assert "Given route" in capsys.readouterr().out


# --- open slots (ticket #60) ---------------------------------------------------------------------


def test_open_suffixes_is_refused_when_the_plan_keeps_no_mods_besides_the_fractured_ones(plan):
    message = error_of(f"rules:\n  - when:\n      open_suffixes: 1\n    do: {CHAOS}\n", plan)

    assert message.startswith("route.yaml:3: rules[0].when.open_suffixes: ")
    assert "no bench action is offered" in message


def test_open_suffixes_must_be_a_whole_number(plan):
    message = error_of(f"rules:\n  - when:\n      open_suffixes: lots\n    do: {CHAOS}\n", plan)

    assert message.startswith("route.yaml:3: rules[0].when.open_suffixes: must be a whole number")


def test_open_prefixes_and_suffixes_count_what_is_free_on_the_item():
    """A rare belt holds 3 prefixes and 3 suffixes; `open_*: n` asks for at least n of them free."""
    from cli_support import price_file as prices_of
    from items_support import item, roll

    from crafting_system.actions import BenchCraft
    from crafting_system.cli import Offer

    belt = "Metadata/Items/Belts/Belt3"
    target = parse_target(
        f"base: Leather Belt\nitem_level: 86\nrequirements:\n  - family: IncreasedLife\nstart_item:\n  rarity: rare\n",
        DATA,
        source="belt.yaml",
    )
    offers = [Offer(CHAOS, ChaosOrb(), {CHAOS: 1}), Offer("Craft damage", BenchCraft("JunMaster2AllDamage2_"), {CHAOS: 4})]
    belt_plan = make_plan(DATA, target, prices_of(), offers=offers)
    route = read(
        """
        rules:
          - when:
              open_prefixes: 3
            do: Chaos Orb
          - when:
              open_prefixes: 2
              open_suffixes: 2
            do: Craft damage
          - do: Chaos Orb
        """,
        belt_plan,
    )
    state_of = lambda *mods: belt_plan.abstraction.compress(item(*mods, base_id=belt, item_level=86))  # noqa: E731
    empty, two_held = state_of(), state_of(roll("IncreasedLife1"), roll("LightningResist1"))
    crowded = state_of(roll("IncreasedLife1"), roll("JunMaster2AllDamage2_", crafted=True))  # two prefixes

    assert [rule.when.matches(empty, DATA) for rule in route.rules] == [True, True, True]
    assert [rule.when.matches(two_held, DATA) for rule in route.rules] == [False, True, True]
    assert [rule.when.matches(crowded, DATA) for rule in route.rules] == [False, False, True]
