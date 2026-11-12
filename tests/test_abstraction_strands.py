"""The Memory Strand count in the compressed state (ticket #277, B5-4; ADR-0040, ADR-0042, ADR-0019 layer 1).

The kernel of a cutting, spending action on a stranded item equals the brute force: every finished item of the draw from the cut pool
(`abstraction_oracle.finished_items`, `abstraction_adds_oracle.drawn_items`), each paired with every count the spend leaves, compressed
and added up. The spend is written again here as plain numbers from ADR-0041 (a uniform whole number on 0 to the ceiling, the count
`max(0, s - x)`), not read from `actions`; the cut pool is `build_pool(cut=...)`, whose cut is checked against the published numbers by
ticket #275.

The small pool has one tier table that a cut splits three ways: Lightning Resistance has three tiers (required levels 1, 13, 25), so it
keeps three at 0 strands, two from 1 to 21 strands and one from 22 (`K = floor(400 / (5 s + 295)) + 1`); every other table of two tiers
keeps one from 1 strand. The counts below cross that boundary (21 and 22).
"""

from fractions import Fraction

import pytest
from abstraction_adds_oracle import drawn_items
from abstraction_oracle import assert_same_distribution, compressed_distribution, finished_items
from abstraction_pool import AMULET, GEM, LEVEL, LIFE_1, RESIST_1, SMALL, roll, small_item
from abstraction_support import GOALS

from crafting_system.abstraction import Abstraction
from crafting_system.actions import AlterationOrb, ChaosOrb, ExaltedOrb, build_pool
from crafting_system.actions.cut import PLAN_READING, Cut, WeightReading
from crafting_system.items import Item, Rarity

COUNTS = (0, 3, 21, 22, 60)
ALTERATION, CHAOS, EXALTED = AlterationOrb(), ChaosOrb(), ExaltedOrb()
# ADR-0041 and its amendment, as plain numbers: Alteration 0 to 8, Chaos 0 to 50, Exalted by the explicit mods before the craft.
CEILING = {"alteration": lambda mods: 8, "chaos": lambda mods: 50, "exalted": lambda mods: (16, 22, 26, 32, 34, 38)[min(mods, 5)]}


def _spent(finished: list[tuple[Item, Fraction]], strands: int, ceiling: int) -> list[tuple[Item, Fraction]]:
    """Each finished item with every count the spend can leave: `max(0, strands - x)`, `x` uniform on 0 to `ceiling`."""
    share = Fraction(1, ceiling + 1)
    return [(item.changed(SMALL, memory_strands=max(0, strands - spent)), chance * share) for item, chance in finished for spent in range(ceiling + 1)]


def _pool(retained: Item, strands: int, reading: WeightReading = PLAN_READING):
    """The pool of a draw on `retained` at `strands`: the ordinary pool at 0, else the cut pool."""
    return None if strands == 0 else build_pool(SMALL, retained, cut=Cut(strands, reading=reading))


def _chaos_oracle(start: Item, reading: WeightReading = PLAN_READING) -> list[tuple[Item, Fraction]]:
    retained = start.changed(SMALL, rarity=Rarity.RARE, mods=start.fractured_mods)
    finished = finished_items(SMALL, start, pool=_pool(retained, start.memory_strands, reading))
    return _spent(finished, start.memory_strands, CEILING["chaos"](len(start.mods)))


def _alteration_oracle(start: Item) -> list[tuple[Item, Fraction]]:
    retained = start.changed(SMALL, mods=start.fractured_mods)
    half = Fraction(1, 2)
    finished = drawn_items(SMALL, retained, {1: half, 2: half}, _pool(retained, start.memory_strands))
    return _spent(finished, start.memory_strands, CEILING["alteration"](len(start.mods)))


def _exalted_oracle(start: Item) -> list[tuple[Item, Fraction]]:
    finished = drawn_items(SMALL, start, {len(start.mods) + 1: Fraction(1)}, _pool(start, start.memory_strands))
    return _spent(finished, start.memory_strands, CEILING["exalted"](len(start.mods)))


def _check(ab: Abstraction, start: Item, action, oracle) -> dict:
    kernel = ab.kernel(ab.compress(start), action)
    assert_same_distribution(kernel, compressed_distribution(oracle(start), ab.compress))
    assert sum(kernel.values()) == 1
    return dict(kernel)


@pytest.mark.parametrize("strands", COUNTS)
def test_chaos_kernel_equals_brute_force_with_strands(strands: int) -> None:
    ab = Abstraction(SMALL, GOALS["tier"], AMULET, LEVEL)
    start = small_item(roll(GEM, fractured=True), roll(LIFE_1), memory_strands=strands)
    kernel = _check(ab, start, CHAOS, _chaos_oracle)
    assert {state.strands for state in kernel} == {max(0, strands - spent) for spent in range(51)}


@pytest.mark.parametrize("strands", COUNTS)
def test_alteration_kernel_equals_brute_force_with_strands(strands: int) -> None:
    ab = Abstraction(SMALL, GOALS["tier"], AMULET, LEVEL)
    start = small_item(roll(LIFE_1), rarity=Rarity.MAGIC, memory_strands=strands)
    _check(ab, start, ALTERATION, _alteration_oracle)


@pytest.mark.parametrize("strands", COUNTS)
def test_exalted_kernel_equals_brute_force_with_strands(strands: int) -> None:
    """The Exalted Orb keeps the junk (its states hold slots) and its ceiling follows the two mods on the item: 0 to 26."""
    ab = Abstraction(SMALL, GOALS["tier"], AMULET, LEVEL, [EXALTED])
    start = small_item(roll(RESIST_1), roll(LIFE_1), memory_strands=strands)
    kernel = _check(ab, start, EXALTED, _exalted_oracle)
    assert {state.strands for state in kernel} == {max(0, strands - spent) for spent in range(27)}


def test_at_zero_strands_the_states_are_todays() -> None:
    """At 0 strands the state holds 0, its text has no strand count, and the kernel has only states at 0 (no spend, no cut)."""
    ab = Abstraction(SMALL, GOALS["tier"], AMULET, LEVEL, [EXALTED])
    start = small_item(roll(RESIST_1), roll(LIFE_1))
    state = ab.compress(start)
    assert state.strands == 0
    assert "strands" not in repr(state)
    for action in (CHAOS, EXALTED):
        kernel = ab.kernel(state, action)
        assert all(found.strands == 0 and "strands" not in repr(found) for found in kernel)


def test_a_stranded_state_shows_and_keeps_its_count() -> None:
    ab = Abstraction(SMALL, GOALS["tier"], AMULET, LEVEL)
    stranded = ab.compress(small_item(roll(GEM, fractured=True), memory_strands=40))
    plain = ab.compress(small_item(roll(GEM, fractured=True)))
    assert stranded.strands == 40
    assert "strands=40" in repr(stranded)
    assert stranded != plain
    assert stranded.order_key != plain.order_key
    assert stranded.held != plain.held  # a memo keyed by the item state beyond the mods tells them apart


def test_the_label_distribution_is_cached_by_cut_class() -> None:
    """Counts of one cut class share one pool and so one label distribution: 0, 1 to 21, and 22 up are three here."""
    ab = Abstraction(SMALL, GOALS["tier"], AMULET, LEVEL)
    for strands in (1, 5, 21, 22, 60, 100, 0, 13):
        ab.kernel(ab.compress(small_item(roll(GEM, fractured=True), memory_strands=strands)), CHAOS)
    assert ab.stats.kernels == 3


def test_kernel_keys_tell_counts_apart() -> None:
    """Two counts of one cut class have different kernels (the counts after the spend differ), so their keys differ."""
    ab = Abstraction(SMALL, GOALS["tier"], AMULET, LEVEL)
    keys = {ab.kernel_key(ab.compress(small_item(roll(GEM, fractured=True), memory_strands=strands)), CHAOS) for strands in (5, 6)}
    assert len(keys) == 2


def test_the_weight_reading_is_a_parameter() -> None:
    """The default is the plan reading of the claim; another reading reaches the pool and changes the kernel (delete-only keeps the
    lone top tier of Lightning Resistance at its own weight, so it is rarer than under the plan)."""
    plain = Abstraction(SMALL, GOALS["tier"], AMULET, LEVEL)
    deleted = Abstraction(SMALL, GOALS["tier"], AMULET, LEVEL, weights=WeightReading.DELETE_ONLY)
    assert plain.weights is PLAN_READING
    start = small_item(roll(GEM, fractured=True), memory_strands=22)
    kernel = _check(deleted, start, CHAOS, lambda item: _chaos_oracle(item, WeightReading.DELETE_ONLY))
    assert kernel != dict(plain.kernel(plain.compress(start), CHAOS))
