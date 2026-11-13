"""The Orb of Remembrance (ticket #278, B5-5; ADR-0043): its count table, its refusals, its kernel and the stop threshold it leaves to the solver.

The expected numbers are the ticket's and the research's, not recomputed the way the code computes them: the table sums to 1, runs from
10 to 100 and has mean 41.84 (ADR-0043); against the author's 2,255 results binned by five (10-14, ..., 90-94, 95-100: 18 bins, 17
degrees of freedom) its chi-square is about 7.2 (research note `2026-10-31-memory-strands.md`) and must stay below 27.6, the 95% point of
chi-square with 17 degrees of freedom. The observed counts are the fixture `tests/fixtures/strands/remembrance_results.json`, copied from
the research note.
"""

import dataclasses
import json
import random
from fractions import Fraction
from pathlib import Path

import pytest
from abstraction_pool import AMULET, LEVEL, LIFE_1, SMALL, roll, small_item
from abstraction_support import GOALS

from crafting_system.abstraction import Abstraction
from crafting_system.actions import NotApplicableError, RemembranceOrb, catalog, remembrance_table
from crafting_system.data import BaseItem
from crafting_system.items import Item, Rarity
from crafting_system.solver import Action, TabularModel, solve

FIXTURE = Path(__file__).parent / "fixtures" / "strands" / "remembrance_results.json"
CHI2_17_DF_95 = 27.587  # the 95% point of chi-square with 17 degrees of freedom
REMEMBRANCE = RemembranceOrb()


def _observed() -> dict[int, int]:
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {int(count): seen for count, seen in record["counts"].items()}


def test_the_table_sums_to_one_runs_from_10_to_100_and_has_mean_41_84() -> None:
    table = remembrance_table()
    assert sum(table.values()) == 1
    assert all(isinstance(chance, Fraction) and chance > 0 for chance in table.values())
    assert sorted(table) == list(range(10, 101))
    assert float(sum(count * chance for count, chance in table.items())) == pytest.approx(41.84, abs=0.005)


def test_the_fixture_is_the_authors_2255_results() -> None:
    observed = _observed()
    assert sum(observed.values()) == 2255
    assert min(observed) == 10 and max(observed) == 100
    assert sum(count * seen for count, seen in observed.items()) / 2255 == pytest.approx(41.56, abs=0.005)  # the sheet's own mean cell


def test_the_table_fits_the_2255_results_by_chi_square() -> None:
    """18 bins of five (the last 95-100), 17 degrees of freedom: recorded 7.2 by the research, asserted below 27.6."""
    table, observed = remembrance_table(), _observed()
    edges = [*range(10, 100, 5), 101]
    statistic = 0.0
    for low, high in zip(edges, edges[1:]):
        seen = sum(observed.get(count, 0) for count in range(low, high))
        expected = 2255 * float(sum(table[count] for count in range(low, high)))
        statistic += (seen - expected) ** 2 / expected
    assert len(edges) - 2 == 17
    assert statistic == pytest.approx(7.2, abs=0.1)  # the research's number, recorded here
    assert statistic < CHI2_17_DF_95


def test_one_orb_keeps_the_mods_and_sets_the_count_from_the_table_whatever_it_was() -> None:
    for before in (0, 7, 100):
        item = small_item(rarity=Rarity.NORMAL, memory_strands=before)
        outcomes = REMEMBRANCE.outcomes(SMALL, item)
        assert dict(outcomes.strands_after) == dict(remembrance_table())
        assert [chance for chance, _ in outcomes.components] == [1]
        assert outcomes.distribution(lambda mod: mod.id) == {frozenset(): 1}
        rng = random.Random(278)
        drawn = [outcomes.sample(rng) for _ in range(200)]
        assert all(found.mods == item.mods and found.rarity is Rarity.NORMAL for found in drawn)
        assert all(10 <= found.memory_strands <= 100 for found in drawn)
        assert len({found.memory_strands for found in drawn}) > 20


@pytest.mark.parametrize(
    ("item", "why"),
    [
        (small_item(roll(LIFE_1), rarity=Rarity.MAGIC), "normal"),
        (small_item(rarity=Rarity.NORMAL, corrupted=True), "corrupted"),
    ],
)
def test_a_non_normal_or_corrupted_item_is_refused(item: Item, why: str) -> None:
    with pytest.raises(NotApplicableError, match=why):
        REMEMBRANCE.outcomes(SMALL, item)


def test_a_jewel_is_refused() -> None:
    jewel = BaseItem("Metadata/Items/Jewels/JewelStr", "Crimson Jewel", "Jewel", "misc", 1, ("default", "strjewel"), (), "released")
    data = dataclasses.replace(SMALL, base_items={**SMALL.base_items, jewel.id: jewel})
    item = Item.build(data, base_id=jewel.id, item_level=LEVEL, rarity=Rarity.NORMAL)
    with pytest.raises(NotApplicableError, match="jewel"):
        REMEMBRANCE.outcomes(data, item)
    assert not any(isinstance(action, RemembranceOrb) for action in catalog(data, item, strands=True))


def test_a_flask_is_no_equipment_and_is_refused() -> None:
    flask = BaseItem("Metadata/Items/Flasks/FlaskLife1", "Small Life Flask", "LifeFlask", "flask", 1, ("default", "flask"), (), "released")
    data = dataclasses.replace(SMALL, base_items={**SMALL.base_items, flask.id: flask})
    item = Item.build(data, base_id=flask.id, item_level=LEVEL, rarity=Rarity.NORMAL)
    with pytest.raises(NotApplicableError, match="equipment only"):
        REMEMBRANCE.outcomes(data, item)


def test_the_kind_is_listed_only_for_a_normal_item_and_only_with_strands_on() -> None:
    normal = small_item(rarity=Rarity.NORMAL)
    assert any(isinstance(action, RemembranceOrb) for action in catalog(SMALL, normal, strands=True))
    assert not any(isinstance(action, RemembranceOrb) for action in catalog(SMALL, normal))
    magic = small_item(roll(LIFE_1), rarity=Rarity.MAGIC, memory_strands=40)
    assert not any(isinstance(action, RemembranceOrb) for action in catalog(SMALL, magic))


def test_the_kernel_is_the_table_over_the_count_and_loops_back_on_itself() -> None:
    """From 0 and from a stranded count alike the kernel is one state per count of the table, with the table's chance (ADR-0043: a self-loop)."""
    ab = Abstraction(SMALL, GOALS["tier"], AMULET, LEVEL)
    table = remembrance_table()
    for before in (0, 55):
        state = ab.compress(small_item(rarity=Rarity.NORMAL, memory_strands=before))
        kernel = ab.kernel(state, REMEMBRANCE)
        assert {found.strands: chance for found, chance in kernel.items()} == dict(table)
        assert all(found.flags == state.flags and found.slots == state.slots for found in kernel)
        assert sum(kernel.values()) == 1


def test_the_solver_chooses_the_stop_threshold_of_a_three_value_toy() -> None:
    """A toy Remembrance of three counts: 10 with 1/2, 50 with 1/3, 100 with 1/6, at 4 Chaos an orb; finishing from a count costs 60, 20, 5.

    By hand, re-rolling below 50 and stopping at 50 or more: E = 1/2 (4 + E) + 1/3 * 20 + 1/6 * 5, so E = 19 and the start costs 4 + 19 = 23.
    Stopping everywhere gives 4 + 30 + 20/3 + 5/6 = 41.5; stopping only at 100 gives E = 5/6 (4 + E) + 5/6, so E = 25 and 29. The threshold
    50 is the cheapest: at 10 a re-roll costs 4 + 19 = 23 < 60, at 50 finishing costs 20 < 23.
    """
    orb = 4.0
    finish = {10: 60.0, 50: 20.0, 100: 5.0}
    outcomes = ((10, 3), (50, 2), (100, 1))  # weights 1/2, 1/3, 1/6
    table = {"normal": [Action("remembrance", orb, outcomes)]}
    for count, cost in finish.items():
        table[count] = [Action("remembrance", orb, outcomes), Action("finish", cost, (("goal", 1),))]
    solution = solve(TabularModel(["goal"], table), ["normal"])
    assert solution.values["normal"] == pytest.approx(23.0)
    assert solution.values[10] == pytest.approx(23.0)
    assert solution.policy[10].label == "remembrance"
    assert solution.policy[50].label == "finish" and solution.policy[100].label == "finish"
