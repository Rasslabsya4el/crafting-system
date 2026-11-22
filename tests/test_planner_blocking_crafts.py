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

    assert raised(_rounds.NoPlan) == ([70, 70, 70, 40], 250)  # the last step makes its plan of 5 states, counted where it stood, at 40
    # a stopped or refused step is undone and tried once more in the second pass (#1276), each counted again
    assert raised(_rounds.Stopped) == ([70, 70, 70, 40, 40, 40], 330)
    assert raised(ValueError) == ([40] * 6, 240)


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
    # #1276: the steps are the seed (the Exalted Orb), the lock's metamod family, the fillers (a kind of many offers); the lock's step cannot beat
    # the seed's plan and is set aside; the second pass, before the fillers, holds it again over the same offers, so it joins with no new
    # search; the fillers' step then holds every offer and makes the plan
    plan = _plan_at(data, target, monkeypatch, divine=divine)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    seed, lock, fills = _rounds_of(plan)
    assert seed.status == fills.status == "closed" and lock.reason.endswith("it joined the second pass with no new search (the same methods)")
    # it ended at once (beaten) when its lower figure reached the plan's certified upper figure, else by closing at the same cost: never below it
    assert lock.status in ("beaten", "closed") and lock.lower >= seed.upper * (1 - 1e-6) and fills.offers == lock.offers + 3
    assert LOCK in {entry.label for entry in plan.offers}  # the fillers' step held every offer, the lock among them; its plan does not take it
    assert plan.search.exact  # every round closed, the last with every method: the plan is the cheapest over them all (OR-13)
    assert any(limit.kind == "rounds" and limit.guarantee.startswith("The plan is the cheapest among every method offered") for limit in plan.limits)


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
    # #1070, #1276: the lock's step meets the run's net before any plan of its own, in the first pass and in the second: the plan of the steps
    # that closed is the answer, and it says so
    from crafting_system.budget import Binding, BudgetExceeded

    real = planner_plan._make_plan

    def later_stopped(*args, round_call=None, **kwargs):
        if round_call is not None and LOCK in {offer.label for offer in kwargs["offers"]}:  # the lock's step
            raise BudgetExceeded(Binding("the search", "time", 600.0, 600.0, "no plan found yet"))
        return real(*args, round_call=round_call, **kwargs)

    monkeypatch.setattr(planner_plan, "_make_plan", later_stopped)
    plan = _plan_at(data, target, monkeypatch, divine=91.0)  # a lock at 182 would be kept: its step is stopped
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    assert [record.status for record in _rounds_of(plan)] == ["closed", "stopped", "stopped", "closed"]  # the lock's retry before the fillers
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
        if round_call is not None and LOCK in {offer.label for offer in kwargs["offers"]} and lock_stopped:  # the lock's step (#1276)
            raise BudgetExceeded(Binding("the search", "time", 600.0, 600.0, "no plan found yet"))
        plan = real(*args, round_call=round_call, **kwargs)
        if round_call is not None:  # every step ends at the gap, as a search past its aim does
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
        assert [record.status for record in _rounds_of(plan)] == ["within", "stopped", "stopped", "within"]
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
        if round_call is not None and LOCK in {offer.label for offer in kwargs["offers"]}:  # the lock's step (#1276)
            cause = NoPolicy("the search stopped", stopped="the time limit of 30 seconds was reached", lower=120.0)
            outer = NoPolicy("the bound was cut short")  # `envelope_result` adds the note of a bound cut short over the search's own refusal
            outer.__cause__ = cause
            raise planner_plan.PlanError("no policy of the offered actions reaches the goal") from outer
        return real(*args, round_call=round_call, **kwargs)

    monkeypatch.setattr(planner_plan, "_make_plan", later_stopped)
    plan = _plan_at(data, target, monkeypatch, divine=91.0)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    first, lock, again, fills = _rounds_of(plan)
    assert first.status == fills.status == "closed" and lock.status == again.status == "stopped"
    assert lock.reason.startswith("the time limit of 30 seconds was reached") and lock.lower == 120.0
    assert not plan.search.exact


STOPPED_AT_10 = ["stopped", "stopped", "stopped", "not tried"]  # the seed, the lock, its retry before the fillers, and the fillers not reached


@pytest.mark.parametrize("states", [10, 40])
def test_through_the_entry_a_run_counted_in_states_gives_the_same_plan_and_answer_whatever_the_clock_does(data, target, monkeypatch, states):
    # #886, #1276: the belt's offers split into steps (the seed's Exalted Orb, the lock's metamod family, the fillers). Under `Budget.in_states`
    # the plan and every line of the answer are the same whether every reading of the clock moves it by 1,000 s or by nothing; the test drives
    # the clock itself and never reads it. With 10 states the steps after the seed's are stopped by their share and the plan is the seed's
    # exalt chain; with 40 every step closes on the fill-then-exalt plan. The run never knows more states than its net.
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
    assert slow.mean_remaining == fast.mean_remaining
    assert slow.mean_remaining == pytest.approx(3 * (C + E) + 2 * S if states == 40 else 565.0, rel=1e-9)
    assert slow.solution.policy == fast.solution.policy and slow.limits == fast.limits  # every line of the answer
    assert slow.risk is not None and slow.risk == fast.risk  # the cost figures too (their ladder has no time net in such a run)
    assert [replace_seconds(record) for record in slow.search.widening] == [replace_seconds(record) for record in fast.search.widening]
    statuses = [record.status for record in slow.search.widening]
    assert statuses == (["closed"] * 3 if states == 40 else STOPPED_AT_10)
    assert all(record.states is not None for record in slow.search.widening)
    assert sum(record.states for record in slow.search.widening) <= states


def test_through_the_entry_the_plan_without_the_lock_is_made_first_counted_in_states_and_the_lock_s_step_shares_what_is_left(data, target, monkeypatch):
    # #1108, #1276: the metamod craft the rule of blocking crafts offers unasked (the lock, Prefixes Cannot Be Changed) adds the feature
    # `metamods` to the model, so the planner's own offers that hold it split into steps (`offer_groups`): the seed (the Exalted Orb) is made
    # first without the lock, the lock's family is a later step. Under `Budget.in_states(N)` each step is given its share of the states left
    # over the steps left (`StatesMeter.net`), never the whole account. The lock's step cannot beat the plan in hand and is set aside; the
    # fillers' step makes the plan of 133, and the second pass holds the lock again with every offer, so the plan is proved over every method.
    # The plan and every line of the answer are the same whether every reading of the clock moves it by 1,000 s or by nothing.
    from crafting_system import budget as budget_module
    from crafting_system.budget import Budget

    states = 1_000
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    prices = dataclasses.replace(_prices(), chaos_per_divine=92.0)
    step, readings = [0.0], iter(range(10**9))
    monkeypatch.setattr(budget_module.time, "perf_counter", lambda: step[0] * next(readings))
    calls, real = [], planner_plan._make_plan

    def spied(*args, **kwargs):  # each step's offers and the states net it is given
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
    assert slow.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)  # the filler, then exalt
    assert LOCK in {entry.label for entry in slow.offers}  # the fillers' step held every offer
    first, lock, fills = rounds
    assert slow_calls[0] == (False, states // 3)  # the seed: a third of the account, three steps left
    assert slow_calls[1] == (True, (states - first.states) // 2)  # the lock's step, which cannot beat the seed's plan and is set aside
    # the second pass, before the fillers (a kind of many offers): the lock over the same offers joins with no new search; the fillers' step
    # then holds every offer, the lock among them
    assert len(slow_calls) == 3 and slow_calls[2][0] is True and fills.offers == lock.offers + 3
    assert [record.status for record in rounds] == ["closed"] * 3 and not lock.carried and lock.covered and slow.search.exact


@pytest.mark.parametrize("states, per_state", [(10, 0.2), (10, 1.5), (10, 100.0), (40, 100.0)])
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
    pieces, share, phase, stopped, _ = slow_builds[0]  # the seed's build: `per_state` pieces per state of its net, the whole of it (`Net.step`)
    assert share == int(per_state * (1 + _envelope_plan.SEARCH_PER_BUILD) * (states // 3))
    if per_state == 0.2:  # 2 pieces: stopped while it counted the kinds of item
        assert phase == "model" and pieces == share and slow_bindings == []
    elif per_state == 1.5:  # a later step's first model is built and solved, the binding step names the offers to join, and their growth is stopped
        assert any(build[2] == "growth" for build in slow_builds[1:]) and slow_bindings[0] == "done"  # (stopped by its count: test_cli_envelope_build.py)
        assert all(record.status == "undone" for record in slow.search.widening[1:])  # a build not complete undoes its step (#1276)
    else:  # every build finishes; with 40 states every step closes on the cheapest plan
        assert all(build[2] == "complete" and build[3] is None for build in slow_builds) and "done" in slow_bindings
        if states == 40:
            assert [record.status for record in slow.search.widening] == ["closed"] * 3
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

    def named_alone(offers, named, added, seed=()):
        head, *rest = real(offers, named, added, seed)
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
    assert len(plan.search.widening) > 1 and plan.search.exact  # searched in steps, not every offer at once
    assert given.risk.mean.value == pytest.approx(16 * E / 3 + 2 * S, rel=1e-9) and not given.gaps
    limit = next(limit for limit in plan.limits if limit.what == "The given route's methods were searched from the first round")
    assert limit.labels == ("Exalted Orb",) and limit.guarantee.startswith("The first round finished: no plan made only of its methods")
    assert not any(limit.what.startswith("The given route") for limit in unjudged.limits)


def test_a_judged_route_that_names_the_lock_holds_it_from_the_first_round(data, target, tmp_path, monkeypatch):
    # #1110, #1276: a route that takes the Lock, an offer of a later family: the Lock leads the seed with the target's named actions, so every
    # step and the plan hold it and the route is read on that plan; the fillers are a step after the seed, and every step closes.
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    route = EXALTING_ROUTE.replace("  - do: Exalted Orb\n", f"  - when:\n      crafted_mods: false\n    do: {LOCK}\n  - do: Exalted Orb\n")
    named, plan, given = _judged(data, target, tmp_path, route)
    assert named == (LOCK, "Exalted Orb") and LOCK in {entry.label for entry in plan.offers}
    assert plan.search.exact and plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    assert all(LOCK in {o.label for o in plan.offers} for _ in plan.search.widening) and plan.search.widening[0].status == "closed"
    assert given.risk.mean.value >= plan.mean_remaining * (1 - 1e-9)  # the last step held every offer, the Lock included: the plan is proved the cheapest


def test_the_judged_route_limit_says_nothing_is_proved_against_the_route_when_the_first_round_did_not_finish():
    from crafting_system.planner import _rounds

    record = _rounds.RoundRecord(("exalted-orb",), 3, _rounds.UNDONE, "its share", 100.0, 140.0, 1.0)
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


def test_a_round_that_proves_no_plan_with_a_plan_in_hand_is_set_aside_like_a_beaten_one():
    # #1097 point 2, #1276: step 2 (b) with the base reaches no plan at all while the plan of 10 is in hand. It proved only that no plan of its
    # offers with the base costs less than 10 (none exists), as a beaten step does: it is set aside, step 3 does not hold b, and the second pass
    # holds both again (b joins with no new search, since its base is the same; c's step then holds every offer), so the proof is the whole one.
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
    assert widened.records[1].reason.endswith("it joined the second pass with no new search (the same methods)")


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


def test_through_the_entry_the_seed_holds_the_offer_that_gives_the_wanted_mod_and_no_tool(data, target, monkeypatch):
    # #1276: the belt's seed is read from the offers' chances on the wanted mods (`_offer_kinds.leaf_providers`): the Exalted Orb, which can add
    # the wanted mod; the fillers and the lock pass no wanted mod alone (tools), so each is in a family of a later step
    from crafting_system.planner import _rounds

    seeds, real = [], _rounds.round_groups

    def spied(offers, named, added, seed=()):
        steps = real(offers, named, added, seed)
        seeds.append([offers[i].label for i in steps[0].positions])
        return steps

    monkeypatch.setattr(_rounds, "round_groups", spied)
    plan = _plan_at(data, target, monkeypatch, divine=92.0)
    assert seeds == [["Exalted Orb"]] and plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)


def test_through_the_entry_a_family_whose_build_does_not_complete_is_undone_and_the_plan_is_not_called_the_cheapest(data, target, monkeypatch):
    # #1276: the lock's step has a plan in hand and its bound's build is stopped (planted): the step is undone with no search, in the first pass
    # and in the second; the fillers' step still makes the plan of 133, and the answer proves it only over the steps that closed, naming the lock's
    real = _envelope_plan.pattern_lower_bound
    searched = []

    def stopped_for_the_lock(abstraction, start, offers, **kwargs):
        bound = real(abstraction, start, offers, **kwargs)
        held = {priced.label for priced in offers}
        searched.append(LOCK in held)
        return dataclasses.replace(bound, stopped="planted: the time limit was reached", phase="model") if LOCK in held else bound

    monkeypatch.setattr(_envelope_plan, "pattern_lower_bound", stopped_for_the_lock)
    plan = _plan_at(data, target, monkeypatch, divine=91.0)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    assert [record.status for record in _rounds_of(plan)] == ["closed", "undone", "undone", "closed"] and searched.count(True) == 2  # its retry comes before the fillers
    assert not plan.search.exact and LOCK not in {entry.label for entry in plan.offers}
    untried = next(limit for limit in plan.limits if limit.what == "Not finished")
    assert "not finished (its count of the cheapest possible cost did not finish in its share" in untried.names[0]
