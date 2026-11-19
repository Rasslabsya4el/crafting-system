"""Blocking and filler bench crafts offered by a rule, not by the target (#886, OR-41), on a hand-worked belt of the fixture data.

The world: a rare belt that holds the Energy Shield prefix and two suffixes (Fire and Cold Resistance). The goal is the top Life prefix,
`IncreasedLife3`. The belt's open pool, with no family it holds: prefixes Life 1, 2 and 3 (1,000 each); suffixes Life Regeneration (1,000),
Lightning Resistance (8 x 1,000) and Chaos Resistance (6 x 250), 10,500 in all. Two prefix slots are open and one suffix slot. The test data
adds two bench crafts of Belts, both suffixes of a family no draw gives (`TestFiller` and `TestFillerTwo`), at 1 and 3 Orbs of Alteration.
The bought start item costs `S`, an Exalted Orb `e`, an Orb of Alteration `c`.

* An Exalted Orb adds a prefix with chance 3,000 / 13,500 = 2/9, and that prefix is Life 3 with chance 1/3; otherwise it adds a suffix,
  which fills the suffixes, and the next Exalted Orb adds a prefix, Life 3 with chance 1/3. A Life 1 or 2 takes the Life family for good,
  and the item is bought again. So `V = e + (7/9) e + (2/3)(S + V)`, that is `V = 16e/3 + 2S`.
* With the filler crafted first the suffixes are full at once: `V = c + e + (2/3)(S + V)`, that is `V = 3(c + e) + 2S`, cheaper exactly
  when `c < 7e/9`.

At S = 50, e = 10, c = 1: 153.33 without the craft and 133 with it. The target names the two kinds the figures are
worked for and no craft: every method is on by default since #886, and with all of them another priced method of the fixture reaches
Life far cheaper (about 3.3 c), so the figures above would not be what the plan is held to. The rule itself is on by default
(`_offers.BLOCKING_CRAFTS`, `tests/test_actions_opt_in.py`).
"""

import dataclasses
import datetime

import pytest
from test_cli_offers import BELT, PRICED_DATA

from crafting_system.abstraction import Goal
from crafting_system.data.model import BenchActions, BenchOption, CostEntry, Mod, StatRange
from crafting_system.planner import PlanSettings, _envelope, _envelope_plan, _offers, plan_target
from crafting_system.planner import _plan as planner_plan
from crafting_system.planner._offers import offers_for
from crafting_system.prices import PriceFile
from crafting_system.prices.price_file import PriceEntry
from crafting_system.prices.provenance import EXCHANGE, Provenance
from crafting_system.targets import load_target

ALTERATION = "Metadata/Items/Currency/CurrencyRerollMagic"
FILLER, FILLER_TWO = "TestMasterFiller", "TestMasterFillerTwo"
S, E, C = 50.0, 10.0, 1.0


def _filler(mod_id: str, family: str) -> Mod:
    template = PRICED_DATA.mods["StrMasterItemGenerationCannotChangePrefixes"]  # a crafted suffix of the fixture, as a template
    return dataclasses.replace(
        template, id=mod_id, name="of Filling", text="+1 to Filling", type=family, families=(family,), stats=(StatRange(f"test_{family}", 1, 1),)
    )


def _option(mod_id: str, alterations: int) -> BenchOption:
    return BenchOption("Test Master", 0, ("Belt",), (CostEntry(ALTERATION, alterations),), BenchActions(mod_id, None, None, None, None, None, None, None, None))


@pytest.fixture(scope="module")
def data():
    mods = {**PRICED_DATA.mods, FILLER: _filler(FILLER, "TestFiller"), FILLER_TWO: _filler(FILLER_TWO, "TestFillerTwo")}
    regal = "Metadata/Items/Currency/CurrencyUpgradeToRare"  # some belt crafts of the fixture bench cost it (unpriced here: they are left out)
    template = PRICED_DATA.base_items[ALTERATION]
    bases = {**PRICED_DATA.base_items, regal: dataclasses.replace(template, id=regal, name="Regal Orb")}
    options = (*PRICED_DATA.bench_options, _option(FILLER, 1), _option(FILLER_TWO, 3))
    return dataclasses.replace(PRICED_DATA, mods=mods, base_items=bases, bench_options=options)


def _prices(alteration: float = C) -> PriceFile:
    day = "2026-10-30"
    entry = lambda chaos: PriceEntry(chaos, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", day, 1e9))  # noqa: E731
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, {"Exalted Orb": entry(E), "Orb of Alteration": entry(alteration)})


TARGET = """\
base: Leather Belt
item_level: 84
influence: []
requirements:
  - family: IncreasedLife
start_item:
  rarity: rare
  mods:
    - mod: IncreasedEnergyShield1
      values: [1]
    - mod: FireResist1
      values: [6]
    - mod: ColdResist1
      values: [6]
start: bought
"""
METHODS = ("exalted-orb", "bench-craft")  # the run's methods setting the belt is planned with (#405: a target names none)


def belt(path, data, methods=METHODS):
    """The belt at `path`, planned with `methods` (`Target.actions`, as the planner's entry sets it from `PlanSettings.methods`)."""
    return dataclasses.replace(load_target(path, data), actions=methods)


@pytest.fixture
def target(tmp_path, data):
    path = tmp_path / "belt.yaml"
    path.write_text(TARGET, encoding="utf-8")
    return belt(path, data)


@pytest.fixture(autouse=True)
def every_shared_kernel_checked(monkeypatch):
    monkeypatch.setattr(_envelope, "CHECK_SHARED", True)  # the search builds every kernel it shares by key again and compares (#886)


def _plan(data, target, monkeypatch, blocking: bool, alteration: float = C):
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", blocking)
    return plan_target(data, target, _prices(alteration), PlanSettings(recipe_starts=False, start_price=S, solver="envelope"))


def _fills(label: str) -> bool:
    return "Filling" in label


def test_without_the_rule_the_plan_exalts_until_a_prefix_at_16e_over_3_plus_2s(data, target, monkeypatch):
    plan = _plan(data, target, monkeypatch, blocking=False)
    assert target.base_id == BELT
    assert plan.mean_remaining == pytest.approx(16 * E / 3 + 2 * S, rel=1e-9)
    assert not any(_fills(entry.label) for entry in plan.offers)
    assert plan.search is not None and not plan.search.widening  # no offer adds more than the junk count: one search, as before the rounds


def test_the_groups_grow_from_the_least_refining_and_fewest_offers_and_one_kind_of_thousands_comes_after_them():
    # no number decides a group: offers that add nothing beyond the junk count are one group; once one adds more, each kind and what it adds is a
    # group, ordered by the features beyond the junk count, then the number of offers; the target's named offers lead the first group
    from types import SimpleNamespace

    from crafting_system.planner import _rounds

    def offer(kind, label=None, blocks=None):
        return SimpleNamespace(kind=kind, label=label or kind, blocks=blocks)

    adds = {"essence": frozenset(), "fossil": frozenset(), "annul": frozenset({"junk"}), "lock": frozenset({"junk", "metamods"}), "exalt": frozenset({"junk"})}
    plain = [offer("essence")] * 3 + [offer("annul")]
    (only,) = _rounds.round_groups(plain, (), lambda o: adds[o.kind])
    assert only.positions == (0, 1, 2, 3)  # main's defaults: one search
    offers = [offer("fossil")] * 9 + [offer("essence")] * 3 + [offer("lock", blocks=("prefix",)), offer("annul"), offer("exalt")]
    groups = _rounds.round_groups(offers, ("exalt",), lambda o: adds[o.kind])
    # the junk count is no refinement in the order (the Annulment Orb's one offer comes first), a metamod is (the lock comes after the 9 fossils)
    assert [(g.kinds, len(g.positions)) for g in groups] == [(("annul", "exalt"), 2), (("essence",), 3), (("fossil",), 9), (("lock",), 1)]
    assert sorted(i for g in groups for i in g.positions) == list(range(len(offers)))  # every offer has its round


def test_a_first_round_with_no_plan_closes_joins_the_next_and_its_record_holds_no_infinity():
    import json
    from types import SimpleNamespace

    from crafting_system.planner import _rounds

    groups = (_rounds.Group((0,), ("a",), frozenset()), _rounds.Group((1,), ("b",), frozenset({"junk", "x"})))
    seen = []

    def run(chosen, call):
        seen.append(chosen)
        if len(chosen) == 1:
            raise _rounds.NoPlan("no plan of a alone")
        return SimpleNamespace(search=SimpleNamespace(lower=5.0), mean_remaining=5.0)

    widened = _rounds.widen(
        groups, ("a", "b"), run, upper_of=lambda plan: 5.0, mean_of=lambda plan: plan.mean_remaining, ended=lambda plan: (_rounds.CLOSED, ""),
        left=lambda: None, clock_now=lambda: 0.0,
    )  # fmt: skip
    assert seen == [("a",), ("a", "b")] and widened.plan.mean_remaining == 5.0  # the round with no plan is the base of the next
    assert [record.status for record in widened.records] == ["no plan", "closed"] and _rounds.all_closed(widened.records)
    json.dumps([record.document() for record in widened.records], allow_nan=False)


def test_a_refused_round_joins_the_next_and_a_round_with_no_plan_in_hand_has_all_the_time_left():
    # a refusal (a solve that failed) proves nothing against its offers: they stay in the next rounds, and the round is not closed (OR-13); until
    # a plan is in hand a round may take all the time left (one search's share), and once one is, the rounds left share it
    from types import SimpleNamespace

    from crafting_system.planner import _rounds

    groups = tuple(_rounds.Group((i,), (kind,), frozenset()) for i, kind in enumerate("abcd"))
    seen = []

    def run(chosen, call):
        seen.append((chosen, call.searches))
        if chosen == ("a", "b"):
            raise ValueError("the policy is improper")
        if len(chosen) == 1:
            raise _rounds.NoPlan("no plan of a alone")
        return SimpleNamespace(search=SimpleNamespace(lower=5.0), mean_remaining=5.0)

    widened = _rounds.widen(
        groups, tuple("abcd"), run, upper_of=lambda plan: 5.0, mean_of=lambda plan: plan.mean_remaining, ended=lambda plan: (_rounds.CLOSED, ""),
        left=lambda: 600.0, clock_now=lambda: 0.0,
    )  # fmt: skip
    assert seen == [(("a",), 1), (("a", "b"), 1), (("a", "b", "c"), 1), (("a", "b", "c", "d"), 1)]  # the last round is alone in its share too
    assert [record.status for record in widened.records] == ["no plan", "refused", "closed", "closed"] and not _rounds.all_closed(widened.records)
    shares = []

    def planned(chosen, call):
        shares.append(call.searches)
        return SimpleNamespace(search=SimpleNamespace(lower=5.0), mean_remaining=5.0)

    _rounds.widen(
        groups[1:], tuple("abcd"), planned, upper_of=lambda plan: 5.0, mean_of=lambda plan: plan.mean_remaining, ended=lambda plan: (_rounds.CLOSED, ""),
        left=lambda: 600.0, clock_now=lambda: 0.0,
    )  # fmt: skip
    # round 1 has no plan in hand; then the plan is, and the two rounds left share the time. Round 2 closed at the plan in hand's cost, so it
    # was not carried and one last round holds it again with every offer (#1080): that round is owed from then on, so round 3 shares the time
    # with it (#1095), and it is alone in its share
    assert shares == [1, 2, 2, 1]


def test_a_round_with_no_plan_in_hand_gives_way_once_it_has_a_plan_and_its_share_and_a_later_round_finds_the_saving():
    # #1080: round 1 begins with no plan in hand, so it may take all the time left; its search makes a plan of 10 at once and then only raises its
    # lower figure (R10's bench crafts: a first plan at 147 s, then 440 s with nothing cheaper). The run has 600 s and three rounds: round 1's share
    # is 200 s. Its search asks after each of its own rounds (one per 50 s here); with a plan in hand and 200 s used it stops with its plan, and
    # rounds 2 and 3 are tried. Round 2 holds the saving: a plan of 7. The answer names what each round did.
    from types import SimpleNamespace

    from crafting_system.planner import _rounds

    groups = tuple(_rounds.Group((i,), (kind,), frozenset({"junk", kind})) for i, kind in enumerate("abc"))
    now = [0.0]  # the run's clock, moved by hand: nothing reads the time
    asked, seen = [], []

    def search(chosen, call):
        seen.append(chosen)
        if call.give_way is None:  # a plan is in hand: the round has its share, and here closes at once
            return SimpleNamespace(search=SimpleNamespace(lower=7.0), mean_remaining=7.0 if "b" in chosen else 10.0, stopped=None)
        for step in range(100):  # each of the search's rounds takes 50 s; the plan of 10 is in hand from the first
            now[0] += 50.0
            standing = SimpleNamespace(lower=1.0 + step / 100, upper=10.0, rounds=step, seconds=now[0])
            if (said := call.give_way(standing)) is not None:
                asked.append((step, now[0]))
                return SimpleNamespace(search=SimpleNamespace(lower=standing.lower), mean_remaining=10.0, stopped=said)
        raise AssertionError("the round never gave way")

    widened = _rounds.widen(
        groups, tuple("abc"), search, upper_of=lambda plan: plan.mean_remaining, mean_of=lambda plan: plan.mean_remaining,
        ended=lambda plan: (_rounds.STOPPED, plan.stopped) if plan.stopped else (_rounds.CLOSED, ""), left=lambda: 600.0 - now[0], clock_now=lambda: now[0],
    )  # fmt: skip
    assert asked == [(3, 200.0)]  # 200 s used, a plan in hand: it gives way there, not at the net
    assert [record.status for record in widened.records] == ["gave way", "closed", "closed"]
    assert widened.plan.mean_remaining == 7.0  # the later round held the saving and found it
    first = _rounds.round_line(1, widened.records[0])
    assert "gave way" in first and "200 seconds" in first and "its plan costs 10.00 Chaos" in first
    assert not _rounds.all_closed(widened.records)  # the round that gave way did not finish: no text calls the plan the cheapest of every method
    # with no plan in its search the round goes on to the net (OR-33): the rule asks for a plan in hand
    share = _rounds.Share(600.0, 3, 0.0, lambda: 500.0)
    assert share(SimpleNamespace(upper=None)) is None and share(SimpleNamespace(upper=float("inf"))) is None
    # past its share, a plan still falling goes on: R11's essences made 7,817 c and the next search round 597 c (a rule that gave way at the
    # first plan answered 7,837 c on a slower runner); the first search round that makes no cheaper plan gives way
    assert [share(SimpleNamespace(upper=upper)) is not None for upper in (7817.0, 597.0, 597.0)] == [False, False, True]
    calls = []
    _rounds.widen(
        groups[:1], tuple("abc"), lambda chosen, call: calls.append(call) or SimpleNamespace(search=SimpleNamespace(lower=7.0), mean_remaining=7.0),
        upper_of=lambda plan: 7.0, mean_of=lambda plan: 7.0, ended=lambda plan: (_rounds.CLOSED, ""), left=lambda: 600.0, clock_now=lambda: 0.0,
    )  # fmt: skip
    assert calls[0].give_way is None  # the last round has no rounds after it to give way to: it has all the time left


def test_counted_in_states_the_rounds_share_the_states_left_and_give_way_on_states_whatever_the_clock_does():
    # #886: the same rounds as the test above, in a run counted in states (`Budget.in_states`): 600 states, three rounds. Round 1 has no plan in
    # hand: its net is all 600 states and its share 200; its search knows 50 more states after each of its rounds, with the plan of 10 from the
    # first, so it gives way at 200 states. Round 2 has the plan in hand and the 400 states left over the 2 rounds left: a net of 200; its plan
    # of 7 closes knowing 120 states. Round 3, the last, has the 280 left. The clock jumps by 1,000 s at every reading, or stands still: the
    # rounds are the same, and each line names its states, never its seconds.
    from types import SimpleNamespace

    from crafting_system.planner import _rounds

    groups = tuple(_rounds.Group((i,), (kind,), frozenset({"junk", kind})) for i, kind in enumerate("abc"))

    def rounds(clock_now):
        nets, asked = [], []

        def search(chosen, call):
            nets.append((len(chosen), call.states))
            if "a" in chosen and len(chosen) == 1:
                for step in range(100):
                    standing = SimpleNamespace(lower=1.0 + step / 100, upper=10.0, rounds=step, seconds=clock_now(), states=50 * (step + 1))
                    if (said := call.give_way(standing)) is not None:
                        asked.append(standing.states)
                        return SimpleNamespace(search=SimpleNamespace(lower=standing.lower, touched=standing.states), mean_remaining=10.0, stopped=said)
                raise AssertionError("the round never gave way")
            call.give_way(SimpleNamespace(lower=7.0, upper=7.0, rounds=1, seconds=clock_now(), states=60))
            return SimpleNamespace(search=SimpleNamespace(lower=7.0, touched=120), mean_remaining=7.0, stopped=None)

        meter = _rounds.StatesMeter(600)
        widened = _rounds.widen(
            groups, tuple("abc"), search, upper_of=lambda plan: plan.mean_remaining, mean_of=lambda plan: plan.mean_remaining,
            ended=lambda plan: (_rounds.STOPPED, plan.stopped) if plan.stopped else (_rounds.CLOSED, ""),
            left=lambda: pytest.fail("a run counted in states reads no time left"), clock_now=clock_now, meter=meter,
        )  # fmt: skip
        return nets, asked, widened, meter

    jumps = iter(range(0, 10**9, 1000))
    slow = rounds(lambda: float(next(jumps)))
    still = rounds(lambda: 0.0)
    nets, asked, widened, meter = slow
    assert nets == [(1, 600), (2, 200), (3, 280)] and asked == [200]  # round 2 made the cheaper plan: round 3 holds it
    assert [record.status for record in widened.records] == ["gave way", "closed", "closed"] and widened.plan.mean_remaining == 7.0
    assert [record.states for record in widened.records] == [200, 120, 120] and meter.spent == 440
    lines = [_rounds.round_line(n, record) for n, record in enumerate(widened.records, start=1)]
    assert "200 states)" in lines[0] and "share of the states (200 states, the states left over the rounds left)" in lines[0]
    assert not any(" s)" in line for line in lines)
    other = still[2]
    assert (still[0], still[1]) == (nets, asked) and [_rounds.round_line(n, record) for n, record in enumerate(other.records, start=1)] == lines
    # out of states, the rounds after are not tried, and say so in states
    spent = _rounds.widen(
        groups, tuple("abc"), lambda chosen, call: SimpleNamespace(search=SimpleNamespace(lower=7.0, touched=900), mean_remaining=7.0),
        upper_of=lambda plan: 7.0, mean_of=lambda plan: 7.0, ended=lambda plan: (_rounds.CLOSED, ""), left=lambda: None, clock_now=lambda: 0.0,
        meter=_rounds.StatesMeter(600),
    )  # fmt: skip
    assert [record.status for record in spent.records] == ["closed", "not tried", "not tried"]
    assert _rounds.round_line(2, spent.records[1]).endswith("0 states): not tried, the run's states net was used up before this round")


def test_counted_in_states_a_round_that_raised_is_counted_at_the_states_its_search_knew_when_it_ended():
    # #1101: a round whose search proved no plan (`NoPlan`) or was stopped before one (`Stopped`) last stood at 40 states, then expanded more
    # before it raised: its search's `NoPolicy` carries the 70 it knew, and the round counts 70, not 40, as a round that made a plan counts its
    # plan's states. A refusal with no count is counted where its search last stood.
    from types import SimpleNamespace

    from crafting_system.planner import _rounds
    from crafting_system.planner._envelope import NoPolicy

    groups = tuple(_rounds.Group((i,), (kind,), frozenset({"junk", kind})) for i, kind in enumerate("abcd"))

    def raised(error):
        def search(chosen, call):
            call.give_way(SimpleNamespace(lower=1.0, upper=None, rounds=1, seconds=0.0, states=40))
            if "d" in chosen:
                return SimpleNamespace(search=SimpleNamespace(lower=7.0, touched=5), mean_remaining=7.0)
            try:
                raise NoPolicy("none", states=70) if error is not ValueError else ValueError("refused")
            except ValueError as cause:
                if error is ValueError:
                    raise
                raise error(*(("none",) if error is _rounds.NoPlan else ("stopped", 1.0))) from cause

        meter = _rounds.StatesMeter(1_000)
        widened = _rounds.widen(
            groups, tuple("abcd"), search, upper_of=lambda plan: 7.0, mean_of=lambda plan: 7.0, ended=lambda plan: (_rounds.CLOSED, ""),
            left=lambda: None, clock_now=lambda: 0.0, meter=meter,
        )  # fmt: skip
        return [record.states for record in widened.records], meter.spent

    assert raised(_rounds.NoPlan) == ([70, 70, 70, 40], 250)  # the last round makes its plan of 5 states, counted where it stood, at 40
    assert raised(_rounds.Stopped) == ([70, 70, 70, 40], 250)
    assert raised(ValueError) == ([40, 40, 40, 40], 160)


def test_a_group_beaten_before_the_last_round_is_not_carried_and_the_answer_does_not_call_the_plan_the_cheapest():
    # #1080 / #1091: the plan in hand is 10. Round 2 (b) ends at once on its lower figure: it is not carried, so round 3 holds a and c only, and
    # the answer names b among the rounds that do not make the plan the cheapest of every method (b with c was not searched: the module text has
    # the counterexample). A beaten last round has no round after it: it closes, and with every round closed the plan is the cheapest.
    from types import SimpleNamespace

    from crafting_system.planner import _rounds

    groups = tuple(_rounds.Group((i,), (kind,), frozenset()) for i, kind in enumerate("abc"))
    seen = []

    def run(chosen, call):
        seen.append(chosen)
        if call.upper is not None:
            raise _envelope.Beaten(10.0, None)
        return SimpleNamespace(search=SimpleNamespace(lower=10.0), mean_remaining=10.0)

    def widened(n):
        return _rounds.widen(
            groups[:n], tuple("abc"), run, upper_of=lambda plan: 10.0, mean_of=lambda plan: plan.mean_remaining, ended=lambda plan: (_rounds.CLOSED, ""),
            left=lambda: None, clock_now=lambda: 0.0,
        )  # fmt: skip

    three = widened(3)
    # b is not in round 3; every round closed, so one last round holds b again with every offer, and its proof is the whole one
    assert seen == [("a",), ("a", "b"), ("a", "c"), ("a", "b", "c")]
    assert [(record.status, record.carried) for record in three.records] == [("closed", True), ("beaten", True), ("beaten", True), ("beaten", True)]
    assert three.records[1].reason.endswith("the last round held them again, with every method") and three.records[3].kinds == ("b",)
    assert _rounds.all_closed(three.records)
    seen.clear()
    two = widened(2)  # a beaten last round has no round after it: it closes, and no round is added
    assert seen == [("a",), ("a", "b")] and [(record.status, record.carried) for record in two.records] == [("closed", True), ("beaten", True)]

    def stopped_c(chosen, call):
        if chosen == ("a", "c"):
            raise _rounds.Stopped("the time limit was reached", 3.0)
        return run(chosen, call)

    seen.clear()
    stopped = _rounds.widen(
        groups, tuple("abc"), stopped_c, upper_of=lambda plan: 10.0, mean_of=lambda plan: plan.mean_remaining, ended=lambda plan: (_rounds.CLOSED, ""),
        left=lambda: None, clock_now=lambda: 0.0,
    )  # fmt: skip
    # round 3 stopped: the whole proof is out of reach, so no last round is added, and b stays set aside, named with its figure
    assert seen == [("a",), ("a", "b")] and [(record.status, record.carried) for record in stopped.records] == [("closed", True), ("beaten", False), ("stopped", True)]
    assert "the rounds after it did not hold them" in _rounds.round_line(2, stopped.records[1])
    not_finished = _rounds.rounds_limits(stopped.records, True, None)[1]
    assert [name.split(" (")[0] for name in not_finished.names] == ["round 2", "round 3"] and not_finished.labels == ("b", "c")

    def rounds_with(last_round):
        return _rounds.widen(
            groups, tuple("abc"), lambda chosen, call: last_round(chosen) if chosen == ("a", "b", "c") else run(chosen, call), upper_of=lambda plan: 10.0,
            mean_of=lambda plan: plan.mean_remaining, ended=lambda plan: (_rounds.STOPPED, "stopped") if plan.mean_remaining < 10.0 else (_rounds.CLOSED, ""),
            left=lambda: None, clock_now=lambda: 0.0,
        ).records  # fmt: skip

    def stops(chosen):
        raise _rounds.Stopped("the time limit was reached", 3.0)

    def cheaper_unfinished(chosen):
        return SimpleNamespace(search=SimpleNamespace(lower=2.0), mean_remaining=2.0)

    for last_round in (stops, cheaper_unfinished):  # the last round did not close: b stays set aside, the proof is not claimed
        records = rounds_with(last_round)
        assert [record.carried for record in records] == [True, False, True, True] and not _rounds.all_closed(records)

    def closes(cost):
        def round_of(chosen, call):
            seen.append(chosen)
            return SimpleNamespace(search=SimpleNamespace(lower=cost if "b" in chosen else 10.0), mean_remaining=cost if "b" in chosen else 10.0)

        return round_of

    # b closes at the plan in hand's cost: set aside, also when its solve says 1e-7 less (each figure is certified to 1e-6 only, OR-32); b
    # closes cheaper: it is the plan, carried
    for cost, carried in ((10.0, False), (10.0 - 1e-7, False), (8.0, True)):
        seen.clear()
        closed_b = _rounds.widen(
            groups, tuple("abc"), closes(cost), upper_of=lambda plan: plan.mean_remaining * (1.0 + 1e-6), mean_of=lambda plan: plan.mean_remaining,
            ended=lambda plan: (_rounds.CLOSED, ""), left=lambda: None, clock_now=lambda: 0.0,
        )  # fmt: skip
        assert seen[2] == (("a", "b", "c") if carried else ("a", "c")) and closed_b.records[1].carried
        assert len(closed_b.records) == (3 if carried else 4) and _rounds.all_closed(closed_b.records)

    def c_refused(chosen, call):
        if chosen == ("a", "c"):
            raise ValueError("the policy is improper")
        return run(chosen, call)

    refused = _rounds.widen(
        groups, tuple("abc"), c_refused, upper_of=lambda plan: 10.0, mean_of=lambda plan: plan.mean_remaining, ended=lambda plan: (_rounds.CLOSED, ""),
        left=lambda: None, clock_now=lambda: 0.0,
    )  # fmt: skip
    assert [record.status for record in refused.records] == ["closed", "beaten", "refused"]  # a refused round: the proof is out of reach, no last round
    out = _rounds.widen(
        groups, tuple("abc"), run, upper_of=lambda plan: 10.0, mean_of=lambda plan: plan.mean_remaining, ended=lambda plan: (_rounds.CLOSED, ""),
        left=iter([600.0, 300.0, 100.0, 0.0]).__next__, clock_now=lambda: 0.0,
    )  # fmt: skip
    assert [record.status for record in out.records] == ["closed", "beaten", "beaten", "not tried"] and not out.records[1].carried  # no time left for it


def test_a_refused_group_is_set_aside_when_the_round_after_it_is_refused_too():
    # #1080 point 2: a refused round's group stays in the base (a wider round may solve it, R10's essences); when the next round is refused too, the
    # group is set aside, so a group whose offers make every solve refuse does not refuse every round after it
    from types import SimpleNamespace

    from crafting_system.planner import _rounds

    groups = tuple(_rounds.Group((i,), (kind,), frozenset()) for i, kind in enumerate("abcd"))
    seen = []

    def run(chosen, call):
        seen.append(chosen)
        if "b" in chosen:
            raise ValueError("the policy is improper")
        return SimpleNamespace(search=SimpleNamespace(lower=5.0), mean_remaining=5.0)

    widened = _rounds.widen(
        groups, tuple("abcd"), run, upper_of=lambda plan: 5.0, mean_of=lambda plan: plan.mean_remaining, ended=lambda plan: (_rounds.CLOSED, ""),
        left=lambda: None, clock_now=lambda: 0.0,
    )  # fmt: skip
    assert seen == [("a",), ("a", "b"), ("a", "b", "c"), ("a", "c", "d")]  # b refused twice: set aside, c stays
    assert [record.status for record in widened.records] == ["closed", "refused", "refused", "closed"]
    assert widened.records[1].reason.endswith("set aside, since the round after it was refused too")


def test_with_the_rule_the_plan_fills_the_suffix_with_the_cheaper_craft_then_exalts_at_3_c_plus_e_plus_2s(data, target, monkeypatch):
    plan = _plan(data, target, monkeypatch, blocking=True)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    first = next(entry for entry in plan.offers if entry.label == plan.solution.policy[plan.start].label)  # the solver's action of that offer
    assert _fills(first.label) and first.cost == C
    assert [entry.label for entry in plan.offers if _fills(entry.label)] == [first.label]  # one class: the dearer filler is not offered ...
    assert any(_fills(label) for limit in plan.limits for label in limit.labels)  # ... and the answer says so


def test_when_the_craft_costs_more_than_seven_ninths_of_an_exalted_orb_the_plan_does_not_use_it(data, target, monkeypatch):
    plan = _plan(data, target, monkeypatch, blocking=True, alteration=8.0)
    assert plan.mean_remaining == pytest.approx(16 * E / 3 + 2 * S, rel=1e-9)


def test_with_no_action_that_keeps_a_craft_and_reads_the_mods_only_the_metamods_are_offered(data, target):
    goal = Goal.from_target(target)
    rerolls = offers_for(data, goal, BELT, target.start_item, ["chaos-orb", "bench-craft"], blocking=True)
    crafts = [entry for entry in rerolls.offers if entry.kind == "bench-craft"]
    assert crafts and all(entry.blocks is not None for entry in crafts)  # every one is offered by the rule ...
    assert all({family for mod_id in entry.action.adds(data, target.start_item).named for family in data.mods[mod_id].families} & _offers.METAMOD_FAMILIES for entry in crafts)  # ... as a metamod
    assert any(_fills(label) for limit in rerolls.limits for label in limit.labels)


def test_a_filler_and_a_family_a_draw_gives_are_different_classes(data, target):
    goal = Goal.from_target(target)
    found = offers_for(data, goal, BELT, target.start_item, ["exalted-orb", "bench-craft"], blocking=True)
    classes = {entry.label: entry.blocks for entry in found.offers if entry.blocks is not None}
    fillers = {blocks for label, blocks in classes.items() if _fills(label)}
    assert fillers == {(("suffix",), frozenset(), frozenset())}  # the two fillers: one class
    assert set(classes.values()) == {
        (("suffix",), frozenset(), frozenset()),
        (("prefix",), frozenset(), frozenset()),  # the Elemental Damage with Attack Skills crafts: no draw on a belt gives that family
        (("prefix",), frozenset({"IncreasedEnergyShield"}), frozenset()),  # the Armour and Energy Shield craft blocks a family the belt draws
        (("suffix",), frozenset({"ItemGenerationCannotChangePrefixes"}), frozenset()),  # a metamod is told apart
    }


def test_on_an_item_that_takes_a_second_craft_two_fillers_are_told_apart_and_both_offered(tmp_path, data, monkeypatch):
    # with the multimod on the item a craft of a family already crafted is refused and one of another family is not: the two fillers differ
    held = TARGET.replace("    - mod: ColdResist1\n      values: [6]\n", "    - mod: StrIntMasterItemGenerationCanHaveMultipleCraftedMods\n      values: [1]\n      crafted: true\n")
    path = tmp_path / "multimod.yaml"
    path.write_text(held, encoding="utf-8")
    multimod = belt(path, data)
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    plan = plan_target(data, multimod, _prices(), PlanSettings(recipe_starts=False, start_price=S, solver="envelope"))
    assert {entry.label for entry in plan.offers if _fills(entry.label)} == {"Bench craft +1 to Filling [TestMasterFiller]", "Bench craft +1 to Filling [TestMasterFillerTwo]"}


def test_r12_with_every_shared_kernel_checked_gives_the_plan_it_gives_unchecked(monkeypatch):
    from cli_support import R12, price_file
    from items_support import DATA

    settings = PlanSettings(recipe_starts=False, solver="envelope")
    checked = plan_target(DATA, load_target(R12, DATA), price_file(), settings)  # `CHECK_SHARED` is on (the fixture of this module)
    monkeypatch.setattr(_envelope, "CHECK_SHARED", False)
    unchecked = plan_target(DATA, load_target(R12, DATA), price_file(), settings)
    assert checked.mean_remaining == unchecked.mean_remaining


# ---- the exact price cut and the rounds (#1069, `planner/_price_cut.py`, `planner/_rounds.py`) ------------------------------------------------
# With the rule on, the belt is offered Prefixes Cannot Be Changed at two Divine Orbs. The lock makes the model keep every mod's tags, so it is a
# group of its own (`Abstraction.features`): round 1 is the target's kinds and the fillers, whose plan is the filler plan above, `U = 3(c + e) + 2S
# = 133`; round 2 adds the lock. Buying the belt again and following that plan costs `S + U = 183`, so a craft priced at 183 or more is never better
# than that restart at any state but the start, and at the start it costs more than the whole plan: round 2 leaves it out before its model is built.
# A Divine Orb at 92 Chaos prices the lock at 184 (cut), at 91 at 182 (kept); either way no plan of round 2 costs less than 133, so round 2 ends as
# soon as its lower figure reaches it (`_envelope.Beaten`), and the plan is round 1's, proved the cheapest over every method.

LOCK = "Bench craft Prefixes Cannot Be Changed"


def _plan_at(data, target, monkeypatch, divine: float):
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    prices = dataclasses.replace(_prices(), chaos_per_divine=divine)
    return plan_target(data, target, prices, PlanSettings(recipe_starts=False, start_price=S, solver="envelope"))


def _rounds_of(plan):
    return plan.search.widening


@pytest.mark.parametrize("divine", [92.0, 91.0])
def test_the_lock_is_a_round_of_its_own_that_ends_once_its_lower_figure_reaches_the_plan_in_hand(data, target, monkeypatch, divine):
    plan = _plan_at(data, target, monkeypatch, divine=divine)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    *closed, last = _rounds_of(plan)
    # it ends at once (beaten) when its lower figure reaches the plan's certified upper figure, else by closing at the same cost: never below it
    assert [record.status for record in closed] == ["closed"] and last.status in ("beaten", "closed") and last.lower >= closed[-1].upper * (1 - 1e-6)
    assert LOCK not in {entry.label for entry in plan.offers} and not plan.abstraction.models_metamods  # the plan is round 1's
    assert plan.search.exact  # every round closed, the last with every method: the plan is the cheapest over them all (OR-13)
    assert any(limit.kind == "rounds" and limit.guarantee.startswith("The plan is the cheapest among every method offered") for limit in plan.limits)


@pytest.mark.parametrize("divine", [92.0, 91.0])
def test_through_the_entry_a_beaten_lock_round_is_not_carried_into_a_round_after_it(data, target, monkeypatch, divine):
    # #1080 / #1091 through `plan_target`: a third group after the lock's, whose offers round 1 already holds. When the lock's round is beaten,
    # round 3 holds round 1's offers without the lock, and a last round holds the lock again with every offer: beaten too, so the plan is the
    # cheapest of every method, as when the lock was carried. When the lock's round closes, it is carried and no round is added.
    from crafting_system.planner import _rounds

    real = planner_plan.offer_groups
    monkeypatch.setattr(planner_plan, "offer_groups", lambda *args: (*real(*args), _rounds.Group((), ("again",), frozenset())))
    plan = _plan_at(data, target, monkeypatch, divine=divine)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    first, lock, again, closing = _rounds_of(plan)
    # the lock's round, beaten or closed at the same cost, could not beat the plan in hand: round 3 does not hold it, the last round does
    assert lock.status in ("beaten", "closed") and again.offers == first.offers and closing.offers == first.offers + 1
    assert closing.kinds == lock.kinds and closing.status in ("beaten", "closed")
    assert lock.carried and plan.search.exact  # the last round held every offer and closed: the plan is the cheapest of every method


def test_through_the_entry_the_lock_gains_of_a_plan_of_rounds_build_only_the_plan_s_own_crafts(data, tmp_path, monkeypatch):
    # #1080 / #1091: the Lock is foreseen once the plan is chosen. Its gains for N fall back after a peek only to the crafts the plan's policy
    # takes (R05's foresight built every offer of the plan's round at each of 200 states: about 100 s and 8 GB after the net). The options of a
    # peek and the second solve still read every offer, and N's line says the largest gain is not proved. The belt names the Lock here; the
    # price file has no Lock price, so the Lock is dropped and N is still found (ADR-0056).
    path = tmp_path / "belt-lock.yaml"
    path.write_text(TARGET, encoding="utf-8")
    target = belt(path, data, (*METHODS, "hinekora-lock"))
    seen = []
    real = planner_plan.plan_foresight

    def spy(*args, fallback=None, **kwargs):
        full = real(*args, **kwargs)[0]  # every offer of the plan as the fallback, as before (and as a plan of one search still does)
        seen.append((args[7], args[6], fallback, full))
        return real(*args, fallback=fallback, **kwargs)

    monkeypatch.setattr(planner_plan, "plan_foresight", spy)
    plan = _plan_at(data, target, monkeypatch, divine=92.0)
    [(offered, priced, fallback, full)] = seen
    used = {action.label for action in plan.solution.policy.values()}
    assert [entry.label for entry in fallback] == [entry.label for entry in offered if entry.label in used]  # the plan's own crafts, in order
    assert len(fallback) < len(offered) and len(priced) == len(plan.offers)  # the options still come from every offer of the plan
    # N is a true gain, at most the gain over every craft (here the same), and its line no longer calls it the largest
    assert plan.foresight.status == full.status and 0.0 < plan.foresight.n <= full.n and full.n_exact and not plan.foresight.n_exact


def test_the_plan_s_own_crafts_are_read_from_a_packed_policy_without_building_an_action_and_cheaper_needs_both_errors():
    # a packed policy builds an action (its kernel) at a state when it is read (`PackedPolicy.__getitem__`); the plan's own crafts are named from
    # its offers, so no action is built at its thousands of states. And a round's plan is cheaper than the plan in hand only beyond the error of
    # both figures; with no certified figure (None) the means decide.
    from types import SimpleNamespace

    from crafting_system.planner import _rounds

    class Packed:
        def offers(self):
            return iter([("s1", SimpleNamespace(label="b")), ("s2", SimpleNamespace(label="b")), ("s3", SimpleNamespace(label="d"))])

        def values(self):
            raise AssertionError("an action was built")

    offered = tuple(SimpleNamespace(label=label) for label in "abcd")
    fallback = planner_plan.plan_fallback(SimpleNamespace(policy=Packed()), offered)
    assert [priced.label for priced in fallback] == ["b", "d"]
    plain = {"s1": SimpleNamespace(label="c")}  # a policy of actions (a walk's) is read as it is
    assert [priced.label for priced in planner_plan.plan_fallback(SimpleNamespace(policy=plain), offered)] == ["c"]
    assert not _rounds._cheaper(9.99999, 10.0, 10.0, 10.00001) and _rounds._cheaper(9.9, 9.90001, 10.0, 10.00001)
    assert _rounds._cheaper(9.99999, None, 10.0, 10.00001) and _rounds._cheaper(9.99999, 10.0, 10.0, None)  # the means decide


def test_a_round_its_net_stops_leaves_the_plan_in_hand_and_says_what_it_did_not_finish(data, target, monkeypatch):
    # #1070: round 1 closes and the next round meets the run's net before any plan of its own: the plan of round 1 is the answer, and it says so
    from crafting_system.budget import Binding, BudgetExceeded

    real = planner_plan._make_plan

    def later_stopped(*args, round_call=None, **kwargs):
        if round_call is not None and not round_call.watched and round_call.searches == 1:  # the last round, the lock's
            raise BudgetExceeded(Binding("the search", "time", 600.0, 600.0, "no plan found yet"))
        return real(*args, round_call=round_call, **kwargs)

    monkeypatch.setattr(planner_plan, "_make_plan", later_stopped)
    plan = _plan_at(data, target, monkeypatch, divine=91.0)  # a lock at 182 would be kept: its round is stopped
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    assert [record.status for record in _rounds_of(plan)] == ["closed", "stopped"]
    assert not plan.search.exact and plan.search.stopped  # no text calls it the cheapest of every method
    assert not any("cheapest among every method" in limit.guarantee for limit in plan.limits)
    untried = next(limit for limit in plan.limits if limit.what == "Not finished")
    assert untried.labels == ("bench-craft",) and "stopped" in untried.names[0]
    assert any(limit.kind == "crafts" and limit.what == "Not offered" for limit in plan.limits)  # what the choice of offers said is kept
    assert plan.foresight.status == "off: the run's methods setting does not name it"  # the run names no Lock
    assert plan.risk is not None


@pytest.mark.parametrize("lock_stopped", [True, False])
def test_a_round_proved_within_the_gap_proves_the_plan_within_it_only_when_every_round_closed(data, target, monkeypatch, lock_stopped):
    # #1182, #1186: round 1 (Exalted Orb and the filler) ends proved within 1% of the cheapest of its own methods, at 3 (c + e) + 2 S = 133 c
    # after the start item (183 c with it). When the lock's round is then stopped by the net, the plan is proved only against round 1's methods: the search
    # reads as stopped, never "within 1% of the cheapest" (R17 and R20 were recorded so, over a lower figure of 0 after the start item); the
    # rounds' limit still says round 1's gap. When the lock's round closes too, the last round held every offer and the gap is the whole proof.
    from crafting_system.budget import Binding, BudgetExceeded
    from crafting_system.cli._benchmark import _record
    from crafting_system.web._work import _search_document

    real = planner_plan._make_plan

    def first_within(*args, round_call=None, **kwargs):
        if round_call is not None and not round_call.watched and lock_stopped:  # the lock's round
            raise BudgetExceeded(Binding("the search", "time", 600.0, 600.0, "no plan found yet"))
        plan = real(*args, round_call=round_call, **kwargs)
        if round_call is not None and round_call.watched:  # round 1 ends at the gap, as a search past its aim does
            info = plan.packed.info["envelope"]
            plan.packed.info["envelope"] = dataclasses.replace(info, exact=False, within=0.01, stopped=None)
        return plan

    monkeypatch.setattr(planner_plan, "_make_plan", first_within)
    plan = _plan_at(data, target, monkeypatch, divine=91.0)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9) == pytest.approx(133.0)
    first, *_ = _rounds_of(plan)
    assert first.status == "within" and first.within == 0.01
    record = _record(plan, plan.mean_remaining + S, S)
    if lock_stopped:
        assert [record.status for record in _rounds_of(plan)] == ["within", "stopped"]
        assert plan.search.within is None and plan.search.stopped == "not every round of the methods finished" and not plan.search.exact
        assert record["stop"] == "stopped: not every round of the methods finished" and record["lower"] == S  # no plan proved within the gap of 0
        assert _search_document(plan)["within"] is None  # the site's JSON says no gap either
        rounds = next(limit for limit in plan.limits if limit.kind == "rounds" and "not every round finished" in limit.what)
        assert ", to within 1.00%" in rounds.guarantee  # round 1's gap, said of the methods of the rounds that finished only
    else:
        assert all(record.closed for record in _rounds_of(plan))
        assert plan.search.within == 0.01 and plan.search.stopped is None and not plan.search.exact
        assert record["stop"] == "proved within 1.00% of the cheapest"


def test_a_round_whose_search_a_net_stops_before_any_plan_is_stopped_not_refused(data, target, monkeypatch):
    # the search of the lock's round meets its share of the net before a plan closes (`NoPolicy` with the net's words): the round is stopped,
    # with the figure it reached, and the plan of round 1 is the answer
    from crafting_system.planner._envelope import NoPolicy

    real = planner_plan._make_plan

    def later_stopped(*args, round_call=None, **kwargs):
        if round_call is not None and not round_call.watched:
            cause = NoPolicy("the search stopped", stopped="the time limit of 30 seconds was reached", lower=120.0)
            outer = NoPolicy("the bound was cut short")  # `envelope_result` adds the note of a bound cut short over the search's own refusal
            outer.__cause__ = cause
            raise planner_plan.PlanError("no policy of the offered actions reaches the goal") from outer
        return real(*args, round_call=round_call, **kwargs)

    monkeypatch.setattr(planner_plan, "_make_plan", later_stopped)
    plan = _plan_at(data, target, monkeypatch, divine=91.0)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    first, last = _rounds_of(plan)
    assert first.status == "closed" and last.status == "stopped" and last.reason == "the time limit of 30 seconds was reached" and last.lower == 120.0
    assert not plan.search.exact


@pytest.mark.parametrize("states", [4, 10])
def test_through_the_entry_a_run_counted_in_states_gives_the_same_plan_and_answer_whatever_the_clock_does(data, target, monkeypatch, states):
    # #886: the belt's offers split into two rounds (the lock's is the second). Under `Budget.in_states` the plan and every line of the answer are
    # the same whether every reading of the clock moves it by 1,000 s or by nothing; the test drives the clock itself and never reads it. With 4
    # states, round 1's first plan reaches the net (counted at every state of its chain, #1101, and inside each kernel, #1105: with 3 the next
    # kernel is left unmade before any plan closes) and the lock's round is not tried; with 10, both rounds close. The run never knows more
    # states than its net.
    from crafting_system import budget as budget_module
    from crafting_system.budget import Budget

    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    prices = dataclasses.replace(_prices(), chaos_per_divine=92.0)

    step, readings = [0.0], iter(range(10**9))
    # the clock as the test drives it, for every module of the run: `budget_module.time` is the one clock module they all read
    monkeypatch.setattr(budget_module.time, "perf_counter", lambda: step[0] * next(readings))

    def planned(seconds_per_reading: float):
        step[0] = seconds_per_reading
        return plan_target(data, target, prices, PlanSettings(recipe_starts=False, start_price=S, solver="envelope", budget=Budget.in_states(states)))

    slow, fast = planned(1000.0), planned(0.0)
    assert slow.mean_remaining == fast.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    assert slow.solution.policy == fast.solution.policy and slow.limits == fast.limits  # every line of the answer
    assert slow.risk is not None and slow.risk == fast.risk  # the cost figures too (their ladder has no time net in such a run)
    assert [replace_seconds(record) for record in slow.search.widening] == [replace_seconds(record) for record in fast.search.widening]
    assert [record.status for record in slow.search.widening] == (["stopped", "not tried"] if states == 4 else ["closed", "closed"])
    assert all(record.states is not None for record in slow.search.widening)
    assert sum(record.states for record in slow.search.widening) <= states


@pytest.mark.parametrize("states", [4, 1_000])
def test_through_the_entry_the_plan_without_the_lock_is_made_first_counted_in_states_and_the_lock_s_round_gets_what_is_left(data, target, monkeypatch, states):
    # #1108: the metamod craft the rule of blocking crafts offers unasked (the lock, Prefixes Cannot Be Changed) adds the feature `metamods` to
    # the model, so the planner's own offers that hold it always split into rounds (`offer_groups`): the plan without the lock is round 1 and
    # is made first, the lock's round 2 holds the lock with them. (The plan made first without the metamod crafts outside the rounds,
    # `_plan.plan_without` and its "Not tried" limit, is reached from the entry only by a walk asked for by name, `solver` object or packed,
    # which is being retired: no test is written against it.) Under `Budget.in_states(N)` round 1 is given the whole
    # account, N; its search knows 4 states (the belt's chain: start, the filler, the exalt that hits, the restart) and round 2 is given N - 4.
    # With N = 4 round 1's net stops it after its plan of 133 (counted at every state of its chain, #1101, and inside each kernel, #1105: with
    # N = 3 the restart's kernel is left unmade before any plan closes, and the run knows no more than its net): that plan is the answer, and round 2,
    # the lock's, is not tried and the answer says so in states. Either way the plan and every line of the answer are the same whether every
    # reading of the clock moves it by 1,000 s or by nothing (the clock driven through `budget_module.time`).
    from crafting_system import budget as budget_module
    from crafting_system.budget import Budget
    from crafting_system.planner import _limits

    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    prices = dataclasses.replace(_prices(), chaos_per_divine=92.0)
    step, readings = [0.0], iter(range(10**9))
    monkeypatch.setattr(budget_module.time, "perf_counter", lambda: step[0] * next(readings))
    calls, real = [], planner_plan._make_plan

    def spied(*args, **kwargs):  # each round's offers and the states net it is given
        if (call := kwargs.get("round_call")) is not None:
            calls.append((LOCK in {offer.label for offer in kwargs["offers"]}, call.states))
        return real(*args, **kwargs)

    monkeypatch.setattr(planner_plan, "_make_plan", spied)

    def planned(seconds_per_reading: float):
        step[0], calls[:] = seconds_per_reading, []
        plan = plan_target(data, target, prices, PlanSettings(recipe_starts=False, start_price=S, solver="envelope", budget=Budget.in_states(states)))
        return plan, list(calls)

    (slow, slow_calls), (fast, fast_calls) = planned(1000.0), planned(0.0)
    assert slow_calls == fast_calls and slow.mean_remaining == fast.mean_remaining and slow.solution.policy == fast.solution.policy
    assert slow.limits == fast.limits and slow.risk == fast.risk
    assert [replace_seconds(record) for record in slow.search.widening] == [replace_seconds(record) for record in fast.search.widening]
    rounds = slow.search.widening
    assert slow.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)  # round 1's plan: the filler, then exalt
    assert LOCK not in {entry.label for entry in slow.offers} and not slow.abstraction.models_metamods
    assert rounds[0].states == 4
    if states == 1_000:
        assert slow_calls == [(False, 1_000), (True, 1_000 - 4)]  # the plan without the lock first, on the whole account; the lock's round the rest
        assert [record.status for record in rounds] == ["closed", "closed"] and slow.search.exact
        assert not any(limit.kind == _limits.UNTRIED for limit in slow.limits)
    else:
        assert slow_calls == [(False, 4)]  # the lock's round is never searched
        assert [(record.status, record.states) for record in rounds] == [("stopped", 4), ("not tried", 0)]
        assert "4 states were known, the limit is 4" in rounds[0].reason
        untried = [limit for limit in slow.limits if limit.kind == _limits.UNTRIED]
        assert len(untried) == 1 and untried[0].what == "Not finished"
        line = untried[0].names[-1]  # (the round's name does not yet say its bench craft is the lock: #1121)
        assert line.startswith("round 2 (bench-craft;") and line.endswith("0 states): not tried, the run's states net was used up before this round")
        assert not slow.search.exact


@pytest.mark.parametrize("states, per_state", [(10, 0.2), (10, 2.0), (10, 100.0), (40, 100.0)])
def test_through_the_entry_the_bound_s_build_and_its_binding_count_their_work_and_stop_on_it_whatever_the_clock_does(data, target, monkeypatch, states, per_state):
    # #1101: the same run as above with the offers' floors on (`MIN_OFFERS` 3 here; 40 for a real target), so the bound's build works out
    # floors, builds its model on part of the offers and examines the others (the binding step). Under `Budget.in_states` each build counts
    # its pieces of work (`build_per_state` per state of its search's net) and asks its net at every offer and before every raise, never on
    # the clock: the plan, every line of the answer and each build's count are the same whether every reading of the clock moves it by
    # 1,000 s or by nothing. A small share stops the build, and the answer names that count.
    from crafting_system import budget as budget_module
    from crafting_system.budget import Budget
    from crafting_system.planner import _pattern_bound

    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    monkeypatch.setattr(_pattern_bound, "MIN_OFFERS", 3)
    monkeypatch.setattr(planner_plan, "MIN_OFFERS", 3)
    prices = dataclasses.replace(_prices(), chaos_per_divine=92.0)
    builds, bindings = [], []
    real, binding = _envelope_plan.pattern_lower_bound, _pattern_bound._binding

    def counted(*args, **kwargs):
        bound = real(*args, **kwargs)
        builds.append((bound.pieces, bound.share, bound.phase, bound.stopped, bound.start_value))
        return bound

    def examined(*args, **kwargs):  # the binding step: whether the build's count stopped it
        try:
            found = binding(*args, **kwargs)
        except _pattern_bound.FloorsStopped:
            bindings.append("stopped")
            raise
        bindings.append("done")
        return found

    monkeypatch.setattr(_envelope_plan, "pattern_lower_bound", counted)
    monkeypatch.setattr(_pattern_bound, "_binding", examined)
    step, readings = [0.0], iter(range(10**9))
    monkeypatch.setattr(budget_module.time, "perf_counter", lambda: step[0] * next(readings))

    def planned(seconds_per_reading: float):
        step[0] = seconds_per_reading
        builds.clear()
        bindings.clear()
        budget = Budget.in_states(states, build_per_state=per_state)
        plan = plan_target(data, target, prices, PlanSettings(recipe_starts=False, start_price=S, solver="envelope", budget=budget))
        return plan, list(builds), list(bindings)

    (slow, slow_builds, slow_bindings), (fast, fast_builds, fast_bindings) = planned(1000.0), planned(0.0)
    assert slow_builds == fast_builds and slow_bindings == fast_bindings and slow_builds
    assert slow.mean_remaining == fast.mean_remaining
    assert slow.solution.policy == fast.solution.policy and slow.limits == fast.limits and slow.risk == fast.risk
    assert [replace_seconds(record) for record in slow.search.widening] == [replace_seconds(record) for record in fast.search.widening]
    pieces, share, phase, stopped, _ = slow_builds[0]  # round 1's build, given `per_state` pieces per state of the round's net (the whole of it)
    assert share == int(per_state * states)
    if per_state == 0.2:  # 2 pieces: stopped while it counted the kinds of item
        assert phase == "model" and pieces == share and slow_bindings == []
    elif per_state == 2.0:  # 20 pieces: the first model is built and solved, the binding step names the offers to join, and their growth is stopped
        assert phase == "growth" and slow_bindings[0] == "done"  # (the binding step stopped by its count: test_cli_envelope_build.py)
    else:  # every build finishes, and both rounds close on the cheapest plan
        assert all(build[2] == "complete" and build[3] is None for build in slow_builds) and "done" in slow_bindings
        assert [record.status for record in slow.search.widening] == ["closed", "closed"]
        assert slow.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    if stopped is not None:  # the answer names the build's count where round 1 stopped (OR-13)
        assert stopped.startswith(f"it had done {pieces:,} pieces of work, its allowance being {share:,} pieces of work, set from the run's states net")
        assert f"was stopped too: {stopped}" in slow.search.widening[0].reason


def replace_seconds(record):
    return dataclasses.replace(record, seconds=0.0)


def test_a_later_round_that_finds_a_cheaper_plan_replaces_the_plan_in_hand(data, target, monkeypatch):
    # with the target's named offers alone in round 1 the fillers are a round of their own: round 1 exalts (16e/3 + 2S), round 2 fills first
    # (3(c + e) + 2S)
    from crafting_system.planner import _rounds

    real = _rounds.round_groups

    def named_alone(offers, named, added):
        head, *rest = real(offers, named, added)
        asked = tuple(i for i in head.positions if offers[i].blocks is None)
        fillers = tuple(i for i in head.positions if i not in asked)
        return (_rounds.Group(asked, (), frozenset()), _rounds.Group(fillers, ("bench-craft",), head.features), *rest)

    monkeypatch.setattr(_rounds, "round_groups", named_alone)
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    plan = plan_target(data, target, dataclasses.replace(_prices(), chaos_per_divine=92.0), PlanSettings(recipe_starts=False, start_price=S, solver="envelope"))
    records = _rounds_of(plan)
    assert records[0].upper == pytest.approx(16 * E / 3 + 2 * S, rel=1e-9)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    assert _fills(plan.solution.policy[plan.start].label)
    assert all(record.closed for record in records) and plan.search.exact


@pytest.mark.parametrize("held", [True, False])
def test_through_the_entry_a_round_with_a_plan_in_hand_completes_its_bound_s_build_within_its_share_and_finds_the_cheaper_plan(data, target, monkeypatch, held):
    # #1099 (R11's and R05's Exalted rounds, #1086): the rounds of the test above, counted in states (`Budget.in_states(40)`, one piece of
    # work per state, the offers' floors on), so no clock moves anything. Round 1 (the Exalted Orb alone) closes at 16e/3 + 2S = 153.33 having
    # known 12 states; round 2 (the fillers) begins with that plan in hand, and its share is the 28 states left over the 2 rounds left: 14.
    # Its bound's build needs 51 pieces of work. Given a quarter's worth (one piece per state, 14), the old rule, it stops while offers join
    # (growth) on a lower figure of 34 (the walk toward the goal raises it, #1142), and the round stops; the walk's plan is the filler's all the same, 133, which the answer takes, saying it is not shown near the best. Given the round's whole share (four
    # times that, 56: the build keeps no room for the search to make a plan, the answer holds one) it completes, and the round closes on
    # the filler's plan, 3(c + e) + 2S = 133.
    from crafting_system.budget import Budget
    from crafting_system.planner import _pattern_bound, _rounds

    real_groups, real_net, real_bound = _rounds.round_groups, planner_plan.search_net, _envelope_plan.pattern_lower_bound

    def named_alone(offers, named, added):
        head, *rest = real_groups(offers, named, added)
        asked = tuple(i for i in head.positions if offers[i].blocks is None)
        fillers = tuple(i for i in head.positions if i not in asked)
        return (_rounds.Group(asked, (), frozenset()), _rounds.Group(fillers, ("bench-craft",), head.features), *rest)

    builds = []

    def counted(*args, **kwargs):
        bound = real_bound(*args, **kwargs)
        builds.append((bound.pieces, bound.share, bound.phase))
        return bound

    monkeypatch.setattr(_rounds, "round_groups", named_alone)
    monkeypatch.setattr(_envelope_plan, "pattern_lower_bound", counted)
    if held:  # its model grows one offer at a time (#1224: past a quarter of its share the build goes on only at a pace that ends in its room)
        _one_offer_per_model(monkeypatch)
    else:  # the rule before #1099: a round's build had a quarter's worth of its share, a plan in hand or not
        monkeypatch.setattr(planner_plan, "search_net", lambda clock, searches=1, give_way=None, states=None, held=False, walked=False, blind=None: real_net(clock, searches, give_way, states))
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    monkeypatch.setattr(_pattern_bound, "MIN_OFFERS", 3)
    monkeypatch.setattr(planner_plan, "MIN_OFFERS", 3)
    prices = dataclasses.replace(_prices(), chaos_per_divine=92.0)
    plan = plan_target(data, target, prices, PlanSettings(recipe_starts=False, start_price=S, solver="envelope", budget=Budget.in_states(40, build_per_state=1.0)))
    first, second = _rounds_of(plan)[:2]
    assert (first.status, first.states, first.upper) == ("closed", 12, pytest.approx(16 * E / 3 + 2 * S, rel=1e-9))
    assert builds[0] == (8, 40, "complete")  # round 1 began with no plan in hand: one piece per state of all the states left, as before
    if held:
        assert builds[1] == (51, 4 * 14, "complete")
        assert second.status == "closed" and plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
        assert _fills(plan.solution.policy[plan.start].label)
    else:
        assert builds[1] == (14, 14, "growth")
        # its bound stopped with no order, so the search walks toward the goal (#1142) and realizes more offers than the least-`la` chain did:
        # the lower figure they raise is 34 (30 before the walk), still below the closed plan's 133
        assert second.status == "stopped" and second.lower == pytest.approx(34.0, abs=1e-6)
        # the walk's plan is the filler's, cheaper than round 1's: the answer takes it, and its limits say it is not shown near the best (OR-33, OR-40)
        assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9) and _fills(plan.solution.policy[plan.start].label)
        (walked,) = [limit for limit in plan.limits if limit.kind == "plan-reached"]
        assert "Not proved: that it is anywhere near the best possible cost" in walked.guarantee


def test_a_build_that_begins_with_a_plan_in_hand_keeps_no_room_for_the_search_while_its_pace_ends_within_its_net(monkeypatch):
    # #1099, #1224, on the clock: a build keeps three times its time for the search (`SEARCH_PER_BUILD`), so of a 20 s net it stops at 5 s;
    # with a plan in hand (`Net.held`) it goes on past 5 s while the pace its model grows at ends within the net (its first model solved at
    # 1 s, half of the 8 offers to add joined by 3 s: 1 + 2 * 8 / 4 = 5 s), and only the net itself stops it. One whose model has not grown
    # yet has nothing to show it will end there: it stops at 5 s too, and the search has the rest. The clock is a figure set here.
    # #1325: a build that runs past the 5 s its pace foretold, its next model unsolved, has the overrun charged to that pace: 5 + (used - 5)
    # * 8 / 4, past the net of 20 s from 12.5 s on. One whose next model is solved on its way (all 12 offers at 9 s: 1 + 8 * 8 / 8 = 9 s,
    # and at most 9 + (used - 9) * 8 / 8 = used after it) reaches the net itself.
    from crafting_system.abstraction._pattern import Growth

    now = [0.0]
    monkeypatch.setattr(_envelope_plan.time, "perf_counter", lambda: now[0])
    fresh, held, blind, late = (_envelope_plan.build_stop(_envelope.Net(seconds=20.0, held=plan), 0.0) for plan in (False, True, True, True))
    held.grows = blind.grows = late.grows = True  # all grow their model from part of their offers (`_pattern_bound`)
    now[0] = 1.0
    for build in (held, blind, late):
        build.grown(Growth(5, 12, 4, 4), build.used())
    now[0] = 3.0
    held.grown(Growth(10, 12, 4, 8), held.used())
    late.grown(Growth(10, 12, 4, 8), late.used())
    assert held.need == pytest.approx(5.0) == late.need
    now[0] = 4.9
    assert fresh() is None and held() is None and blind() is None
    now[0] = 5.0
    assert fresh().startswith("stopped after 5 of the 20 seconds") and held() is None
    assert blind().startswith("stopped after 5 of the 20 seconds of the time limit, to leave the rest for the search for the plan: its model had not grown")
    now[0] = 9.0
    held.grown(Growth(12, 12, 4, 12), held.used())
    now[0] = 12.4
    assert late() is None and late.need == pytest.approx(5.0 + 7.4 * 2)
    now[0] = 12.6
    assert late().startswith("stopped after 13 of the 20 seconds of the time limit, to leave the rest for the search for the plan: its next model was not solved")
    now[0] = 19.9
    assert held() is None
    now[0] = 20.0
    assert held() == "the time limit of 20 seconds was reached"


def test_the_cut_keeps_the_restart_cuts_at_a_tie_and_cuts_nothing_without_a_finite_figure():
    from crafting_system.planner._offers import RESTART, BuyStartItem, Offer, PricedOffer
    from crafting_system.planner._price_cut import restart_dominated

    restart = PricedOffer(Offer(RESTART, BuyStartItem(None), {"belt": 1}, shares=False), 500.0, ())
    cheap, tie, dear = (PricedOffer(Offer(label, None, {}), cost, ()) for label, cost in (("cheap", 182.9), ("tie", 183.0), ("dear", 600.0)))
    kept, cut = restart_dominated((cheap, tie, dear, restart), 50.0, 133.0)
    assert kept == (cheap, restart) and cut == (tie, dear)
    assert restart_dominated((cheap, dear), 50.0, float("inf")) == ((cheap, dear), ())
    # #1110: an offer a judged route names is kept whatever its price: the route is read on the plan's offers, and keeping it changes no cost
    assert restart_dominated((cheap, tie, dear, restart), 50.0, 133.0, keep=frozenset({"dear"})) == ((cheap, dear, restart), (tie,))


def test_the_cut_and_the_craft_classes_split_the_offers_by_identity_never_by_comparing_two_offers():
    # #1073: with 9,000 fossil sets, a test of membership in the kept offers compared every pair (cheapest_per_class 32 s, the cut 12 s, before the
    # fossil round's search began). Each is a split of the offers it was given, told apart by identity: no two offers are ever compared.
    from crafting_system.planner._offers import RESTART, BuyStartItem, Offer, PricedOffer, cheapest_per_class
    from crafting_system.planner._price_cut import restart_dominated

    @dataclasses.dataclass(frozen=True)
    class Uncomparable(PricedOffer):
        def __eq__(self, other):
            raise AssertionError("two offers were compared")

        __hash__ = object.__hash__

    restart = Uncomparable(Offer(RESTART, BuyStartItem(None), {"belt": 1}, shares=False), 500.0, ())
    offers = [Uncomparable(Offer(f"set {n}", None, {}), float(n), ()) for n in range(300)]
    crafts = [Uncomparable(Offer(f"craft {n}", None, {}, blocks=("prefix",)), 10.0 - n, ()) for n in range(3)]
    kept, cut = restart_dominated((*offers, restart), 50.0, 133.0)
    assert [each.label for each in kept] == [f"set {n}" for n in range(183)] + [RESTART]
    assert [each.label for each in cut] == [f"set {n}" for n in range(183, 300)]
    kept, others = cheapest_per_class((*offers, *crafts))
    assert [each.label for each in kept] == [f"set {n}" for n in range(300)] + ["craft 2"]
    assert others == ("craft 0", "craft 1")
    # Two equal offers of one class, two objects: the second is left out and named. Compared by value it was left out unnamed, as the first was kept.
    twin, again = (PricedOffer(Offer("craft", None, {}, blocks=("prefix",)), 1.0, ()) for _ in range(2))
    assert twin == again and twin is not again
    kept, others = cheapest_per_class((twin, again))
    assert kept == (twin,) and kept[0] is twin and others == ("craft",)


def test_a_judged_route_whose_actions_are_not_known_is_judged_against_every_offer_in_one_search(data, target, monkeypatch):
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    prices = dataclasses.replace(_prices(), chaos_per_divine=92.0)
    plan = plan_target(data, target, prices, PlanSettings(recipe_starts=False, start_price=S, solver="envelope", judges_route=True))
    assert LOCK in {entry.label for entry in plan.offers} and not plan.search.widening  # a route may name the lock: it is a fixed policy


# #1110: the route of the module text that exalts until a prefix, and buys the belt again when that prefix is a lower Life tier: `16e/3 + 2S`.
EXALTING_ROUTE = """\
name: exalt until a prefix
rules:
  - when:
      requirements:
        - family: IncreasedLife
          status: below
    do: restart
  - do: Exalted Orb
"""


def _judged(data, target, tmp_path, text: str):
    """The plan judged against the route `text` through the planner's entry, with the route's actions read from its file first (as the
    command and `benchmark` do), and the route read and evaluated on that plan."""
    from crafting_system.cli._route import evaluate_route, load_route, route_actions

    path = tmp_path / "route.yaml"
    path.write_text(text, encoding="utf-8")
    named = route_actions(path)
    prices = dataclasses.replace(_prices(), chaos_per_divine=92.0)
    plan = plan_target(data, target, prices, PlanSettings(recipe_starts=False, start_price=S, solver="envelope", judges_route=True, route_actions=named))
    return named, plan, evaluate_route(plan, load_route(path, plan, data), data)


def test_a_judged_route_is_judged_against_the_plan_of_the_rounds_and_the_answer_says_the_first_round_held_it(data, target, tmp_path, monkeypatch):
    # #1110: the belt's offers split into two rounds (the Lock's is the second). The route's action leads the first round, which finishes; the
    # plan is the rounds' plan, the same as with no route (fill, then exalt: 3(c + e) + 2S = 133), proved over every method; the route costs
    # 16e/3 + 2S = 153.33 on its own actions, and the answer says that no plan of the first round's methods, the route's among them, costs less.
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    named, plan, given = _judged(data, target, tmp_path, EXALTING_ROUTE)
    assert named == ("Exalted Orb",)
    unjudged = plan_target(data, target, dataclasses.replace(_prices(), chaos_per_divine=92.0), PlanSettings(recipe_starts=False, start_price=S, solver="envelope"))
    assert plan.mean_remaining == unjudged.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    assert [record.status for record in plan.search.widening] == [record.status for record in unjudged.search.widening]
    assert len(plan.search.widening) == 2 and plan.search.exact  # searched in rounds, not every offer at once
    assert given.risk.mean.value == pytest.approx(16 * E / 3 + 2 * S, rel=1e-9) and not given.gaps
    limit = next(limit for limit in plan.limits if limit.what == "The given route's methods were searched from the first round")
    assert limit.labels == ("Exalted Orb",) and limit.guarantee.startswith("The first round finished: no plan made only of its methods")
    assert not any(limit.what.startswith("The given route") for limit in unjudged.limits)


def test_a_judged_route_that_names_the_lock_holds_it_from_the_first_round(data, target, tmp_path, monkeypatch):
    # #1110: a route that takes the Lock, an offer of the second round: the Lock leads the first round with the target's named actions, so the
    # plan holds it and the route is read on that plan. Its group is then empty: the offers are one group, one search (no round of its own).
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    route = EXALTING_ROUTE.replace("  - do: Exalted Orb\n", f"  - when:\n      crafted_mods: false\n    do: {LOCK}\n  - do: Exalted Orb\n")
    named, plan, given = _judged(data, target, tmp_path, route)
    assert named == (LOCK, "Exalted Orb") and LOCK in {entry.label for entry in plan.offers}
    assert not plan.search.widening and plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    assert given.risk.mean.value >= plan.mean_remaining * (1 - 1e-9)  # the plan of one search over every offer, the Lock included, is proved the cheapest


def test_the_judged_route_limit_says_nothing_is_proved_against_the_route_when_the_first_round_did_not_finish():
    from crafting_system.planner import _rounds

    record = _rounds.RoundRecord(("exalted-orb",), 3, _rounds.GAVE_WAY, "its share", 100.0, 140.0, 1.0)
    limit = _rounds.judged_route_limit(("Exalted Orb",), record)
    assert limit.guarantee.startswith("The first round did not finish, so the plan shown is not proved to cost no more than the route")
    within = _rounds.judged_route_limit(("Exalted Orb",), dataclasses.replace(record, status=_rounds.WITHIN, within=0.01))
    assert "to within 1.00%" in within.guarantee


def test_a_given_start_has_no_restart_so_no_round_cuts_and_with_no_plan_in_any_round_the_refusal_stands(tmp_path, data, monkeypatch):
    path = tmp_path / "given.yaml"
    path.write_text(TARGET.replace("start: bought", "start: given"), encoding="utf-8")
    given = belt(path, data)
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    cut = []
    real = planner_plan.restart_dominated
    monkeypatch.setattr(planner_plan, "restart_dominated", lambda *args: cut.append(1) or real(*args))
    with pytest.raises(planner_plan.PlanError, match="no policy"):  # a Life 1 or 2 takes the family for good, and a held belt cannot be bought again
        plan_target(data, given, _prices(), PlanSettings(recipe_starts=False, solver="envelope"))
    assert not cut  # with no restart an offer dearer than any plan may still be the only way on


class _HandClock:
    """The run's clock, moved only by the test: nothing here reads the time (`tests/test_no_timing.py`)."""

    def __init__(self) -> None:
        self.now = 1000.0

    def perf_counter(self) -> float:
        return self.now


def _share_entry(data, target, monkeypatch, *, held_again: bool):
    """A run of 600 s and two rounds through `plan_target`: round 1 begins with no plan in hand, and its first plan (133) is in hand when 400 s of
    the run have passed (the watch moves the run's clock), past its share of 300 s. With `held_again` its search is asked once more holding the
    same plan, as a search round that made no cheaper plan asks (this small search closes before it would). Returns the plan and the asks."""
    from crafting_system import budget as budget_module
    from crafting_system.budget import Budget
    from crafting_system.planner import _rounds

    clock = _HandClock()
    for module in (budget_module, _envelope, _envelope_plan):
        monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    moved, asks = [], []
    ask = _rounds.Share.__call__

    def asked(share, standing):
        said = ask(share, standing)
        if said is None and held_again:
            said = ask(share, standing)  # the next search round's ask, with no cheaper plan
        asks.append((standing.upper, said))
        return said

    monkeypatch.setattr(_rounds.Share, "__call__", asked)

    def watch(_standing):
        if not moved:
            moved.append(True)
            clock.now += 400.0

    prices = dataclasses.replace(_prices(), chaos_per_divine=91.0)
    budget = Budget(aim_seconds=None, seconds=600.0, gap=0.0)
    return plan_target(data, target, prices, PlanSettings(recipe_starts=False, start_price=S, solver="envelope", watch=watch, budget=budget)), asks


def test_through_the_entry_a_first_round_whose_plan_was_just_made_goes_on_past_its_share(data, target, monkeypatch):
    # #1080: the round's search has just made its plan (133): a plan still falling is not cut, so it goes on and closes; round 2 is tried
    plan, asks = _share_entry(data, target, monkeypatch, held_again=False)
    assert asks[0] == (pytest.approx(133.0, rel=1e-9), None)
    first, last = _rounds_of(plan)
    assert first.status == "closed" and last.status in ("beaten", "closed")


def test_through_the_entry_a_first_round_that_used_its_share_gives_way_with_its_plan_and_the_next_round_is_tried(data, target, monkeypatch):
    # #1080 through `plan_target`: past its share of 300 s, round 1's search holds its plan (133) and a search round made none cheaper, so it gives
    # way with that plan instead of keeping the rest; round 2 (the lock) is tried in the 200 s left and saves nothing. The answer keeps the plan
    # and names what each round did.
    plan, asks = _share_entry(data, target, monkeypatch, held_again=True)
    assert asks[0][1] is not None
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)  # the plan of the round that gave way is kept (OR-33)
    first, last = _rounds_of(plan)
    assert first.status == "gave way" and "300 seconds" in first.reason and first.upper == pytest.approx(133.0, rel=1e-9)
    assert last.status in ("beaten", "closed")  # tried in the time left
    assert not plan.search.exact and not any("cheapest among every method" in limit.guarantee for limit in plan.limits)  # round 1 did not finish
    untried = next(limit for limit in plan.limits if limit.what == "Not finished")
    assert "gave way" in untried.names[0] and "its plan costs 133.00 Chaos" in untried.names[0]


def test_past_its_share_a_round_whose_plan_falls_by_less_than_the_run_s_gap_gives_way_and_one_still_falling_by_much_goes_on():
    # #1094: `Share` gave way only after a search round that made no cheaper plan, so a plan falling by a cent a search round never gave way and
    # took the rest of the net. Past its share (500 of 200 s), a fall of more than the run's gap (1%) goes on: R11's essences, 7,817 c and then
    # 597 c (a fall of 92%); a fall of 1 c on 597 (0.17%) gives way. With no gap (a run that owes an exact proof) every fall counts, as before.
    from types import SimpleNamespace

    from crafting_system.planner import _rounds

    def gives_way(gap, uppers):
        share = _rounds.Share(600.0, 3, 0.0, lambda: 500.0, gap=gap)
        return [share(SimpleNamespace(upper=upper)) is not None for upper in uppers]

    assert gives_way(0.01, (7817.0, 597.0, 596.0)) == [False, False, True]
    assert gives_way(0.01, (7817.0, 597.0, 590.0, 589.0)) == [False, False, False, True]  # 597 -> 590 is 1.2%: still falling
    assert gives_way(0.0, (7817.0, 597.0, 596.0, 595.0, 595.0)) == [False, False, False, False, True]
    assert "by no more than the run's gap of 1.00%" in _rounds.Share(600.0, 3, 0.0, lambda: 0.0, gap=0.01).said
    # through the rounds, the clock moved by hand: round 1 has no plan in hand and its search's plan falls by a cent every 50 s search round,
    # from 10; its share is 600 s over 3 rounds. It gives way at 200 s, and rounds 2 and 3 are tried, round 2 holding the saving
    groups = tuple(_rounds.Group((i,), (kind,), frozenset({"junk", kind})) for i, kind in enumerate("abc"))
    now, asked = [0.0], []

    def search(chosen, call):
        if call.give_way is None:  # a plan in hand: the round closes at once
            return SimpleNamespace(search=SimpleNamespace(lower=7.0), mean_remaining=7.0 if "b" in chosen else 10.0, stopped=None)
        for step in range(1_000):
            now[0] += 50.0
            standing = SimpleNamespace(lower=1.0, upper=10.0 - 0.01 * step, rounds=step, seconds=now[0])
            if (said := call.give_way(standing)) is not None:
                asked.append(now[0])
                return SimpleNamespace(search=SimpleNamespace(lower=1.0), mean_remaining=standing.upper, stopped=said)
            if now[0] >= 600.0:  # the run's net
                return SimpleNamespace(search=SimpleNamespace(lower=1.0), mean_remaining=standing.upper, stopped="the time limit was reached")
        raise AssertionError("the search never stopped")

    def widened(gap):
        now[0], asked[:] = 0.0, []
        return _rounds.widen(
            groups, tuple("abc"), search, upper_of=lambda plan: plan.mean_remaining, mean_of=lambda plan: plan.mean_remaining,
            ended=lambda plan: (_rounds.STOPPED, plan.stopped) if plan.stopped else (_rounds.CLOSED, ""), left=lambda: max(600.0 - now[0], 0.0),
            clock_now=lambda: now[0], gap=gap,
        )  # fmt: skip

    trickle = widened(0.01)
    assert asked == [200.0] and [record.status for record in trickle.records] == ["gave way", "closed", "closed"] and trickle.plan.mean_remaining == 7.0
    exact = widened(0.0)  # with no gap the trickle is still a cheaper plan at every search round: it takes the whole net, and the rounds after it are not tried
    assert asked == [] and [record.status for record in exact.records] == ["stopped", "not tried", "not tried"] and exact.plan.mean_remaining > 9.0


def test_once_a_group_is_set_aside_the_last_round_that_holds_it_again_is_counted_among_the_rounds_left():
    # #1095: a group set aside comes back in one last round that holds every offer; the shares counted only the original groups, so when every
    # round used its share that last round was not tried. Four groups, the plan of 10 from round 1 (at once); each later round is beaten at
    # once after using its whole share of the time, moved by hand. Round 2 (b) is set aside: from then on the last round is owed and counted.
    # Shares: round 2 600/3 = 200, round 3 400/3, round 4 (266.7 left) over itself and the last round, then the last round has 133.3 s and
    # closes: the plan is proved the cheapest over every offer. Counting only the groups (200, 200, 200) left it no time and no proof.
    from types import SimpleNamespace

    from crafting_system.planner import _rounds

    groups = tuple(_rounds.Group((i,), (kind,), frozenset()) for i, kind in enumerate("abcd"))
    now, shares = [0.0], []

    def run(chosen, call):
        shares.append(call.searches)
        if call.upper is None:
            return SimpleNamespace(search=SimpleNamespace(lower=10.0), mean_remaining=10.0)
        now[0] += (600.0 - now[0]) / call.searches  # the round uses its whole share
        raise _envelope.Beaten(10.0, None)

    widened = _rounds.widen(
        groups, tuple("abcd"), run, upper_of=lambda plan: 10.0, mean_of=lambda plan: plan.mean_remaining, ended=lambda plan: (_rounds.CLOSED, ""),
        left=lambda: max(600.0 - now[0], 0.0), clock_now=lambda: now[0],
    )  # fmt: skip
    assert shares == [1, 3, 3, 2, 1] and now[0] == pytest.approx(600.0)
    assert [(record.status, record.carried) for record in widened.records] == [("closed", True), ("beaten", True), ("beaten", True), ("beaten", True), ("beaten", True)]
    assert _rounds.all_closed(widened.records) and widened.records[-1].offers == 4


def test_a_round_that_proves_no_plan_with_a_plan_in_hand_is_set_aside_like_a_beaten_one():
    # #1097 point 2: round 2 (b) with the base reaches no plan at all while the plan of 10 is in hand. It proved only that no plan of its offers
    # with the base costs less than 10 (none exists), as a beaten round does: it is set aside, round 3 does not hold b, and the last round
    # holds it again with every offer, so the proof is the whole one.
    from types import SimpleNamespace

    from crafting_system.planner import _rounds

    groups = tuple(_rounds.Group((i,), (kind,), frozenset()) for i, kind in enumerate("abc"))
    seen = []

    def run(chosen, call):
        seen.append(chosen)
        if chosen == ("a", "b"):
            raise _rounds.NoPlan("no plan of a and b reaches the target")
        if call.upper is not None:
            raise _envelope.Beaten(10.0, None)
        return SimpleNamespace(search=SimpleNamespace(lower=10.0), mean_remaining=10.0)

    widened = _rounds.widen(
        groups, tuple("abc"), run, upper_of=lambda plan: 10.0, mean_of=lambda plan: plan.mean_remaining, ended=lambda plan: (_rounds.CLOSED, ""),
        left=lambda: None, clock_now=lambda: 0.0,
    )  # fmt: skip
    assert seen == [("a",), ("a", "b"), ("a", "c"), ("a", "b", "c")]
    assert [record.status for record in widened.records] == ["closed", "no plan", "beaten", "beaten"] and _rounds.all_closed(widened.records)
    assert widened.records[1].reason.endswith("the last round held them again, with every method")


def test_a_nearly_done_build_goes_on_past_its_net_to_at_most_twice_it_and_one_far_from_done_stops(monkeypatch):
    # #1135, on a hand clock (no real clock is read): a 20 s net of a round with a plan in hand, room for one more share past it
    # (`Net.late` 1, `_plan.search_net`: three rounds or more left). Its build's model holds 80 of 84 offers (R11's
    # Exalted round): at 20 s it is expected to need 20 * 84 / 80 = 21 s in all, within twice the net (40 s), so it goes on; at 39 s it would
    # need 40.95 s: it stops. Holding 19 of 89 (R11's harvest swap round), it would need 93.7 s at 20 s: it stops at its net, as before. No
    # build goes past 40 s, nor one that is not told how far it is (the first model), nor one of a round with no plan in hand, nor the last
    # round's (its share is all the time left: past it the run would pass its net).
    from types import SimpleNamespace

    from crafting_system.abstraction._pattern import Growth
    from crafting_system.budget import Budget

    assert Growth(80, 84).nearly_done(20.0, 20.0) and not Growth(80, 84).nearly_done(39.0, 20.0) and not Growth(84, 84).nearly_done(40.0, 20.0)
    assert not Growth(19, 89).nearly_done(20.0, 20.0) and not Growth(80, 84).nearly_done(20.0, 20.0, late=0.0)
    assert Growth(80, 84).nearly_done(28.0, 20.0, late=0.5) and not Growth(80, 84).nearly_done(29.0, 20.0, late=0.5) and not Growth(80, 84).nearly_done(30.0, 20.0, late=0.5)
    # the room past the share: none for the last round, half of the others' time for the second last, one share from three rounds left on
    clock = SimpleNamespace(budget=Budget(seconds=600.0), left=lambda: 300.0)
    assert [planner_plan.search_net(clock, searches, held=True).late for searches in (1, 2, 3, 10)] == [0.0, 0.5, 1.0, 1.0]
    assert planner_plan.search_net(clock, 10).late == 0.0  # no plan in hand: the quarter's rule, no room past it
    now = [0.0]
    monkeypatch.setattr(_envelope_plan.time, "perf_counter", lambda: now[0])
    near, far, blind, fresh = (_envelope_plan.build_stop(_envelope.Net(seconds=20.0, held=held, late=1.0), 0.0) for held in (True, True, True, False))
    last = _envelope_plan.build_stop(_envelope.Net(seconds=20.0, held=True, late=0.0), 0.0)  # the last round: no room past its share
    # past the net the clock's rule reads the pace (`Pace.need`, #1224): 21 s and 93.7 s, the figures above; a build with no pace stops there
    last.need = near.need = fresh.need = 21.0
    far.need = 93.7
    now[0] = 20.0
    assert near() is None and near.late
    assert far() == blind() == "the time limit of 20 seconds was reached" and not far.late
    assert fresh() == last() == "the time limit of 20 seconds was reached"
    now[0] = 39.0
    assert near() is None
    now[0] = 40.0
    assert near() == "the time limit of 20 seconds was reached, the build having gone on past it to 40 s, nearly done"


@pytest.mark.parametrize("late", [1.0, 0.0])
def test_through_the_entry_a_round_whose_build_its_share_ends_nearly_done_finishes_it_and_finds_the_cheaper_plan(data, target, monkeypatch, late):
    # #1135 (R11's Exalted round, essences in its base: a build of 24 to 28 s on a runner against a share of 26 to 27 s). The rounds of the
    # #1099 test above, counted in states with a smaller net, `Budget.in_states(30)`: round 1 (the Exalted Orb alone) closes at
    # 16e/3 + 2S = 153.33 having known 12 states; round 2 (the fillers) begins with that plan in hand and has the 18 states left over the 2
    # rounds left, 9, so its build may do 4 * 9 = 36 pieces of work. It needs 51. Its room past them is half the other round's share
    # (`Net.late` 0.5: 18 pieces, to 54). At 36 its model holds every offer of the round (the last joining), so it is expected to need 36
    # pieces, within 54: it goes on, completes at 51, and the round closes on the filler's plan, 3(c + e) + 2S = 133. With no room past the
    # net (`LATE` 0, the rule before), it stops at 36 while offers join, and the answer keeps 153.33. Under `in_states(28)` (a share of 8,
    # 32 pieces, room to 48) it goes on to 48, short of 51: it stops there.
    from crafting_system.abstraction import _pattern
    from crafting_system.budget import Budget
    from crafting_system.planner import _pattern_bound, _rounds

    real_groups, real_bound = _rounds.round_groups, _envelope_plan.pattern_lower_bound

    def named_alone(offers, named, added):
        head, *rest = real_groups(offers, named, added)
        asked = tuple(i for i in head.positions if offers[i].blocks is None)
        fillers = tuple(i for i in head.positions if i not in asked)
        return (_rounds.Group(asked, (), frozenset()), _rounds.Group(fillers, ("bench-craft",), head.features), *rest)

    builds = []

    def counted(*args, **kwargs):
        bound = real_bound(*args, **kwargs)
        builds.append((bound.pieces, bound.share, bound.phase, bound.late))
        return bound

    monkeypatch.setattr(_rounds, "round_groups", named_alone)
    monkeypatch.setattr(_envelope_plan, "pattern_lower_bound", counted)
    monkeypatch.setattr(_pattern, "LATE", late)
    _one_offer_per_model(monkeypatch)  # a pace to go on by past a quarter of the share (#1224): the first model holds one offer, each model adds one
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    monkeypatch.setattr(_pattern_bound, "MIN_OFFERS", 3)
    monkeypatch.setattr(planner_plan, "MIN_OFFERS", 3)
    prices = dataclasses.replace(_prices(), chaos_per_divine=92.0)

    def planned(states):
        builds.clear()
        plan = plan_target(data, target, prices, PlanSettings(recipe_starts=False, start_price=S, solver="envelope", budget=Budget.in_states(states, build_per_state=1.0)))
        return plan, _rounds_of(plan)

    plan, (first, second, *_) = planned(30)
    assert (first.status, first.states, first.upper) == ("closed", 12, pytest.approx(16 * E / 3 + 2 * S, rel=1e-9))
    if late:
        assert builds[1] == (51, 36, "complete", True)
        assert second.status == "closed" and plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
        assert _fills(plan.solution.policy[plan.start].label)
        plan, (first, second, *_) = planned(28)
        assert builds[1] == (49, 32, "growth", True) and second.status == "stopped"  # (#1325: 48 before; an offer built at the keys that need it)
        assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)  # (#1325: its search on the bound it stopped finds the cheaper plan)
    else:
        assert builds[1] == (37, 36, "growth", False)  # (#1325: 36 before)
        assert second.status == "stopped" and plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)  # (#1325: as above)


def test_a_later_round_that_makes_the_first_plan_and_gives_way_joins_the_base_of_the_rounds_after_it():
    # #1135 (R11's round 7, the essences: rounds 1 to 6 show no plan of their offers alone; on 2 of 9 runners the essence round made its plan
    # of 597.28 c at about 52 s, past its share, and gave way, and the Exalted round, without the essences, reached no plan). Round 1 (a)
    # shows no plan; round 2 (a, b) begins with no plan in hand, makes a plan of 10 and gives way at its share of 300 s (the 600 s left over
    # its 2 rounds); round 3 holds b too, and its plan of 7 needs it. Before, a round that gave way did not join the base: round 3 held a
    # and c only.
    from types import SimpleNamespace

    from crafting_system.planner import _rounds

    groups = tuple(_rounds.Group((i,), (kind,), frozenset({"junk", kind})) for i, kind in enumerate("abc"))
    now, seen = [0.0], []

    def search(chosen, call):
        seen.append(chosen)
        if chosen == ("a",):
            raise _rounds.NoPlan("no plan of a alone")
        if call.give_way is None:  # a plan is in hand: round 3 closes at once, on 7 only with b
            return SimpleNamespace(search=SimpleNamespace(lower=7.0), mean_remaining=7.0 if "b" in chosen else 10.0, stopped=None)
        for step in range(100):
            now[0] += 100.0
            standing = SimpleNamespace(lower=1.0, upper=10.0, rounds=step, seconds=now[0])
            if (said := call.give_way(standing)) is not None:
                return SimpleNamespace(search=SimpleNamespace(lower=1.0), mean_remaining=10.0, stopped=said)
        raise AssertionError("the round never gave way")

    widened = _rounds.widen(
        groups, tuple("abc"), search, upper_of=lambda plan: plan.mean_remaining, mean_of=lambda plan: plan.mean_remaining,
        ended=lambda plan: (_rounds.STOPPED, plan.stopped) if plan.stopped else (_rounds.CLOSED, ""), left=lambda: 600.0 - now[0], clock_now=lambda: now[0],
    )  # fmt: skip
    assert seen == [("a",), ("a", "b"), ("a", "b", "c")]
    assert [record.status for record in widened.records] == ["no plan", "gave way", "closed"] and widened.plan.mean_remaining == 7.0
    assert not _rounds.all_closed(widened.records)  # the round that gave way did not finish: nothing calls the plan the cheapest of every method


def test_once_the_first_plan_is_in_hand_the_rounds_left_go_by_their_offers_floors_lowest_first():
    # #1135 (R11 without the guide: the Exalted Orb's round, its floor 9.64 c over the essences, was the tenth after the essence round, behind
    # rounds whose floor was the essences' own 75.2 c; on probe 44104520931's runner 5 they took its share). Round 1 (a) makes the first plan
    # of 100; the groups b, c, d, e then have floors (with the base a) of 75, 10, 75 and none (the floors pass was refused): c goes first, b
    # and d keep their order, e goes last. Each floor is asked once, of the group's offers with the base, as a floors-only call.
    from types import SimpleNamespace

    from crafting_system.planner import _rounds

    groups = tuple(_rounds.Group((i,), (kind,), frozenset({"junk", kind})) for i, kind in enumerate("abcde"))
    floors = {"b": 75.0, "c": 10.0, "d": 75.0, "e": ValueError("refused: the model of these offers cannot be built")}
    asked = []

    def search(chosen, call):
        assert not call.floors
        return SimpleNamespace(search=SimpleNamespace(lower=1.0), mean_remaining=100.0 if chosen == ("a",) else 90.0, stopped=None)

    def floor(chosen, call):
        assert call.floors and call.upper == 100.0 and call.held and call.searches == 4
        asked.append(chosen)
        if isinstance(figure := floors[chosen[-1]], Exception):
            raise figure  # a refusal of the floors pass is no figure: the group goes last, and its round says the refusal itself
        return figure

    widened = _rounds.widen(
        groups, tuple("abcde"), search, upper_of=lambda plan: plan.mean_remaining, mean_of=lambda plan: plan.mean_remaining,
        ended=lambda plan: (_rounds.CLOSED, ""), left=lambda: 600.0, clock_now=lambda: 0.0, floor=floor,
    )  # fmt: skip
    assert asked == [("a", "b"), ("a", "c"), ("a", "d"), ("a", "e")]  # once, after the first plan, never again
    assert [record.kinds for record in widened.records][:5] == [("a",), ("c",), ("b",), ("d",), ("e",)]
    assert _rounds.by_floor(groups, lambda group: {"a": 3.0, "b": None}.get(group.kinds[0], 3.0)) == [groups[0], *groups[2:], groups[1]]
    assert _rounds.figure_of(floor, ("a", "b"), widened_call := _rounds.RoundCall(4, 100.0, False, held=True, floors=True), lambda: 0.0) is None
    assert asked[-1] == ("a", "e")  # with the run's time used up nothing is asked
    assert _rounds.figure_of(floor, ("a", "b"), widened_call, lambda: None) == 75.0


def test_a_plan_in_hand_that_a_stopped_search_walked_to_is_not_held_by_the_next_round():
    # #1142 (R13 on the heavy benchmark: 11,246 c on main, 32,813 c once the walk gave round 1 a plan): a round that begins with a plan in hand
    # lets its bound's build take its whole share (`RoundCall.held`, #1099). A plan its search walked to (a `REACHED` limit) is proved near
    # nothing, so the round after it keeps the room for its search a round with no plan keeps; a plan of any other search is held as before
    from types import SimpleNamespace

    from crafting_system.planner import _limits, _rounds

    groups = tuple(_rounds.Group((i,), (kind,), frozenset()) for i, kind in enumerate("abc"))
    walk = _limits.Limit(_limits.REACHED, "walked", "why", "Not proved: near the best.")

    def rounds(limits):
        held = []

        def run(chosen, call):
            held.append(call.held)
            return SimpleNamespace(search=SimpleNamespace(lower=1.0), mean_remaining=100.0 - len(chosen), limits=limits if len(chosen) == 1 else ())

        _rounds.widen(
            groups, tuple("abc"), run, upper_of=lambda plan: plan.mean_remaining, mean_of=lambda plan: plan.mean_remaining,
            ended=lambda plan: (_rounds.STOPPED, "stopped"), left=lambda: 600.0, clock_now=lambda: 0.0,
        )  # fmt: skip
        return held

    assert rounds((walk,)) == [False, False, True]  # round 2 begins with round 1's walked plan: not held; round 3 with round 2's own plan: held
    assert rounds(()) == [False, True, True]
    assert _rounds.walked(SimpleNamespace(limits=(walk,))) and not _rounds.walked(SimpleNamespace(limits=())) and not _rounds.walked(object())


def test_past_a_quarter_of_its_share_a_build_with_a_plan_in_hand_goes_on_only_at_a_pace_that_ends_within_its_room():
    # #1224, in hand-worked seconds (`Pace.verdict` reads no clock). R11's Exalted round, essences in its base (probe run 44124277553, runner
    # 1): a share of 27 s and room for one more (`Room.late` 1: 54 s); its first model (10 of 84 offers) is solved at 2.5 s, its second (18)
    # at 4.3 s: at that pace it needs 2.5 + 1.8 * 74 / 8 = 19.15 s; its third (30) at 11.6 s: 2.5 + 9.1 * 74 / 20 = 36.17 s; it ends at
    # 38.3 s. The figure holds between two solved models: its fourth model takes 8.5 s, and the pace is not read off a model being built.
    from crafting_system.abstraction._pattern import OUTRUN, PACE, QUARTER, SHARE, Growth, Pace, Room, Tally

    def exalted() -> Pace:
        pace = Pace()
        pace.grows = True
        pace.grown(Growth(18, 84, 10, 10), 2.5)
        pace.grown(Growth(30, 84, 10, 18), 4.3)
        return pace

    walked = held = Room(late=1.0, quarter=0.25)  # a walked plan in hand is in hand like a held one (#1224)
    pace = exalted()
    assert pace.need == pytest.approx(2.5 + 1.8 * 74 / 8)
    # after a plan a stopped search walked to (R11's site plan: the essence round's 230,524 c), the quarter's rule cut it at 6.8 s; it goes on
    assert pace.verdict(6.8, 27.0, walked) is None and pace.verdict(6.8, 27.0, held) is None
    pace.grown(Growth(40, 84, 10, 30), 11.6)
    assert pace.need == pytest.approx(2.5 + 9.1 * 74 / 20)
    assert pace.verdict(19.0, 27.0, walked) is None  # inside its fourth model: the pace of the third holds
    assert pace.verdict(27.0, 27.0, walked) is None and pace.verdict(38.3, 27.0, walked) is None  # past the share, within 54 s at its pace
    # #1325: past the 36.17 s foretold, no model solved, the overrun is charged to the pace, with no jump: 36.17 at 36.17 s, and at its end
    # (38.3 s) 36.17 + 2.13 * 74 / 20 = 44.05 s, within its room; it would stop past 36.17 + 17.83 * 20 / 74 = 40.99 s
    late = exalted()
    late.grown(Growth(40, 84, 10, 30), 11.6)
    assert late.verdict(36.17, 27.0, walked) is None and late.need == pytest.approx(2.5 + 9.1 * 74 / 20) and not late.outrun
    assert late.verdict(36.2, 27.0, walked) is None and late.need == pytest.approx(36.17 + 0.03 * 3.7, abs=1e-3) and late.outrun
    assert late.verdict(38.3, 27.0, walked) is None and late.need == pytest.approx(2.5 + 9.1 * 3.7 + (38.3 - 2.5 - 9.1 * 3.7) * 3.7)
    assert late.verdict(40.9, 27.0, walked) is None and late.verdict(41.1, 27.0, walked) == SHARE  # past its share: the share's reason
    assert pace.verdict(54.0, 27.0, walked) == SHARE  # never past its room
    assert pace.verdict(27.0, 27.0, Room(late=0.0)) == SHARE  # the last round: no room past its share
    # R13's round 2 (#1142, heavy run 44097630217): its first model held 49 of 51 offers and the model adding the other 2 never ended; R17's
    # rounds on the site plan (server run l2-R17-2: models of 10 to 69 offers, 160,000 to 320,000 kernels, unsolved after their whole
    # share, searches of 0 s). Their growth has no pace: nothing shows they will end in their room, so past the quarter they stop and leave
    # their search the rest, whatever the plan in hand (#1142 kept this for a walked plan only)
    r13 = Pace()
    r13.grown(Growth(51, 51, 49, 49), 1.5)
    assert r13.need is None
    r13.grows = True
    assert r13.verdict(74.0, 297.0, walked) is None and r13.verdict(74.3, 297.0, walked) == QUARTER == r13.verdict(74.3, 297.0, held)
    unsolved = Pace()
    unsolved.grows = True
    assert unsolved.verdict(74.3, 297.0, held) == QUARTER  # its first model not even solved
    # a build that does not grow its model (one model on every offer, or a floors pass alone) keeps its whole share, as since #1099
    assert Pace().verdict(296.0, 297.0, held) is None and Pace().verdict(297.0, 297.0, held) == SHARE
    # a build whose pace ends past its room stops there, past the quarter, and leaves its search the rest of the share, where it took the
    # whole share and left the search none (R17, R20: #1167): its first model solved at 2 s, 10 of the 80 offers to add joined by 8 s, so
    # it would need 2 + 6 * 80 / 10 = 50 s of a room of 40
    slow = Pace()
    slow.grows = True
    slow.grown(Growth(20, 90, 10, 10), 2.0)
    slow.grown(Growth(25, 90, 10, 20), 8.0)
    assert slow.need == pytest.approx(50.0)
    assert slow.verdict(4.9, 20.0, held) is None and slow.verdict(8.0, 20.0, held) == PACE and slow.verdict(8.0, 20.0, walked) == PACE
    # with no plan in hand the net is the quarter itself: the build stops at it, whatever its pace
    assert exalted().verdict(6.8, 6.8, None) == SHARE and exalted().verdict(6.7, 6.8, None) is None
    # #1325, R13's site plan (server runs n1325-R13 to n1325d-R13): with per-key joining a model's work is no longer in proportion to its
    # offers. A round's share of 20 s, room 40 s: its first model (54 of 78 offers) solved at 0.3 s, its second (4 offers at the 29 keys
    # that need them) at 0.4 s, so its pace foretells 0.3 + 0.1 * 24 / 4 = 0.9 s; its third model (5 offers more) begins the build again at
    # 8,943 keys and is not solved in 40 s. Read alone, that figure let it run to 40 s, nearly done, and its search had 0 s. Past 0.9 s it
    # has outrun it, and the overrun is charged to the pace of the 4 offers it was read from: 0.9 + (used - 0.9) * 24 / 4, past the room
    # of 40 s from 7.42 s on: it stops there, and its search has the rest of the share
    r13 = Pace()
    r13.grows = True
    r13.grown(Growth(58, 78, 54, 54), 0.3)
    r13.grown(Growth(63, 78, 54, 58), 0.4)
    assert r13.need == pytest.approx(0.9)
    assert r13.verdict(7.4, 20.0, held) is None and r13.need == pytest.approx(0.9 + 6.5 * 6)
    assert r13.verdict(7.5, 20.0, held) == OUTRUN == r13.verdict(7.5, 20.0, walked) and r13.need == pytest.approx(0.9 + 6.6 * 6)
    # counted in pieces the same rule holds, and the stop names the forecast it ran past and the need it reads now
    tally = Tally(20_000, lambda done, cap: "pieces", room=held)
    tally.grows = True
    tally.grown(Growth(58, 78, 54, 54), 300.0)
    tally.grown(Growth(63, 78, 54, 58), 400.0)
    tally.done = 7_400
    assert tally() is None
    tally.done = 7_500
    assert tally() == (
        "it had done 7,500 of its 20,000 pieces of work, past the 900 its model's pace of growth foretold, its next model unsolved, and with "
        "what it ran over charged to that pace it would need about 40,500, more than it may take: the rest is left for the search"
    )
    # a build that keeps to its pace goes on: its third model solved before the 13 s foretold, the figure moves on
    steady = Pace()
    steady.grows = True
    steady.grown(Growth(58, 78, 54, 54), 1.0)
    steady.grown(Growth(63, 78, 54, 58), 3.0)
    assert steady.need == pytest.approx(13.0) and steady.verdict(12.9, 20.0, held) is None and steady.need == pytest.approx(13.0)
    steady.grown(Growth(70, 78, 54, 63), 12.0)
    assert steady.need == pytest.approx(1.0 + 11.0 * 24 / 9) and not steady.outrun


@pytest.mark.parametrize("pace", [True, False])
def test_through_the_entry_after_a_walked_plan_a_round_whose_build_grows_at_a_pace_that_ends_within_its_room_completes_it(data, target, monkeypatch, pace):
    # #1224 (R11's site plan: the essence round's plan of 230,524 c was one its stopped search walked to, #1142, so the Exalted round's build
    # kept the quarter of its share for the search, was cut at 7 of 27 s, and the answer kept 617.28 c where its finished bound's first plan
    # is 168.03 c). The rounds of the #1099 test above, counted in states (`Budget.in_states(40)`, one piece of work per state): round 1
    # (the Exalted Orb alone) closes at 16e/3 + 2S = 153.33 having known 12 states, and its plan is taken as one a stopped search walked to.
    # Round 2 (the fillers) has 14 states, so its build may do 4 * 14 = 56 pieces of work, past the quarter (14) only at a pace that ends
    # within its room (1.5 * 56 = 84: `Net.late` 0.5, two rounds left).
    # * Its model grows one offer at a time from one (the offers' floors keep one, the binding lets one in per model: R11's Exalted round
    #   grows over 17 models): the first model is solved at 2 pieces, the second at 13, so at the quarter it is expected to need
    #   2 + 11 * 4 / 1 = 46 pieces: it goes on, completes at 51, and the round closes on the filler's plan, 3(c + e) + 2S = 133.
    # * Its first model holds 4 of the 5 offers and the model adding the last one is all its work (R13's round 2, R17's shape, #1180): its
    #   growth has no pace, so after a walked plan it stops at the quarter, as before (#1142); the round stops, and its walk's plan is the
    #   filler's, 133, which the answer takes saying it is not shown near the best.
    from crafting_system.budget import Budget
    from crafting_system.planner import _pattern_bound, _rounds

    real_groups, real_bound = _rounds.round_groups, _envelope_plan.pattern_lower_bound

    def named_alone(offers, named, added):
        head, *rest = real_groups(offers, named, added)
        asked = tuple(i for i in head.positions if offers[i].blocks is None)
        fillers = tuple(i for i in head.positions if i not in asked)
        return (_rounds.Group(asked, (), frozenset()), _rounds.Group(fillers, ("bench-craft",), head.features), *rest)

    builds = []

    def counted(*args, **kwargs):
        bound = real_bound(*args, **kwargs)
        builds.append((bound.pieces, bound.share, bound.phase, bound.rounds))
        return bound

    monkeypatch.setattr(_rounds, "round_groups", named_alone)
    monkeypatch.setattr(_rounds, "walked", lambda plan: True)
    monkeypatch.setattr(_envelope_plan, "pattern_lower_bound", counted)
    if pace:
        _one_offer_per_model(monkeypatch)
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    monkeypatch.setattr(_pattern_bound, "MIN_OFFERS", 3)
    monkeypatch.setattr(planner_plan, "MIN_OFFERS", 3)
    prices = dataclasses.replace(_prices(), chaos_per_divine=92.0)
    plan = plan_target(data, target, prices, PlanSettings(recipe_starts=False, start_price=S, solver="envelope", budget=Budget.in_states(40, build_per_state=1.0)))
    first, second = _rounds_of(plan)[:2]
    assert (first.status, first.states, first.upper) == ("closed", 12, pytest.approx(16 * E / 3 + 2 * S, rel=1e-9))
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9) and _fills(plan.solution.policy[plan.start].label)
    if pace:
        assert builds[1] == (51, 4 * 14, "complete", 18)  # (#1325: 5 models before; an offer is built at the keys that need it, and found needed at more keys in later models)
        assert second.status == "closed"
    else:
        assert builds[1] == (14, 4 * 14, "growth", 1)
        assert second.status == "stopped" and any(limit.kind == "plan-reached" for limit in plan.limits)


def _one_offer_per_model(monkeypatch):
    """The belt's bound grows over several models (#1224): the offers' floors keep one offer in the first model and the binding lets one more
    in per model (R11's Exalted round grows over 17 models), so its growth has a pace once the second model is solved: the first model at 2
    pieces of work, the second at 13 (expected need 2 + 11 * 4 / 1 = 46), the third at 25 (48), the fourth at 51, where it ends. Without it
    the first model holds 4 of the 5 offers and the model adding the last is all the work: no pace (R13's and R17's shape, #1180)."""
    from crafting_system.planner import _offer_floor, _pattern_bound

    real_binding, real_initial = _pattern_bound._binding, _offer_floor.OfferFloors.initial

    def one_at_a_time(*args, **kwargs):
        more, limits = real_binding(*args, **kwargs)
        return dict(list(more.items())[-1:]), limits  # (the offer with the largest floor, with the keys that need it, #1325)

    monkeypatch.setattr(_pattern_bound, "_binding", one_at_a_time)
    monkeypatch.setattr(_offer_floor.OfferFloors, "initial", lambda self: real_initial(self)[:1])
