"""The planner on several cores gives the same answers as on one (ticket #250).

`CRAFTING_WORKERS` sets the size of the process pool. The answer a plan gives (the JSON policy document, the prices,
the policy, the certificate and the approximate marks) must be byte-identical for 1 and for N workers. The cases here use
the committed fixture of `coarse_support.py`, so they need no game data and run on every system; the real routes are in
`test_cli_parallel_real.py`.
"""

import json
from datetime import UTC, datetime

import pytest
from coarse_support import CHAOS, CRAFTS, DATA, HYBRID_CRAFT, MANA, REMOVE
from abstraction_pool import MANA_1

from crafting_system.cli import Offer, build_report, make_plan, policy_document
from crafting_system.cli import _pool
from crafting_system.cli._decide import Rates
from crafting_system.prices import PriceFile
from crafting_system.targets import parse_target

CH = "Chaos Orb"
TARGET = f"""\
base: Paua Amulet
item_level: 84
requirements:
  - family: ColdResistance
    mod: {HYBRID_CRAFT}
  - family: IncreasedLife
start_item:
  rarity: rare
  mods:
    - mod: {MANA_1}
      tier: 1
      values: {[min(stat.min, stat.max) for stat in DATA.mods[MANA_1].stats]}
"""
OFFERS = [
    Offer("Chaos Orb", CHAOS, {CH: 1}),
    *(Offer(f"Craft {craft.mod_id}", craft, {CH: 2}) for craft in CRAFTS),
    Offer("Remove Crafted Mods", REMOVE, {CH: 1}),
]
PRICES = PriceFile("Test", datetime(2026, 10, 30, tzinfo=UTC), 300.0, {})


def answer_of(plan) -> str:
    """The JSON policy document of a plan, as the CLI writes it, without the seconds it took."""
    document = policy_document(build_report(plan, DATA), None, target_name="t.yaml")
    document.pop("timings_seconds", None)
    return json.dumps(document, sort_keys=True, indent=1)


def planned(monkeypatch, workers: int, **options):
    monkeypatch.setenv("CRAFTING_WORKERS", str(workers))
    target = parse_target(TARGET, DATA, source="t.yaml")
    return make_plan(DATA, target, PRICES, offers=OFFERS, start_price=0.0, **options)


@pytest.fixture
def pool_calls(monkeypatch):
    """The numbers of actions the state pool was asked to build per batch."""
    sizes: list[int] = []
    real = _pool.StatePool.build

    def counting(self, tasks):
        sizes.append(sum(len(positions) for _, positions in tasks))
        return real(self, tasks)

    monkeypatch.setattr(_pool.StatePool, "build", counting)
    return sizes


def test_one_worker_starts_no_pool(monkeypatch, pool_calls):
    planned(monkeypatch, 1)

    assert pool_calls == []


@pytest.mark.parametrize("workers", [2, 4])
def test_an_exact_plan_is_byte_identical_for_one_and_many_workers(monkeypatch, pool_calls, workers):
    serial = answer_of(planned(monkeypatch, 1))
    pooled = answer_of(planned(monkeypatch, workers))

    assert pooled == serial
    assert pool_calls and max(pool_calls) >= _pool.MIN_PENDING  # the pool really built actions


def test_the_solution_values_are_equal_to_the_last_bit(monkeypatch):
    serial = planned(monkeypatch, 1)
    pooled = planned(monkeypatch, 4)

    assert list(pooled.solution.values.items()) == list(serial.solution.values.items())
    assert {s: (a.label, a.cost, a.outcomes) for s, a in pooled.policy.items()} == {
        s: (a.label, a.cost, a.outcomes) for s, a in serial.policy.items()
    }
