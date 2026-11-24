"""The one-side role of the growth (#1542, hypothesis H40 of #1434; `planner/_growth.py`, module text "the one-side role").

On R24 the planner's own model holds a plan of 1,710.64 c after the start that main's search never reached (2,134.44 c): its four methods
that make the difference (a bench craft that fills the prefixes, the beast side swap, the Eldritch Orb of Annulment and the Ember that
sets the side it removes from) were named by no role, since none read an offer that acts on one side only. By hand, the group of main's
plan with the one-side offers of its steps gave R14 2,579.55 c against main's 3,168.07 c (issue #1542, comment 7126096558).

* The hand table: what the role names for a step that waits for, or can lose, the mods of one side; the cleaner of each side; the
  closure that brings what a removal reads to choose its side.
* The growth on a hand search (`_rounds.widen`, the costs worked by hand): a plan of 100 whose one step waits for a suffix alone; with
  the prefix filler and the removal of a prefix it costs 10. The growth's second round names them; main's growth names nothing for the
  step, and the plan of 10 comes only from the widening.
* The real 3.29.3.3 dump (skips without it): R14's and R24's offers as the table reads them.
"""

import dataclasses
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_growth import MAGIC, RARE, A, B, _entry, _names, _Plan, _State, _table, _widen

from crafting_system.abstraction import Status
from crafting_system.planner import _growth, _rounds
from crafting_system.planner._growth import OWN_POOL, Grower, OfferTable
from crafting_system.solver import Action, Outcome

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "references-allflame-2026-07-31.json"


def _one_side_table() -> OfferTable:
    """A (a prefix) is on the start item; B (a suffix) is open. Offers: 0 "exalt" (adds B 1 in 10 at the rare), 1 a prefix filler, 2 a suffix
    filler, 3 a beast swap that removes a prefix (it draws a suffix, held back for the later group), 4 an Eldritch annulment that removes a
    prefix after an Ember and a suffix after an Ichor, 5 the Ember, 6 the Ichor, 7 an annulment of either side (the cheapest cleaner)."""
    return _table(
        _entry("exalt", 10.0, at=RARE, chance={B: Fraction(1, 10)}),
        _entry("fill prefix", 0.05, kind="craft", crafted=True, fills=frozenset({"prefix"})),
        _entry("fill suffix", 0.04, kind="craft", crafted=True, fills=frozenset({"suffix"})),
        _entry("swap remove prefix", 5.0, clears=frozenset({"prefix"}), fans=OWN_POOL),
        _entry("eldritch annul", 44.0, kind="terminal", draws=False, clears=frozenset({"prefix", "suffix"}), sets={"prefix": (5,), "suffix": (6,)}),
        _entry("ember", 0.25, kind="implicit", draws=False),
        _entry("ichor", 0.3, kind="implicit", draws=False),
        _entry("annul", 12.0, kind="craft", removes=True),
    )


def test_a_step_that_waits_for_one_side_names_the_other_side_s_filler_and_its_cheapest_removals_with_and_without_a_draw():
    table = _one_side_table()
    table.held_back = frozenset({3})  # the swap waits for the later group, yet the one-side role names it
    # waits for B, a suffix: the additions go to the suffixes when the prefixes are full or emptied of what they may lose
    assert _names(table, table.side_roles({B}, set())) == {"fill prefix", "swap remove prefix", "eldritch annul", "ember"}
    # can lose A, a prefix: the removals are kept off the prefixes, the suffix side is filled and cleared alone
    assert _names(table, table.side_roles(set(), {A})) == {"fill suffix", "eldritch annul", "ichor"}
    # waits on both sides: no one side, nothing named
    assert table.side_roles({A, B}, set()) == set()


def test_the_cleaners_are_the_cheapest_annulment_and_the_cheapest_removal_of_each_side_the_held_back_ones_waiting():
    table = _one_side_table()
    assert _names(table, table.cleaners()) == {"annul", "swap remove prefix", "eldritch annul", "ichor"}
    table.held_back = frozenset({3})
    assert _names(table, table.cleaners()) == {"annul", "eldritch annul", "ember", "ichor"}


def test_a_removal_that_reads_an_implicit_to_choose_its_side_brings_the_cheapest_offer_that_sets_one():
    table = _one_side_table()
    assert _names(table, table.closure({4})) == {"eldritch annul", "ember"}
    assert _names(table, table.closure({4, 6})) == {"eldritch annul", "ichor"}  # it can act already: nothing more


def _one_side_world():
    table = _one_side_table()
    offers = tuple(SimpleNamespace(label=entry.label) for entry in table.entries)
    start, goal = _State("start", (Status.PASSING, Status.ABSENT), RARE), _State("goal", (Status.PASSING, Status.PASSING), RARE)
    seen = []

    def run(chosen, call):
        labels = {offer.label for offer in chosen}
        seen.append(labels)
        if {"fill prefix", "swap remove prefix"} <= labels:  # the hand search: with the filler and the swap, 10
            view = {start: Action("swap remove prefix", 5.0, (Outcome(goal, 1), Outcome(start, 1)))}
            plan = _Plan(mean_remaining=10.0, start=start, packed=SimpleNamespace(view=view, risk_policy=None, risk_start=None), search=SimpleNamespace(lower=10.0, bound_stopped=None))
        else:  # the exalt alone waits for B: 100
            view = {start: Action("exalt", 10.0, (Outcome(goal, 1), Outcome(start, 9)))}
            plan = _Plan(mean_remaining=100.0, start=start, packed=SimpleNamespace(view=view, risk_policy=None, risk_start=None), search=SimpleNamespace(lower=100.0, bound_stopped=None))
        if call.upper is not None and plan.mean_remaining >= call.upper:
            raise _rounds.Beaten(call.upper)
        return plan

    groups = tuple(_rounds.Group((n,), (entry.label,), frozenset({entry.label})) for n, entry in enumerate(table.entries))
    grower = Grower(table, ())
    grower.seed = lambda: ((0,), "the seed")
    return table, offers, groups, grower, run, seen


def _netted(groups, offers, run, grower, rounds):
    """`_rounds.widen` under a net that runs out after `rounds` searches (the run's time, counted in rounds)."""
    calls = []

    def counted(chosen, call):
        calls.append(chosen)
        return run(chosen, call)

    return _rounds.widen(
        groups, offers, counted, upper_of=lambda plan: plan.mean_remaining, mean_of=lambda plan: plan.mean_remaining,
        ended=lambda plan: (_rounds.CLOSED, ""), left=lambda: 1000.0 - 1000.0 * (len(calls) >= rounds), clock_now=lambda: 0.0, grow=grower,
    )  # fmt: skip


def test_the_growth_s_second_round_names_the_one_side_offers_and_makes_the_cheaper_plan_before_any_widening_round():
    _table_, offers, groups, grower, run, seen = _one_side_world()
    widened = _widen(groups, offers, run, grower)
    assert widened.plan.mean_remaining == 10.0
    made = widened.records[1]
    assert made.growth is not None and "exalt" in made.growth and made.upper == 10.0
    assert {"fill prefix", "swap remove prefix", "eldritch annul", "ember"} <= seen[1]
    # under a net of three rounds the branch holds the plan of 10
    _table_, offers, groups, grower, run, _seen = _one_side_world()
    assert _netted(groups, offers, run, grower, 3).plan.mean_remaining == 10.0


def test_without_the_one_side_role_main_s_growth_names_nothing_for_the_step_and_ends_dearer_under_the_same_net(monkeypatch):
    monkeypatch.setattr(OfferTable, "side_roles", lambda self, waits, risks: set())
    _table_, offers, groups, grower, run, _seen = _one_side_world()
    assert _netted(groups, offers, run, grower, 3).plan.mean_remaining == 100.0  # main: the exalt alone, 100
    _table_, offers, groups, grower, run, _seen = _one_side_world()
    widened = _widen(groups, offers, run, grower)
    assert widened.plan.mean_remaining == 10.0  # with no net every method closes in the end
    made = next(record for record in widened.records if record.upper == 10.0)
    assert made.growth is None or made.growth.startswith("the later group")  # not a round the growth named for the step


def _real_table(name):
    from abstraction_support import real_game_data

    from crafting_system.abstraction._goal import Goal
    from crafting_system.planner._plan import cheapest_per_class, offers_for, price_offers
    from crafting_system.prices import load_price_file
    from crafting_system.targets import load_target

    data = real_game_data()
    target = dataclasses.replace(load_target(ROOT / "examples" / "targets" / name, data), actions=None)
    goal = Goal.from_target(target)
    priced, _dropped = price_offers(offers_for(data, goal, target.base_id, target.start_item, target.actions).offers, load_price_file(PRICES), "test")
    priced, _same = cheapest_per_class(priced)
    return _growth.growth_table(data, goal, target, priced, None)


def _labels(table, positions):
    return {table.entries[position].label for position in positions}


def test_on_r14_the_role_names_the_hand_lists_fillers_and_beast_swaps():
    table = _real_table("r14-hunter-bow.yaml")
    position = {entry.label: entry.position for entry in table.entries}
    swaps = {"Beastcraft Add Prefix Remove Suffix": "suffix", "Beastcraft Add Suffix Remove Prefix": "prefix"}
    assert {label: sorted(table.entries[position[label]].clears) for label in swaps} == {label: [side] for label, side in swaps.items()}
    assert not any(entry.clears for entry in table.entries if entry.label not in swaps)  # an Orb of Annulment takes either side: no one side
    # the Augmentation step waits for Attack Speed, a suffix: the prefix filler of the hand list and the swap that removes a prefix
    speed = next(leaf for leaf in range(len(table.goal.leaves)) if table.side_of(leaf) == "suffix")
    prefix = next(leaf for leaf in range(len(table.goal.leaves)) if table.side_of(leaf) == "prefix")
    for leaves, side, swap in ((({speed}, set()), "prefix", "Beastcraft Add Suffix Remove Prefix"), ((set(), {prefix}), "suffix", "Beastcraft Add Prefix Remove Suffix")):
        named = table.side_roles(*leaves)
        fillers = [table.entries[position] for position in named if table.entries[position].fills]
        # one filler of the other side, among the cheapest (four prefix crafts tie at 0.042 c), and the swap that removes from that side
        assert [entry.fills for entry in fillers] == [{side}] and fillers[0].cost == min(entry.cost for entry in table.entries if entry.fills == {side})
        assert _labels(table, named) == {fillers[0].label, swap}


def test_on_r24_the_eldritch_annulment_removes_a_prefix_after_an_ember_and_a_suffix_after_an_ichor():
    table = _real_table("r24-avoid-shock-boots.yaml")
    annul = next(entry for entry in table.entries if entry.label == "Eldritch Orb of Annulment")
    assert annul.clears == {"prefix", "suffix"}
    assert table.entries[annul.sets["prefix"][0]].label == "Lesser Eldritch Ember" and table.entries[annul.sets["suffix"][0]].label == "Lesser Eldritch Ichor"
    resistances = [leaf for leaf in range(len(table.goal.leaves)) if table.side_of(leaf) == "suffix"]
    named = _labels(table, table.side_roles(set(resistances), set()))
    assert {"Eldritch Orb of Annulment", "Lesser Eldritch Ember", "Beastcraft Add Suffix Remove Prefix"} <= named
    filler = next(table.entries[position] for position in table.side_roles(set(resistances), set()) if table.entries[position].fills)
    assert filler.fills == {"prefix"} and filler.cost < 0.05
    # a filler never takes a wanted mod's family: the Fire Resistance craft would block the T2+ resistance R24 wants
    assert not any(entry.fills and entry.label.endswith("Fire Resistance") for entry in table.entries)
    # nor is a metamod a filler: a lock, a tag kept out of the draws, more crafted mods
    assert not any(entry.fills and (entry.locks or entry.keeps_out or entry.more_crafted) for entry in table.entries)
    assert any(entry.locks and entry.crafted for entry in table.entries)
