"""A plan whose actions read a rule axis, solved at every reading and shown with its interval, end to end through the command (ticket #589).

No action the planner offers today reads an axis that is not `planned` (the recombinator and the Awakener's Orb take donors, which the planner
refuses), so the test registers a toy kind: a "lucky craft" that adds R12's "+1 to Level of all Lightning Skill Gems" with a chance the sources
are taken to leave open (the toy axis `toy.luck`, 1/5, 1/2 or 4/5, planned at 1/2), and leaves the amulet as it was otherwise. It is cheap, so
the plan uses it at every reading, and its mean cost is then the craft's price over that chance, worked by hand in `MEANS`.
"""

import dataclasses
import json
from collections.abc import Iterator
from fractions import Fraction

import pytest
from cli_support import R12, TODAY, price_file
from items_support import DATA, roll

from crafting_system.actions import Action, Adds, Axis, Finite, Kind, NotApplicableError, OutOfScopeError, Reading, Reads, registered
from crafting_system.cli import PlanError, build_report, make_plan
from crafting_system.cli._axes import AXIS_WORDS, AxisWords
from crafting_system.cli._main import main
from crafting_system.cli._reach import policy_states
from crafting_system.data import GameData
from crafting_system.items import Item, ItemError, Rarity
from crafting_system.prices import PriceEntry
from crafting_system.targets import load_target

GEM = "GlobalLightningGemLevel1"
LUCK = Axis("toy.luck", (Fraction(1, 5), Fraction(1, 2), Fraction(4, 5)), Fraction(1, 2))
LUCKY = "Toy Lucky Craft"
PRICE = 0.01  # Chaos a use, far below a Harvest reforge: the plan takes the craft at every reading


@dataclasses.dataclass(frozen=True)
class LuckyCraft(Action):
    """Adds the +1 Lightning gem mod to a rare item that lacks it with the chance of the reading; otherwise the item is unchanged."""

    def label(self, data: GameData | None = None) -> str:
        return LUCKY

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {LUCKY: 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset(data.mods[GEM].families))

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(draws=False)

    def rule_axes(self, data: GameData) -> tuple[Axis, ...]:
        return (LUCK,)

    def outcomes(self, data: GameData, item: Item, reading: Reading | None = None) -> Finite:
        if item.rarity is not Rarity.RARE or any(entry.mod_id == GEM for entry in item.mods):
            raise NotApplicableError("the toy craft works on a rare item without the gem mod")
        luck = (reading or Reading()).get(LUCK.name, LUCK.plan)
        try:
            crafted = item.changed(data, mods=(*item.mods, roll(GEM)))
        except ItemError as error:
            raise NotApplicableError("the gem mod does not fit on the item") from error
        return Finite(data, item, ((luck, crafted), (1 - luck, item)))


def _members(data: GameData, item: Item) -> Iterator[Action]:
    if item.rarity is Rarity.RARE:
        yield LuckyCraft()


LUCKY_KIND = Kind("toy-lucky-craft", _members, order=903)
MEANS = {Fraction(1, 5): PRICE * 5, Fraction(1, 2): PRICE * 2, Fraction(4, 5): PRICE * 5 / 4}  # a geometric number of uses, each PRICE
START = 4.0  # the start amulet's price in `price_file`


def route_labels(plan) -> set[str]:
    """The actions the plan takes in the states its route reaches from the start."""
    return {plan.policy[state].label for state in policy_states(plan.start, plan.policy, plan.is_goal) if not plan.is_goal(state)}


@pytest.fixture
def lucky(monkeypatch):
    monkeypatch.setitem(AXIS_WORDS, LUCK.name, AxisWords("luck", "the chance of the toy craft"))
    with registered(LUCKY_KIND):
        yield dataclasses.replace(price_file(), prices={**price_file().prices, LUCKY: PriceEntry(PRICE, "test")})


def test_a_plan_that_reads_an_axis_is_solved_at_every_reading_not_refused(lucky):
    plan = make_plan(DATA, load_target(R12, DATA), lucky)

    assert plan.readings is not None
    assert route_labels(plan) == {LUCKY}
    assert plan.mean_remaining == pytest.approx(MEANS[LUCK.plan])  # the plan is the route at the plan reading
    costs = {reading[LUCK.name]: cost.value for reading, cost in plan.readings.plan.costs.items()}
    assert costs == pytest.approx(MEANS)  # the driver's costs are without the start item; the answer adds it


def test_the_report_carries_the_interval_of_the_plan_over_the_grid(lucky):
    report = build_report(make_plan(DATA, load_target(R12, DATA), lucky), DATA)

    assert report.interval is not None and report.interval.axes == (LUCK.name,)
    assert report.interval.plan_reading == "luck = 0.5"
    assert report.interval.best.value == pytest.approx(START + MEANS[Fraction(4, 5)])
    assert report.interval.worst.value == pytest.approx(START + MEANS[Fraction(1, 5)])
    assert report.interval.worst_reading == "luck = 0.2"


def test_the_command_shows_the_interval_in_the_text_the_json_and_the_page(lucky, tmp_path, capsys):
    out = tmp_path / "policy.json"

    code = main([str(R12), "--json", str(out)], data=DATA, prices=lucky, env={}, today=TODAY)

    shown = capsys.readouterr().out
    assert code == 0, shown
    assert "Plan and its interval" in shown and "luck = 0.2: the plan costs" in shown
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["interval"]["rule_axes"] == [{"axis": LUCK.name, "words": "the chance of the toy craft"}]
    assert [row["reading"] for row in document["interval"]["readings"]] == ["luck = 0.2", "luck = 0.5", "luck = 0.8"]
    page = (tmp_path / f"{R12.stem}.route.html").read_text(encoding="utf-8")
    assert "the chance of the toy craft" in page
    assert f"{START + MEANS[Fraction(4, 5)]:,.2f} to {START + MEANS[Fraction(1, 5)]:,.2f} Chaos over the grid" in page


def test_a_solver_that_takes_no_reading_is_refused_with_the_rule_in_words(lucky):
    for solver in ("packed", "envelope"):
        with pytest.raises(PlanError, match="the chance of the toy craft"):
            make_plan(DATA, load_target(R12, DATA), lucky, solver=solver)


def test_a_plan_whose_route_reads_no_axis_has_no_interval_block(lucky):
    dear = dataclasses.replace(lucky, prices={**lucky.prices, LUCKY: PriceEntry(1e6, "test")})  # the reforge wins: the plan never crafts

    plan = make_plan(DATA, load_target(R12, DATA), dear)

    assert plan.readings is not None and LUCKY not in route_labels(plan)
    assert build_report(plan, DATA).interval is None


def test_a_time_budget_is_said_not_to_apply_to_a_plan_solved_at_every_reading(lucky):
    plan = make_plan(DATA, load_target(R12, DATA), lucky, budget=60.0)

    assert plan.readings is not None and plan.approximation is None
    assert "The time budget was not applied" in [limit.what for limit in plan.limits]


SHAKY = "Toy Shaky Craft"


@dataclasses.dataclass(frozen=True)
class ShakyCraft(LuckyCraft):
    """The lucky craft, but with no rule at the lowest reading: the model of that reading leaves it out (a gap)."""

    def label(self, data: GameData | None = None) -> str:
        return SHAKY

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {SHAKY: 1}

    def outcomes(self, data: GameData, item: Item, reading: Reading | None = None) -> Finite:
        if (reading or Reading()).get(LUCK.name, LUCK.plan) == Fraction(1, 5):
            raise OutOfScopeError("no rule for the toy craft at this reading")
        return super().outcomes(data, item, reading)


def test_a_gap_of_another_reading_is_said_in_the_limits(lucky):
    shaky = Kind("toy-shaky-craft", lambda data, item: (ShakyCraft(),) if item.rarity is Rarity.RARE else (), order=904)
    prices = dataclasses.replace(lucky, prices={**lucky.prices, SHAKY: PriceEntry(PRICE, "test")})
    with registered(shaky):
        plan = make_plan(DATA, load_target(R12, DATA), prices)

    assert not plan.abstraction.gaps.entries()  # the plan reading has a rule everywhere
    said = [limit for limit in plan.limits if any(text.startswith(SHAKY) for text in limit.labels)]
    assert said, [limit.what for limit in plan.limits]
