"""The bound's model holds its rows and its offers held at some keys in arrays, and the search reads them a key at a time (ticket #1366, OR-12,
OR-40). The figures behind it are in `abstraction/_packed_rows.py`: on R04 the rows, the holdings and the search's two dicts a key took 4.1 GB,
about 290 bytes an action, and the first plan's walk was cut by the 12 GB net with them held.

* `Rows` and `Held` answer what the lists and sets answered, on hand-worked rows and holdings; a copy keeps what it said when the original goes on.
* The search's backups read off the packed rows (`CraftingProblem.lowest`) are, key by key and to the last bit, the dicts it held before, on the
  world of `test_cli_envelope_build` (offers held at some keys only, a stopped build's closed model).
* Through the planner's entry, on the hand-worked belt of `test_planner_blocking_crafts` (153.33 c with the Exalted Orb alone, 133 c with
  the filler first: its module text has the figures), with the memory read as a figure the test controls: 100 MB, plus 1 MB for each Python
  object (a number apart) the search's problem holds beside the abstraction, the offers and the model's keys, and that the model holds for
  its rows and holdings.
  Under a net of 100 MB plus one MB for each key and action of the model, the plan is the hand-worked 133; with the search's dicts a key
  and the model's rows held as before #1366 (a dict a key, a float an action, a list a key, a tuple an action), every round stops on that
  net with no plan.
"""

import dataclasses
import gc
import math
import weakref

import numpy as np
import pytest
from test_cli_envelope_build import START_ITEM, abstraction, assert_lower_bound, counting_stop, floors_on, world  # noqa: F401  (fixtures)
from test_planner_blocking_crafts import C, E, S, _prices, data, target  # noqa: F401  (the fixtures)

from crafting_system import budget, parallel
from crafting_system.abstraction._packed_rows import Held, Rows
from crafting_system.abstraction._pattern import CHOICE
from crafting_system.budget import Budget
from crafting_system.planner import PlanSettings, _offers, _pattern_bound, plan_target
from crafting_system.planner._envelope_plan import CraftingProblem
from crafting_system.planner._plan import PlanError
from crafting_system.planner._offer_floor import OTHER, UNOPENED
from crafting_system.planner._pattern_bound import _doubled, pattern_lower_bound


def test_rows_answer_what_the_lists_answered():
    lists = [[(0, 1), (2, 3)], [], [(CHOICE, 0)], [(1, 4), (1, 5), (0, 2)]]
    rows = Rows.of(lists)
    assert len(rows) == 4 and rows.entries == 6 and [rows.size(k) for k in range(4)] == [2, 0, 1, 3]
    assert rows[0] == [(0, 1), (2, 3)] and rows[-1] == [(1, 4), (1, 5), (0, 2)] and list(rows) == lists and rows == lists
    assert rows.ptr.tolist() == [0, 2, 2, 3, 6] and rows.offer.tolist() == [0, 2, CHOICE, 1, 1, 0] and rows.kernel.tolist() == [1, 3, 0, 4, 5, 2]
    assert rows.owner().tolist() == [0, 0, 2, 3, 3, 3]
    assert rows == Rows.of(lists) and rows != Rows.of(lists[:3])
    with pytest.raises(IndexError):
        rows[4]
    assert rows.offer.nbytes + rows.kernel.nbytes == 8 * rows.entries  # two 32-bit integers an action


def test_held_offers_answer_what_the_sets_answered_and_a_copy_keeps_what_it_said():
    held = Held()
    assert held.add(5, [7, 3, 7]).tolist() == [3, 7]  # the keys it was not held at, sorted, once
    assert held.add(5, [3, 9]).tolist() == [9]
    assert held.add(2, []).tolist() == [] and 2 in held and len(held) == 2  # an offer held at no key yet is held at some keys only
    before = held.copy()
    held.add(2, [9, 1])
    assert held[5].tolist() == [3, 7, 9] and held[2].tolist() == [1, 9] and before[2].tolist() == []
    assert held.holds(9, 5) and not held.holds(4, 5) and not held.holds(9, 8)
    assert held.offers_at(9).tolist() == [5, 2] and held.offers_at(4).tolist() == [] and held.offers_at(100).tolist() == []
    assert held.counts().tolist() == [0, 1, 0, 1, 0, 0, 0, 1, 0, 2] and held.pairs == 5
    assert held == {5: {3, 7, 9}, 2: {1, 9}} and Held.of({5: {3, 7, 9}, 2: {1, 9}}) == held
    renamed = held.renamed([10, 11, 12, 13, 14, 15])
    assert renamed[15] is held[5] and renamed[12] is held[2]  # the same arrays, under the offers' positions
    with pytest.raises(ValueError):
        held[5][0] = 1  # read-only: a copy shares them


def _old_lowest(problem: CraftingProblem, bound, expected: list[float], finite: bool) -> list[dict[int, float]]:
    """The dicts a key the search held before #1366 (`lowest`, `closed_lowest`), made as it made them, in Python floats."""
    out = []
    for row in bound.model.actions:
        found: dict[int, float] = {}
        for index, kernel in row:
            if index == CHOICE:
                continue
            position = bound.positions[index]
            q = problem.offers[position].cost + expected[kernel]
            if (not finite or math.isfinite(q)) and (position not in found or q < found[position]):
                found[position] = q
        out.append(found)
    return out


def test_a_key_in_two_classes_is_given_an_offer_once_as_one_pair_at_a_time():
    # `_doubled` makes its pairs in arrays (#1366); one pair at a time, a key found in two classes was given the next least floors in each, and
    # never an offer twice. Key 0 holds 2 offers of some keys only (8, 9) and is given 1 (offer 0): it is given 1 more in each class, 1 then 2.
    class Floors:
        def lower(self, p, klass):
            return 1.0 + p

    needs = {0: np.array([0], dtype=np.int64)}
    found = [(1.0, 0)]
    keys_of = {OTHER: np.array([0], dtype=np.int64), UNOPENED: np.array([0], dtype=np.int64)}
    added = _doubled(needs, {8: {0}, 9: {0}}, keys_of, [0, 1, 2, 3], Floors(), found)
    assert added == 2
    assert {p: np.asarray(keys).tolist() for p, keys in needs.items()} == {0: [0], 1: [0], 2: [0]}
    assert sorted(found) == [(1.0, 0), (2.0, 1), (3.0, 2)]


def test_a_grown_model_whose_solve_would_pass_the_memory_net_is_not_solved_and_the_round_before_stands(world, floors_on, monkeypatch):  # noqa: F811
    # The solve cannot be cut: its memory (`SOLVE_BYTES` an action) is asked before it (#1366: R04's model 29, 108 million actions, was to take
    # 11 GB more on 10.6 GB and the system killed the run at 16 GB). Held 100 MB of a 1,000 MB net, and an action taken as 1 GB: the first model
    # is solved whatever it takes (nothing stands before it), the grown one is not, and the bound is the first round's, a lower bound.
    ab, start, offers, _, exact, _ = world
    monkeypatch.setattr(parallel, "held_mb", lambda under=None, paced=True: 100.0)
    monkeypatch.setattr(_pattern_bound, "SOLVE_BYTES", 1 << 30)
    said = []
    fresh = abstraction()
    with parallel.memory_net(1000.0):
        bound = pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM, progress=said.append)
    assert bound.phase == "growth" and bound.rounds == 1 and bound.positions == (0, 6)
    assert "past the limit of 1,000 MB" in bound.stopped and "the solve of" in bound.stopped
    assert sum("solving the count" in line for line in said) == 1
    assert any("model 2: the net was reached before the solve" in line for line in said)
    assert_lower_bound(bound, ab, exact)
    with parallel.memory_net(1e9):  # with room, the model grows as before
        assert pattern_lower_bound(abstraction(), fresh.compress(START_ITEM), offers, item=START_ITEM).rounds > 1


def test_the_backups_read_off_the_packed_rows_are_the_dicts_the_search_held(world, floors_on):  # noqa: F811
    _ab, _start, offers, *_ = world
    fresh = abstraction()
    begin = fresh.compress(START_ITEM)
    grown = pattern_lower_bound(fresh, begin, offers, item=START_ITEM)  # offers join, some held at some keys only (#1325)
    stopped = pattern_lower_bound(abstraction(), begin, offers, stop=counting_stop(12))  # a stopped build: the closed model's order (#948)
    assert len(grown.narrow) > 0 and not stopped.complete
    for bound, closed in ((grown, False), (stopped, True)):
        problem = CraftingProblem(fresh, begin, offers, bound)
        assert isinstance(bound.model.actions, Rows) and isinstance(bound.narrow, Held)
        pairs = [(problem.expected, False)] + ([(problem.closed_expected, True)] if closed else [])
        for expected, finite in pairs:
            old = _old_lowest(problem, bound, expected.tolist(), finite)
            assert [problem.lowest(k, expected, finite) for k in range(len(old))] == old  # equal dicts of equal floats, to the last bit
        for position in bound.narrow:
            for k in range(len(bound.model.keys)):
                assert bound.holds(k, position) == (k in set(bound.narrow[position].tolist()))


NOT_PER_ACTION = {"ab", "start", "offers", "pattern", "index", "floors", "goal", "distance", "first_choice", "holds", "_last_key"}  # what the search holds whatever the model's rows


def _objects(roots) -> int:
    """The Python objects reachable from `roots`, a numpy array counted as one, not below an abstraction, an offer, a key or a state."""
    seen: set[int] = set()
    stack = list(roots)
    count = 0
    while stack:
        o = stack.pop()
        if id(o) in seen or o is None or isinstance(o, (bool, type)) or (type(o) is int and -5 <= o <= 256):
            continue
        seen.add(id(o))
        name = type(o).__name__
        if name in ("Abstraction", "Pattern", "PricedOffer", "OfferFloors", "CompressedState", "PatternKey", "function", "method", "module"):
            continue
        count += 1
        if not isinstance(o, np.ndarray):
            stack.extend(gc.get_referents(o))
    return count


@pytest.fixture
def figure(monkeypatch):
    """The memory as this test's figure: 100 MB, plus 1 MB for each Python object the live searches' problems hold beside the abstraction, the
    offers and the keys, and their bounds' models hold for their rows and holdings. Returns the problems made (weak references)."""
    made: list[tuple[weakref.ref, weakref.ref, int]] = []  # (the problem, its bound's model, its keys and actions)
    real = CraftingProblem.__init__

    def init(self, abstraction, start, offers, bound, *args, **kwargs):
        real(self, abstraction, start, offers, bound, *args, **kwargs)
        made.append((weakref.ref(self), weakref.ref(bound.model), len(bound.model.keys) + bound.model.actions.entries))

    def held() -> float:
        roots = []
        for problem, model in ((p(), m()) for p, m, _size in made):
            if problem is not None:
                roots.extend(v for name, v in vars(problem).items() if name not in NOT_PER_ACTION and not isinstance(v, (int, float)))  # a number is the problem's, not a key's
            if model is not None:
                roots.extend((model.actions, model.narrow))
        return 100.0 + _objects(roots)

    monkeypatch.setattr(CraftingProblem, "__init__", init)
    monkeypatch.setattr(parallel, "held_mb", lambda under=None, paced=True: held())
    monkeypatch.setattr(budget, "process_mb", lambda pid=None: held())
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    return made


def _belt(data, target, net_mb):  # noqa: F811
    given = dataclasses.replace(Budget.in_states(10_000), memory_mb=net_mb)
    return plan_target(data, target, _prices(), PlanSettings(recipe_starts=False, start_price=S, solver="envelope", budget=given))


def test_the_search_holds_no_python_object_a_key_for_the_bounds_rows(data, target, figure, monkeypatch):  # noqa: F811
    free = _belt(data, target, None)  # no net: the hand-worked plan, and the size of its model
    assert free.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    size = max(size for _p, _m, size in figure)  # the keys and the actions of the largest model a search was given (#1276: the seed's is 13)
    assert size >= 30
    net = 100.0 + size  # one Python object a key and an action of the model: more than the searches hold beside their arrays, less than a dict a key and a float an action
    figure.clear()
    plan = _belt(data, target, net)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    assert not any("the limit is" in (round_.reason or "") for round_ in plan.search.widening)

    real = CraftingProblem.__init__

    def as_before(self, *args, **kwargs):  # the search's dicts a key and the model's rows as lists of tuples, held as before #1366
        real(self, *args, **kwargs)
        self.held_before = ([self.lowest(k, self.expected) for k in range(len(self.tip))], list(self.rows))

    monkeypatch.setattr(CraftingProblem, "__init__", as_before)
    figure.clear()
    with pytest.raises(PlanError, match=f"the limit is {net:.0f} MB"):
        _belt(data, target, net)  # each round's search stops on the net with no plan


def test_a_search_keeps_the_label_distributions_read_lately_and_plans_the_same(data, target, monkeypatch):  # noqa: F811
    # The label distributions' memos (`Abstraction._cache`, `_expanded`) keep the distributions read lately, a share of the net (#1366): with a
    # generation of one outcome, every distribution is let go at once and made again when it is asked again, and the plan is the hand-worked 133.
    from crafting_system.abstraction import _kernel
    from crafting_system.abstraction._recent import Recent

    held = []
    made: dict = {}  # a key -> the distributions written for it (held, so that no two are the same object by a reused id)
    real = Recent.__setitem__

    def write(self, key, value):
        real(self, key, value)
        if self.size is _kernel._distributions_kept:  # a memo of label distributions
            held.append(len(self.young) + len(self.old))
            made.setdefault((id(self), key), {})[id(value)] = value

    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    whole = _belt(data, target, None)
    monkeypatch.setattr(_kernel, "DISTRIBUTIONS_KEPT", 1)
    monkeypatch.setattr(Recent, "__setitem__", write)
    small = _belt(data, target, None)
    assert small.mean_remaining == whole.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    assert held and max(held) <= 2  # the young generation and the old one, one distribution each
    assert any(len(values) > 1 for values in made.values())  # a distribution let go was asked again and made again
