"""The finishes as the last steps of the route (#1234, OR-16): the catalyst quality and the base implicit's roll drawn as rows of the page and
blocks of the text, and their cost folded into the result's mean, percentiles and CVaR, the JSON, the price list and `--verify`.

On the fixture Paua Amulet of item level 84 (`targets_support`), with the hand figures of `test_planner_catalysts` and `test_planner_blessed`:

* one Intrinsic Catalyst adds +1 point with chance `1 - frac(f)` and +2 with chance `frac(f)`, `f = 30 e^(-84/30) - 0.3 = 1.5243`, up to 20%;
  the number `N` of catalysts from 0% has the law worked below by the recursion over the points (`_catalyst_law`), mean `E(0) = 13.35`;
* a Blessed Orb meets a wish for 30 on a roll of (20-30) with chance `1/11` per use: the number `G` of orbs is geometric, `P(G <= n) = 1 -
  (10/11)^n`, so its median is 8 (`1 - (10/11)^8 = 0.533`, while 7 gives 0.487) and its 9 in 10 is 25 (`0.908`; 24 gives 0.898);
* the bench craft of `CRAFTED` costs 6 Orbs of Alteration at `a = 0.5`, for sure: 3 c.

So the craft of `CRAFTED` with 20% Intrinsic quality costs `C = 3 + k N` at `k = 2`: its mean `3 + 2 E(0)`, its percentiles `3 + 2 q(N)`; the
one of `HELD` with the wish for 30 costs `b G` at `b = 0.25`: its median 2.0 c and its 9 in 10 6.25 c. The cost grid is exact on both (every cost
a whole multiple of 0.25), so the risk's figures are these numbers, not bounds of them.
"""

import datetime
import math
import textwrap

import pytest
from targets_support import DATA, parse
from test_cli_offers import with_currency_names

from crafting_system.cli import evaluate_route, parse_route
from crafting_system.cli._report import build_report, policy_document, render_text
from crafting_system.cli._route_view import build_section, route_input
from crafting_system.cli._verify import verify
from crafting_system.planner import PlanSettings, plan_target
from crafting_system.planner import _envelope
from crafting_system.prices import PriceFile
from crafting_system.prices.price_file import PriceEntry
from crafting_system.prices.provenance import EXCHANGE, Provenance

D = with_currency_names(DATA)
K, A, B = 2.0, 0.5, 0.25  # an Intrinsic Catalyst, an Orb of Alteration and a Blessed Orb, in Chaos
IMPLICIT = "ManaRegenerationImplicitAmulet1"
QUALITY = "quality:\n  type: intrinsic\n  min_percent: 20\n"
CRAFTED = (
    "requirements:\n  - family: IncreasedWeaponElementalDamagePercent\n    mod: EinharMasterWeaponElementalDamage1_\n"
    + QUALITY
    + "start_item:\n  rarity: rare\n  mods:\n    - mod: LightningResist7\n      values: [45]\n"
)
HELD = (
    f"requirements:\n  - family: LightningResistance\n    min_tier: 2\nimplicits:\n  - family: {DATA.mods[IMPLICIT].families[0]}\n    min_roll: 30\n"
    "start_item:\n  rarity: rare\n  mods:\n    - mod: LightningResist7\n      values: [45]\n"
)
CATALYST_TITLE = "Intrinsic Catalyst until the item has 20% Intrinsic quality"


@pytest.fixture(autouse=True)
def every_shared_kernel_checked(monkeypatch):
    monkeypatch.setattr(_envelope, "CHECK_SHARED", True)  # the search builds every kernel it shares by key again and compares (#886)


def _prices() -> PriceFile:
    entry = lambda value: PriceEntry(value, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", "2026-10-30", 1e9))  # noqa: E731
    named = {"Intrinsic Catalyst": K, "Orb of Alteration": A, "Blessed Orb": B}
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, {name: entry(value) for name, value in named.items()})


def _plan(text: str, methods: tuple[str, ...]):
    return plan_target(D, parse(text, methods=methods), _prices(), PlanSettings(recipe_starts=False, solver="envelope"))


def _catalyst_law() -> dict[int, float]:
    """P(N = n) for the catalysts from 0% to 20% at item level 84, by hand: the points walk up by 1 or 2 until they reach 20."""
    two = 30 * math.exp(-84 / 30) - 0.3 - 1  # frac(f): the chance of +2
    at = {0: 1.0}  # the chance the walk stands at q points after n uses (not yet at 20)
    law: dict[int, float] = {}
    for n in range(1, 21):
        nxt: dict[int, float] = {}
        for q, chance in at.items():
            for gain, share in ((1, 1 - two), (2, two)):
                if q + gain >= 20:
                    law[n] = law.get(n, 0.0) + chance * share
                else:
                    nxt[q + gain] = nxt.get(q + gain, 0.0) + chance * share
        at = nxt
    return law


def _quantile(law: dict[int, float], level: float) -> int:
    total = 0.0
    for n in sorted(law):
        total += law[n]
        if total >= level - 1e-12:
            return n
    raise AssertionError("the law does not reach the level")


@pytest.fixture(scope="module")
def crafted():
    return _plan(CRAFTED, ("bench-craft", "catalyst"))


def test_the_risk_is_that_of_the_mods_and_the_catalysts_together(crafted):
    law = _catalyst_law()
    mean_n = sum(n * chance for n, chance in law.items())
    assert mean_n == pytest.approx(13.35, abs=0.005)
    risk = crafted.risk
    assert crafted.mean_remaining == pytest.approx(3.0, rel=1e-12)  # the mods alone: the bench craft
    assert risk.mean.value == pytest.approx(3 + K * mean_n, rel=1e-9) == pytest.approx(crafted.craft_mean, rel=1e-9)
    assert risk.p50.value == pytest.approx(3 + K * _quantile(law, 0.5), abs=1e-9)
    assert risk.p90.value == pytest.approx(3 + K * _quantile(law, 0.9), abs=1e-9)
    worst = _quantile(law, 0.9)  # CVaR at 0.9: the mean of the dearest tenth of the runs, the atom at the 9-in-10 split in part
    above = {n: chance for n, chance in law.items() if n > worst}
    at = 0.1 - sum(above.values())
    cvar = (sum(n * chance for n, chance in above.items()) + worst * at) / 0.1
    assert risk.cvar.value == pytest.approx(3 + K * cvar, rel=1e-9)


def test_the_blessed_orbs_percentiles_are_those_of_the_geometric_count():
    plan = _plan(HELD, ("blessed-orb",))
    assert plan.mean_remaining == 0.0 and plan.risk.mean.value == pytest.approx(11 * B, rel=1e-9)
    assert plan.risk.p50.value == pytest.approx(8 * B, abs=1e-9) and plan.risk.p90.value == pytest.approx(25 * B, abs=1e-9)


def test_both_finishes_follow_the_mods_one_after_the_other():
    plan = _plan(CRAFTED.replace("start_item:", f"implicits:\n  - family: {DATA.mods[IMPLICIT].families[0]}\n    min_roll: 30\nstart_item:"), ("bench-craft", "catalyst", "blessed-orb"))
    assert [step.kind for step in plan.finish_steps] == ["quality", "implicit"]
    assert plan.risk.mean.value == pytest.approx(3 + K * sum(n * chance for n, chance in _catalyst_law().items()) + 11 * B, rel=1e-9)


def test_the_page_draws_the_catalysts_as_the_last_step_with_the_quality_on_the_cards(crafted):
    section = build_section(route_input(crafted), D)
    *mods, last = section.rows
    assert last.title == CATALYST_TITLE and last.final and not any(row.final for row in mods)
    fields = {field.label: [line.text for line in field.lines] for field in last.fields}
    assert fields["Goal"] == ["20% Intrinsic quality"]
    assert fields["Cost per use"] == ["1 × Intrinsic Catalyst 2 c"]
    assert fields["Uses on average"] == ["≈ 13.3"] and fields["Step cost"] == ["≈ 26.7 c"]
    assert any("approximate input" in note for note in fields["Note"])
    assert "Intrinsic catalyst quality 20% or more" in last.after.properties  # the item the step leaves
    assert "Intrinsic catalyst quality 20% or more" in section.goal.target.properties  # the target as asked
    goal = {field.label: [line for line in field.lines] for field in section.goal.fields}
    assert goal["Mean"][0].text.startswith("≈ 29.7 c")  # 3 + 26.7: the mods and the catalysts
    assert any(line.text.startswith("Intrinsic Catalyst: 2 Chaos") for line in goal["Prices"])  # the price list holds what the step buys
    assert mods[-1].title.startswith("Benchcraft") and last.number == mods[-1].number + 1  # the sure craft that makes the mods is right above


def test_the_text_and_the_json_say_the_same_step_and_the_whole_mean(crafted):
    report = build_report(crafted, D)
    *_, last = report.steps
    mean_n = sum(n * chance for n, chance in _catalyst_law().items())
    assert last.title == CATALYST_TITLE and last.uses == pytest.approx(mean_n, rel=1e-9) and last.step_cost == pytest.approx(K * mean_n, rel=1e-9)
    text = render_text(report)
    assert f"Step {last.number}: {CATALYST_TITLE}" in text and "used 13.35 times on average, 26.69 Chaos in all" in text
    totals = policy_document(report)["totals"]
    assert totals["mean_cost_without_start"] == pytest.approx(3 + K * mean_n, rel=1e-9) == pytest.approx(totals["mean_cost"]["value"], rel=1e-9)


def test_verify_runs_the_catalysts_after_the_mods_and_agrees(crafted):
    check = verify(D, crafted, runs=2_000, seed=7)
    assert check.agrees, check.reason
    assert check.computed_mean == pytest.approx(3 + K * sum(n * chance for n, chance in _catalyst_law().items()), rel=1e-9)
    assert check.report.cost.value == pytest.approx(check.computed_mean, rel=0.03)  # each run pays its catalysts: about 26.7 c of 29.7 c


def test_a_routes_catalyst_rule_is_read_as_the_finish(crafted):
    bench = crafted.policy[crafted.start].label  # the bench craft of the plan
    route = parse_route(textwrap.dedent(f"""\
        rules:
          - do: Intrinsic Catalyst
          - do: {bench}
    """), crafted, D)  # fmt: skip
    assert route.finished == ("Intrinsic Catalyst",) and [rule.do for rule in route.rules] == [bench]
    result = evaluate_route(crafted, route, D)
    assert not result.gaps and result.risk.mean.value == pytest.approx(crafted.risk.mean.value, rel=1e-9)


def test_a_finish_hung_on_int_states_follows_only_the_target_s_own_goals():
    """The fold works on any states (a packed plan's ints, a product's tuples): two uses of 1 c at a half to the goal, then a finish of 2 c a
    use at a half: `E = 2 + 4 = 6`; a donor's goal (`main_goal` false) takes no finish, so a policy whose input ends there costs no more."""
    from fractions import Fraction
    from types import SimpleNamespace

    from crafting_system.planner import FinishStep, evaluate_risk
    from crafting_system.solver import Action

    step = FinishStep("implicit", SimpleNamespace(label="Orb", cost=2.0), "the roll", Fraction(2), Fraction(1, 2), ((0, ((Fraction(1, 2), None), (Fraction(1, 2), 0))),), "")
    policy = {0: Action("a", 1.0, ((1, 1), (0, 1)))}
    risk = evaluate_risk(policy, 0, lambda state: state == 1, 2.0, steps=(step,))
    assert risk.mean.value == pytest.approx(6.0, rel=1e-9)
    alone = evaluate_risk(policy, 0, lambda state: state == 1, 2.0, steps=(step,), main_goal=lambda state: False)
    assert alone.mean.value == pytest.approx(2.0, rel=1e-9)


def test_a_route_naming_the_catalyst_loads_when_the_start_already_has_the_quality():
    text = CRAFTED.replace("      values: [45]\n", "      values: [45]\n  quality:\n    type: intrinsic\n    percent: 20\n")
    plan = _plan(text, ("bench-craft", "catalyst"))
    assert plan.quality_finish is not None and not plan.finish_steps
    route = parse_route(f"rules:\n  - do: Intrinsic Catalyst\n  - do: {plan.policy[plan.start].label}\n", plan, D)
    assert route.finished == ("Intrinsic Catalyst",) and evaluate_route(plan, route, D).risk.mean.value == pytest.approx(3.0, rel=1e-9)


def test_the_blessed_orbs_are_in_the_price_list_and_a_start_that_needs_no_mod_is_not_the_last_row():
    plan = _plan(HELD, ("blessed-orb",))
    section = build_section(route_input(plan), D)
    first, last = section.rows
    assert not first.final and last.final and last.title.startswith("Blessed Orb until the implicit")
    prices = next(field for field in section.goal.fields if field.label == "Prices")
    assert any(line.text.startswith("Blessed Orb: 0.25 Chaos") for line in prices.lines)
