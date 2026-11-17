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

At S = 50, e = 10, c = 1: 153.33 without the craft and 133 with it. The target names the kinds it uses (an Exalted Orb is opt-in until
#886's second part) and names no craft.
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
actions: [exalted-orb, bench-craft]
"""


@pytest.fixture
def target(tmp_path, data):
    path = tmp_path / "belt.yaml"
    path.write_text(TARGET, encoding="utf-8")
    return load_target(path, data)


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
    # was not carried and one last round holds it again with every offer (#1080), alone in its share
    assert shares == [1, 2, 1, 1]


def test_a_round_with_no_plan_in_hand_gives_way_once_it_has_a_plan_and_its_share_and_a_later_round_finds_the_saving():
    # #1080: round 1 begins with no plan in hand, so it may take all the time left; its search makes a plan of 10 at once and then only raises its
    # lower figure (R10's bench crafts: a first plan at 147 s, then 440 s with nothing cheaper). The run has 600 s and three rounds: round 1's share
    # is 200 s. Its search asks after each of its own rounds (one per 50 s here); with a plan in hand and 200 s used it stops with its plan, and
    # rounds 2 and 3 are tried. Round 2 holds the saving: a plan of 7. The answer names what each round did.
    from types import SimpleNamespace

    from crafting_system.planner import _rounds

    groups = tuple(_rounds.Group((i,), (kind,), frozenset({"junk", kind})) for i, kind in enumerate("abc"))
    now = [0.0]  # the run's clock, moved by hand: nothing reads the time
    asked = []

    def search(chosen, call):
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
    multimod = load_target(path, data)
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
    path.write_text(TARGET.replace("actions: [exalted-orb, bench-craft]", "actions: [exalted-orb, bench-craft, hinekora-lock]"), encoding="utf-8")
    target = load_target(path, data)
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
    assert plan.foresight.status == "switched off by the target"  # the target names no Lock
    assert plan.risk is not None


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


@pytest.mark.parametrize("states", [3, 10])
def test_through_the_entry_a_run_counted_in_states_gives_the_same_plan_and_answer_whatever_the_clock_does(data, target, monkeypatch, states):
    # #886: the belt's offers split into two rounds (the lock's is the second). Under `Budget.in_states` the plan and every line of the answer are
    # the same whether every reading of the clock moves it by 1,000 s or by nothing; the test drives the clock itself and never reads it. With 3
    # states, round 1 uses the net and the lock's round is not tried; with 10, both rounds close.
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
    assert [record.status for record in slow.search.widening] == (["closed", "not tried"] if states == 3 else ["closed", "closed"])
    assert all(record.states is not None for record in slow.search.widening)


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


def test_the_cut_keeps_the_restart_cuts_at_a_tie_and_cuts_nothing_without_a_finite_figure():
    from crafting_system.planner._offers import RESTART, BuyStartItem, Offer, PricedOffer
    from crafting_system.planner._price_cut import restart_dominated

    restart = PricedOffer(Offer(RESTART, BuyStartItem(None), {"belt": 1}, shares=False), 500.0, ())
    cheap, tie, dear = (PricedOffer(Offer(label, None, {}), cost, ()) for label, cost in (("cheap", 182.9), ("tie", 183.0), ("dear", 600.0)))
    kept, cut = restart_dominated((cheap, tie, dear, restart), 50.0, 133.0)
    assert kept == (cheap, restart) and cut == (tie, dear)
    assert restart_dominated((cheap, dear), 50.0, float("inf")) == ((cheap, dear), ())


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
    given = load_target(path, data)
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
