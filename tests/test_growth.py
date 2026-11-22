"""The plan-led growth of the rounds (#1414, #1276; `planner/_growth.py`, research note 2026-11-22-rounds-design-2, section 4).

Each role is tested on a hand-made table of offers (what they declare, their chances on two wanted mods `A` and `B`), the rounds on a
hand-made search (`_rounds.widen` with a `run` whose costs are worked by hand), and the whole through the planner's entry on the fixture's
belt of `test_planner_blocking_crafts` (its plan worked out there: `3(c + e) + 2S`).

The G/H shape of `_rounds.py` (#1389): a plan in hand of 10 whose one step waits for `A` and `B`; tool G adds `A` for 1, tool H adds `B` for 1,
and with one of them alone the plan stays 10. Main's widening tries G with the base (beaten, 10, set aside), then H with the base (beaten), and
holds the two together only in its closing round of every offer; the growth names both adders in its second round, whose plan costs 2.
"""

import dataclasses
import math
from fractions import Fraction
from types import SimpleNamespace

import pytest
from test_planner_blocking_crafts import C, E, S, _plan, data, target  # noqa: F401  (the belt world and its fixtures)

from crafting_system.abstraction import Status
from crafting_system.items import Rarity, Side
from crafting_system.planner import _growth, _rounds
from crafting_system.planner._growth import Entry, Grower, OfferTable, read_step, step_shares
from crafting_system.solver import Action, Outcome

MAGIC, RARE = Rarity.MAGIC, Rarity.RARE
A, B = 0, 1  # the two wanted mods: A a prefix, B a suffix


def _table(*entries: Entry, tags=("attack",)) -> OfferTable:
    """A table of `entries` over the wanted mods A (a prefix) and B (a suffix), both open at a magic start; `tags` are the wanted mods' tags."""
    table = OfferTable.__new__(OfferTable)
    mods = {"A1": SimpleNamespace(generation_type="prefix", implicit_tags=tags, families=()), "B1": SimpleNamespace(generation_type="suffix", implicit_tags=(), families=())}
    table.data = SimpleNamespace(mods=mods)
    table.goal = SimpleNamespace(leaves=(SimpleNamespace(mod_ids=frozenset({"A1"}), tier_ok=None), SimpleNamespace(mod_ids=frozenset({"B1"}), tier_ok=None)))
    table.open, table.start_rarity = (A, B), MAGIC
    table.entries = [dataclasses.replace(entry, position=n) for n, entry in enumerate(entries)]
    return table


def _entry(label, cost, kind="add", at=MAGIC, chance=None, leads=None, **declared) -> Entry:
    return Entry(0, label, cost, kinds={MAGIC: kind, RARE: kind}, leads=leads or {}, chance={(at, leaf): Fraction(p) for leaf, p in (chance or {}).items()}, **{"draws": kind != "craft", **declared})


def _names(table: OfferTable, positions) -> set[str]:
    return {table.entries[p].label for p in positions}


def test_the_adders_of_a_waited_mod_are_the_cheapest_over_chance_that_keep_the_mods_and_are_not_held():
    table = _table(
        _entry("reroll A", 0.1, kind="reroll", chance={A: 1}),  # a reroll is no adder, however cheap
        _entry("add A cheap", 1.0, chance={A: Fraction(1, 2)}),  # 2 per A
        _entry("add A dear", 9.0, chance={A: Fraction(1, 2)}),  # 18 per A
        _entry("craft A", 3.0, kind="craft", chance={A: 1}),  # 3 per A
        _entry("add A held", 0.5, chance={A: 1}),  # held by the round that made the plan: not named again
    )
    named = table.roles({A}, set(), frozenset({MAGIC}), False, frozenset({4}), frozenset())
    assert {"add A cheap", "craft A"} <= _names(table, named) and not _names(table, named) & {"reroll A", "add A dear", "add A held"}


def test_an_adder_at_another_shape_brings_the_cheapest_moves_there():
    table = _table(
        _entry("exalt A", 1.0, at=RARE, chance={A: 1}),  # an adder at the rare shape only
        _entry("regal", 2.0, leads={MAGIC: frozenset({RARE})}),  # magic to rare for 2
        _entry("dear regal", 5.0, leads={MAGIC: frozenset({RARE})}),
    )
    named = table.roles({A}, set(), frozenset({MAGIC}), False, frozenset(), frozenset())
    assert _names(table, named) >= {"exalt A", "regal"} and "dear regal" not in _names(table, named)


def test_the_protectors_of_a_mod_at_risk_keep_the_mods_they_are_given():
    table = _table(
        _entry("fracture", 4.0, kind="terminal", fractures=True, draws=False),
        _entry("reroll that fractures", 1.0, kind="reroll", fractures=True),  # it draws: it keeps nothing it was given
        _entry("lock prefixes", 6.0, kind="craft", locks=frozenset({Side.PREFIX})),
        _entry("lock suffixes", 6.0, kind="craft", locks=frozenset({Side.SUFFIX})),
        _entry("imprint", 3.0, kind="terminal", makes_imprint=True, draws=False, leads={MAGIC: frozenset({MAGIC})}),
    )
    # A (a prefix) is at risk while the step waits for B (a suffix): the prefix lock, never the suffix one, which would keep B from coming
    named = _names(table, table.roles({B}, {A}, frozenset({MAGIC}), False, frozenset(), frozenset()))
    assert {"fracture", "lock prefixes", "imprint"} <= named and not named & {"reroll that fractures", "lock suffixes"}
    # a state that holds a fractured mod already names no fracture
    assert "fracture" not in _names(table, table.roles({B}, {A}, frozenset({MAGIC}), True, frozenset(), frozenset()))


def test_a_step_that_waits_on_both_sides_locks_each_side_and_one_that_waits_on_one_side_alone_never_locks_it():
    # a reroll that waits for A (a prefix) and B (a suffix) and can lose both: under the prefix lock it still gains B, under the suffix lock A
    table = _table(
        _entry("lock prefixes", 6.0, kind="craft", locks=frozenset({Side.PREFIX})),
        _entry("lock suffixes", 6.0, kind="craft", locks=frozenset({Side.SUFFIX})),
    )
    assert _names(table, table.roles({A, B}, {A, B}, frozenset({MAGIC}), True, frozenset(), frozenset())) == {"lock prefixes", "lock suffixes"}
    # a step that waits for A alone gains nothing under the prefix lock: only B's side is locked
    assert _names(table, table.roles({A}, {A, B}, frozenset({MAGIC}), True, frozenset(), frozenset())) == {"lock suffixes"}


def test_a_wanted_mod_s_side_is_read_from_its_prefixes_and_suffixes_alone():
    table = _table()
    table.data.mods["A2"] = SimpleNamespace(generation_type="unique", implicit_tags=(), families=())  # a unique's mod that passes A too
    table.goal.leaves[A].mod_ids = frozenset({"A1", "A2"})
    assert table.side_of(A) == "prefix"


def test_an_imprint_is_named_only_where_it_can_be_made():
    # an imprint taken of magic items only (its outcomes read at the magic shape alone) protects nothing on a step that acts on a rare item
    table = _table(_entry("imprint", 3.0, kind="terminal", makes_imprint=True, draws=False, leads={MAGIC: frozenset({MAGIC})}))
    assert _names(table, table.roles({B}, {A}, frozenset({RARE}), True, frozenset(), frozenset())) == set()
    assert _names(table, table.roles({B}, {A}, frozenset({MAGIC}), True, frozenset(), frozenset())) == {"imprint"}


def test_the_cleaners_and_narrowers_of_the_adders():
    table = _table(
        _entry("add A", 1.0, chance={A: 1}),
        _entry("add B", 1.0, chance={B: 1}),
        _entry("annul", 2.0, kind="craft", removes=True),
        _entry("dear annul", 9.0, kind="craft", removes=True),
        _entry("remove crafted", 1.0, kind="craft", removes=True, needs_crafted=True),
        _entry("no caster", 5.0, kind="craft", keeps_out=frozenset({"caster"}), crafted=True),
        _entry("no attack", 5.0, kind="craft", keeps_out=frozenset({"attack"}), crafted=True),  # A carries the attack tag
        _entry("more crafted", 7.0, kind="craft", more_crafted=True),
    )
    # the adders draw A and B: the caster tag is kept out, the attack tag never (keeping it out would keep A from coming); one crafted mod
    # held (the caster narrower) names RCM but no multimod
    named = _names(table, table.roles({A, B}, set(), frozenset({MAGIC}), False, frozenset(), frozenset()))
    assert {"annul", "remove crafted", "no caster"} <= named and not named & {"dear annul", "no attack", "more crafted"}


def test_a_narrower_reads_the_tags_of_the_wanted_mods_the_adders_must_draw():
    """#1423, worked by hand. A (a prefix with the attack tag) and B (a suffix, no tag) are open; "no attack" keeps the attack tag out.

    1. The step waits for A and B, and A comes only from an addition (it is drawn): the attack tag is kept, "no attack" is not named.
    2. The round holds "craft A", a bench craft that gives A (R04's Attack Speed craft, made after the slam): A is not drawn, so the attack
       tag may be kept out of B's draws and "no attack" is named; it and "craft A" are two crafted mods held, so the multimod is named too.
    3. A passes at every state where the step acts (R14's Attack Speed at the Regal step): the step draws B alone, "no attack" is named,
       though A's only adder draws; it is the one crafted mod held, so no multimod.
    """
    table = _table(
        _entry("add A", 1.0, chance={A: 1}),
        _entry("add B", 1.0, chance={B: 1}),
        _entry("craft A", 3.0, kind="craft", chance={A: 1}, crafted=True),
        _entry("no attack", 5.0, kind="craft", keeps_out=frozenset({"attack"}), crafted=True),
        _entry("more crafted", 7.0, kind="craft", more_crafted=True),
    )
    add_a, add_b, craft_a = 0, 1, 2
    assert not _names(table, table.roles({A, B}, set(), frozenset({MAGIC}), False, frozenset({craft_a}), frozenset({add_a, add_b}))) & {"no attack", "more crafted"}
    assert table.narrowers({A, B}, {add_a, add_b}) == set()
    named = _names(table, table.roles({B}, set(), frozenset({RARE}), False, frozenset(), frozenset({add_a, add_b, craft_a}), {A, B}))
    assert {"no attack", "more crafted"} <= named
    assert _names(table, table.narrowers({A, B}, {add_a, add_b, craft_a})) == {"no attack"}
    named = _names(table, table.roles({B}, set(), frozenset({RARE}), False, frozenset({craft_a}), frozenset({add_a, add_b}), {B}))
    assert "no attack" in named and "more crafted" not in named


def test_the_mods_a_step_waits_on_are_those_not_passing_where_it_acts():
    passing, failing = Status.PASSING, Status.ABSENT
    acts = [
        (SimpleNamespace(status=(passing, failing)), None, 2.0),
        (SimpleNamespace(status=(passing, passing)), None, 1.0),
        (SimpleNamespace(status=(failing, failing)), None, 0.0),  # a state the plan never visits reads nothing
    ]
    assert _growth.pending_at(acts, 2) == {B}


def test_the_dependencies_a_pick_brings_the_unveil_the_veiled_sources_and_every_pick_and_a_restore_its_imprint():
    table = _table(
        _entry("pick 1", 0.0, kind="veiled", needs_veiled=True),
        _entry("pick 2", 0.0, kind="veiled", needs_veiled=True),
        _entry("unveil", 0.0, kind="veiled", needs_veiled=True),
        _entry("veiled reroll", 3.0, kind="reroll", veils=True),
        _entry("veiled add", 9.0, kind="veil", veils=True),
        _entry("restore", 0.0, kind="refused", restores=True),
        _entry("imprint", 3.0, kind="terminal", makes_imprint=True),
        _entry("other", 1.0),
    )
    assert _names(table, table.closure({0})) == {"pick 1", "pick 2", "unveil", "veiled reroll", "veiled add"}
    assert _names(table, table.closure({5})) == {"restore", "imprint"}
    assert _names(table, table.closure({7})) == {"other"}  # an offer that needs nothing brings nothing
    # a free pick is ranked with what its placeholder costs: the cheapest source (3), so an adder of 2 comes before it
    table.entries[0].chance = {(MAGIC, A): Fraction(1)}
    table.entries[7].chance = {(MAGIC, A): Fraction(1)}
    table.entries[7].cost = 2.0
    table.priced_needs()
    assert table.entries[0].need == 3.0 and table._best(A, lambda entry: True, 1) == [7]


@dataclasses.dataclass(frozen=True)
class _State:
    name: str
    status: tuple
    rarity: Rarity = MAGIC
    fractured: tuple = ()

    @property
    def flags(self):
        return SimpleNamespace(rarity=self.rarity)


def test_the_dearest_step_is_read_on_the_plan_s_chain_and_what_it_waits_for_and_can_lose_from_the_statuses():
    # a state that holds A rerolls (price 1, 1 in 10 to the goal, else back to itself): 10 uses, 10 Chaos; the start crafts A for 3 first
    passing, empty, done = (Status.PASSING, Status.ABSENT), (Status.ABSENT, Status.ABSENT), (Status.PASSING, Status.PASSING)
    start, half, goal = _State("start", empty), _State("half", passing), _State("goal", done)
    view = {start: Action("craft A", 3.0, (Outcome(half, 1),)), half: Action("reroll", 1.0, (Outcome(goal, 1), Outcome(half, 8), Outcome(start, 1)))}
    plan = SimpleNamespace(start=start, packed=SimpleNamespace(view=view, risk_policy=None, risk_start=None))
    shares = step_shares(plan)
    # from `half`: 1 in 10 to the goal, 1 in 10 back to the start: 5 uses of the reroll a visit of `half`, and `half` is visited twice on average
    assert [label for label, _share, _acts in shares] == ["reroll", "craft A"]
    assert shares[0][1] == pytest.approx(10.0) and shares[1][1] == pytest.approx(6.0)  # the start is visited twice: 2 crafts at 3
    waits, risks, shapes, fractured = read_step(shares[0][2], 2)
    assert waits == {B} and risks == {A} and shapes == {MAGIC} and not fractured


def test_the_narrowers_of_a_drawing_adder_are_read_at_each_state_where_it_acts_from_what_it_waits_for_there():
    """#1423, R04's shape, worked by hand. A (a prefix with the attack tag: R04's extra Arrow) and B (a suffix with no tag: Life, Bow Damage).

    The plan exalts (a drawing addition) at two states: `none`, where it waits for A and B, and `has A`, where A passes and it waits for B
    alone. Read as one step it waits for A and B, so the attack tag is kept; read at `has A` it waits for B alone, so "no attack" is named
    there, and with it the multimod: "no attack" and "craft C" (a crafted mod the plan holds) are two crafted mods held. A state the plan
    never visits, and a step that is no drawing addition (the craft), name nothing.
    """
    table = _table(
        _entry("exalt", 1.0, chance={A: Fraction(1, 4), B: Fraction(1, 4)}),
        _entry("craft C", 2.0, kind="craft", crafted=True),
        _entry("no attack", 5.0, kind="craft", keeps_out=frozenset({"attack"}), crafted=True),
        _entry("more crafted", 7.0, kind="craft", more_crafted=True),
    )
    absent, passing = Status.ABSENT, Status.PASSING
    none, has_a, has_b, goal = _State("none", (absent, absent)), _State("has A", (passing, absent)), _State("has B", (absent, passing)), _State("goal", (passing, passing))
    exalt_none = Action("exalt", 1.0, (Outcome(has_a, 1), Outcome(has_b, 1), Outcome(none, 2)))
    exalt_has_a = Action("exalt", 1.0, (Outcome(goal, 1), Outcome(has_a, 3)))
    craft = Action("craft C", 2.0, (Outcome(none, 1),))
    grower = Grower(table, ())
    one_step = [("exalt", 9.0, [(none, exalt_none, 2.0), (has_a, exalt_has_a, 1.0)]), ("craft C", 2.0, [(none, craft, 1.0)])]
    assert read_step(one_step[0][2], 2)[0] == {A, B}  # the step's own reading keeps the attack tag
    assert _names(table, grower.state_narrowers(one_step, frozenset({0, 1}))) == {"no attack"}
    assert _names(table, table.crafted_roles(frozenset({0, 1, 2}))) == {"more crafted"}
    unvisited = [("exalt", 9.0, [(none, exalt_none, 2.0), (has_a, exalt_has_a, 0.0)])]
    assert grower.state_narrowers(unvisited, frozenset({0, 1})) == set()
    crafts_only = [("craft C", 2.0, [(has_a, Action("craft C", 2.0, (Outcome(goal, 1),)), 1.0)])]
    assert grower.state_narrowers(crafts_only, frozenset({0, 1})) == set()


class _Plan(SimpleNamespace):
    pass


def _g_h_world():
    """The G/H shape (module text): offers 0 the base's tool (in the plan), 1 G (adds A for 1), 2 H (adds B for 1). A plan of the base alone
    costs 10, of the base with G and H together 2, of the base with one of them 10 (beaten)."""
    table = _table(_entry("base", 1.0, kind="reroll", chance={A: Fraction(1, 10), B: Fraction(1, 10)}), _entry("G", 1.0, chance={A: 1}), _entry("H", 1.0, chance={B: 1}))
    start, goal = _State("start", (Status.ABSENT, Status.ABSENT)), _State("goal", (Status.PASSING, Status.PASSING))

    def plan_of(chosen):
        labels = {offer.label for offer in chosen}
        if {"G", "H"} <= labels:
            view = {start: Action("G", 1.0, (Outcome(goal, 1),))}
            return _Plan(mean_remaining=2.0, start=start, packed=SimpleNamespace(view=view, risk_policy=None, risk_start=None), search=SimpleNamespace(lower=2.0, bound_stopped=None))
        view = {start: Action("base", 1.0, (Outcome(goal, 1), Outcome(start, 9)))}  # waits for A and B at once
        return _Plan(mean_remaining=10.0, start=start, packed=SimpleNamespace(view=view, risk_policy=None, risk_start=None), search=SimpleNamespace(lower=10.0, bound_stopped=None))

    offers = tuple(SimpleNamespace(label=entry.label) for entry in table.entries)
    return table, offers, plan_of


def _widen(groups, offers, run, grow, ended=lambda plan: (_rounds.CLOSED, "")):
    return _rounds.widen(
        groups, offers, run, upper_of=lambda plan: plan.mean_remaining, mean_of=lambda plan: plan.mean_remaining, ended=ended,
        left=lambda: None, clock_now=lambda: 0.0, grow=grow,
    )  # fmt: skip


def test_g_and_h_that_pay_only_together_are_named_in_one_round_by_the_step_that_waits_for_both():
    table, offers, plan_of = _g_h_world()
    seen = []

    def run(chosen, call):
        seen.append(tuple(sorted(offer.label for offer in chosen)))
        plan = plan_of(chosen)
        if call.upper is not None and plan.mean_remaining >= call.upper:
            raise _rounds.Beaten(call.upper)
        return plan

    grower = Grower(table, ())
    grower.seed = lambda: ((0,), "the seed")  # the seed holds the base's tool alone
    groups = (_rounds.Group((0,), ("base",), frozenset()), _rounds.Group((1,), ("G",), frozenset({"junk", "g"})), _rounds.Group((2,), ("H",), frozenset({"junk", "h"})))
    widened = _widen(groups, offers, run, grower)
    assert seen[:2] == [("base",), ("G", "H", "base")]  # the second round holds G and H together, named by the one step that waits for A and B
    assert widened.plan.mean_remaining == 2.0
    assert widened.records[1].growth is not None and "base" in widened.records[1].growth
    # main's widening alone sets G aside (beaten with the base) and finds the pair only in its closing round of every offer, which a net that
    # stops a round before it never reaches (#1389)
    main = _widen(groups, offers, run, None)
    assert main.plan.mean_remaining == 2.0 and len(main.records) == 4 and "the last round held them again" in main.records[1].reason


def test_when_the_plan_s_support_holds_every_offer_one_widening_round_of_them_all_closes_the_proof_over_every_method():
    # one offer, the base's tool: its plan costs 10 and uses it, so the support is every offer and no group is left to widen with
    table, _offers, plan_of = _g_h_world()
    table.entries = table.entries[:1]
    offers = (SimpleNamespace(label="base", kind="reroll"),)
    seen = []

    def run(chosen, call):
        seen.append(tuple(offer.label for offer in chosen))
        return plan_of(chosen)

    grower = Grower(table, ())
    grower.seed = lambda: ((0,), "the seed")
    widened = _widen((_rounds.Group((0,), ("reroll",), frozenset()),), offers, run, grower)
    assert seen == [("base",), ("base",)] and widened.plan.mean_remaining == 10.0
    closing = widened.records[-1]
    assert closing.growth is None and closing.kinds == ("reroll",) and closing.closed  # named by the base's own kind, not an invented label
    assert _rounds.all_closed(widened.records)


def test_the_plan_in_hand_never_gets_dearer_and_a_round_whose_build_did_not_complete_ends_the_growth_and_says_so():
    table, offers, plan_of = _g_h_world()
    seen = []

    def run(chosen, call):
        labels = tuple(sorted(offer.label for offer in chosen))
        seen.append(labels)
        if labels == ("G", "H", "base"):  # the grown round: its build stopped at its share, its search walked to a dearer plan
            return _Plan(**{**vars(plan_of(chosen[:1])), "mean_remaining": 30.0, "search": SimpleNamespace(lower=1.0, bound_stopped="the share ended")})
        return plan_of(chosen)

    def ended(plan):
        return (_rounds.STOPPED, "the round's share of the time ended") if plan.search.bound_stopped else (_rounds.CLOSED, "")

    grower = Grower(table, ())
    grower.seed = lambda: ((0,), "the seed")
    groups = (_rounds.Group((0, 1, 2), ("all",), frozenset({"junk"})), _rounds.Group((), ("none",), frozenset({"junk", "x"})))
    widened = _widen(groups, offers, run, grower, ended)
    assert widened.plan.mean_remaining == 10.0  # the dearer plan of the stopped round did not replace the plan in hand
    stopped = widened.records[1]
    assert stopped.status == _rounds.STOPPED and "the growth of the methods ended here" in stopped.reason and "build did not complete" in stopped.reason
    assert seen[2:] and all(len(labels) == 3 for labels in seen[2:])  # the widening came next, with the time left
    assert not _rounds.all_closed(widened.records[:2])  # growth rounds alone prove nothing over every method


def test_through_the_entry_the_belt_begins_with_its_seed_round_and_reaches_the_hand_worked_plan_and_the_widening_closes_every_method(data, target, monkeypatch):  # noqa: F811
    plan = _plan(data, target, monkeypatch, blocking=True)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    records = plan.search.widening
    grown = [record for record in records if record.growth is not None]
    assert grown and grown[0].growth.startswith("the seed")
    assert any(record.growth is None for record in records) and plan.search.exact  # the widening's last round held every method and closed
    assert not math.isnan(plan.mean_remaining)


def test_with_no_plan_in_hand_the_roles_are_read_at_the_start_and_the_support_is_what_the_plan_uses():
    # the seed holds a reroll alone that gives A: A waits (its providers all reroll), and B, whose only provider there is that reroll, is at risk
    table = _table(
        _entry("reroll A", 1.0, kind="reroll", chance={A: Fraction(1, 2)}),
        _entry("add A", 2.0, chance={A: 1}),
        _entry("fracture", 4.0, kind="terminal", fractures=True, draws=False),
        _entry("add B", 2.0, chance={B: 1}),
    )
    grower = Grower(table, ())
    grower.ran((0,), None, False)
    positions, why = grower.next()
    assert _names(table, positions) == {"reroll A", "add A", "add B", "fracture"} and why.startswith("no plan yet")
    grower.ran(positions, None, False)
    assert grower.next() is None  # the same reading names nothing new: the growth ends
    view = {_State("s", (Status.ABSENT, Status.ABSENT)): Action("add A", 2.0, (Outcome(_State("g", (Status.PASSING, Status.PASSING)), 1),))}
    assert _names(table, grower.support(SimpleNamespace(packed=SimpleNamespace(view=view), policy={}))) == {"add A"}


def test_no_plan_words_never_take_a_growth_round_with_no_plan_for_the_proof_over_every_method():
    stopped = _rounds.RoundRecord(("x",), 1, _rounds.STOPPED, "the time limit", None, None, 1.0)
    grown = _rounds.RoundRecord(("a",), 1, _rounds.NONE, "no plan", None, None, 1.0, growth="the seed")
    assert _rounds.no_plan_words((stopped, grown)) is not None  # a growth round held only its own offers: no proof that none reaches the goal
    assert not _rounds.all_closed((dataclasses.replace(grown, status=_rounds.CLOSED),))  # growth rounds alone prove nothing over every method


def test_an_offer_a_finished_growth_round_held_is_not_listed_as_untried_when_a_later_round_held_it_again_and_stopped():
    R = _rounds.RoundRecord
    records = [
        R(("base", "G"), 2, _rounds.CLOSED, "", 10.0, 10.0, 0.0, growth="the seed"),  # finished: base and G were searched
        R(("G", "H", "base"), 3, _rounds.STOPPED, "its share ended", 1.0, None, 0.0, growth="the plan's dearest step"),  # H alone is new
        R(("fossil-set",), 4, _rounds.UNTRIED, "the time was used up", None, None, 0.0),
    ]
    untried = _rounds.rounds_limits(records, True, None)[1]
    assert untried.labels == ("H", "fossil-set")


def test_the_dearest_step_is_read_when_the_weights_are_integers_past_float_s_range():
    # the chain of the test above with its weights on one common denominator of 2**1100 (a kernel held exactly, #957): the same shares
    big = 2**1100
    passing, empty, done = (Status.PASSING, Status.ABSENT), (Status.ABSENT, Status.ABSENT), (Status.PASSING, Status.PASSING)
    start, half, goal = _State("start", empty), _State("half", passing), _State("goal", done)
    view = {start: Action("craft A", 3.0, (Outcome(half, big),)), half: Action("reroll", 1.0, (Outcome(goal, big), Outcome(half, 8 * big), Outcome(start, big)))}
    shares = step_shares(SimpleNamespace(start=start, packed=SimpleNamespace(view=view, risk_policy=None, risk_start=None)))
    assert [label for label, _share, _acts in shares] == ["reroll", "craft A"]
    assert shares[0][1] == pytest.approx(10.0) and shares[1][1] == pytest.approx(6.0)
