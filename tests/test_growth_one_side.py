"""The one-side role of the growth and its group (#1542, hypothesis H40 of #1434; `planner/_growth.py`, module text "the one-side group").

On R24 the planner's own model holds a plan of 1,710.64 c after the start that main's growth never reached (2,134.44 c): its methods that
make the difference (a bench craft that fills the prefixes, the beast side swap, the Eldritch Orb of Annulment and the Ember that sets the
side it removes from) were named by no role, since none read an offer that acts on one side only. Given main's plan group with those four
as one search, the model hands over 1,710.64 c (312,146 keys built in 568 s on 6 workers; `.claude/scratch/t1542/cheap/A.log`).

* The role, read at the states where a step acts: what it names when the step waits on one side and the other has room, or is full
  of a wanted mod; nothing when it waits on both sides.
* The group: in place of the first re-read of a step, once per plan; never on a first read.
"""

import dataclasses
from fractions import Fraction
from types import SimpleNamespace

from test_growth import RARE, A, B, _entry, _names, _Plan, _table

from crafting_system.abstraction import Status
from crafting_system.items import Side
from crafting_system.planner._growth import OWN_POOL, Grower, OfferTable
from crafting_system.solver import Action, Outcome

P, N = Status.PASSING, Status.ABSENT


@dataclasses.dataclass(frozen=True)
class _Held:
    """A state with the sides of its slots (`CompressedState.slots`, `fractured`)."""

    name: str
    status: tuple
    sides: tuple = ()
    rarity: object = RARE
    fractured: tuple = ()

    @property
    def flags(self):
        return SimpleNamespace(rarity=self.rarity)

    @property
    def slots(self):
        return tuple(SimpleNamespace(side=Side(side)) for side in self.sides)


def _one_side_table() -> OfferTable:
    """A (a prefix) and B (a suffix), two slots a side. Offers: 0 "exalt" (adds B), 1 a prefix filler, 2 a suffix filler, 3 a beast swap
    that removes a suffix and draws a prefix (held back for the later group), 4 a swap the other way, 5 an Eldritch annulment that removes
    a suffix after an Ichor and a prefix after an Ember, 6 the Ember, 7 the Ichor, 8 a dearer prefix filler, 9 another adder of B (the usual roles name it)."""
    table = _table(
        _entry("exalt", 10.0, chance={B: Fraction(1, 10)}),
        _entry("fill prefix", 0.05, kind="craft", crafted=True, fills=frozenset({"prefix"})),
        _entry("fill suffix", 0.04, kind="craft", crafted=True, fills=frozenset({"suffix"})),
        _entry("swap remove suffix", 5.0, clears=frozenset({"suffix"}), fans=OWN_POOL),
        _entry("swap remove prefix", 5.0, clears=frozenset({"prefix"}), fans=OWN_POOL),
        _entry("eldritch annul", 44.0, kind="terminal", draws=False, clears=frozenset({"prefix", "suffix"}), sets={"prefix": (6,), "suffix": (7,)}),
        _entry("ember", 0.25, kind="implicit", draws=False),
        _entry("ichor", 0.3, kind="implicit", draws=False),
        _entry("fill prefix dear", 1.0, kind="craft", crafted=True, fills=frozenset({"prefix"})),
        _entry("add B", 20.0, chance={B: Fraction(1, 2)}),
    )
    table._sides_read = True  # the sides are declared above, not read on probe items
    table.capacity_of = lambda rarity, side: 2
    table._item_ids = frozenset({"A1", "B1"})
    table.held_back = frozenset({3, 4})  # the swaps wait for the later group, yet the one-side role names them
    return table


def _acts(*states, label="exalt"):
    """The step "exalt" acting at `states` (each its own (state, action, visits)), each use making B pass."""
    return [(state, Action(label, 10.0, (Outcome(_with_b(state), 1), Outcome(state, 9))), 1.0) for state in states]


def _with_b(state):
    return dataclasses.replace(state, name=state.name + "+B", status=(state.status[0], P))


def test_a_step_that_waits_on_one_side_with_room_on_the_other_names_its_cheapest_filler_and_the_swap_that_clears_the_waited_side():
    table = _one_side_table()
    room = _Held("room", (N, N), sides=("prefix",))  # one prefix of two: the prefixes have room
    assert _names(table, table.side_roles(_acts(room))) == {"fill prefix", "swap remove suffix"}


def test_with_the_other_side_full_of_a_wanted_mod_it_names_the_removal_of_the_waited_side_alone_with_the_one_offer_that_sets_it():
    table = _one_side_table()
    full = _Held("full", (P, N), sides=("prefix", "prefix"))  # the prefixes are full and hold A
    assert _names(table, table.side_roles(_acts(full))) == {"eldritch annul", "ichor"}
    junk = _Held("junk", (N, N), sides=("prefix", "prefix"))  # full of junk: nothing to keep there, nothing named
    assert table.side_roles(_acts(junk)) == set()


def test_a_step_that_waits_on_both_sides_or_on_none_names_nothing():
    table = _one_side_table()
    goal = _Held("goal", (P, P))
    start = _Held("start", (N, N), sides=("prefix",))
    both = [(start, Action("exalt", 10.0, (Outcome(goal, 1), Outcome(start, 9))), 1.0)]
    assert table.side_roles(both) == set()
    held = _Held("held", (P, P), sides=("prefix",))
    assert table.side_roles([(held, Action("exalt", 10.0, (Outcome(held, 1),)), 1.0)]) == set()


def _plan_of(*states):
    """A plan whose one step, "exalt", acts at `states` and makes B pass 1 in 10."""
    view = {state: Action("exalt", 10.0, (Outcome(_with_b(state), 1), Outcome(state, 9))) for state in states}
    return _Plan(mean_remaining=100.0, start=states[0], policy=view, packed=SimpleNamespace(view=view, risk_policy=None, risk_start=None))


def test_the_one_side_group_comes_in_place_of_the_first_re_read_of_a_step_once_per_plan_never_on_a_first_read():
    table = _one_side_table()
    grower = Grower(table, ())
    room = _Held("room", (N, N), sides=("prefix",))
    first = _plan_of(room)
    grower.ran((0,), first, True)
    read = grower._next()  # the first read of "exalt": the usual roles, no one-side offer
    assert read is not None and "one-side" not in read[1]
    assert not _names(table, read[0]) & {"fill prefix", "swap remove suffix"}
    grower.ran(read[0], _plan_of(room), True)  # a newer plan: "exalt" is read again
    again = grower._next()
    assert again is not None and "one-side group" in again[1]
    assert {"exalt", "fill prefix", "swap remove suffix"} <= _names(table, again[0])
    grower.ran(again[0], grower.plan, False)
    assert grower.one_side_for is grower.plan
    later = grower._next()  # the same plan: the group is not named twice
    assert later is None or "one-side" not in later[1]
