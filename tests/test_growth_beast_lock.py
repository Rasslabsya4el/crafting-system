"""The Wild Bristle Matron beside the bench lock (#1513, hypothesis H35 of #1434; OR-12), through the planner's entry and on the real data.

The toy, on the fixture data of `test_cli_offers` with the bench craft "Suffixes Cannot Be Changed" added for belts at 2 Divine Orbs `d`: a
rare Leather Belt whose three suffixes are full (Fire, Cold Resistance and Life Regeneration, the first two wanted) and that holds no prefix;
the goal adds the top Life prefix, `IncreasedLife3`. Every beta method is on (no methods setting), the start is bought at `S` = 50.

* A Chaos Orb under the suffix lock keeps the three suffixes and rerolls the prefixes, the lock with them (a crafted prefix). It makes 4
  mods with chance 2/3 (one prefix) and more with 1/3, which is two prefixes (the belt's prefix families are Life and Energy Shield). The prefix
  pool is Life 1, 2, 3 and Energy Shield 1, 1,000 each: one prefix is Life 3 with chance 1/4; two hold it with 1/4 + (1/4)(1/3) = 1/3.
  So `p = (2/3)(1/4) + (1/3)(1/3) = 5/18`, and a plan that locks before each Chaos Orb costs `V = (lock + 1) / p = (18/5)(lock + 1)`.
* On these suffix-full items the Matron's one metamod with room is the suffix lock (the other four are suffixes): it puts on the same lock
  for the Matron's price `m` and three rare beasts priced as Chaos Orbs, `m + 3`.
* At `d` = 3.5 (the bench lock at 7): with the Matron at 1, `V = (18/5)(1 + 3 + 1)` = 18; with it at 30, the bench lock's
  `(18/5)(7 + 1)` = 28.8, below every plan without a lock (30.74).

This toy holds the figures of the two locks through the entry; it does not witness the rule that names the Matron with the bench lock (#1665 J4: the other ways of making the same lock), since its rounds after the growth
hold every method and main reaches the same plans. The rule is held by the table tests: `tests/test_growth.py` (the hand table and the
growth's protector round) and the R24 test below.

The R24 test reads the real 3.29.3.3 dump (it skips without it): the table of every offer of the reference craft R24, whose plan in the hour
paid the bench lock (353.2 c) where the Matron (238 c) puts the same lock on.
"""

import dataclasses
import datetime
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from test_cli_offers import PRICED_DATA

from crafting_system.abstraction._goal import Goal
from crafting_system.data.model import BenchActions, BenchOption, CostEntry
from crafting_system.planner import PlanSettings, _growth, plan_target
from crafting_system.planner._plan import cheapest_per_class, offers_for, price_offers
from crafting_system.prices import PriceFile, load_price_file
from crafting_system.prices.price_file import PriceEntry
from crafting_system.prices.provenance import EXCHANGE, Provenance
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
MATRON = "Beastcraft Wild Bristle Matron (add a metamod)"
SUFFIX_LOCK, PREFIX_LOCK = "Bench craft Suffixes Cannot Be Changed", "Bench craft Prefixes Cannot Be Changed"
DIVINE = 3.5
TARGET = """\
base: Leather Belt
item_level: 84
influence: []
requirements:
  - family: FireResistance
  - family: ColdResistance
  - family: IncreasedLife
    mod: IncreasedLife3
start_item:
  rarity: rare
  mods:
    - mod: FireResist1
      values: [6]
    - mod: ColdResist1
      values: [6]
    - mod: LifeRegeneration1
      values: [60]
start: bought
"""


@pytest.fixture(scope="module")
def data():
    lock = BenchOption(
        "Einhar, Beastmaster", 0, ("Belt",), (CostEntry("Metadata/Items/Currency/CurrencyModValues", 2),),
        BenchActions("DexMasterItemGenerationCannotChangeSuffixes", None, None, None, None, None, None, None, None),
    )  # fmt: skip
    return dataclasses.replace(PRICED_DATA, bench_options=(*PRICED_DATA.bench_options, lock))


def _plan(data, tmp_path, matron: float):
    path = tmp_path / "belt.yaml"
    path.write_text(TARGET, encoding="utf-8")
    entry = lambda chaos: PriceEntry(chaos, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", "2026-10-30", 1e9))  # noqa: E731
    names = {"Divine Orb": DIVINE, "Wild Bristle Matron": matron, "Exalted Orb": 10.0, "Orb of Alteration": 1.0}
    prices = PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, {name: entry(price) for name, price in names.items()})
    return plan_target(data, load_target(path, data), prices, PlanSettings(recipe_starts=False, start_price=50.0, solver="envelope"))


def _labels(plan) -> set[str]:
    return {offer.label for offer in plan.offers}


def test_through_the_entry_the_cheaper_of_the_beast_and_the_bench_lock_is_paid_before_each_chaos_orb(data, tmp_path):
    cheap = _plan(data, tmp_path, matron=1.0)
    assert cheap.mean_remaining == pytest.approx(18 / 5 * (1 + 3 + 1), rel=1e-9)
    assert MATRON in _labels(cheap) and SUFFIX_LOCK not in _labels(cheap)
    dear = _plan(data, tmp_path, matron=30.0)
    assert dear.mean_remaining == pytest.approx(18 / 5 * (2 * DIVINE + 1), rel=1e-9)
    assert SUFFIX_LOCK in _labels(dear) and MATRON not in _labels(dear)


def test_on_r24_the_matron_is_another_way_of_making_the_suffix_lock():
    data = real_game_data()
    # every beta method, as the benchmark plans it (the suite reads this file with the methods it named before #405: `former_keys`)
    target = dataclasses.replace(load_target(ROOT / "examples" / "targets" / "r24-avoid-shock-boots.yaml", data), actions=None)
    goal = Goal.from_target(target)
    prices = load_price_file(ROOT / "tests" / "fixtures" / "prices" / "references-allflame-2026-07-31.json")
    priced, _dropped = price_offers(offers_for(data, goal, target.base_id, target.start_item, target.actions).offers, prices, "test")
    priced, _same = cheapest_per_class(priced)
    table = _growth.growth_table(data, goal, target, priced, None)
    position = {entry.label: entry.position for entry in table.entries}
    matron = table.entries[position[MATRON]]
    # the Matron draws which metamod it adds (so the protector rule, among the offers that draw nothing, never names it) and is cheaper
    assert matron.draws and matron.cost < table.entries[position[SUFFIX_LOCK]].cost
    # on these boots, at the rare item holding the wanted suffixes, the Matron's draw can make the suffix lock: it is the same lock, named with
    # the bench one; a closure brings no locker (#1665 J4)
    table.held_back = frozenset()
    suffixes = frozenset(leaf for leaf in range(len(goal.leaves)) if table.side_of(leaf) == "suffix")
    assert position[MATRON] in table.lock_ways("suffix", frozenset(table.views), suffixes)
    assert {table.entries[each].label for each in table.closure({position[SUFFIX_LOCK]})} == {SUFFIX_LOCK}
