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
from crafting_system.planner import PlanSettings, _envelope, _offers, plan_target
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
    assert shares == [1, 2, 1]  # round 1 has no plan in hand; then the plan is, and the two rounds left share the time


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


def test_a_judged_route_is_judged_against_every_offer_in_one_search(data, target, monkeypatch):
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    prices = dataclasses.replace(_prices(), chaos_per_divine=92.0)
    plan = plan_target(data, target, prices, PlanSettings(recipe_starts=False, start_price=S, solver="envelope", judges_route=True))
    assert LOCK in {entry.label for entry in plan.offers} and not plan.search.widening  # a route may name the lock: it is a fixed policy


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
