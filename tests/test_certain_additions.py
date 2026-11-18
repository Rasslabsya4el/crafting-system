"""A certain addition is asked at the members of a key until one takes it (ticket #1193).

The bound's build asks every offer of a key at every member of it (`PatternBuilder._offers_of_key`). A bench craft taken at a member built the
item, its outcome and its successor there, a distinct kernel at nearly every member (each member keeps its own slots): R04's round of bench
crafts made 1.17 million such pairs and stopped at its quarter of the run. An action declared `Adds.only_named` (a bench craft, an aspect
beast) has one outcome, the item with its named mods added, so at every member of the key that takes it the successor key is the same (the
module text of `_pattern.py`, "The certain additions"): the build now leaves the members after the first that takes it out.

* The declaration holds on the contract's fixture items (`contract_support.check_item_state_declarations`), and a wrong one is caught.
* The model the build makes is the model before the ticket (every member asked): the same keys, actions, kernels and values, and the same
  count of pairs, on the hand-worked bow world and on a real route up to a net of pairs (OR-10, OR-12).
"""

import contextlib
import dataclasses

import pytest
from abstraction_support import real_game_data
from contract_support import CONTRACT_DATA, check_item_state_declarations, contract_pairs, finished, fixture_items
from test_abstraction_pattern import ACTIONS, BOW, GOAL, LEVEL, STARTS, build, offers_of, pattern_data
from test_abstraction_pattern_real import CASES, E
from test_pattern_items_kept import PIECES, same_model

from crafting_system.abstraction import Abstraction, _pattern
from crafting_system.abstraction._pattern import PatternOffer, build_pattern_model
from crafting_system.actions import Adds
from crafting_system.actions.bench import BenchCraft
from crafting_system.actions.errors import ActionError
from crafting_system.planner._pattern_bound import pattern_lower_bound


@contextlib.contextmanager
def every_member_asked():
    """The build before #1193: a certain addition is asked at every member of a key."""
    _pattern.SHARE_ADDITIONS = False
    try:
        yield
    finally:
        _pattern.SHARE_ADDITIONS = True


DECLARING = [(kind, action, name) for kind, action, name in contract_pairs() if action.adds(CONTRACT_DATA).only_named]


def test_the_bench_crafts_and_the_aspects_are_the_certain_additions():
    assert {type(action).__name__ for _, action, _ in DECLARING} == {"BenchCraft", "AspectBeast"}
    assert not any(type(action).__name__ == "RemoveCraftedMods" for _, action, _ in DECLARING)


def test_a_wrong_declaration_is_caught():
    item = fixture_items()["rare_junk"]

    @dataclasses.dataclass(frozen=True)
    class GreedyCraft(BenchCraft):
        """A craft that also takes the first ordinary mod off, while it declares a certain addition."""

        def outcomes(self, data, item):
            outcomes = super().outcomes(data, item)
            first = next(entry for entry in item.mods if not (entry.crafted or entry.fractured))
            return dataclasses.replace(outcomes, retained=item.remove_mod(data, first.mod_id))

    craft = next(
        action for _, action, name in DECLARING if isinstance(action, BenchCraft) and name == "rare_junk" and _taken(action, item)
    )
    wrong = GreedyCraft(craft.mod_id)
    assert wrong.adds(CONTRACT_DATA).only_named
    reads, adds = wrong.reads(CONTRACT_DATA), wrong.adds(CONTRACT_DATA, item)
    items = finished(wrong.outcomes(CONTRACT_DATA, item))
    with pytest.raises(AssertionError, match="certain addition"):
        check_item_state_declarations(wrong, reads, adds, items, item, CONTRACT_DATA)
    check_item_state_declarations(craft, reads, adds, finished(craft.outcomes(CONTRACT_DATA, item)), item, CONTRACT_DATA)


def _taken(action, item) -> bool:
    try:
        action.outcomes(CONTRACT_DATA, item)
    except ActionError:
        return False
    return True


def test_a_removal_or_a_draw_is_no_certain_addition():
    assert not Adds.removal().only_named
    assert not Adds(named=frozenset({"x"})).only_named  # it draws besides (an essence)
    assert not Adds(named=frozenset({"x"}), draws=False, implicits=True).only_named
    assert Adds(named=frozenset({"x"}), crafted=True, draws=False).only_named


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
def test_the_build_of_the_hand_worked_world_is_the_build_before(tags):
    data = pattern_data()
    offers = [*offers_of(), PatternOffer("bench-lock", ACTIONS["bench-lock"], 1.0), PatternOffer("bench-craft", ACTIONS["bench-craft"], 2.0)]

    def made(before: bool):
        ab = Abstraction(data, GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
        start = ab.compress(build(data, BOW, STARTS[0]))
        with every_member_asked() if before else contextlib.nullcontext():
            return build_pattern_model(ab, start, offers, tags=tags)

    old, new = made(True), made(False)
    same_model(old, new)
    assert new.stats.pairs == old.stats.pairs > 100
    assert old.stats.shared_pairs == 0 and new.stats.shared_pairs > 0


@pytest.mark.parametrize(("route", "tags"), [case for case in CASES if case.id == "r13-auto"])
def test_the_bound_of_a_real_route_is_the_bound_before(route, tags):
    real_game_data()  # skips without the dump

    def made(before: bool):
        _, _, _, abstraction, start, priced, _ = E.build_model(route, "twins", True, False)
        with every_member_asked() if before else contextlib.nullcontext():
            return pattern_lower_bound(abstraction, start, priced, tags=tags, pieces=PIECES)

    old, new = made(True), made(False)
    same_model(old.model, new.model)
    assert list(new.value) == list(old.value)
    assert new.start_value == old.start_value
    assert new.model.stats.pairs == old.model.stats.pairs > 1_000
    assert new.model.stats.shared_pairs > 0
    assert new.pieces == old.pieces and str(new.model.stopped) == str(old.model.stopped)  # the counted net (`PIECES`) stops where it did
