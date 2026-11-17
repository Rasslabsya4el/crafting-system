"""An action whose refusal reads, of the junk, only its count per side and the families it names is asked once per refusal class (ticket #1178).

The bound's build asks every offer of a key at every member of it (`PatternBuilder._offers_of_key`), and the members of a key differ in their
junk alone. A bench craft refused at a key (its side full, the crafted mods at their limit, its family in a crafted or fractured mod) was asked
at each member: on R05 at N = 10,000, 789,000 of the 1,000,568 pairs were such refusals. An action that declares `Reads.refusal_by_families`
(a bench craft, Remove Crafted Mods) is now asked once per refusal class of the item it is given (`Abstraction._refusal_class`): the item
without its junk, the junk's count per side, and the junk mods that share a family with the action's.

* The declaration holds on the contract's fixture items: a junk mod outside the action's families swapped for another of its side leaves the
  refusal as it was; a wrong declaration is caught.
* Every pair answers what it answered when each was asked (the refusal, its words, the key), on generated states.
* The model the build makes is the model before the ticket (each pair asked): the same keys, actions, kernels and values, on the hand-worked
  bow world and on a real route up to a net of pairs, and the build shared refusals there (OR-10, OR-12).
"""

import contextlib
import dataclasses

import pytest
from abstraction_support import real_game_data
from contract_support import CONTRACT_DATA, contract_pairs, fixture_items
from test_abstraction_pattern import ACTIONS, BOW, GOAL, LEVEL, STARTS, build, offers_of, pattern_data
from test_abstraction_pattern_real import CASES, E
from test_kernel_projection import answer, generated
from test_pattern_items_kept import PIECES, same_model

from crafting_system.abstraction import Abstraction
from crafting_system.abstraction._pattern import build_pattern_model
from crafting_system.actions import Reads
from crafting_system.actions.bench import BenchCraft
from crafting_system.actions.errors import ActionError
from crafting_system.items import ExplicitMod, Item, ItemError
from crafting_system.items.model import UNVEILED_DOMAIN, VEILED_DOMAIN
from crafting_system.planner._pattern_bound import pattern_lower_bound


@contextlib.contextmanager
def each_pair_asked(ab: Abstraction):
    """The code before #1178 on `ab`: every pair asks the action whether it is refused."""
    ab.share_refusals = False
    try:
        yield ab
    finally:
        ab.share_refusals = True


def _refusal(action, data, item) -> str | None:
    """The kind of the game's refusal of `action` on `item`, or None when it is taken."""
    try:
        action.outcomes_under(data, item)
    except ActionError as refusal:
        return type(refusal).__name__
    return None


def _junk(data, entry: ExplicitMod) -> bool:
    return not (entry.fractured or entry.crafted) and data.mods[entry.mod_id].domain not in (VEILED_DOMAIN, UNVEILED_DOMAIN)


def swapped_refusals(action, item: Item, data, per_mod: int = 6) -> tuple[list[tuple[str, str, str | None, str | None]], int]:
    """For `action` declaring `Reads.refusal_by_families`: each junk mod of `item` outside the action's families swapped for up to `per_mod`
    ordinary mods of its side outside them, where the refusal changed: (the mod, its swap, the refusal before, after), empty when it holds;
    and how many swaps were tried."""
    reads = action.reads(data)
    families = reads.families
    before = _refusal(action, data, item)
    changed = []
    tried_all = 0
    for index, entry in enumerate(item.mods):
        mod = data.mods[entry.mod_id]
        if not _junk(data, entry) or not families.isdisjoint(mod.families):
            continue
        tried = 0
        for other in data.mods.values():
            if tried >= per_mod:
                break
            if other.id == mod.id or other.generation_type != mod.generation_type or other.domain != mod.domain or not families.isdisjoint(other.families):
                continue
            low = tuple(min(stat.min, stat.max) for stat in other.stats)
            mods = (*item.mods[:index], ExplicitMod(other.id, low), *item.mods[index + 1 :])
            try:
                swapped = dataclasses.replace(item, mods=mods)
                swapped.validate(data)
            except (ItemError, ValueError):
                continue
            tried += 1
            tried_all += 1
            after = _refusal(action, data, swapped)
            if after != before:
                changed.append((mod.id, other.id, before, after))
    return changed, tried_all


DECLARING = [
    (kind, action, name)
    for kind, action, name in contract_pairs()
    if action.reads(CONTRACT_DATA).refusal_by_families
]


def test_the_bench_declares_its_refusal_by_families():
    kinds = {type(action).__name__ for _, action, _ in DECLARING}
    assert kinds == {"BenchCraft", "RemoveCraftedMods"}
    assert all(action.reads(CONTRACT_DATA).families is not None for _, action, _ in DECLARING)


@pytest.mark.parametrize(("kind", "action", "name"), DECLARING, ids=[f"{kind}-{name}-{i}" for i, (kind, _, name) in enumerate(DECLARING)])
def test_a_declared_refusal_reads_no_other_family_of_the_junk(kind, action, name):
    item = fixture_items()[name]
    changed, tried = swapped_refusals(action, item, CONTRACT_DATA)
    assert changed == []
    SWAPS[name] = SWAPS.get(name, 0) + tried


SWAPS: dict[str, int] = {}


def test_the_swaps_were_tried_on_items_that_hold_junk():
    for kind, action, name in DECLARING:
        if name not in SWAPS:
            SWAPS[name] = swapped_refusals(action, fixture_items()[name], CONTRACT_DATA)[1]
    assert SWAPS.get("rare_junk", 0) > 0 and SWAPS.get("rare_four", 0) > 0


def test_a_wrong_declaration_is_caught():
    item = fixture_items()["rare_junk"]
    junk = next(entry for entry in item.mods if _junk(CONTRACT_DATA, entry))

    @dataclasses.dataclass(frozen=True)
    class PicksyCraft(BenchCraft):
        """A craft refused on an item that holds one given junk mod, which its families do not name."""

        def outcomes(self, data, item):
            from crafting_system.actions.errors import NotApplicableError

            if any(entry.mod_id == junk.mod_id for entry in item.mods):
                raise NotApplicableError("a mod the declaration does not name")
            return super().outcomes(data, item)

    craft = next(action for _, action, name in DECLARING if isinstance(action, BenchCraft) and name == "rare_junk")
    wrong = PicksyCraft(craft.mod_id)
    assert isinstance(wrong.reads(CONTRACT_DATA), Reads) and wrong.reads(CONTRACT_DATA).refusal_by_families
    assert swapped_refusals(wrong, item, CONTRACT_DATA)[0] != []


@pytest.mark.parametrize(("name", "seed"), [("tiny", 1), ("bow", 2), ("bow", 3)])
def test_every_pair_answers_what_it_answered_when_each_was_asked(name, seed):
    data, ab, states = generated(name, seed, count=30, steps=150)
    ab.release_prepared()
    ab.refusals_shared = 0  # the walk that made the states shared some
    readers = [action for action in ab.enabled if ab._kinds.reads(action).refusal_by_families]
    assert readers
    before = {}
    with each_pair_asked(ab):
        for action in readers:
            for state in states:
                before[(state, action)] = answer(lambda: ab.kernel_key(state, action))
        ab.release_prepared()
    assert ab.refusals_shared == 0
    for action in readers:  # the build's order: offer after offer, at every state
        for state in states:
            assert answer(lambda: ab.kernel_key(state, action)) == before[(state, action)], (state, action)
    assert ab.refusals_shared > 0


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
def test_the_build_of_the_hand_worked_world_is_the_build_before(tags):
    data = pattern_data()

    def made(before: bool):
        ab = Abstraction(data, GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
        start = ab.compress(build(data, BOW, STARTS[0]))
        with each_pair_asked(ab) if before else contextlib.nullcontext():
            return build_pattern_model(ab, start, offers_of(), tags=tags), ab.refusals_shared

    (old, none), (new, shared) = made(True), made(False)
    same_model(old, new)
    assert new.stats.pairs == old.stats.pairs > 100 and new.stats.refused_pairs == old.stats.refused_pairs
    assert none == 0 and shared > 0


def test_the_alike_twin_asks_as_its_abstraction_asks():
    """The twin the build lumps with (`alike_twin`) keeps its abstraction's choice: a reference build asks every pair in the twin too."""
    ab = Abstraction(pattern_data(), GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
    assert ab.alike_twin().share_refusals
    with each_pair_asked(ab):
        assert not ab.alike_twin().share_refusals


@pytest.mark.parametrize(("route", "tags"), [case for case in CASES if case.id == "r13-auto"])
def test_the_bound_of_a_real_route_is_the_bound_before(route, tags):
    real_game_data()  # skips without the dump

    def made(before: bool):
        _, _, _, abstraction, start, priced, _ = E.build_model(route, "twins", True, False)
        with each_pair_asked(abstraction) if before else contextlib.nullcontext():
            return pattern_lower_bound(abstraction, start, priced, tags=tags, pieces=PIECES), abstraction.refusals_shared

    (old, none), (new, shared) = made(True), made(False)
    same_model(old.model, new.model)
    assert list(new.value) == list(old.value)
    assert new.start_value == old.start_value
    assert new.model.stats.pairs > 1_000
    assert none == 0 and shared > 0
